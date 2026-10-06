import json
import re
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class TrivyAdapter(ScannerAdapter):
    name = "trivy"
    binary_name = "trivy"
    binary_env_var = "TRIVY_BINARY"
    report_filename = "trivy-results.json"

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

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "fs",
            "--no-progress",
            "--skip-version-check",
            "--skip-db-update",
            "--skip-java-db-update",
            "--skip-check-update",
            "--offline-scan",
            "--cache-backend",
            "memory",
            "--format",
            "json",
            "--output",
            "/workspace/output/trivy-results.json",
            "--scanners",
            "vuln,secret,misconfig",
            "/workspace/source",
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        return self._parse_report(
            completed,
            output_directory,
            lambda report: (
                isinstance(report, dict)
                and (
                    isinstance(report.get("Results"), list)
                    or (
                        "Results" not in report
                        and report.get("SchemaVersion") == 2
                        and report.get("ArtifactType") == "filesystem"
                        and report.get("ArtifactName") == "/workspace/source"
                    )
                )
                and all(
                    isinstance(result, dict)
                    and all(
                        isinstance(result[key], list) and all(isinstance(item, dict) for item in result[key])
                        for key in ("Vulnerabilities", "Secrets", "Misconfigurations")
                        if key in result
                    )
                    for result in report.get("Results", [])
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
                    "fs",
                    "--no-progress",
                    "--skip-version-check",
                    "--format",
                    "json",
                    "--output",
                    "trivy-results.json",
                    "--scanners",
                    "vuln,secret,misconfig",
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
