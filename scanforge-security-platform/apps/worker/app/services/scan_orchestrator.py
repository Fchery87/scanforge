import asyncio
import copy
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import TYPE_CHECKING

import httpx

from app.clients.queue import QueueClient, QueueJob
from app.clients.r2 import R2Client
from app.scanners.base import ScannerResult
from app.scanners.registry import SCANNER_REGISTRY, scanners_for_scan_type

if TYPE_CHECKING:
    from app.services.notifications import NotificationDispatcher


@dataclass
class ScanContext:
    scan_id: str
    organization_id: str
    repository_id: str
    project_id: str
    branch: str | None
    commit_sha: str | None
    job_id: str
    user_id: str | None = None
    repo_path: Path | None = None
    start_time: datetime = None
    scanner_results: dict = None
    findings: list = None
    artifact_uris: dict = None
    scanner_run_ids: dict = None
    changed_files: list[str] | None = None
    expected_scanners: list[str] | None = None
    coverage_scope: dict | None = None
    critical_count: int = 0
    high_count: int = 0
    scan_failed: bool = False
    error_message: str | None = None

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now(UTC).replace(tzinfo=None)
        if self.scanner_results is None:
            self.scanner_results = {}
        if self.findings is None:
            self.findings = []
        if self.artifact_uris is None:
            self.artifact_uris = {}
        if self.scanner_run_ids is None:
            self.scanner_run_ids = {}


class ScanOrchestrator:
    SCAN_TIMEOUT = 1800
    MAX_RETRIES = 3
    API_BASE_URL = "http://localhost:8000"

    def __init__(
        self,
        queue: QueueClient,
        r2: R2Client,
        api_base_url: str = "http://localhost:8000",
    ):
        self.queue = queue
        self.r2 = r2
        self.api_base_url = api_base_url
        self._notifier: NotificationDispatcher | None = None
        self._internal_api_key = os.environ.get("INTERNAL_API_KEY", "")

    def _redact_sensitive_text(self, value: str) -> str:
        redacted = value or ""
        if self._internal_api_key:
            redacted = redacted.replace(self._internal_api_key, "[REDACTED]")
        return re.sub(r"Authorization: Basic\s+\S+", "Authorization: Basic [REDACTED]", redacted)

    def set_notifier(self, notifier: "NotificationDispatcher"):
        self._notifier = notifier

    async def process_job(self, job: QueueJob) -> bool:
        context = await self._load_scan_context(job)

        try:
            await self._update_status(context, "claimed")
            await self._update_scan_status(context, "running")

            await self._update_status(context, "repo_preparing")
            context.repo_path = await self._prepare_repository(context)
            if job.job_type == "scan.repo.diff":
                context.changed_files = await self._collect_changed_files(context.repo_path)

            await self._update_status(context, "scanners_running")
            context.scanner_results = await self._run_scanners(context, job.job_type)

            await self._update_status(context, "artifacts_uploading")
            context.artifact_uris = await self._upload_artifacts(context)

            await self._update_status(context, "normalizing")
            context.findings = await self._normalize_results(context)
            if job.job_type == "scan.repo.diff":
                context.findings = self._filter_findings_to_changed_files(context.findings, context.changed_files or [])

            context.critical_count = sum(1 for f in context.findings if f.get("severity") == "critical")
            context.high_count = sum(1 for f in context.findings if f.get("severity") == "high")

            await self._update_status(context, "persisting")
            await self._persist_findings(context)

            await self._update_status(context, "done")
            duration = (datetime.utcnow() - context.start_time).total_seconds()
            await self._update_scan_status(
                context,
                "completed",
                summary=self._build_completion_summary(context, job_type=job.job_type, duration_seconds=duration),
            )

            await self._send_notifications(context)

            return True

        except Exception as e:
            context.scan_failed = True
            safe_error = self._redact_sensitive_text(str(e))
            context.error_message = safe_error
            await self._update_status(context, "failed", {"error": safe_error})

            retry_count = await self.queue.increment_retry(context.job_id)

            await self._update_scan_status(
                context,
                "failed",
                error=safe_error,
                summary={"retry_count": retry_count},
            )

            if retry_count >= self.MAX_RETRIES:
                await self.queue.enqueue_to_dlq(job)
                await self._update_scan_status(context, "failed", error=f"Max retries exceeded: {safe_error}")
                await self._send_failure_notification(context, retry_count)
                return False

            await asyncio.sleep(min(retry_count * 30, 300))
            await self.queue.requeue(job)
            return False

        finally:
            if context.repo_path and context.repo_path.exists():
                shutil.rmtree(context.repo_path, ignore_errors=True)

    async def _prepare_repository(self, context: ScanContext) -> Path:
        """Clone the repository using a GitHub App installation token."""
        repo_dir = Path(mkdtemp(prefix="scan_repo_"))

        # Fetch the installation token from the API
        clone_url, auth_header = await self._get_clone_url(context)
        git_env = copy.deepcopy(os.environ)
        git_env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraHeader",
                "GIT_CONFIG_VALUE_0": auth_header,
            }
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--single-branch",
                    *(["--branch", context.branch] if context.branch else []),
                    clone_url,
                    str(repo_dir),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                env=git_env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git clone failed: {self._redact_sensitive_text(result.stderr).strip()}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("git clone timed out after 5 minutes")

        return repo_dir

    async def _collect_changed_files(self, repo_path: Path) -> list[str]:
        commands = [
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        ]
        for command in commands:
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(repo_path),
                )
                if result.returncode == 0:
                    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
            except Exception:
                continue
        return []

    async def _load_scan_context(self, job: QueueJob) -> ScanContext:
        scan_id = job.payload.get("scan_id")
        if not scan_id:
            raise RuntimeError("scan job payload missing scan_id")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_base_url}/api/v1/internal/scans/{scan_id}/execution-context",
                headers={"X-Service-Key": self._internal_api_key},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

        return ScanContext(
            scan_id=data["scan_id"],
            organization_id=data["org_id"],
            repository_id=data["repository_id"],
            project_id=data["project_id"],
            branch=data.get("branch"),
            commit_sha=data.get("commit_sha"),
            user_id=data.get("user_id"),
            job_id=job.job_id,
            expected_scanners=data.get("expected_scanners"),
            coverage_scope=data.get("coverage_scope"),
        )

    async def _get_clone_url(self, context: ScanContext) -> tuple[str, str]:
        """Build an authenticated clone URL via the internal API."""

        async with httpx.AsyncClient() as client:
            # Ask the API for repo details + installation token
            resp = await client.get(
                f"{self.api_base_url}/api/v1/internal/repositories/{context.repository_id}/clone-url",
                headers={"X-Service-Key": self._internal_api_key},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["clone_url"], data["auth_header"]

    async def _create_scanner_run(
        self, context: ScanContext, scanner_name: str, version: str | None = None
    ) -> str | None:
        """Create a ScannerRun record via internal API and return its ID."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/scanner-runs",
                    json={"scanner_name": scanner_name, "scanner_version": version},
                    headers={"X-Service-Key": self._internal_api_key},
                    timeout=30.0,
                )
                resp.raise_for_status()
                return resp.json()["id"]
            except Exception as e:
                print(f"[orchestrator] Failed to create scanner run for {scanner_name}: {e}")
                return None

    async def _update_scanner_run(self, run_id: str, **kwargs) -> None:
        """Update a ScannerRun record via internal API."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.patch(
                    f"{self.api_base_url}/api/v1/internal/scanner-runs/{run_id}",
                    json=kwargs,
                    headers={"X-Service-Key": self._internal_api_key},
                    timeout=30.0,
                )
                resp.raise_for_status()
            except Exception as e:
                print(f"[orchestrator] Failed to update scanner run {run_id}: {e}")

    async def _run_scanners(
        self,
        context: ScanContext,
        scan_type: str,
    ) -> dict:
        results = {}
        scanners_to_run = self._get_scanners_for_type(scan_type)

        async def run_single(scanner_name: str) -> tuple[str, ScannerResult]:
            scanner = self._get_scanner(scanner_name)
            if not scanner:
                return scanner_name, ScannerResult(
                    scanner_name=scanner_name,
                    success=True,
                    raw_output={},
                    artifact_paths=[],
                )

            version = scanner.get_version() if hasattr(scanner, "get_version") else None
            run_id = await self._create_scanner_run(context, scanner_name, version)
            if run_id:
                context.scanner_run_ids[scanner_name] = run_id
            start = datetime.utcnow()
            print(
                f"[orchestrator] scanner {scanner_name} started "
                f"scan={context.scan_id} run_id={run_id or 'n/a'} version={version or 'unknown'}"
            )

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(scanner.run, context.repo_path),
                    timeout=self.SCAN_TIMEOUT,
                )
                duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
                result.duration_ms = duration_ms

                if run_id:
                    await self._update_scanner_run(
                        run_id,
                        status="completed" if result.success else "failed",
                        duration_ms=duration_ms,
                        exit_code=0 if result.success else 1,
                        error_message=result.error or None,
                    )
                print(
                    f"[orchestrator] scanner {scanner_name} finished "
                    f"scan={context.scan_id} success={result.success} duration_ms={duration_ms} "
                    f"error={result.error or 'none'}"
                )
                return scanner_name, result
            except TimeoutError:
                if run_id:
                    duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
                    await self._update_scanner_run(
                        run_id,
                        status="failed",
                        duration_ms=duration_ms,
                        error_message="Scanner timed out after 30 minutes",
                    )
                print(
                    f"[orchestrator] scanner {scanner_name} timed out scan={context.scan_id} duration_ms={duration_ms}"
                )
                return scanner_name, ScannerResult(
                    scanner_name=scanner_name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    error="Scanner timed out after 30 minutes",
                )
            except Exception as e:
                if run_id:
                    duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
                    await self._update_scanner_run(
                        run_id,
                        status="failed",
                        duration_ms=duration_ms,
                        error_message=str(e),
                    )
                print(f"[orchestrator] scanner {scanner_name} crashed scan={context.scan_id} error={e}")
                return scanner_name, ScannerResult(
                    scanner_name=scanner_name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    error=str(e),
                )

        tasks = [run_single(name) for name in scanners_to_run]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in completed:
            if isinstance(item, Exception):
                continue
            name, result = item
            results[name] = result

        return results

    def _get_scanners_for_type(self, scan_type: str) -> list[str]:
        return scanners_for_scan_type(scan_type)

    def _get_scanner(self, name: str):
        registration = SCANNER_REGISTRY.get(name)
        if registration:
            return registration.adapter_factory()
        return None

    async def _upload_artifacts(self, context: ScanContext) -> dict:
        uris = {"scanner_runs": {}}

        for scanner_name, result in context.scanner_results.items():
            if not result.success:
                continue

            run_uploads = {}

            if result.raw_output:
                try:
                    uri = self.r2.upload_raw_output(
                        scan_id=context.scan_id,
                        scanner_name=scanner_name,
                        output_data=result.raw_output,
                    )
                    uris[f"{scanner_name}_raw"] = uri
                    run_uploads["raw_output_uri"] = uri
                except Exception as e:
                    print(f"[orchestrator] Failed to upload {scanner_name} raw output: {e}")

            if result.artifact_paths:
                for artifact_path in result.artifact_paths:
                    try:
                        key = f"scans/{context.scan_id}/{scanner_name}/{artifact_path.name}"
                        meta = self.r2.upload_file(artifact_path, key)
                        uris[f"{scanner_name}_{artifact_path.name}"] = meta["storage_uri"]
                        run_uploads["artifact_uri"] = meta["storage_uri"]
                    except Exception as e:
                        print(f"[orchestrator] Failed to upload artifact {artifact_path}: {e}")

            if run_uploads:
                uris["scanner_runs"][scanner_name] = run_uploads
                run_id = context.scanner_run_ids.get(scanner_name)
                if run_id:
                    await self._update_scanner_run(
                        run_id,
                        artifact_uri=run_uploads.get("artifact_uri") or run_uploads.get("raw_output_uri"),
                        metadata_json=run_uploads,
                    )

        return uris

    async def _normalize_results(self, context: ScanContext) -> list[dict]:
        all_findings = []

        for scanner_name, result in context.scanner_results.items():
            if not result.success:
                continue

            normalizer = self._get_normalizer(scanner_name)
            if normalizer:
                findings = normalizer(result.raw_output, context.repository_id)
                all_findings.extend(findings)

        return all_findings

    def _get_normalizer(self, name: str):
        registration = SCANNER_REGISTRY.get(name)
        if registration:
            return registration.normalize
        return None

    def _filter_findings_to_changed_files(self, findings: list[dict], changed_files: list[str]) -> list[dict]:
        if not changed_files:
            return findings

        changed = {path.strip("./") for path in changed_files}
        filtered = []
        for finding in findings:
            instance = finding.get("instance") or {}
            path = (instance.get("path") or "").strip("./")
            if not path or path in changed:
                filtered.append(finding)
        return filtered

    def _build_completion_summary(self, context: ScanContext, *, job_type: str, duration_seconds: float) -> dict:
        expected = context.expected_scanners or list(context.scanner_results.keys())
        completed = [name for name, result in context.scanner_results.items() if result.success]
        failed = [name for name, result in context.scanner_results.items() if not result.success]
        missing = [name for name in expected if name not in context.scanner_results]

        return {
            "finding_count": len(context.findings),
            "critical_count": context.critical_count,
            "high_count": context.high_count,
            "scanners_run": list(context.scanner_results.keys()),
            "scanner_health": {
                "expected": expected,
                "completed": completed,
                "failed": failed,
                "missing": missing,
                "complete": not failed and not missing,
            },
            "seen_fingerprints": [
                finding["canonical_fingerprint"]
                for finding in context.findings
                if finding.get("canonical_fingerprint")
            ],
            "scope": "diff" if job_type == "scan.repo.diff" else "full",
            "changed_files": context.changed_files or [],
            "duration_ms": int(duration_seconds * 1000),
            "duration_seconds": round(duration_seconds, 1),
            "artifact_uris": context.artifact_uris,
        }

    async def _persist_findings(self, context: ScanContext):
        if not context.findings:
            return

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/findings",
                    json={"findings": context.findings},
                    headers={"X-Service-Key": self._internal_api_key},
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
                print(f"[orchestrator] Persisted findings: {data}")
            except httpx.HTTPStatusError as e:
                print(f"[orchestrator] Failed to persist findings (HTTP {e.response.status_code}): {e.response.text}")
            except Exception as e:
                print(f"[orchestrator] Failed to persist findings: {e}")

    async def _send_notifications(self, context: ScanContext):
        if not self._notifier or not context.user_id:
            return

        try:
            await self._notifier.send_scan_completed(
                user_id=context.user_id,
                scan_id=context.scan_id,
                org_id=context.organization_id,
                project_id=context.project_id,
                finding_count=len(context.findings),
                critical_count=context.critical_count,
                has_failures=context.scan_failed,
            )

            for finding in context.findings:
                if finding.get("category") == "secret":
                    await self._notifier.send_secret_found(
                        user_id=context.user_id,
                        scan_id=context.scan_id,
                        org_id=context.organization_id,
                        project_id=context.project_id,
                        finding_title=finding.get("title", "Unknown secret"),
                    )
                    break
        except Exception as e:
            print(f"[orchestrator] Failed to send notifications: {e}")

    async def _send_failure_notification(self, context: ScanContext, retry_count: int):
        if not self._notifier or not context.user_id:
            return

        try:
            await self._notifier.send_scan_failed(
                user_id=context.user_id,
                scan_id=context.scan_id,
                org_id=context.organization_id,
                project_id=context.project_id,
                error=context.error_message or "Unknown error",
                retry_count=retry_count,
            )
        except Exception:
            pass

    async def _update_status(
        self,
        context: ScanContext,
        stage: str,
        metadata: dict | None = None,
    ):
        await self.queue.update_job_status(context.job_id, stage, metadata)

    async def _update_scan_status(
        self,
        context: ScanContext,
        status: str,
        error: str | None = None,
        summary: dict | None = None,
    ):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.patch(
                    f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/status",
                    json={
                        "status": status,
                        "error_message": error,
                        "summary_json": summary,
                    },
                    headers={"X-Service-Key": self._internal_api_key},
                    timeout=30.0,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                print(f"[orchestrator] Failed to update scan status (HTTP {e.response.status_code}): {e.response.text}")
            except Exception as e:
                print(f"[orchestrator] Failed to update scan status: {e}")
