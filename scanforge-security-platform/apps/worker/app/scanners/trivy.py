import json
import re
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class TrivyAdapter(ScannerAdapter):
    name = "trivy"
    binary_name = "trivy"

    def get_version(self) -> str:
        try:
            result = subprocess.run(
                [self.binary_name, "--version"],
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

    def run(self, repo_path: Path) -> ScannerResult:
        import time
        start = time.time()

        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "fs",
                    "--format", "json",
                    "--output", "trivy-results.json",
                    "--scanners", "vuln,secret,misconfig",
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
            output_file = repo_path / "trivy-results.json"

            if output_file.exists():
                with open(output_file) as f:
                    try:
                        output = json.load(f)
                    except json.JSONDecodeError:
                        output = {"raw": f.read()}

                artifacts.append(output_file)

            # Trivy may return non-zero when it finds vulnerabilities
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
