import hashlib
from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import ScanStatus
from app.db.models import (
    Finding,
    FindingEvent,
    FindingInstance,
    FindingReference,
    Organization,
    OrganizationMember,
    Project,
    Repository,
    Scan,
    ScannerRun,
)
from app.schemas.canonical_findings import CanonicalFindingCandidate
from app.schemas.findings import (
    FindingStats,
)
from app.services.finding_lifecycle import (
    ABSENCE_THRESHOLD,
    POLICY_VERSION,
    REOPEN_CHECKPOINT_KEY,
    AbsenceBlockReason,
    absence_transition_target,
    branch_obligation_counts,
    evaluate_scan_absence_evidence,
    observed_branches,
    record_manual_reopen_checkpoint,
    record_observed_branch,
    record_qualifying_absence,
    reset_branch_series,
    scan_precedes_checkpoint,
    transition_event_for_state,
    validate_transition,
)
from app.services.risk_scoring import calculate_risk_score
from app.services.scans import ScanAuthorizationError
from app.services.secret_safety import sanitize_secret_mapping


class FindingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _set_status(
        self,
        finding_id: UUID,
        user_id: UUID,
        status: str,
        event_type: str | None = None,
        *,
        reason: str | None = None,
        metadata_json: dict | None = None,
    ) -> Finding | None:
        finding = await self.get_by_id(finding_id, user_id)
        if not finding:
            return None

        next_state = validate_transition(finding.status, status)
        finding.status = next_state.value

        event = FindingEvent(
            finding_id=finding_id,
            event_type=event_type or transition_event_for_state(next_state.value),
            actor_user_id=user_id,
            reason=reason,
            metadata_json=metadata_json,
        )
        self.db.add(event)

        await self.db.commit()
        await self.db.refresh(finding)
        return finding

    async def list_for_project(
        self,
        project_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
        *,
        severity: str | None = None,
        category: str | None = None,
        status: str | None = None,
        scanner: str | None = None,
        repository_id: UUID | None = None,
        search: str | None = None,
    ) -> tuple[list[Finding], int]:
        base_query = (
            select(Finding)
            .join(Project, Finding.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .options(selectinload(Finding.assignee))
            .where(
                Finding.project_id == project_id,
                OrganizationMember.user_id == user_id,
            )
        )

        if severity:
            base_query = base_query.where(Finding.severity == severity)
        if category:
            base_query = base_query.where(Finding.category == category)
        if status:
            base_query = base_query.where(Finding.status == status)
        if scanner:
            base_query = base_query.where(Finding.primary_scanner == scanner)
        if repository_id:
            base_query = base_query.where(Finding.repository_id == repository_id)
        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Finding.title.ilike(search_term),
                    Finding.description.ilike(search_term),
                )
            )

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        result = await self.db.execute(base_query.order_by(Finding.created_at.desc()).offset(skip).limit(limit))
        findings = list(result.scalars().all())

        return findings, total

    async def get_by_id(
        self,
        finding_id: UUID,
        user_id: UUID,
    ) -> Finding | None:
        result = await self.db.execute(
            select(Finding)
            .join(Project, Finding.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .options(
                selectinload(Finding.instances),
                selectinload(Finding.references),
                selectinload(Finding.events),
                selectinload(Finding.assignee),
            )
            .where(
                Finding.id == finding_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_triage(
        self,
        finding_id: UUID,
        user_id: UUID,
        assignee_user_id: UUID | None = None,
        due_date: date | None = None,
    ) -> Finding | None:
        finding = await self.get_by_id(finding_id, user_id)
        if not finding:
            return None

        if assignee_user_id is not None:
            member_exists = await self.db.scalar(
                select(func.count())
                .select_from(Project)
                .join(
                    OrganizationMember,
                    OrganizationMember.organization_id == Project.organization_id,
                )
                .where(
                    Project.id == finding.project_id,
                    OrganizationMember.user_id == assignee_user_id,
                )
            )
            if not member_exists:
                raise ValueError("Assignee must be a member of the organization")

        finding.assignee_user_id = str(assignee_user_id) if assignee_user_id else None
        finding.due_date = due_date

        event = FindingEvent(
            finding_id=finding_id,
            event_type="triage_updated",
            actor_user_id=user_id,
            metadata_json={
                "assignee_user_id": str(assignee_user_id) if assignee_user_id else None,
                "due_date": due_date.isoformat() if due_date else None,
            },
        )
        self.db.add(event)
        await self.db.commit()
        result = await self.db.execute(
            select(Finding).options(selectinload(Finding.assignee)).where(Finding.id == finding_id)
        )
        return result.scalar_one()

    async def upsert_from_scan(
        self,
        scan_id: str,
        repository_id: str,
        project_id: str,
        normalized_findings: Sequence[dict | CanonicalFindingCandidate],
        *,
        commit: bool = True,
        caller_organization_id: UUID | None = None,
    ) -> tuple[int, int]:
        if caller_organization_id is not None:
            project = await self.db.get(Project, project_id)
            if project is None or str(project.organization_id) != str(caller_organization_id):
                raise ScanAuthorizationError(
                    "Worker principal is not bound to the organization that owns the scan"
                )

        new_count = 0
        updated_count = 0
        repository = await self.db.get(Repository, repository_id)
        repository_importance = getattr(repository, "importance", "normal") or "normal"
        scan_row = await self.db.get(Scan, str(scan_id))
        presence_branch = getattr(scan_row, "branch_name", None) if scan_row else None

        for finding_input in normalized_findings:
            candidate = (
                finding_input
                if isinstance(finding_input, CanonicalFindingCandidate)
                else CanonicalFindingCandidate.model_validate(finding_input)
            )
            fingerprint = candidate.canonical_fingerprint
            candidate_data = sanitize_secret_mapping(candidate.model_dump())
            candidate = CanonicalFindingCandidate.model_validate(candidate_data)
            instance_data = candidate.instance.model_dump() if candidate.instance else {}
            references_data = [reference.model_dump() for reference in candidate.references]

            existing = await self.db.execute(
                select(Finding).where(
                    and_(
                        Finding.repository_id == repository_id,
                        Finding.canonical_fingerprint == fingerprint,
                    )
                )
            )
            finding = existing.scalar_one_or_none()

            if finding:
                finding.last_seen_at = datetime.now(UTC)
                if finding.status in ("fixed", "not_observed"):
                    # API reappearance: ordered positive evidence reopens
                    # machine-closed states and resets the series (D2/D7).
                    finding.status = "open"
                if presence_branch:
                    # Positive evidence on this branch: record the observed
                    # ref and reset its absence series (presence wins, D2).
                    presence_meta = record_observed_branch(finding.metadata_json, branch=presence_branch)
                    presence_meta = reset_branch_series(presence_meta, branch=presence_branch)
                    finding.metadata_json = presence_meta
                updated_count += 1
            else:
                finding = Finding(
                    project_id=project_id,
                    repository_id=repository_id,
                    category=candidate.category,
                    severity=candidate.severity,
                    status="open",
                    title=candidate.title,
                    description=candidate.description,
                    canonical_fingerprint=fingerprint,
                    primary_scanner=candidate.primary_scanner,
                    confidence_score=candidate.confidence_score,
                    risk_score=calculate_risk_score(
                        severity=candidate.severity,
                        confidence_score=candidate.confidence_score,
                        workflow_state="open",
                        repository_importance=repository_importance,
                    ),
                    fixed_version=candidate.fixed_version,
                    metadata_json=(
                        record_observed_branch(candidate.metadata_json, branch=presence_branch)
                        if presence_branch
                        else candidate.metadata_json
                    ),
                    first_seen_at=datetime.now(UTC),
                    last_seen_at=datetime.now(UTC),
                )
                self.db.add(finding)
                new_count += 1

            await self.db.flush()

            occurrence_fingerprint = hashlib.sha256(
                "|".join(
                    [
                        fingerprint,
                        str(instance_data.get("path") or ""),
                        str(instance_data.get("line_start") or ""),
                        str(instance_data.get("line_end") or ""),
                        str(instance_data.get("package_name") or ""),
                        str(instance_data.get("installed_version") or ""),
                    ]
                ).encode()
            ).hexdigest()
            existing_instance = await self.db.scalar(
                select(FindingInstance.id).where(
                    FindingInstance.scan_id == scan_id,
                    FindingInstance.occurrence_fingerprint == occurrence_fingerprint,
                )
            )
            if existing_instance is None:
                instance = FindingInstance(
                    finding_id=finding.id,
                    scan_id=scan_id,
                    occurrence_fingerprint=occurrence_fingerprint,
                    path=instance_data.get("path"),
                    line_start=instance_data.get("line_start"),
                    line_end=instance_data.get("line_end"),
                    package_name=instance_data.get("package_name"),
                    installed_version=instance_data.get("installed_version"),
                    fixed_version=instance_data.get("fixed_version"),
                    evidence_json=instance_data,
                    ai_annotation=instance_data.get("ai_annotation"),
                )
                self.db.add(instance)

            for ref_data in references_data or []:
                existing_reference = await self.db.scalar(
                    select(FindingReference.id).where(
                        FindingReference.finding_id == finding.id,
                        FindingReference.reference_type == ref_data.get("type", "unknown"),
                        FindingReference.reference_value == ref_data.get("value", ""),
                    )
                )
                if existing_reference is not None:
                    continue
                reference = FindingReference(
                    finding_id=finding.id,
                    reference_type=ref_data.get("type", "unknown"),
                    reference_value=ref_data.get("value", ""),
                    url=ref_data.get("url"),
                )
                self.db.add(reference)

        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
        return new_count, updated_count

    async def _list_open_findings_for_repository(self, repository_id: str) -> list[Finding]:
        result = await self.db.execute(
            select(Finding).where(
                Finding.repository_id == repository_id,
                Finding.status.in_(["open", "reviewing", "to_fix", "not_observed"]),
            )
        )
        return list(result.scalars().all())

    async def _scan_persisted_fingerprints(self, scan_id: str) -> set[str]:
        result = await self.db.execute(
            select(Finding.canonical_fingerprint)
            .join(FindingInstance, FindingInstance.finding_id == Finding.id)
            .where(FindingInstance.scan_id == scan_id)
        )
        return set(result.scalars().all())

    async def _scan_has_incomplete_scanner_evidence(self, scan_id: str) -> bool:
        """Committed ScannerRun rows must show healthy coverage (D3)."""
        result = await self.db.execute(select(ScannerRun.status).where(ScannerRun.scan_id == scan_id))
        statuses = [getattr(status, "value", status) for status in result.scalars().all()]
        if not statuses:
            # No committed scanner outcome: missing evidence is ineligible,
            # never assumed clean.
            return True
        return any(status != ScanStatus.COMPLETED.value for status in statuses)

    async def _apply_branch_absence(self, finding, scan, branch: str, present: set[str]) -> int:
        """Record one branch-local absence and transition when eligible.

        Returns 1 when the finding state changed, else 0.
        """
        if finding.canonical_fingerprint in present:
            return 0
        metadata = dict(finding.metadata_json or {})
        known_branches = observed_branches(metadata)
        if not known_branches:
            # Unknown branch provenance blocks auto-closure.
            return 0
        if branch not in known_branches:
            # Absence on a branch where the finding was never seen is
            # ignored for this finding.
            return 0
        if scan_precedes_checkpoint(scan.created_at, metadata.get(REOPEN_CHECKPOINT_KEY)):
            # Scan issued at/before a manual reopen decision.
            return 0

        metadata, counted = record_qualifying_absence(
            metadata, branch=branch, scan_id=str(scan.id), commit_sha=str(scan.commit_sha)
        )
        finding.metadata_json = metadata
        counts = branch_obligation_counts(metadata)
        min_count = min(counts.get(name, 0) for name in known_branches)
        next_state = absence_transition_target(finding.status, min_branch_absences=min_count)

        if next_state:
            finding.status = next_state
            self.db.add(
                FindingEvent(
                    finding_id=finding.id,
                    event_type=transition_event_for_state(next_state),
                    actor_user_id=None,
                    metadata_json={
                        "scan_id": str(scan.id),
                        "commit_sha": str(scan.commit_sha),
                        "branch": branch,
                        "policy": POLICY_VERSION,
                        "threshold": ABSENCE_THRESHOLD,
                        "qualifying_absences": min_count,
                    },
                )
            )
            return 1
        if counted:
            # Observation recorded without a transition (human triage state
            # or unresolved branch obligation).
            blocked = [AbsenceBlockReason.HUMAN_BLOCK_STATE.value]
            if finding.status in ("open", "not_observed"):
                blocked = [AbsenceBlockReason.UNRESOLVED_BRANCH_OBLIGATION.value]
            self.db.add(
                FindingEvent(
                    finding_id=finding.id,
                    event_type="absence_recorded",
                    actor_user_id=None,
                    metadata_json={
                        "scan_id": str(scan.id),
                        "commit_sha": str(scan.commit_sha),
                        "branch": branch,
                        "policy": POLICY_VERSION,
                        "qualifying_absences": counts.get(branch, 0),
                        "state": finding.status,
                        "blocked_by": blocked,
                    },
                )
            )
        return 0

    async def mark_not_observed_after_scan(
        self,
        *,
        repository_id: str,
        scan_id: str,
        seen_fingerprints: set[str],
        scan_summary: dict | None,
        commit: bool = True,
    ) -> int:
        """Apply ordered-series disappearance for one completed scan.

        Scope safety (R03 D2/D3/D7): only a full, healthy, comparable scan on
        a branch where the finding was observed may record a qualifying
        absence. Two distinct-commit absences on every observed branch close
        the finding; a manual reopen checkpoint blocks older scans. The
        ``seen_fingerprints`` argument stays for call compatibility; the
        finding instances persisted for this scan are the authoritative
        presence set.
        """
        scan = await self.db.get(Scan, str(scan_id))
        if scan is None:
            # Without committed scan context (ref, commit, type) absence is
            # unknown, never assumed.
            return 0

        scan_context = {
            "scan_type": scan.scan_type,
            "branch_name": scan.branch_name,
            "commit_sha": scan.commit_sha,
            "scanner_health": (scan_summary or {}).get("scanner_health"),
        }
        eligible, _ = evaluate_scan_absence_evidence(scan_context)
        if not eligible:
            return 0
        if await self._scan_has_incomplete_scanner_evidence(str(scan.id)):
            return 0

        present = await self._scan_persisted_fingerprints(str(scan.id))
        present = present | set(seen_fingerprints or [])

        branch = scan.branch_name
        updated = 0
        for finding in await self._list_open_findings_for_repository(repository_id):
            updated += await self._apply_branch_absence(finding, scan, branch, present)

        if updated:
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()

        return updated

    async def mark_not_observed_for_completed_scan(self, scan) -> int:
        return await self.mark_not_observed_after_scan(
            repository_id=str(scan.repository_id),
            scan_id=str(scan.id),
            seen_fingerprints=set((scan.summary_json or {}).get("seen_fingerprints") or []),
            scan_summary=scan.summary_json,
        )

    async def suppress(
        self,
        finding_id: UUID,
        user_id: UUID,
        reason: str,
        rule_id: UUID | None = None,
    ) -> Finding | None:
        return await self._set_status(
            finding_id,
            user_id,
            "false_positive",
            reason=reason,
            metadata_json={"rule_id": str(rule_id)} if rule_id else None,
        )

    async def resolve(
        self,
        finding_id: UUID,
        user_id: UUID,
        fixed_version: str | None = None,
        reason: str | None = None,
    ) -> Finding | None:
        finding = await self._set_status(
            finding_id,
            user_id,
            "fixed",
            reason=reason,
            metadata_json={"fixed_version": fixed_version} if fixed_version else None,
        )
        if not finding:
            return None
        if fixed_version:
            finding.fixed_version = fixed_version
            await self.db.commit()
            await self.db.refresh(finding)
        return finding

    async def accept_risk(
        self,
        finding_id: UUID,
        user_id: UUID,
        reason: str,
    ) -> Finding | None:
        return await self._set_status(
            finding_id,
            user_id,
            "accepted_risk",
            reason=reason,
        )

    async def mark_duplicate(
        self,
        finding_id: UUID,
        user_id: UUID,
        reason: str,
    ) -> Finding | None:
        return await self._set_status(
            finding_id,
            user_id,
            "duplicate",
            reason=reason,
        )

    async def reopen(
        self,
        finding_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> Finding | None:
        finding = await self._set_status(
            finding_id,
            user_id,
            "open",
            reason=reason,
        )
        if not finding:
            return None
        # Manual reopen clears every absence series and records a checkpoint
        # so old or delayed receipts cannot immediately reclose it (D7).
        finding.metadata_json = record_manual_reopen_checkpoint(
            finding.metadata_json, checkpoint=datetime.now(UTC)
        )
        await self.db.commit()
        await self.db.refresh(finding)
        return finding

    async def get_events(
        self,
        finding_id: UUID,
        user_id: UUID,
    ) -> list[FindingEvent]:
        finding = await self.get_by_id(finding_id, user_id)
        if not finding:
            return []
        return finding.events or []

    async def get_stats(
        self,
        project_id: UUID,
        user_id: UUID,
        repository_id: UUID | None = None,
    ) -> FindingStats:
        repo_filter = [Finding.repository_id == repository_id] if repository_id else []
        base_where = (
            select(Finding)
            .join(Project, Finding.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Finding.project_id == project_id,
                OrganizationMember.user_id == user_id,
                *repo_filter,
            )
        )

        total = await self.db.scalar(select(func.count()).select_from(base_where.subquery())) or 0

        open_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(Finding)
                .join(Project, Finding.project_id == Project.id)
                .join(Organization, Project.organization_id == Organization.id)
                .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                .where(
                    Finding.project_id == project_id,
                    OrganizationMember.user_id == user_id,
                    Finding.status == "open",
                    *repo_filter,
                )
            )
            or 0
        )

        fixed_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(Finding)
                .join(Project, Finding.project_id == Project.id)
                .join(Organization, Project.organization_id == Organization.id)
                .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                .where(
                    Finding.project_id == project_id,
                    OrganizationMember.user_id == user_id,
                    Finding.status == "fixed",
                    *repo_filter,
                )
            )
            or 0
        )

        false_positive_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(Finding)
                .join(Project, Finding.project_id == Project.id)
                .join(Organization, Project.organization_id == Organization.id)
                .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                .where(
                    Finding.project_id == project_id,
                    OrganizationMember.user_id == user_id,
                    Finding.status == "false_positive",
                    *repo_filter,
                )
            )
            or 0
        )

        severity_counts = {}
        for sev in ["critical", "high", "medium", "low", "info"]:
            count = (
                await self.db.scalar(
                    select(func.count())
                    .select_from(Finding)
                    .join(Project, Finding.project_id == Project.id)
                    .join(
                        OrganizationMember,
                        OrganizationMember.organization_id == Project.organization_id,
                    )
                    .where(
                        Finding.project_id == project_id,
                        OrganizationMember.user_id == user_id,
                        Finding.severity == sev,
                        Finding.status == "open",
                        *repo_filter,
                    )
                )
                or 0
            )
            severity_counts[sev] = count

        category_counts = {}
        categories = ["vulnerability", "secret", "dependency_outdated", "code_quality"]
        for cat in categories:
            count = (
                await self.db.scalar(
                    select(func.count())
                    .select_from(Finding)
                    .join(Project, Finding.project_id == Project.id)
                    .join(
                        OrganizationMember,
                        OrganizationMember.organization_id == Project.organization_id,
                    )
                    .where(
                        Finding.project_id == project_id,
                        OrganizationMember.user_id == user_id,
                        Finding.category == cat,
                        Finding.status == "open",
                    )
                )
                or 0
            )
            category_counts[cat] = count

        return FindingStats(
            total=total,
            open=open_count,
            fixed=fixed_count,
            suppressed=false_positive_count,
            by_severity=severity_counts,
            by_category=category_counts,
        )

    async def bulk_suppress(
        self,
        finding_ids: list[UUID],
        user_id: UUID,
        reason: str,
    ) -> int:
        count = 0
        for finding_id in finding_ids:
            result = await self.suppress(finding_id, user_id, reason)
            if result:
                count += 1
        return count

    async def bulk_resolve(
        self,
        finding_ids: list[UUID],
        user_id: UUID,
        fixed_version: str | None = None,
    ) -> int:
        count = 0
        for finding_id in finding_ids:
            result = await self.resolve(finding_id, user_id, fixed_version)
            if result:
                count += 1
        return count

    async def bulk_accept_risk(
        self,
        finding_ids: list[UUID],
        user_id: UUID,
        reason: str,
    ) -> int:
        count = 0
        for finding_id in finding_ids:
            result = await self.accept_risk(finding_id, user_id, reason)
            if result:
                count += 1
        return count

    async def bulk_mark_duplicate(
        self,
        finding_ids: list[UUID],
        user_id: UUID,
        reason: str,
    ) -> int:
        count = 0
        for finding_id in finding_ids:
            result = await self.mark_duplicate(finding_id, user_id, reason)
            if result:
                count += 1
        return count
