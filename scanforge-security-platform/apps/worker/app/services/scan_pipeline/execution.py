from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import urlparse

import httpx

from app.clients.r2 import R2Client
from app.core.logging import get_logger
from app.scanners.base import ScannerResult
from app.scanners.image_manifest import scanner_provenance, validate_manifest
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
        self._runtime_factory = build_scan_runtime if runtime is None else None
        self.runtime = runtime or build_scan_runtime()

    def begin_scan(self) -> None:
        if self._runtime_factory and os.environ.get("APP_ENV", "development").lower() == "private-beta":
            self.runtime = self._runtime_factory()

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
        try:
            clone_url, auth_header = await self._get_clone_url(context)
            parsed_url = urlparse(clone_url)
            if parsed_url.scheme != "https" or parsed_url.hostname != "github.com":
                raise RuntimeError("clone target must be the verified github.com origin")
        except BaseException:
            shutil.rmtree(repo_dir)
            raise
        git_env = dict(os.environ)
        git_env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraHeader",
                "GIT_CONFIG_VALUE_0": auth_header,
            }
        )
        try:
            result = await self._run_git_process(
                [
                    "git", "-c", "http.followRedirects=false", "clone", "--no-checkout", "--depth", "1", "--single-branch", "--no-recurse-submodules",
                    *(["--branch", context.branch] if context.branch and not context.head_commit_sha else []),
                    clone_url, str(repo_dir),
                ],
                env=git_env,
            )
            if result[0] != 0:
                raise RuntimeError("Git clone failed for recorded repository")
            target = context.head_commit_sha or context.commit_sha
            for sha in dict.fromkeys(filter(None, (target, context.base_commit_sha))):
                self._verify_commit_id(sha)
                await self._git(repo_dir, ["fetch", "--depth", "1", "origin", sha], env=git_env)
                await self._git(repo_dir, ["rev-parse", "--verify", f"{sha}^{{commit}}"], env=git_env)
            await self._git(repo_dir, ["checkout", "--detach", target or "HEAD", "--"], env=git_env)
            observed = await self._git(repo_dir, ["rev-parse", "HEAD"], env=git_env)
            self._verify_commit_id(observed.strip())
            if target and observed.strip().lower() != target.lower():
                raise RuntimeError("Repository checkout does not match recorded commit")
            context.commit_sha = observed.strip().lower()
        except TimeoutError as exc:
            shutil.rmtree(repo_dir)
            raise RuntimeError("git clone timed out after 5 minutes") from exc
        except BaseException:
            shutil.rmtree(repo_dir, ignore_errors=True)
            raise
        finally:
            auth_header = ""
            git_env.pop("GIT_CONFIG_VALUE_0", None)
        repo_dir.chmod(0o755)
        return repo_dir

    @staticmethod
    def _verify_commit_id(sha: str | None) -> None:
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?", sha):
            raise RuntimeError("Recorded commit identity is missing or invalid")

    async def _git(self, repo_path: Path, arguments: list[str], *, env=None) -> str:
        status, stdout = await self._run_git_process(
            ["git", "-c", "http.followRedirects=false", *arguments], cwd=str(repo_path), env=env,
        )
        if status != 0:
            raise RuntimeError(f"Git {arguments[0]} failed for recorded commit context")
        return stdout

    @staticmethod
    async def _run_git_process(command: list[str], *, cwd=None, env=None) -> tuple[int, str]:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            cwd=cwd, env=env,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=300)
            return process.returncode, stdout.decode("utf-8", errors="replace")
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise

    async def collect_changed_files(
        self, repo_path: Path, *, base_sha: str | None = None, head_sha: str | None = None,
    ) -> list[str]:
        self._verify_commit_id(base_sha)
        self._verify_commit_id(head_sha)
        for sha in (base_sha, head_sha):
            await self._git(repo_path, ["rev-parse", "--verify", f"{sha}^{{commit}}"])
        output = await self._git(repo_path, ["diff", "--name-only", "-z", base_sha, head_sha, "--"])
        return [path for path in output.split("\0") if path]

    async def run_scanners(self, context: ScanContext, scan_type: str) -> dict:
        results: dict[str, ScannerResult] = {}
        scan_runtime = self.runtime
        scanner_names = scanners_for_scan_type(scan_type)
        contained = os.environ.get("APP_ENV", "development").lower() == "private-beta"
        if context.output_root is None:
            context.output_root = Path(mkdtemp(prefix="scan_output_"))
        manifest = await self._load_image_manifest(context) if contained else None

        async def run_single(scanner_name: str) -> tuple[str, ScannerResult]:
            registration = SCANNER_REGISTRY.get(scanner_name)
            if not registration:
                return scanner_name, ScannerResult(
                    scanner_name=scanner_name, success=False, raw_output={}, artifact_paths=[],
                    error="Scanner is not registered",
                )
            scanner = registration.adapter_factory()
            version = manifest["scanners"][scanner_name] if manifest else scanner.get_version()
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
                    if contained:
                        return scanner.run_contained(
                            context.repo_path, scan_runtime, context.output_root / scanner_name,
                        )
                    return scanner.run(context.repo_path)

                result = await asyncio.wait_for(
                    asyncio.to_thread(scanner_run),
                    timeout=SCAN_TIMEOUT,
                )
                duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
                result.duration_ms = duration_ms
                if manifest:
                    result.version = version
                    result.provenance = scanner_provenance(manifest, scanner_name, scan_runtime.image, scanner.runtime_arguments())
                if run_id:
                    await self._update_scanner_run(
                        context, run_id,
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
                        context, run_id, status="failed", duration_ms=duration_ms,
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
            except Exception:
                duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
                if run_id:
                    await self._update_scanner_run(
                        context, run_id, status="failed", duration_ms=duration_ms, error_message="Scanner execution failed",
                    )
                _log.error(
                    "scanner crashed",
                    extra={"scan_id": context.scan_id, "scanner": scanner_name},
                )
                return scanner_name, ScannerResult(
                    scanner_name=scanner_name, success=False, raw_output={}, artifact_paths=[],
                    error="Scanner execution failed",
                )

        completed = await asyncio.gather(*[run_single(n) for n in scanner_names], return_exceptions=True)
        for item in completed:
            if isinstance(item, Exception):
                continue
            name, result = item
            results[name] = result
        return results

    async def _load_image_manifest(self, context: ScanContext) -> dict:
        from app.runtime.models import ScanRuntimeRequest

        directory = context.output_root / "manifest"
        directory.mkdir()
        result = await asyncio.to_thread(
            self.runtime.run,
            ScanRuntimeRequest(
                executable="python3", arguments=("/opt/scanforge-image-manifest.py", "verify"),
                source_directory=context.repo_path, output_directory=directory,
                timeout_seconds=60, output_limit_bytes=64 * 1024,
            ),
        )
        if result.timed_out or result.exit_code != 0:
            raise RuntimeError("Scanner image has missing or invalid offline assets")
        try:
            return validate_manifest(json.loads(result.stdout))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Scanner image manifest is invalid") from exc

    async def upload_artifacts(self, context: ScanContext) -> dict:
        uris: dict = {"scanner_runs": {}}
        for scanner_name, result in context.scanner_results.items():
            if scanner_name == "gitleaks":
                # Raw Gitleaks records contain matched values and never cross
                # the coordinator boundary. Only normalized findings persist.
                result.raw_output = {}
                result.artifact_paths = []
            if not result.success:
                continue
            for artifact_path in result.artifact_paths:
                root = context.output_root or context.repo_path
                if root is None or artifact_path.is_symlink() or not artifact_path.resolve().is_relative_to(root.resolve()):
                    raise RuntimeError("Scanner artifact is outside its scan workspace")
                info = artifact_path.stat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 50 * 1024 * 1024:
                    raise RuntimeError("Scanner artifact is unsafe or oversized")
            if scanner_name == "trivy":
                sanitized_output = sanitize_trivy_output(result.raw_output)
                result.raw_output = sanitized_output
                for artifact_path in result.artifact_paths:
                    with open(artifact_path, "w", opener=lambda name, flags: os.open(name, flags | os.O_NOFOLLOW)) as artifact:
                        artifact.write(json.dumps(sanitized_output, separators=(",", ":")))
            run_uploads: dict = {}
            if result.raw_output and scanner_name != "gitleaks" and not result.artifact_paths:
                try:
                    uri = await self.r2.upload_raw_output(
                        scan_id=context.scan_id,
                        organization_id=context.organization_id,
                        scanner_name=scanner_name,
                        attempt_id=context.attempt_id, execution_revision=context.execution_revision,
                        output_data=(
                            sanitize_trivy_output(result.raw_output)
                            if scanner_name == "trivy" else result.raw_output
                        ),
                    )
                    uris[f"{scanner_name}_raw"] = uri
                    run_uploads["raw_output_uri"] = uri
                except Exception as exc:
                    raise RuntimeError("Validated scanner evidence upload failed") from exc
            if result.artifact_paths:
                for artifact_path in result.artifact_paths:
                    try:
                        key = safe_artifact_key(
                            context.organization_id,
                            context.scan_id,
                            scanner_name,
                            artifact_path.name,
                        )
                        meta = await self.r2.upload_file(
                            artifact_path, key, attempt_id=context.attempt_id,
                            execution_revision=context.execution_revision,
                        )
                        uris[f"{scanner_name}_{artifact_path.name}"] = meta["storage_uri"]
                        run_uploads["artifact_uri"] = meta["storage_uri"]
                        if result.raw_output:
                            uris[f"{scanner_name}_raw"] = meta["storage_uri"]
                            run_uploads["raw_output_uri"] = meta["storage_uri"]
                    except Exception as exc:
                        raise RuntimeError("Validated scanner artifact upload failed") from exc
            if run_uploads:
                uris["scanner_runs"][scanner_name] = run_uploads
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
                    json={"scanner_name": scanner_name, "scanner_version": version,
                          "attempt_id": context.attempt_id, "execution_revision": context.execution_revision},
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

    async def _update_scanner_run(self, context: ScanContext, run_id: str, **kwargs) -> None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.patch(
                    f"{self.api_base_url}/api/v1/internal/scanner-runs/{run_id}",
                    json={**kwargs, "attempt_id": context.attempt_id,
                          "execution_revision": context.execution_revision},
                    headers=self._headers,
                    timeout=30.0,
                )
                resp.raise_for_status()
            except Exception:
                _log.warning("failed to update scanner run")
