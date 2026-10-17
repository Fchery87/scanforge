from __future__ import annotations

from typing import Any

from app.scanners.registry import SCANNER_REGISTRY
from app.security.secret_evidence import sanitize_gitleaks_output, sanitize_secret_finding
from app.services.scan_pipeline.context import ScanContext

_SEVERITY_RANK: dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}


def _reconcile_provider_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconcile findings sharing a canonical_fingerprint while preserving provider conflicts."""
    by_fingerprint: dict[str, dict[str, Any]] = {}
    ordered_fingerprints: list[str] = []

    for finding in findings:
        fp = finding.get("canonical_fingerprint")
        scanner = str(finding.get("primary_scanner") or "unknown")
        sev = str(finding.get("severity") or "medium").lower()
        fixed_ver = finding.get("fixed_version") or (finding.get("instance") or {}).get("fixed_version")
        fixed_str = str(fixed_ver).strip() if fixed_ver else None
        meta = dict(finding.get("metadata_json") or {})
        observation = {
            "scanner": scanner,
            "severity": sev,
            "raw_severity": meta.get("raw_severity", sev.upper()),
            "confidence_score": finding.get("confidence_score"),
            "fixed_version": fixed_str,
        }

        if not fp or fp not in by_fingerprint:
            cloned = dict(finding)
            cloned_meta = dict(meta)
            cloned_meta.setdefault("severity_source", scanner)
            if fixed_str:
                cloned_meta.setdefault("remediation_source", scanner)
            cloned_meta["provider_observations"] = [observation]
            cloned["metadata_json"] = cloned_meta
            if fp:
                by_fingerprint[fp] = cloned
                ordered_fingerprints.append(fp)
            else:
                ordered_fingerprints.append(f"__unfingerprinted_{len(ordered_fingerprints)}")
                by_fingerprint[ordered_fingerprints[-1]] = cloned
            continue

        existing = by_fingerprint[fp]
        existing_meta = dict(existing.get("metadata_json") or {})
        observations = list(existing_meta.get("provider_observations") or [])
        observations.append(observation)
        existing_meta["provider_observations"] = observations

        provider_severities = {
            obs["scanner"]: obs["severity"] for obs in observations if obs.get("scanner")
        }
        highest_obs = max(
            observations,
            key=lambda obs: _SEVERITY_RANK.get(str(obs.get("severity") or "info").lower(), 0),
        )
        existing["severity"] = highest_obs["severity"]
        existing_meta["severity_source"] = highest_obs["scanner"]
        if len(set(provider_severities.values())) > 1:
            existing_meta["severity_conflict"] = True
            existing_meta["provider_severities"] = provider_severities

        provider_fixed = {
            obs["scanner"]: obs["fixed_version"]
            for obs in observations
            if obs.get("scanner") and obs.get("fixed_version")
        }
        unique_fixed = set(provider_fixed.values())
        if len(unique_fixed) > 1:
            existing["fixed_version"] = None
            if isinstance(existing.get("instance"), dict):
                existing["instance"] = dict(existing["instance"])
                existing["instance"]["fixed_version"] = None
            existing_meta["remediation_conflict"] = True
            existing_meta["remediation_source"] = None
            existing_meta["provider_fixed_versions"] = provider_fixed
        elif len(unique_fixed) == 1:
            agreed_fixed = next(iter(unique_fixed))
            existing["fixed_version"] = agreed_fixed
            if isinstance(existing.get("instance"), dict):
                existing["instance"] = dict(existing["instance"])
                existing["instance"]["fixed_version"] = agreed_fixed
            existing_meta["remediation_source"] = next(iter(provider_fixed.keys()))
            existing_meta["provider_fixed_versions"] = provider_fixed

        existing_refs = list(existing.get("references") or [])
        seen_refs = {
            (r.get("type"), r.get("value"), r.get("url"))
            for r in existing_refs
            if isinstance(r, dict)
        }
        for ref in finding.get("references") or []:
            if isinstance(ref, dict):
                key = (ref.get("type"), ref.get("value"), ref.get("url"))
                if key not in seen_refs:
                    existing_refs.append(ref)
                    seen_refs.add(key)
        existing["references"] = existing_refs
        existing["metadata_json"] = existing_meta

    return [by_fingerprint[fp] for fp in ordered_fingerprints]


class NormalizationStage:
    def normalize_results(self, context: ScanContext) -> list[dict]:
        all_findings: list[dict] = []
        for scanner_name, result in context.scanner_results.items():
            if not result.success:
                continue
            registration = SCANNER_REGISTRY.get(scanner_name)
            if registration:
                normalized = [
                    sanitize_secret_finding(finding)
                    for finding in registration.normalize(result.raw_output, context.repository_id)
                ]
                all_findings.extend(normalized)
            if scanner_name == "gitleaks":
                result.raw_output = sanitize_gitleaks_output(result.raw_output)
        return _reconcile_provider_findings(all_findings)

    def filter_to_changed_files(self, findings: list[dict], changed_files: list[str]) -> list[dict]:
        if not changed_files:
            return findings
        changed = {path.strip("./") for path in changed_files}
        return [
            f
            for f in findings
            if not (instance_path := (f.get("instance") or {}).get("path", "").strip("./"))
            or instance_path in changed
        ]
