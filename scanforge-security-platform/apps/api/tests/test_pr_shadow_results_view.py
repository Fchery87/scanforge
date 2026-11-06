"""#50 / P2.3: internal shadow results view with reviewer labels.

Seam: the scan-scoped route functions (shadow review view and candidate labelling) over a
real database session, fed by real evidence ingress (ScanCompletionService). Labels are
evaluation data: they must never change findings, candidate state or remediation evidence,
and nothing here publishes to GitHub. Real PostgreSQL was NOT run.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from test_pr_shadow_classification import (  # noqa: F401
    _baseline_scans,
    _complete,
    _finding,
    _head,
    _runs,
    _uniform_sqlite_uuid_columns,
)
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.api.v1.routes import scans as scan_routes
from app.db.enums import MemberRole
from app.db.models import (
    AuditLog,
    Finding,
    Organization,
    OrganizationMember,
    ShadowReviewCandidate,
    ShadowReviewCandidateLabel,
    User,
)
from app.schemas.scans import ShadowCandidateLabelRequest
from app.services.pr_candidates import ShadowCandidateService


async def _member(db, org, role):
    user = User(
        id=str(uuid4()),
        email=f"m-{uuid4().hex[:6]}@example.com",
        name="M",
        auth_provider_user_id=f"user_{uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=role))
    await db.commit()
    return user


def _ctx(user):
    return SimpleNamespace(user_id=UUID(str(user.id)))


async def _view(db, org, project, scan, user):
    return await scan_routes.get_shadow_review(
        UUID(str(org.id)), UUID(str(project.id)), UUID(str(scan.id)), current_user=_ctx(user), db=db
    )


async def _label(db, org, project, scan, candidate, user, label):
    return await scan_routes.label_shadow_candidate(
        UUID(str(org.id)),
        UUID(str(project.id)),
        UUID(str(scan.id)),
        UUID(str(candidate.id)),
        ShadowCandidateLabelRequest(label=label),
        current_user=_ctx(user),
        db=db,
    )


async def _owner_org(db_session):
    org, project, repo, owner = await _seed_org_project_repo(db_session)
    db_session.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role=MemberRole.OWNER))
    await db_session.commit()
    return org, project, repo, owner


async def _setup(db_session, *, head_findings=("fp-a", "fp-b"), baseline_findings=("fp-a",)):
    org, project, repo, owner = await _owner_org(db_session)
    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding(f) for f in head_findings])
    (baseline,) = await _baseline_scans(db_session, repo)
    await _complete(db_session, baseline, findings=[_finding(f) for f in baseline_findings])
    return org, project, repo, owner, head


@pytest.mark.asyncio
async def test_view_renders_revisions_coverage_classified_results_and_cost_honestly(db_session):
    org, project, repo, owner, head = await _setup(db_session)

    view = await _view(db_session, org, project, head, owner)

    assert view.state == "ready"
    assert view.revisions.head_sha == head.commit_sha
    assert view.revisions.base_sha == head.base_sha
    assert view.revisions.merge_base_sha == head.merge_base_sha
    assert view.revisions.pull_request_number == 17
    assert {c.capability for c in view.capability_coverage} == {"secrets", "sast", "dependencies", "iac"}
    by_fp = {r.fingerprint: r for r in view.results}
    assert by_fp["fp-a"].classification == "existing"
    assert by_fp["fp-b"].classification == "new"
    assert by_fp["fp-b"].candidate_id is not None
    assert by_fp["fp-b"].candidate_state == "active"
    assert view.classification_counts.new == 1
    # Cost is not measured anywhere: it must say so rather than invent a number.
    assert view.cost_estimate.state == "unavailable"
    assert view.duration.state in {"measured", "partial", "unavailable"}


@pytest.mark.asyncio
async def test_view_states_are_distinct_for_pending_empty_and_partial(db_session):
    org, project, repo, owner = await _owner_org(db_session)

    pending = await _head(db_session, repo)
    assert (await _view(db_session, org, project, pending, owner)).state == "pending"

    # Complete head with no results: "empty" is a distinct state, never styled or worded clean.
    await _complete(db_session, pending)
    empty = await _view(db_session, org, project, pending, owner)
    assert empty.state in {"empty", "partial"}
    assert empty.results == []

    # A coverage gap makes the view partial, with the gap listed as a limitation.
    other = await _head(db_session, repo, number=18, head_sha="c" * 40)
    await _complete(
        db_session,
        other,
        runs=_runs(coverage={"semgrep": {"declared_scope": "workspace", "inputs_found": 3, "inputs_supported": 1}}),
    )
    partial = await _view(db_session, org, project, other, owner)
    assert partial.state == "partial"
    assert any("sast" in item for item in partial.limitations)


@pytest.mark.asyncio
async def test_unknown_results_are_reported_unknown_with_limitation_not_clean(db_session):
    org, project, repo, owner = await _owner_org(db_session)
    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding("fp-x")])  # baseline never completes

    view = await _view(db_session, org, project, head, owner)

    assert view.results[0].classification == "unknown"
    assert view.state == "partial"
    assert view.limitations  # explains why results are unknown


@pytest.mark.asyncio
async def test_view_is_tenant_and_pr_scoped(db_session):
    org, project, repo, owner, head = await _setup(db_session)
    outsider = await _member(db_session, org, MemberRole.OWNER)
    # Move the outsider to a different organization: membership elsewhere grants nothing here.
    other_org = Organization(id=str(uuid4()), name="Other", slug=f"o-{uuid4().hex[:6]}", created_by_user_id=outsider.id)
    db_session.add(other_org)
    await db_session.flush()
    member = (
        await db_session.execute(select(OrganizationMember).where(OrganizationMember.user_id == outsider.id))
    ).scalar_one()
    await db_session.delete(member)
    db_session.add(OrganizationMember(organization_id=other_org.id, user_id=outsider.id, role=MemberRole.OWNER))
    await db_session.commit()

    with pytest.raises(HTTPException) as denied:
        await _view(db_session, org, project, head, outsider)
    assert denied.value.status_code == 404

    viewer = await _member(db_session, org, MemberRole.VIEWER)
    assert (await _view(db_session, org, project, head, viewer)).state == "ready"  # read roles may view

    with pytest.raises(HTTPException) as missing:
        await _view(db_session, org, project, SimpleNamespace(id=uuid4()), owner)
    assert missing.value.status_code == 404


@pytest.mark.asyncio
async def test_label_persists_with_actor_timestamp_and_audit_and_is_updatable(db_session):
    org, project, repo, owner, head = await _setup(db_session)
    reviewer = await _member(db_session, org, MemberRole.SECURITY_REVIEWER)
    view = await _view(db_session, org, project, head, owner)
    cid = next(r.candidate_id for r in view.results if r.fingerprint == "fp-b")
    candidate = await db_session.get(ShadowReviewCandidate, str(cid))

    await _label(db_session, org, project, head, candidate, reviewer, "useful")
    await _label(db_session, org, project, head, candidate, reviewer, "duplicate")

    rows = (await db_session.execute(select(ShadowReviewCandidateLabel))).scalars().all()
    assert len(rows) == 1  # one current label per reviewer per candidate
    assert rows[0].label == "duplicate"
    assert str(rows[0].actor_user_id) == str(reviewer.id)
    assert str(rows[0].organization_id) == str(org.id)
    assert rows[0].updated_at is not None
    audits = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "shadow_candidate.labeled")))
        .scalars()
        .all()
    )
    assert sorted(a.metadata_json["label"] for a in audits) == ["duplicate", "useful"]

    refreshed = await _view(db_session, org, project, head, owner)
    labels = next(r for r in refreshed.results if r.fingerprint == "fp-b").labels
    assert [(item.label, str(item.actor_user_id)) for item in labels] == [("duplicate", str(reviewer.id))]


@pytest.mark.asyncio
async def test_labels_never_change_findings_candidate_state_or_remediation_evidence(db_session):
    org, project, repo, owner, head = await _setup(db_session)
    reviewer = await _member(db_session, org, MemberRole.SECURITY_REVIEWER)
    candidates = (await db_session.execute(select(ShadowReviewCandidate))).scalars().all()
    before = {c.id: (c.state, c.resolution_basis, c.head_sha) for c in candidates}
    findings_before = (await db_session.execute(select(func.count()).select_from(Finding))).scalar_one()

    for candidate in candidates:
        for label in ("not_useful", "incorrect", "missing_context"):
            await _label(db_session, org, project, head, candidate, reviewer, label)

    after = {
        c.id: (c.state, c.resolution_basis, c.head_sha)
        for c in (await db_session.execute(select(ShadowReviewCandidate))).scalars()
    }
    assert after == before
    assert (await db_session.execute(select(func.count()).select_from(Finding))).scalar_one() == findings_before
    assert await ShadowCandidateService(db_session).remediation_evidence(repo.id, 17) == []


@pytest.mark.asyncio
async def test_label_requires_reviewer_role_valid_label_and_a_candidate_of_this_pr(db_session):
    org, project, repo, owner, head = await _setup(db_session)
    developer = await _member(db_session, org, MemberRole.DEVELOPER)
    viewer = await _member(db_session, org, MemberRole.VIEWER)
    candidate = (await db_session.execute(select(ShadowReviewCandidate))).scalars().first()

    for user in (developer, viewer):
        with pytest.raises(HTTPException) as denied:
            await _label(db_session, org, project, head, candidate, user, "useful")
        assert denied.value.status_code == 403

    with pytest.raises(ValueError):
        ShadowCandidateLabelRequest(label="suppress")

    # A candidate from a different PR is not addressable through this scan.
    other = await _head(db_session, repo, number=99, head_sha="e" * 40)
    await _complete(db_session, other, findings=[_finding("fp-other")])
    foreign = (
        await db_session.execute(select(ShadowReviewCandidate).where(ShadowReviewCandidate.fingerprint == "fp-other"))
    ).scalar_one()
    with pytest.raises(HTTPException) as missing:
        await _label(db_session, org, project, head, foreign, owner, "useful")
    assert missing.value.status_code == 404
    assert (await db_session.execute(select(func.count()).select_from(ShadowReviewCandidateLabel))).scalar_one() == 0
