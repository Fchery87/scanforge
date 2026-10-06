import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Finding, FindingInstance, Project, Repository, RepositoryIntegration, Scan
from app.services.github import GitHubService
from app.services.policy_evaluation import evaluate_advisory_policy
from app.services.sla_policy import EXEMPT_WORKFLOW_STATES

logger = logging.getLogger(__name__)
SCANNERS = {"trivy", "gitleaks", "semgrep", "osv", "osv-scanner", "syft", "grype", "checkov"}
SEVERITIES = ("critical", "high", "medium", "low", "info")


def build_check_payload(
    scan,
    *,
    organization_id: UUID,
    counts: dict[str, int],
    risk_score_average: float | None = None,
    sla_overdue: int = 0,
) -> dict:
    state = str(scan.status)
    health = (scan.summary_json or {}).get("scanner_health") or {}
    complete = state == "completed" and health.get("complete") is True
    policy = evaluate_advisory_policy(
        risk_score_average=risk_score_average,
        sla_overdue=sla_overdue,
        scanner_health={"partial_scans": int(state == "completed" and not complete)},
    )
    status = {"queued": "queued", "running": "in_progress"}.get(state, "completed")
    detail_url = (
        f"{settings.WEB_APP_URL.rstrip('/')}/dashboard/{organization_id}/projects/{scan.project_id}/scans/{scan.id}"
    )
    counts_text = ", ".join(f"{severity}={max(0, int(counts.get(severity, 0)))}" for severity in SEVERITIES)
    failed = sorted(SCANNERS.intersection(health.get("failed") or []))
    missing = sorted(SCANNERS.intersection(health.get("missing") or []))
    coverage = "complete" if complete else "partial" if state == "completed" else "not yet verified"
    evaluation = policy["status"] if state == "completed" else "pending"
    summary = (
        f"Scan status {state}. Coverage {coverage}.\n"
        f"Finding counts {counts_text}.\n"
        f"Failed scanners {', '.join(failed) or 'none'}. Missing scanners {', '.join(missing) or 'none'}.\n"
        f"Advisory policy {evaluation}. Merge blocking disabled."
    )
    payload = {
        "name": "ScanForge advisory",
        "status": status,
        "details_url": detail_url,
        "output": {"title": "ScanForge repository scan", "summary": summary},
    }
    if status == "completed":
        payload["conclusion"] = "neutral"
        payload["completed_at"] = datetime.now(UTC).isoformat()
    return payload


class GitHubCheckPublisher:
    def __init__(self, db: AsyncSession, *, github: GitHubService | None = None):
        self.db = db
        self.github = github or GitHubService(db)

    async def publish(self, scan_id: UUID) -> bool:
        scan = None
        try:
            scan = await self.db.scalar(
                select(Scan).where(Scan.id == str(scan_id)).with_for_update().execution_options(populate_existing=True)
            )
            if scan is None or scan.trigger_type != "pull_request":
                await self.db.rollback()
                return False
            if not scan.github_check_pending:
                await self.db.commit()
                return True
            repo = await self.db.get(Repository, scan.repository_id)
            project = await self.db.get(Project, scan.project_id)
            integration = await self.db.scalar(
                select(RepositoryIntegration).where(RepositoryIntegration.repository_id == scan.repository_id)
            )
            if (
                not repo
                or not project
                or not integration
                or not integration.installation_id
                or not scan.head_commit_sha
            ):
                await self.db.rollback()
                await self.db.refresh(scan)
                return False
            finding_ids = select(FindingInstance.finding_id).where(FindingInstance.scan_id == str(scan.id))
            rows = await self.db.execute(
                select(Finding.severity, func.count()).where(Finding.id.in_(finding_ids)).group_by(Finding.severity)
            )
            counts = dict(rows.all())
            risk_average = await self.db.scalar(select(func.avg(Finding.risk_score)).where(Finding.id.in_(finding_ids)))
            overdue = await self.db.scalar(
                select(func.count())
                .select_from(Finding)
                .where(
                    Finding.id.in_(finding_ids),
                    Finding.status.not_in(EXEMPT_WORKFLOW_STATES),
                    Finding.due_date < datetime.now(UTC).date(),
                )
            )
            payload = build_check_payload(
                scan,
                organization_id=project.organization_id,
                counts=counts,
                risk_score_average=risk_average,
                sla_overdue=overdue or 0,
            )
            digest_payload = {key: value for key, value in payload.items() if key != "completed_at"}
            digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True).encode()).hexdigest()
            if scan.github_check_run_id is None or digest != scan.github_check_payload_digest:
                async with asyncio.timeout(20):
                    scan.github_check_run_id = await self.github.publish_check_run(
                        installation_id=integration.installation_id,
                        owner=repo.owner_name,
                        repository=repo.repo_name,
                        head_sha=scan.head_commit_sha,
                        external_id=str(scan.id),
                        payload=payload,
                        check_run_id=scan.github_check_run_id,
                    )
            scan.github_check_payload_digest = digest
            scan.github_check_pending = False
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            if scan is not None:
                await self.db.refresh(scan)
            logger.warning("GitHub Check publication deferred for scan %s", scan_id)
            return False

    async def retry_pending(self, limit: int = 20) -> int:
        rows = await self.db.execute(
            select(Scan.id).where(Scan.github_check_pending.is_(True)).order_by(Scan.updated_at).limit(limit)
        )
        scan_ids = list(rows.scalars().all())
        await self.db.commit()
        published = 0
        for scan_id in scan_ids:
            published += int(await self.publish(scan_id))
        return published
