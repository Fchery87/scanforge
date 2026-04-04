import json
import re
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class SyftAdapter(ScannerAdapter):
    name = "syft"
    binary_name = "syft"
    binary_env_var = "SYFT_BINARY"

    def run(self, repo_path: Path) -> ScannerResult:
        import time

        start = time.time()

        try:
            output_file = repo_path / "syft-results.json"

            result = subprocess.run(
                [
                    self.binary_name,
                    "scan",
                    f"dir:{repo_path}",
                    "-o",
                    "json",
                    "--file",
                    str(output_file),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(repo_path),
            )

            duration_ms = int((time.time() - start) * 1000)

            output = {}
            artifacts = []

            if output_file.exists():
                with open(output_file) as f:
                    try:
                        output = json.load(f)
                    except json.JSONDecodeError:
                        output = {"raw": f.read()}

                artifacts.append(output_file)

            # Treat as success if output file has artifacts key
            has_output = bool(output and "artifacts" in output)
            return ScannerResult(
                scanner_name=self.name,
                success=result.returncode == 0 or has_output,
                raw_output=output,
                artifact_paths=artifacts,
                version=self.get_version(),
                duration_ms=duration_ms,
                error=result.stderr.strip() if result.returncode != 0 and not has_output else "",
            )

        except subprocess.TimeoutExpired:
            return ScannerResult(
                scanner_name=self.name,
                success=False,
                raw_output={},
                artifact_paths=[],
                error="Scanner timed out",
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            return ScannerResult(
                scanner_name=self.name,
                success=False,
                raw_output={},
                artifact_paths=[],
                error=str(e),
            )

    def get_version(self) -> str:
        try:
            result = subprocess.run(
                [self.binary_name, "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            match = re.search(r"Version:\s*([^\s]+)", result.stdout)
            if match:
                return match.group(1)
            return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        except Exception:
            return ""
