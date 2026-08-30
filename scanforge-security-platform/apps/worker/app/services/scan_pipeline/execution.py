from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import urlparse

import httpx

from app.clients.r2 import R2Client
from app.core.logging import get_logger
from app.scanners.base import ScannerResult
from app.scanners.registry import SCANNER_REGISTRY, scanners_for_scan_type
from app.security.secret_evidence import safe_artifact_key, sanitize_trivy_output
from app.services.scan_pipeline.context import ScanContext

_log = get_logger(__name__)

SCAN_TIMEOUT = 1800


class ScanExecutionStage:
    def __init__(
        self,
        r2: R2Client,
        api_base_url: str,
        worker_credential: str,
        runtime=None,
    ) -> None:
        from app.runtime.base import build_scan_runtime

        self.r2 = r2
        self.api_base_url = api_base_url
        self.worker_credential = worker_credential
        self.runtime = runtime or build_scan_runtime()

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Worker-Credential": self.worker_credential}

    def _redact(self, value: str) -> str:
        redacted = value or ""
        if self.worker_credential:
            redacted = redacted.replace(self.worker_credential, "[REDACTED]")
        return re.sub(r"Authorization: Basic\s+\S+", "Authorization: Basic [REDACTED]", redacted)

    async def prepare_repository(self, context: ScanContext) -> Path:
        repo_dir = Path(mkdtemp(prefix="scan_repo_"))
        clone_url, auth_header = await self._get_clone_url(context)
        parsed_url = urlparse(clone_url)
        if parsed_url.scheme != "https" or parsed_url.hostname != "github.com":
            raise RuntimeError("clone target must be the verified github.com origin")
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
                    "git", "-c", "http.followRedirects=false", "clone", "--depth", "1", "--single-branch", "--no-recurse-submodules",
                    *(["--branch", context.branch] if context.branch else []),
                    clone_url, str(repo_dir),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                env=git_env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git clone failed: {self._redact(result.stderr).strip()}")
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("git clone timed out after 5 minutes") from exc
        except Exception:
            shutil.rmtree(repo_dir, ignore_errors=True)
            raise
        finally:
            auth_header = ""
            git_env.pop("GIT_CONFIG_VALUE_0", None)
        return repo_dir

    async def collect_changed_files(self, repo_path: Path) -> list[str]:
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
            except Exception:  # noqa: S112
                continue
        return []

    async def run_scanners(self, context: ScanContext, scan_type: str) -> dict:
        results: dict[str, ScannerResult] = {}
        scanner_names = scanners_for_scan_type(scan_type)

        async def run_single(scanner_name: str) -> tuple[str, ScannerResult]:
            registration = SCANNER_REGISTRY.get(scanner_name)
            if not registration:
                return scanner_name, ScannerResult(
                    scanner_name=scanner_name, success=True, raw_output={}, artifact_paths=[]
                )
            scanner = registration.adapter_factory()
            version = scanner.get_version() if hasattr(scanner, "get_version") else None
            run_id = await self._create_scanner_run(context, scanner_name, version)
            if run_id:
                context.scanner_run_ids[scanner_name] = run_id
            start = datetime.now(UTC)
            _log.info(
                "scanner started",
                extra={"scan_id": context.scan_id, "scanner": scanner_name, "job_id": context.job_id},
            )
            try:
                def scanner_run():
                    if os.environ.get("APP_ENV", "development").lower() == "private-beta":
                        return scanner.run_contained(context.repo_path, self.runtime)
                    return scanner.run(context.repo_path)

                result = await asyncio.wait_for(
                    asyncio.to_thread(scanner_run),
                    timeout=SCAN_TIMEOUT,
                )
                duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
                result.duration_ms = duration_ms
                if run_id:
                    await self._update_scanner_run(
                        run_id,
                        status="completed" if result.success else "failed",
                        duration_ms=duration_ms,
                        exit_code=0 if result.success else 1,
                        error_message=result.error or None,
                    )
                _log.info(
                    "scanner finished",
                    extra={
                        "scan_id": context.scan_id,
                        "scanner": scanner_name,
                        "success": result.success,
                        "duration_ms": duration_ms,
                    },
                )
                return scanner_name, result
            except TimeoutError:
                duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
                if run_id:
                    await self._update_scanner_run(
                        run_id, status="failed", duration_ms=duration_ms,
                        error_message="Scanner timed out after 30 minutes",
                    )
                _log.warning(
                    "scanner timed out",
                    extra={"scan_id": context.scan_id, "scanner": scanner_name, "duration_ms": duration_ms},
                )
                return scanner_name, ScannerResult(
                    scanner_name=scanner_name, success=False, raw_output={}, artifact_paths=[],
                    error="Scanner timed out after 30 minutes",
                )
            except Exception as exc:
                duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
                if run_id:
                    await self._update_scanner_run(
                        run_id, status="failed", duration_ms=duration_ms, error_message=str(exc),
                    )
                _log.error(
                    "scanner crashed",
                    extra={"scan_id": context.scan_id, "scanner": scanner_name, "error": str(exc)},
                )
                return scanner_name, ScannerResult(
                    scanner_name=scanner_name, success=False, raw_output={}, artifact_paths=[], error=str(exc),
                )

        completed = await asyncio.gather(*[run_single(n) for n in scanner_names], return_exceptions=True)
        for item in completed:
            if isinstance(item, Exception):
                continue
            name, result = item
            results[name] = result
        return results

    async def upload_artifacts(self, context: ScanContext) -> dict:
        uris: dict = {"scanner_runs": {}}
        for scanner_name, result in context.scanner_results.items():
            if scanner_name == "gitleaks":
                # Raw Gitleaks records contain matched values and never cross
                # the coordinator boundary. Only normalized findings persist.
                result.raw_output = {}
                result.artifact_paths = []
            elif scanner_name == "trivy":
                sanitized_output = sanitize_trivy_output(result.raw_output)
                result.raw_output = sanitized_output
                for artifact_path in result.artifact_paths:
                    artifact_path.write_text(
                        json.dumps(sanitized_output, separators=(",", ":"))
                    )
            if not result.success:
                continue
            run_uploads: dict = {}
            if result.raw_output and scanner_name != "gitleaks":
                try:
                    uri = await self.r2.upload_raw_output(
                        scan_id=context.scan_id,
                        organization_id=context.organization_id,
                        scanner_name=scanner_name,
                        output_data=(
                            sanitize_trivy_output(result.raw_output)
                            if scanner_name == "trivy" else result.raw_output
                        ),
                    )
                    uris[f"{scanner_name}_raw"] = uri
                    run_uploads["raw_output_uri"] = uri
                except Exception:
                    _log.warning(
                        "artifact upload failed",
                        extra={"scan_id": context.scan_id, "scanner": scanner_name},
                    )
            if result.artifact_paths:
                for artifact_path in result.artifact_paths:
                    try:
                        key = safe_artifact_key(
                            context.organization_id,
                            context.scan_id,
                            scanner_name,
                            artifact_path.name,
                        )
                        meta = await self.r2.upload_file(artifact_path, key)
                        uris[f"{scanner_name}_{artifact_path.name}"] = meta["storage_uri"]
                        run_uploads["artifact_uri"] = meta["storage_uri"]
                    except Exception:
                        _log.warning(
                            "artifact file upload failed",
                            extra={"scan_id": context.scan_id, "scanner": scanner_name},
                        )
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

    async def _get_clone_url(self, context: ScanContext) -> tuple[str, str]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_base_url}/api/v1/internal/repositories/{context.repository_id}/clone-url",
                headers=self._headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["clone_url"], data["auth_header"]

    async def _create_scanner_run(self, context: ScanContext, scanner_name: str, version: str | None) -> str | None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/scanner-runs",
                    json={"scanner_name": scanner_name, "scanner_version": version},
                    headers=self._headers,
                    timeout=30.0,
                )
                resp.raise_for_status()
                return resp.json()["id"]
            except Exception:
                _log.warning(
                    "failed to create scanner run",
                    extra={"scan_id": context.scan_id, "scanner": scanner_name},
                )
                return None

    async def _update_scanner_run(self, run_id: str, **kwargs) -> None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.patch(
                    f"{self.api_base_url}/api/v1/internal/scanner-runs/{run_id}",
                    json=kwargs,
                    headers=self._headers,
                    timeout=30.0,
                )
                resp.raise_for_status()
            except Exception:
                _log.warning("failed to update scanner run")
