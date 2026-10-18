from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.runtime.docker import DockerScanRuntime
from app.runtime.local import LocalScanRuntime
from app.runtime.models import ScanRuntime
from app.security.secret_evidence import assert_ai_disabled_for_private_beta

CUSTOMER_FACING_ENVIRONMENTS: frozenset[str] = frozenset(
    {"beta", "private-beta", "managed-beta", "production", "staging"}
)
DEFAULT_WORKSPACE_ROOT = "/var/lib/scanforge/workspaces"
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def is_customer_runtime_environment(env_name: str | None = None) -> bool:
    resolved = (env_name if env_name is not None else os.environ.get("APP_ENV", "development")).strip().lower()
    return resolved in CUSTOMER_FACING_ENVIRONMENTS


def get_workspace_root() -> Path:
    configured = os.environ.get("WORKER_WORKSPACE_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    if is_customer_runtime_environment():
        return Path(DEFAULT_WORKSPACE_ROOT)
    return (Path("/tmp") / "scanforge-workspaces").resolve()  # noqa: S108


def ensure_workspace_root(workspace_root: Path | None = None) -> Path:
    root = (workspace_root or get_workspace_root()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    return root


def prepare_isolated_scan_workspace(
    workspace_root: Path | None = None,
    *,
    scan_id: str,
    attempt_id: str = "attempt-0",
) -> Path:
    safe_scan = scan_id.strip()
    safe_attempt = (attempt_id or "attempt-0").strip()
    if not _SAFE_TOKEN_RE.fullmatch(safe_scan) or not _SAFE_TOKEN_RE.fullmatch(safe_attempt):
        raise ValueError("Invalid scan_id or attempt_id for workspace path")
    root = ensure_workspace_root(workspace_root)
    scan_dir = (root / f"{safe_scan}_{safe_attempt}").resolve()
    if root not in scan_dir.parents:
        raise ValueError("Scan workspace escaped controlled workspace root")
    if scan_dir.exists():
        shutil.rmtree(scan_dir, ignore_errors=True)
    scan_dir.mkdir(parents=True, exist_ok=True)
    # 0o711 on the per-scan parent directory inside 0o700 workspace_root allows
    # container UID 65532 to traverse bind-mounted subdirectories without allowing
    # directory listing or access by unrelated local accounts.
    scan_dir.chmod(0o711)
    source_dir = scan_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_dir.chmod(0o755)
    return source_dir


def make_source_readable_for_scanner(source_dir: Path) -> None:
    """Ensure cloned source tree can be read by non-root scanner container user 65532:65532."""
    source_dir.chmod(0o755)
    if source_dir.parent.exists():
        source_dir.parent.chmod(0o711)
    for root_str, dirs, files in os.walk(source_dir, followlinks=False):
        root_path = Path(root_str)
        for d in dirs:
            p = root_path / d
            if not p.is_symlink():
                p.chmod(0o755)
        for f in files:
            p = root_path / f
            if not p.is_symlink():
                current_mode = p.stat().st_mode & 0o777
                p.chmod(0o755 if (current_mode & 0o111) else 0o644)


def prepare_scanner_output_directory(output_dir: Path) -> Path:
    """Prepare a writable output directory for container UID 65532:65532."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.chmod(0o1777)
    return output_dir


def compute_directory_size_bytes(directory: Path) -> int:
    total = 0
    if not directory.exists():
        return 0
    for root_str, _dirs, files in os.walk(directory, followlinks=False):
        root_path = Path(root_str)
        for name in files:
            candidate = root_path / name
            try:
                if not candidate.is_symlink():
                    total += candidate.stat().st_size
            except OSError:
                continue
    return total


def enforce_directory_quota(directory: Path, max_bytes: int, *, label: str = "workspace") -> int:
    used = compute_directory_size_bytes(directory)
    if used > max_bytes:
        raise RuntimeError(f"{label} size {used} bytes exceeds quota {max_bytes} bytes")
    return used


def verify_host_coordinator_prerequisites() -> dict[str, str]:
    assert_ai_disabled_for_private_beta()
    git_bin = shutil.which("git")
    if not git_bin:
        raise RuntimeError("git is required on the worker host coordinator")
    if is_customer_runtime_environment():
        docker_bin = shutil.which("docker")
        if not docker_bin:
            raise RuntimeError("Docker is required for the customer scanner runtime")
        ws_root = ensure_workspace_root()
        return {"git": git_bin, "docker": docker_bin, "workspace_root": str(ws_root)}
    return {"git": git_bin, "workspace_root": str(get_workspace_root())}


def build_scan_runtime() -> ScanRuntime:
    assert_ai_disabled_for_private_beta()
    if is_customer_runtime_environment():
        image = os.environ.get("SCANNER_IMAGE", "").strip()
        runtime = DockerScanRuntime(image=image)
        if not shutil.which("git"):
            raise RuntimeError("git is required on the worker host coordinator")
        return runtime
    return LocalScanRuntime()


def provision_scanner_manifest(runtime: ScanRuntime, path: Path | None = None) -> Path | None:
    """Cache scanner provenance from the exact image the host coordinator will run."""
    if not isinstance(runtime, DockerScanRuntime):
        return None

    try:
        manifest = json.loads(runtime.read_image_file("/opt/scanner-manifest.json"))
    except (json.JSONDecodeError, OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("scanner image has no readable provenance manifest") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("scanners"), dict):
        raise RuntimeError("scanner image provenance manifest has an invalid structure")

    from app.scanners.registry import SCANNER_REGISTRY

    entries = manifest["scanners"]
    if set(entries) != set(SCANNER_REGISTRY):
        raise RuntimeError("scanner image provenance manifest does not cover every registered scanner")
    for name, registration in SCANNER_REGISTRY.items():
        entry = entries[name]
        if not isinstance(entry, dict) or not entry.get("scanner_version"):
            raise RuntimeError(f"scanner image provenance is missing the {name} version")
        if registration.adapter_factory().db_backed and not (
            entry.get("db_digest") and entry.get("db_published_at")
        ):
            raise RuntimeError(f"scanner image provenance is missing the {name} database identity")

    manifest["image_digest"] = runtime.image_digest
    destination = path or Path(
        os.environ.get("SCANNER_MANIFEST_PATH", str(Path(tempfile.gettempdir()) / "scanforge-scanner-manifest.json"))
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".scanner-manifest-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w") as temporary:
            temporary.write(json.dumps(manifest, indent=2) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    os.environ["SCANNER_MANIFEST_PATH"] = str(destination)
    return destination

