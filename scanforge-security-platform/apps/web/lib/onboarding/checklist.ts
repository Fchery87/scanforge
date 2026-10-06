import { api, ApiError } from "../api";
import type { OnboardingStep } from "./next-step";

export interface OnboardingChecklist {
  user_id: string;
  organization_id: string | null;
  steps: OnboardingStep[];
}

export async function loadOnboardingChecklist(organizationId?: string): Promise<OnboardingChecklist> {
  const user = await api.users.me();
  const organization = organizationId
    ? await api.organizations.get(organizationId)
    : (await api.organizations.list(0, 1)).items[0];
  const orgId = organization?.id ?? null;
  let hasGitHub = false;
  if (orgId) {
    try { await api.github.getIntegration(orgId); hasGitHub = true; }
    catch (error) { if (!(error instanceof ApiError) || error.status !== 404) throw error; }
  }
  const project = orgId ? (await api.projects.list(orgId, 0, 1)).items[0] : undefined;
  const projectUrl = orgId && project ? `/dashboard/${orgId}/projects/${project.id}` : null;
  const repositories = orgId && project ? (await api.repositories.list(orgId, project.id)).items : [];
  const scans = orgId && project ? (await api.scans.list(orgId, project.id, 0, 100)).items : [];
  const findings = orgId && project ? (await api.findings.list(orgId, project.id, { limit: "100" })).items : [];
  const schedules = orgId && project && repositories[0]
    ? await api.schedules.list(orgId, project.id, repositories[0].id) : [];
  const completedScan = scans.some((scan) => scan.status === "completed");
  const cleanScan = scans.some((scan) => scan.status === "completed" && scan.summary_json?.coverage_complete === true);
  return {
    user_id: user.id, organization_id: orgId,
    steps: [
      { id: "create_org", label: "Create an organization", description: "Organize your team and access.",
        completed: orgId !== null, action_url: "/dashboard" },
      { id: "connect_github", label: "Connect GitHub", description: "Install the ScanForge GitHub App.",
        completed: hasGitHub, action_url: orgId ? `/dashboard/${orgId}/settings#integrations` : null },
      { id: "create_project", label: "Create a project", description: "Group related repositories and findings.",
        completed: !!project, action_url: orgId ? `/dashboard/${orgId}` : null },
      { id: "connect_repo", label: "Connect a repository", description: "Connect a GitHub repository to this project.",
        completed: repositories.length > 0, action_url: projectUrl ? `${projectUrl}/repositories` : null },
      { id: "run_first_scan", label: "Run your first scan", description: "Complete a scan of this project.",
        completed: completedScan, action_url: projectUrl ? `${projectUrl}/scans` : null },
      { id: "review_findings", label: "Review findings", description: "Triage detected findings or review a clean completed scan.",
        completed: findings.some((finding) => finding.status !== "open") || (cleanScan && findings.length === 0),
        action_url: projectUrl ? `${projectUrl}/findings` : null },
      { id: "setup_schedule", label: "Set up automated scanning", description: "Enable a daily, weekly, or push schedule.",
        completed: schedules.some((schedule) => schedule.is_active), action_url: projectUrl ? `${projectUrl}/repositories` : null },
    ],
  };
}
