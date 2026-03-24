from dataclasses import dataclass


@dataclass
class OnboardingChecklist:
    user_id: str
    organization_id: str | None
    steps: list["OnboardingStep"]

    def completion_percentage(self) -> int:
        if not self.steps:
            return 0
        completed = sum(1 for s in self.steps if s.completed)
        return int((completed / len(self.steps)) * 100)

    def is_complete(self) -> bool:
        return all(s.completed for s in self.steps)


@dataclass
class OnboardingStep:
    id: str
    label: str
    description: str
    completed: bool
    action_url: str | None = None



def build_onboarding_checklist(
    user_id: str,
    org_id: str | None,
    has_github: bool,
    has_projects: bool,
    has_repositories: bool,
    has_scans: bool,
    has_findings: bool,
) -> OnboardingChecklist:
    steps = []

    steps.append(
        OnboardingStep(
            id="create_org",
            label="Create an organization",
            description="Organize your team and manage access across projects",
            completed=org_id is not None,
            action_url=None if org_id else "/dashboard",
        )
    )

    steps.append(
        OnboardingStep(
            id="connect_github",
            label="Connect GitHub",
            description="Install ScanForge GitHub App to access your repositories",
            completed=has_github,
            action_url=None if has_github else f"/dashboard/{org_id}/settings#integrations",
        )
    )

    steps.append(
        OnboardingStep(
            id="create_project",
            label="Create a project",
            description="Projects group related repositories and their security findings",
            completed=has_projects,
            action_url=None if has_projects else f"/dashboard/{org_id}",
        )
    )

    steps.append(
        OnboardingStep(
            id="connect_repo",
            label="Connect a repository",
            description="Link your GitHub, GitLab, or Bitbucket repository",
            completed=has_repositories,
            action_url=None if not org_id or not has_projects else f"/dashboard/{org_id}",
        )
    )

    steps.append(
        OnboardingStep(
            id="run_first_scan",
            label="Run your first scan",
            description="Trigger a manual scan to discover security issues",
            completed=has_scans,
            action_url=None,
        )
    )

    steps.append(
        OnboardingStep(
            id="review_findings",
            label="Review findings",
            description="Examine detected vulnerabilities, secrets, and code issues",
            completed=has_findings,
            action_url=None,
        )
    )

    steps.append(
        OnboardingStep(
            id="setup_schedule",
            label="Set up automated scanning",
            description="Schedule daily or weekly scans for continuous monitoring",
            completed=False,
            action_url=None,
        )
    )

    return OnboardingChecklist(
        user_id=user_id,
        organization_id=org_id,
        steps=steps,
    )
