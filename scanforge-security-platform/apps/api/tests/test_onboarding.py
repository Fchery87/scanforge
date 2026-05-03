from app.services.onboarding import build_onboarding_checklist


def test_onboarding_schedule_step_reflects_schedule_domain_fact():
    checklist = build_onboarding_checklist(
        user_id="user-1",
        org_id="org-1",
        has_github=True,
        has_projects=True,
        has_repositories=True,
        has_scans=True,
        has_findings=True,
        has_schedules=True,
    )

    setup_schedule = next(step for step in checklist.steps if step.id == "setup_schedule")
    assert setup_schedule.completed is True


def test_onboarding_schedule_step_is_incomplete_without_schedule():
    checklist = build_onboarding_checklist(
        user_id="user-1",
        org_id="org-1",
        has_github=True,
        has_projects=True,
        has_repositories=True,
        has_scans=True,
        has_findings=True,
        has_schedules=False,
    )

    setup_schedule = next(step for step in checklist.steps if step.id == "setup_schedule")
    assert setup_schedule.completed is False
