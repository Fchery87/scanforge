import json
import re
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class SyftAdapter(ScannerAdapter):
    name = "syft"
    binary_name = "syft"
    binary_env_var = "SYFT_BINARY"
    report_filename = "syft-results.json"

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "scan",
            "dir:/workspace/source",
            "--quiet",
            "--base-path",
            "/workspace/source",
            "--output",
            "syft-json=/workspace/output/syft-results.json",
        )

    def runtime_timeout_seconds(self) -> int:
        return 300

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        return self._parse_report(
            completed,
            output_directory,
            lambda report: (
                isinstance(report, dict)
                and isinstance(report.get("artifacts"), list)
                and all(
                    isinstance(item, dict)
                    and isinstance(item.get("name"), str)
                    and isinstance(item.get("version"), str)
                    for item in report["artifacts"]
                )
            ),
        )

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
