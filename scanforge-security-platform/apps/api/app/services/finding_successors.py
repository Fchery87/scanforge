"""Link fp.v2 findings to their exact fp.v3 successors (ADR-014, P1.5).

A link is evidence of lineage only. It never changes status, severity or any
human disposition on either finding, and it is derived solely from stored
evidence inside one repository (the tenant boundary). Matches must be exact:

* source, secret and IaC findings: same scanner, rule and path, and an
  observation at the same recorded location. fp.v2 identity never recorded a
  snippet digest, so recorded location stands in for it on the legacy side.
* dependency findings: same scanner, ecosystem, package, installed version and
  advisory.

A finding with more than one candidate on either side stays unlinked.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models import Finding, FindingEvent, FindingInstance, FindingReference
from app.schemas.canonical_findings import CURRENT_FINGERPRINT_VERSION

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

SUCCESSOR_FINGERPRINT_VERSION = "fp.v3"
PREDECESSOR_KEY = "predecessor_finding_id"
SUCCESSOR_KEY = "successor_finding_id"


def _lower(value) -> str:
    return str(value or "").strip().lower()


def _identity_keys(finding, instances, advisories) -> set[tuple]:
    """Exact-match keys for one finding; an empty set means nothing can match."""
    scanner = finding.primary_scanner
    if not scanner:
        return set()
    keys: set[tuple] = set()
    metadata = finding.metadata_json or {}
    rule = _lower(metadata.get("check_id") or metadata.get("rule_id"))
    for inst in instances:
        evidence = inst.evidence_json or {}
        if inst.package_name and inst.installed_version:
            ecosystem = _lower(
                evidence.get("type")
                or evidence.get("package_type")
                or evidence.get("ecosystem")
                or finding.package_ecosystem
            )
            if not ecosystem:
                continue
            for advisory in advisories:
                keys.add(
                    ("dep", scanner, ecosystem, _lower(inst.package_name), inst.installed_version, advisory)
                )
        elif rule and inst.path and inst.line_start is not None:
            keys.add(("src", scanner, rule, inst.path, inst.line_start, inst.line_end))
    return keys


async def link_fp_successors(db: AsyncSession, *, repository_id: str) -> dict[str, int]:
    """Link exact fp.v2 -> fp.v3 pairs in one repository. Repeatable.

    Returns ``newly_linked`` (links written by this call), ``linked`` (fp.v3
    findings with a predecessor afterwards), ``unlinked`` (fp.v3 findings
    without one) and ``preserved`` (fp.v2 findings kept untouched in state).
    """
    findings = (
        (await db.execute(select(Finding).where(Finding.repository_id == repository_id))).scalars().all()
    )
    legacy = [f for f in findings if f.fingerprint_version == CURRENT_FINGERPRINT_VERSION]
    current = [f for f in findings if f.fingerprint_version == SUCCESSOR_FINGERPRINT_VERSION]
    result = {"newly_linked": 0, "linked": 0, "unlinked": 0, "preserved": len(legacy)}
    if not current:
        return result

    ids = [f.id for f in findings]
    instances: dict[str, list] = defaultdict(list)
    for inst in (
        (await db.execute(select(FindingInstance).where(FindingInstance.finding_id.in_(ids)))).scalars().all()
    ):
        instances[inst.finding_id].append(inst)
    advisories: dict[str, set[str]] = defaultdict(set)
    for ref in (
        (
            await db.execute(
                select(FindingReference).where(
                    FindingReference.finding_id.in_(ids), FindingReference.reference_type == "advisory"
                )
            )
        )
        .scalars()
        .all()
    ):
        advisories[ref.finding_id].add(ref.reference_value)

    def keys(finding):
        return _identity_keys(finding, instances[finding.id], advisories[finding.id])

    legacy_keys = {f.id: keys(f) for f in legacy if SUCCESSOR_KEY not in (f.metadata_json or {})}
    candidates: dict[str, list[Finding]] = {}
    reverse: dict[str, list[Finding]] = defaultdict(list)
    for new in current:
        if PREDECESSOR_KEY in (new.metadata_json or {}):
            continue
        new_keys = keys(new)
        matches = [f for f in legacy if f.id in legacy_keys and legacy_keys[f.id] & new_keys]
        candidates[new.id] = matches
        for old in matches:
            reverse[old.id].append(new)

    for new in current:
        matches = candidates.get(new.id, [])
        if len(matches) != 1 or len(reverse[matches[0].id]) != 1:
            continue
        old = matches[0]
        basis = "dependency_exact" if any(k[0] == "dep" for k in keys(new)) else "rule_path_location"
        new.metadata_json = {**(new.metadata_json or {}), PREDECESSOR_KEY: str(old.id)}
        old.metadata_json = {**(old.metadata_json or {}), SUCCESSOR_KEY: str(new.id)}
        for finding, event_type, other in (
            (new, "predecessor_linked", old),
            (old, "successor_linked", new),
        ):
            db.add(
                FindingEvent(
                    finding_id=finding.id,
                    event_type=event_type,
                    actor_user_id=None,
                    metadata_json={
                        "linked_finding_id": str(other.id),
                        "linked_fingerprint_version": other.fingerprint_version,
                        "match_basis": basis,
                        "dispositions_transferred": False,
                    },
                )
            )
            await db.flush()  # one event row per flush, as elsewhere in the lifecycle code
        result["newly_linked"] += 1

    await db.flush()
    result["linked"] = sum(1 for f in current if PREDECESSOR_KEY in (f.metadata_json or {}))
    result["unlinked"] = len(current) - result["linked"]
    return result
