import json
import subprocess
import tempfile
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class GitleaksAdapter(ScannerAdapter):
    name = "gitleaks"
    binary_name = "gitleaks"

    def run(self, repo_path: Path) -> ScannerResult:
        import time
        start = time.time()

        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "detect",
                    "--source", str(repo_path),
                    "--report-format", "json",
                    "--no-git",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )

            duration_ms = int((time.time() - start) * 1000)

            output = {}
            if result.stdout:
                try:
                    output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    output = {"raw": result.stdout}

            artifacts = []
            if result.stdout:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".json",
                    delete=False,
                ) as f:
                    f.write(result.stdout)
                    artifacts.append(Path(f.name))

            return ScannerResult(
                scanner_name=self.name,
                success=result.returncode in (0, 1),
                raw_output=output,
                artifact_paths=artifacts,
                version=self.get_version(),
                duration_ms=duration_ms,
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
