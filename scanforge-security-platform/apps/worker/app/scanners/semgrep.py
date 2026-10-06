import json
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class SemgrepAdapter(ScannerAdapter):
    name = "semgrep"
    binary_name = "semgrep"
    binary_env_var = "SEMGREP_BINARY"
    report_filename = "semgrep-results.json"

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "scan",
            "--json",
            "--disable-version-check",
            "--metrics",
            "off",
            "--strict",
            "--jobs",
            "1",
            "--config",
            "/opt/scanner-rules/semgrep",
            "--json-output",
            "/workspace/output/semgrep-results.json",
            "/workspace/source",
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        return self._parse_report(
            completed,
            output_directory,
            lambda report: (
                isinstance(report, dict)
                and isinstance(report.get("results"), list)
                and report.get("errors") == []
                and all(
                    isinstance(item, dict)
                    and isinstance(item.get("check_id"), str)
                    and isinstance(item.get("path"), str)
                    and isinstance(item.get("extra"), dict)
                    for item in report["results"]
                )
            ),
        )

    def run(self, repo_path: Path) -> ScannerResult:
        import time

        start = time.time()

        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "scan",
                    "--json",
                    "--disable-version-check",
                    "--jobs",
                    "1",
                    "--config",
                    "auto",
                    "--json-output",
                    "semgrep-results.json",
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
            output_file = repo_path / "semgrep-results.json"

            if output_file.exists():
                with open(output_file) as f:
                    try:
                        output = json.load(f)
                    except json.JSONDecodeError:
                        output = {"raw": f.read()}

                artifacts.append(output_file)

            # Semgrep returns exit code 1 when findings are found
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
