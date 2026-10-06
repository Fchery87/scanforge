import json
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class CheckovAdapter(ScannerAdapter):
    name = "checkov"
    binary_name = "checkov"
    binary_env_var = "CHECKOV_BINARY"
    report_filename = "checkov-results.json"
    report_from_stdout = True
    accepted_exit_codes = frozenset({0, 1})

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "--directory",
            "/workspace/source",
            "--quiet",
            "--skip-download",
            "--download-external-modules",
            "false",
            "--skip-framework",
            "secrets",
            "--output",
            "json",
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        def valid_report(report):
            reports = report if isinstance(report, list) else [report]
            return bool(reports) and all(
                isinstance(item, dict)
                and isinstance(item.get("results"), dict)
                and isinstance(item["results"].get("failed_checks"), list)
                and not item["results"].get("parsing_errors")
                and all(
                    isinstance(check, dict) and isinstance(check.get("check_id"), str)
                    for check in item["results"]["failed_checks"]
                )
                for item in reports
            )

        return self._parse_report(completed, output_directory, valid_report)

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
