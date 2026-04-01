export interface OnboardingStep {
  id: string;
  completed: boolean;
  action_url?: string | null;
  label?: string;
  description?: string;
}

export interface OnboardingNextAction {
  id: string;
  label: string;
  description: string;
  isPrimary: boolean;
  url?: string;
}

const STEP_ORDER = [
  "create_org",
  "connect_github",
  "create_project",
  "connect_repo",
  "run_first_scan",
  "review_findings",
];

const STEP_LABELS: Record<string, string> = {
  create_org: "Create Organization",
  connect_github: "Connect GitHub",
  create_project: "Create Project",
  connect_repo: "Connect Repository",
  run_first_scan: "Run First Scan",
  review_findings: "Review Findings",
};

const STEP_DESCRIPTIONS: Record<string, string> = {
  create_org: "Set up your organization to get started",
  connect_github: "Link your GitHub account to import repositories",
  create_project: "Create a project to organize your scans",
  connect_repo: "Add a repository to scan",
  run_first_scan: "Trigger your first security scan",
  review_findings: "Review and triage detected findings",
};

export function deriveOnboardingNextActions(steps: OnboardingStep[]): OnboardingNextAction[] {
  const stepMap = new Map(steps.map((s) => [s.id, s]));
  const nextActions: OnboardingNextAction[] = [];

  for (const stepId of STEP_ORDER) {
    const step = stepMap.get(stepId);
    if (!step || !step.completed) {
      nextActions.push({
        id: stepId,
        label: step?.label ?? STEP_LABELS[stepId] ?? stepId,
        description: step?.description ?? STEP_DESCRIPTIONS[stepId] ?? "",
        isPrimary: nextActions.length === 0,
        url: step?.action_url ?? undefined,
      });
      break;
    }
  }

  return nextActions;
}

export function getOnboardingCompletionSummary(steps: OnboardingStep[]): {
  completed: number;
  total: number;
  percentage: number;
  isComplete: boolean;
} {
  const completed = steps.filter((s) => s.completed).length;
  const total = steps.length || STEP_ORDER.length;
  return {
    completed,
    total,
    percentage: Math.round((completed / total) * 100),
    isComplete: completed === total,
  };
}

export type CallbackRecoveryState =
  | { kind: "success"; orgId: string }
  | { kind: "missing-install-id" }
  | { kind: "missing-org-context" }
  | { kind: "connect-failed" };

export function deriveCallbackState(params: {
  installation_id?: string | null;
  storedOrgId?: string | null;
  connectError?: boolean;
}): CallbackRecoveryState {
  if (params.connectError) return { kind: "connect-failed" };
  if (!params.installation_id) return { kind: "missing-install-id" };
  if (!params.storedOrgId) return { kind: "missing-org-context" };
  return { kind: "success", orgId: params.storedOrgId };
}
