import json
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class CheckovAdapter(ScannerAdapter):
    name = "checkov"
    binary_name = "checkov"
    binary_env_var = "CHECKOV_BINARY"

    def run(self, repo_path: Path) -> ScannerResult:
        import time

        start = time.time()
        output_file = repo_path / "checkov-results.json"

        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "--directory",
                    str(repo_path),
                    "--quiet",
                    "--skip-download",
                    "--output",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(repo_path),
            )

            duration_ms = int((time.time() - start) * 1000)
            output = {}
            artifacts = []

            if result.stdout:
                try:
                    output = json.loads(result.stdout)
                    output_file.write_text(json.dumps(output, indent=2))
                    artifacts.append(output_file)
                except json.JSONDecodeError:
                    output = {"raw": result.stdout}

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
