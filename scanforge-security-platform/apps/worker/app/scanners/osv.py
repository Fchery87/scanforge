import json
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class OsvAdapter(ScannerAdapter):
    name = "osv"
    binary_name = "osv-scanner"
    binary_env_var = "OSV_SCANNER_BINARY"

    def run(self, repo_path: Path) -> ScannerResult:
        import time

        start = time.time()

        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "--format",
                    "json",
                    "--output",
                    "osv-results.json",
                    "-r",
                    str(repo_path),
                ],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(repo_path),
            )

            duration_ms = int((time.time() - start) * 1000)

            output = {}
            artifacts = []
            output_file = repo_path / "osv-results.json"

            if output_file.exists():
                with open(output_file) as f:
                    try:
                        output = json.load(f)
                    except json.JSONDecodeError:
                        output = {"raw": f.read()}

                artifacts.append(output_file)

            # osv-scanner returns exit code 1 when vulnerabilities are found
            # but still produces valid output — treat as success if output exists
            has_output = bool(output and output != {"raw": ""})
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
