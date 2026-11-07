"""#42 / P1.7: a dependency finding earns absence credit only from Syft inventory evidence.

An advisory vanishing while the package version is still installed is an intelligence
change, not remediation. Inventory must come from the same scan as the absence.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from test_findings_disappearance_scope import (  # noqa: F401
    MAIN,
    TRIVY_V1,
    _absence,
    _events,
    _seed_repo,
    _seed_scan,
    db_session,
)

from app.db.enums import ScanStatus
from app.db.models import Finding, ScannerRun
from app.services.findings import FindingService

SYFT_V1 = {"scanner_version": "1.4.1", "parser_version": "2026-10-parser.v1", "rules_digest": None}
RUNS = (("trivy", "completed", TRIVY_V1), ("syft", "completed", SYFT_V1))
HEALTH = {
    "scanner_health": {
        "expected": ["trivy", "syft"],
        "completed": ["trivy", "syft"],
        "failed": [],
        "missing": [],
        "complete": True,
    }
}
FP = "fp-dep"


def _inventory(*packages, complete=True):
    return {
        "inventory": {
            "complete": complete,
            "packages": [{"name": n, "version": v, "path": p} for n, v, p in packages],
        }
    }


async def _observe_dependency(session, repo_id, project_id, *, name="lodash", version="4.17.20"):
    """Positive evidence: a scan where Trivy reported the vulnerable package."""
    service = FindingService(session)
    scan = await _seed_scan(session, repo_id, project_id, commit="0" * 40)
    for scanner, status, signature in RUNS:
        session.add(ScannerRun(scan_id=str(scan.id), scanner_name=scanner, status=ScanStatus(status), **signature))
        await session.flush()
    candidate = {
        "category": "vulnerability",
        "severity": "high",
        "title": "t",
        "canonical_fingerprint": FP,
        "fingerprint_version": "fp.v3",
        "primary_scanner": "trivy",
        "confidence_score": 0.9,
    }
    if name:
        candidate["package_name"] = name
        candidate["instance"] = {"package_name": name, "installed_version": version, "path": "package-lock.json"}
    await service.upsert_from_scan(
        scan_id=str(scan.id), repository_id=repo_id, project_id=project_id, normalized_findings=[candidate]
    )
    return service


async def _absence_with_inventory(service, repo_id, project_id, metadata, *, syft_status="completed", commit="a" * 40):
    """Absence scan whose Syft run carries `metadata` (None leaves the run without inventory)."""
    session = service.db
    scan = await _seed_scan(session, repo_id, project_id, commit=commit)
    session.add(ScannerRun(scan_id=str(scan.id), scanner_name="trivy", status=ScanStatus.COMPLETED, **TRIVY_V1))
    await session.flush()
    session.add(
        ScannerRun(
            scan_id=str(scan.id),
            scanner_name="syft",
            status=ScanStatus(syft_status),
            metadata_json=metadata,
            **SYFT_V1,
        )
    )
    await session.flush()
    health = HEALTH
    if syft_status != "completed":
        health = {"scanner_health": {**HEALTH["scanner_health"], "completed": ["trivy"], "failed": ["syft"]}}
    return await service.mark_not_observed_after_scan(
        repository_id=repo_id, scan_id=str(scan.id), seen_fingerprints=set(), scan_summary=health
    )


async def _setup(db_session, **kwargs):
    repo_id, project_id, _ = await _seed_repo(db_session)
    service = await _observe_dependency(db_session, repo_id, project_id, **kwargs)
    return repo_id, project_id, service


async def _finding(db_session):
    return (await db_session.execute(select(Finding).where(Finding.canonical_fingerprint == FP))).scalar_one()


@pytest.mark.asyncio
async def test_withdrawn_advisory_with_package_still_installed_is_not_credited(db_session):
    repo_id, project_id, service = await _setup(db_session)

    updated = await _absence_with_inventory(
        service, repo_id, project_id, _inventory(("lodash", "4.17.20", "package-lock.json"))
    )

    finding = await _finding(db_session)
    assert updated == 0
    assert finding.status == "open"
    assert finding.metadata_json["absence_series"][MAIN]["qualifying_absences"] == []
    not_credited = [e for e in await _events(db_session, finding) if e.event_type == "absence_not_credited"]
    assert [e.metadata_json["blocked_by"] for e in not_credited] == [["package_still_installed"]]
    assert not_credited[0].metadata_json["packages"] == [
        {"name": "lodash", "version": "4.17.20", "path": "package-lock.json"}
    ]


@pytest.mark.asyncio
async def test_upgraded_package_earns_absence_credit(db_session):
    repo_id, project_id, service = await _setup(db_session)

    updated = await _absence_with_inventory(
        service, repo_id, project_id, _inventory(("lodash", "4.17.21", "package-lock.json"))
    )

    assert updated == 1
    assert (await _finding(db_session)).status == "not_observed"


@pytest.mark.asyncio
async def test_removed_package_earns_absence_credit(db_session):
    repo_id, project_id, service = await _setup(db_session)

    updated = await _absence_with_inventory(
        service, repo_id, project_id, _inventory(("express", "4.19.2", "package-lock.json"))
    )

    assert updated == 1
    assert (await _finding(db_session)).status == "not_observed"


@pytest.mark.asyncio
async def test_package_name_matching_ignores_case_and_separators(db_session):
    repo_id, project_id, service = await _setup(db_session, name="Typing_Extensions", version="4.0.0")

    updated = await _absence_with_inventory(
        service, repo_id, project_id, _inventory(("typing-extensions", "4.0.0", "requirements.txt"))
    )

    assert updated == 0


@pytest.mark.asyncio
async def test_maven_coordinate_matches_inventory_artifact_name(db_session):
    repo_id, project_id, service = await _setup(db_session, name="org.apache:log4j-core", version="2.14.0")

    updated = await _absence_with_inventory(
        service, repo_id, project_id, _inventory(("log4j-core", "2.14.0", "pom.xml"))
    )

    assert updated == 0


@pytest.mark.asyncio
async def test_failed_inventory_grants_no_dependency_absence_credit(db_session):
    repo_id, project_id, service = await _setup(db_session)

    updated = await _absence_with_inventory(service, repo_id, project_id, _inventory(), syft_status="failed")

    assert updated == 0
    assert (await _finding(db_session)).status == "open"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [None, {}, {"inventory": "oops"}, _inventory(complete=False), {"inventory": {"complete": True}}],
)
async def test_missing_or_incomplete_inventory_grants_no_credit_and_is_explained(db_session, metadata):
    repo_id, project_id, service = await _setup(db_session)

    updated = await _absence_with_inventory(service, repo_id, project_id, metadata)

    finding = await _finding(db_session)
    assert updated == 0
    assert finding.status == "open"
    events = [e for e in await _events(db_session, finding) if e.event_type == "absence_not_credited"]
    assert [e.metadata_json["blocked_by"] for e in events] == [["inventory_unavailable"]]


@pytest.mark.asyncio
async def test_scan_without_a_syft_run_grants_no_dependency_credit(db_session):
    repo_id, project_id, service = await _setup(db_session)
    health = {"scanner_health": {**HEALTH["scanner_health"], "expected": ["trivy"], "completed": ["trivy"]}}

    updated = await _absence(
        service,
        repo_id,
        project_id,
        commit="a" * 40,
        summary=health,
        run_statuses=(("trivy", "completed", TRIVY_V1),),
        inventory=False,
    )

    assert updated == 0
    assert (await _finding(db_session)).status == "open"


@pytest.mark.asyncio
async def test_inventory_from_an_earlier_scan_is_never_used(db_session):
    repo_id, project_id, service = await _setup(db_session)
    # An earlier scan's inventory showed the package gone (it credits and counts one absence)...
    assert (
        await _absence_with_inventory(service, repo_id, project_id, _inventory(("express", "4", "p")), commit="b" * 40)
        == 1
    )

    # ...but the next scan carries no inventory of its own, so it cannot borrow that one.
    updated = await _absence_with_inventory(service, repo_id, project_id, None, commit="c" * 40)

    assert updated == 0
    assert (await _finding(db_session)).status == "not_observed"


@pytest.mark.asyncio
async def test_dependency_finding_without_package_identity_gets_no_credit(db_session):
    repo_id, project_id, service = await _setup(db_session, name=None)

    updated = await _absence_with_inventory(service, repo_id, project_id, _inventory())

    assert updated == 0
    assert (await _finding(db_session)).status == "open"
