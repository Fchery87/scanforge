from __future__ import annotations

from app.scanners.registry import SCANNER_REGISTRY
from app.security.secret_evidence import sanitize_secret_finding
from app.services.scan_pipeline.context import ScanContext


class NormalizationStage:
    def normalize_results(self, context: ScanContext) -> list[dict]:
        all_findings: list[dict] = []
        for scanner_name, result in context.scanner_results.items():
            if not result.success:
                continue
            registration = SCANNER_REGISTRY.get(scanner_name)
            if registration:
                all_findings.extend(
                    sanitize_secret_finding(finding)
                    for finding in registration.normalize(result.raw_output, context.repository_id)
                )
        return all_findings

    def filter_to_changed_files(self, findings: list[dict], changed_files: list[str]) -> list[dict]:
        if not changed_files:
            return findings
        changed = {path.strip("./") for path in changed_files}
        return [
            f for f in findings
            if not (instance_path := (f.get("instance") or {}).get("path", "").strip("./"))
            or instance_path in changed
        ]
