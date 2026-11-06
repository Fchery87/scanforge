"""#40 / P1.5: exact fp.v2 -> fp.v3 successor links without disposition transfer."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from test_findings_disappearance_scope import (  # noqa: F401
    OK_RUNS,
    _add_runs,
    _events,
    _reload,
    _seed_finding,
    _seed_repo,
    _seed_scan,
    db_session,
)

from app.db.models import Finding, FindingInstance, FindingReference, Repository
from app.services.finding_successors import link_fp_successors
from app.services.findings import FindingService

RULE = "python.lang.security.eval"


async def _legacy(
    session,
    repo_id,
    project_id,
    fp,
    *,
    scanner="semgrep",
    rule=RULE,
    path="app/a.py",
    lines=(10, 12),
    status="open",
    package=None,
    advisory=None,
    ecosystem=None,
):
    finding = await _seed_finding(
        session,
        repo_id,
        project_id,
        fp,
        status=status,
        scanner=scanner,
        fingerprint_version="fp.v2",
    )
    finding.metadata_json = {"check_id": rule}
    scan = await _seed_scan(session, repo_id, project_id, commit="1" * 40)
    evidence = {"path": path}
    if ecosystem:
        evidence["type"] = ecosystem
    session.add(
        FindingInstance(
            finding_id=finding.id,
            scan_id=scan.id,
            occurrence_fingerprint=f"o-{fp}",
            path=path,
            line_start=lines[0],
            line_end=lines[1],
            package_name=package,
            installed_version="1.0.0" if package else None,
            evidence_json=evidence,
        )
    )
    if advisory:
        session.add(FindingReference(finding_id=finding.id, reference_type="advisory", reference_value=advisory))
    await session.commit()
    return finding


def _source(fp, *, rule=RULE, path="app/a.py", lines=(10, 12)):
    return {
        "category": "vulnerability",
        "severity": "high",
        "title": rule,
        "canonical_fingerprint": fp,
        "fingerprint_version": "fp.v3",
        "primary_scanner": "semgrep",
        "metadata_json": {"check_id": rule},
        "instance": {"path": path, "line_start": lines[0], "line_end": lines[1], "check_id": rule},
    }


def _dep(fp, *, package="lodash", ecosystem="npm", advisory="CVE-1"):
    return {
        "category": "vulnerability",
        "severity": "high",
        "title": "dep",
        "canonical_fingerprint": fp,
        "fingerprint_version": "fp.v3",
        "primary_scanner": "trivy",
        "advisory_id": advisory,
        "package_name": package,
        "instance": {
            "package_name": package,
            "installed_version": "1.0.0",
            "type": ecosystem,
            "path": "package-lock.json",
        },
        "references": [{"type": "advisory", "value": advisory}],
    }


async def _ingest(session, repo_id, project_id, candidates):
    scan = await _seed_scan(session, repo_id, project_id, commit="2" * 40)
    await _add_runs(session, scan.id, OK_RUNS)
    await FindingService(session).upsert_from_scan(
        scan_id=str(scan.id), repository_id=repo_id, project_id=project_id, normalized_findings=candidates
    )


async def _by_fp(session, fp):
    return (await session.execute(select(Finding).where(Finding.canonical_fingerprint == fp))).scalar_one()


def _meta(finding):
    return finding.metadata_json or {}


@pytest.mark.asyncio
async def test_exact_source_match_is_linked_both_ways_without_disposition_transfer(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    old = await _legacy(db_session, repo_id, project_id, "v2-a", status="accepted_risk")

    await _ingest(db_session, repo_id, project_id, [_source("v3-a")])

    new = await _by_fp(db_session, "v3-a")
    old = await _reload(db_session, old)
    assert _meta(new)["predecessor_finding_id"] == str(old.id)
    assert _meta(old)["successor_finding_id"] == str(new.id)
    assert new.status == "open"  # accepted risk never transfers
    assert old.status == "accepted_risk"
    assert "predecessor_linked" in [e.event_type for e in await _events(db_session, new)]
    assert "successor_linked" in [e.event_type for e in await _events(db_session, old)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidate",
    [
        _source("v3-b", rule="other.rule"),
        _source("v3-b", path="app/other.py"),
        _source("v3-b", lines=(40, 41)),
    ],
)
async def test_non_exact_source_match_is_not_linked(db_session, candidate):
    repo_id, project_id, _ = await _seed_repo(db_session)
    old = await _legacy(db_session, repo_id, project_id, "v2-b")

    await _ingest(db_session, repo_id, project_id, [candidate])

    assert "predecessor_finding_id" not in _meta(await _by_fp(db_session, "v3-b"))
    assert "successor_finding_id" not in _meta(await _reload(db_session, old))


@pytest.mark.asyncio
async def test_dependency_links_only_on_same_ecosystem_package_version_advisory(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    old = await _legacy(
        db_session,
        repo_id,
        project_id,
        "v2-d",
        scanner="trivy",
        package="lodash",
        advisory="CVE-1",
        ecosystem="npm",
    )

    await _ingest(
        db_session,
        repo_id,
        project_id,
        [_dep("v3-pypi", ecosystem="pip"), _dep("v3-other-adv", advisory="CVE-2"), _dep("v3-ok")],
    )

    assert "predecessor_finding_id" not in _meta(await _by_fp(db_session, "v3-pypi"))
    assert "predecessor_finding_id" not in _meta(await _by_fp(db_session, "v3-other-adv"))
    old = await _reload(db_session, old)
    assert _meta(await _by_fp(db_session, "v3-ok"))["predecessor_finding_id"] == str(old.id)


@pytest.mark.asyncio
async def test_ambiguous_matches_are_not_linked(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    await _legacy(db_session, repo_id, project_id, "v2-x")

    await _ingest(db_session, repo_id, project_id, [_source("v3-x1"), _source("v3-x2")])

    for fp in ("v3-x1", "v3-x2"):
        assert "predecessor_finding_id" not in _meta(await _by_fp(db_session, fp))


@pytest.mark.asyncio
async def test_links_are_tenant_scoped(db_session):
    repo_a, project_a, _ = await _seed_repo(db_session)
    repo_b = str(uuid4())
    db_session.add(
        Repository(
            id=repo_b, project_id=project_a, provider="github", owner_name="o", repo_name="r2", full_name="o/r2"
        )
    )
    await db_session.commit()
    project_b = project_a
    await _legacy(db_session, repo_a, project_a, "v2-t")

    await _ingest(db_session, repo_b, project_b, [_source("v3-t")])

    assert "predecessor_finding_id" not in _meta(await _by_fp(db_session, "v3-t"))


@pytest.mark.asyncio
async def test_migration_is_repeatable_and_reports_counts(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    await _legacy(db_session, repo_id, project_id, "v2-m1")
    await _legacy(db_session, repo_id, project_id, "v2-m2", path="app/b.py", lines=(1, 2))
    await _seed_finding(db_session, repo_id, project_id, "v3-lone", fingerprint_version="fp.v3", scanner="semgrep")
    # Rows that predate link-at-ingest: ingest without the linker by seeding directly.
    new = await _seed_finding(db_session, repo_id, project_id, "v3-m1", fingerprint_version="fp.v3", scanner="semgrep")
    new.metadata_json = {"check_id": RULE}
    scan = await _seed_scan(db_session, repo_id, project_id, commit="3" * 40)
    db_session.add(
        FindingInstance(
            finding_id=new.id,
            scan_id=scan.id,
            occurrence_fingerprint="o-v3-m1",
            path="app/a.py",
            line_start=10,
            line_end=12,
            evidence_json={"path": "app/a.py"},
        )
    )
    await db_session.commit()

    first = await link_fp_successors(db_session, repository_id=repo_id)
    second = await link_fp_successors(db_session, repository_id=repo_id)

    assert first == {"newly_linked": 1, "linked": 1, "unlinked": 1, "preserved": 2}
    assert second == {"newly_linked": 0, "linked": 1, "unlinked": 1, "preserved": 2}
    events = [
        e for e in await _events(db_session, await _by_fp(db_session, "v3-m1")) if e.event_type == "predecessor_linked"
    ]
    assert len(events) == 1
