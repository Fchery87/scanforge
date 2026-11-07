import { z } from "zod";

// ── Core entity schemas (passthrough to tolerate API additions) ─────

export const userSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string().nullable().optional(),
  avatar_url: z.string().nullable().optional(),
  is_active: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

export const organizationSchema = z.object({
  id: z.string(),
  name: z.string(),
  slug: z.string(),
  created_by_user_id: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

export const projectSchema = z.object({
  id: z.string(),
  name: z.string(),
  slug: z.string(),
  organization_id: z.string(),
  description: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

export const repositorySchema = z.object({
  id: z.string(),
  project_id: z.string(),
  full_name: z.string(),
  owner_name: z.string(),
  repo_name: z.string(),
  default_branch: z.string().nullable().optional(),
  clone_url: z.string().nullable().optional(),
  html_url: z.string().nullable().optional(),
  importance: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

export const scanSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  repository_id: z.string(),
  trigger_type: z.string(),
  scan_type: z.string(),
  status: z.string(),
  branch_name: z.string().nullable().optional(),
  commit_sha: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

export const scannerRunSchema = z.object({
  id: z.string(),
  scan_id: z.string(),
  scanner_name: z.string(),
  status: z.string(),
  duration_ms: z.number().nullable().optional(),
  exit_code: z.number().nullable().optional(),
  error_message: z.string().nullable().optional(),
  artifact_download_url: z.string().nullable().optional(),
}).passthrough();

export const scannerCoverageSchema = z.object({
  scanner_name: z.string(),
  state: z.string(),
  reasons: z.array(z.string()).optional(),
  declared_scope: z.string().nullable().optional(),
  inputs_found: z.number().nullable().optional(),
  inputs_supported: z.number().nullable().optional(),
  unsupported_inputs: z.array(z.string()).nullable().optional(),
  exclusions: z.array(z.string()).nullable().optional(),
  parse_failures: z.number().nullable().optional(),
  truncated: z.boolean().nullable().optional(),
  timed_out: z.boolean().nullable().optional(),
}).passthrough();

export const capabilityCoverageSchema = z.object({
  capability: z.string(),
  state: z.string(),
  reasons: z.array(z.string()).optional(),
  scanners: z.array(scannerCoverageSchema).optional(),
}).passthrough();

export const shadowCandidateLabelSchema = z.object({
  candidate_id: z.string(),
  label: z.string(),
  actor_user_id: z.string().nullable().optional(),
  labeled_at: z.string(),
}).passthrough();

export const shadowReviewResultSchema = z.object({
  fingerprint: z.string(),
  scanner: z.string().nullable().optional(),
  capability: z.string().nullable().optional(),
  classification: z.string(),
  reason: z.string(),
  candidate_id: z.string().nullable().optional(),
  candidate_state: z.string().nullable().optional(),
  path: z.string().nullable().optional(),
  line_start: z.number().nullable().optional(),
  labels: z.array(shadowCandidateLabelSchema).optional(),
}).passthrough();

export const shadowReviewSchema = z.object({
  state: z.string(),
  scan_id: z.string(),
  scan_status: z.string(),
  revisions: z.object({
    pull_request_number: z.number().nullable().optional(),
    base_sha: z.string().nullable().optional(),
    head_sha: z.string().nullable().optional(),
    merge_base_sha: z.string().nullable().optional(),
    comparison_strategy: z.string().nullable().optional(),
    baseline_scan_id: z.string().nullable().optional(),
    head_is_fork: z.boolean().optional(),
  }).passthrough(),
  capability_coverage: z.array(capabilityCoverageSchema).optional(),
  classification_state: z.string(),
  classification_counts: z.object({ new: z.number(), existing: z.number(), unknown: z.number() }).passthrough(),
  results: z.array(shadowReviewResultSchema).optional(),
  limitations: z.array(z.string()).optional(),
  duration: z.object({ state: z.string(), total_ms: z.number().nullable().optional() }).passthrough(),
  cost_estimate: z.object({ state: z.string(), reason: z.string().nullable().optional() }).passthrough(),
}).passthrough();

export const scanDetailSchema = scanSchema.extend({
  scanner_runs: z.array(scannerRunSchema).optional(),
  capability_coverage: z.array(capabilityCoverageSchema).optional(),
  error_message: z.string().nullable().optional(),
  summary_json: z.record(z.string(), z.unknown()).nullable().optional(),
});

export const findingSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  repository_id: z.string(),
  category: z.string(),
  severity: z.string(),
  status: z.string(),
  title: z.string(),
  description: z.string().nullable(),
  canonical_fingerprint: z.string(),
  primary_scanner: z.string().nullable(),
  confidence_score: z.number().nullable(),
  risk_score: z.number().nullable(),
  fixed_version: z.string().nullable(),
  metadata_json: z.record(z.string(), z.unknown()).nullable(),
  first_seen_at: z.string(),
  last_seen_at: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

export const findingEventSchema = z.object({
  id: z.string(),
  finding_id: z.string(),
  event_type: z.string(),
  actor_user_id: z.string().nullable().optional(),
  reason: z.string().nullable().optional(),
  created_at: z.string(),
}).passthrough();

export const findingEventsSchema = z.object({ items: z.array(findingEventSchema), total: z.number() });

export const memberSchema = z.object({
  user_id: z.string(),
  email: z.string().nullable().optional(),
  name: z.string().nullable().optional(),
  role: z.string(),
  created_at: z.string().optional(),
}).passthrough();

export const exportSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  export_type: z.string(),
  format: z.string(),
  title: z.string().nullable().optional(),
  status: z.string().optional(),
  created_at: z.string(),
}).passthrough();

export const auditLogSchema = z.object({
  id: z.string(),
  organization_id: z.string().nullable().optional(),
  actor_user_id: z.string().nullable().optional(),
  action: z.string(),
  target_type: z.string(),
  target_id: z.string().nullable().optional(),
  ip_address: z.string().nullable().optional(),
  created_at: z.string(),
}).passthrough();

export const notificationSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  notification_type: z.string(),
  title: z.string(),
  body: z.string().nullable().optional(),
  link: z.string().nullable().optional(),
  is_read: z.boolean().optional(),
  created_at: z.string(),
}).passthrough();

export const githubIntegrationSchema = z.object({
  installation_id: z.string(),
  account_login: z.string().nullable().optional(),
  account_type: z.string().nullable().optional(),
  created_at: z.string().optional(),
}).passthrough();

export const suppressionRuleSchema = z.object({
  id: z.string(),
  organization_id: z.string(),
  reason: z.string(),
  scope: z.record(z.string(), z.unknown()).optional(),
  created_at: z.string(),
}).passthrough();

export const scanScheduleSchema = z.object({
  id: z.string(),
  repository_id: z.string(),
  schedule_type: z.string(),
  scan_type: z.string().optional(),
  cron_expression: z.string().nullable().optional(),
  created_at: z.string(),
}).passthrough();

export const scorecardSchema = z.object({
  organization_id: z.string().optional(),
  project_id: z.string(),
  overall_score: z.number().nullable().optional(),
  security_score: z.number().nullable().optional(),
  secrets_score: z.number().nullable().optional(),
  dependency_score: z.number().nullable().optional(),
  grade: z.string().nullable().optional(),
  open_critical: z.number().optional(),
  open_high: z.number().optional(),
  open_medium: z.number().optional(),
  open_low: z.number().optional(),
  open_total: z.number().optional(),
  fixed_30d: z.number().optional(),
  new_this_week: z.number().optional(),
  scan_count: z.number().optional(),
  last_scan_at: z.string().nullable().optional(),
  risk_score_average: z.number().nullable().optional(),
  sla_overdue: z.number().optional(),
  scanner_health: z.record(z.string(), z.unknown()).optional(),
  policy_evaluation: z.record(z.string(), z.unknown()).nullable().optional(),
  metrics: z.record(z.string(), z.unknown()).optional(),
  generated_at: z.string().optional(),
}).passthrough();

export const findingStatsSchema = z.object({
  total: z.number(),
  open: z.number(),
  fixed: z.number(),
  suppressed: z.number(),
  by_severity: z.record(z.string(), z.number()).optional(),
  by_category: z.record(z.string(), z.number()).optional(),
}).passthrough();

export const orgStatsSchema = z.object({
  project_count: z.number(),
  open_findings: z.number(),
  critical_findings: z.number(),
  scans_today: z.number(),
  scans_this_week: z.number(),
}).passthrough();

export const findingDetailSchema = findingSchema.extend({
  instances: z.array(z.object({ id: z.string(), finding_id: z.string(), scan_id: z.string(), scanner_run_id: z.string().nullable(), path: z.string().nullable(), line_start: z.number().nullable(), line_end: z.number().nullable(), package_name: z.string().nullable(), installed_version: z.string().nullable(), fixed_version: z.string().nullable(), evidence_json: z.record(z.string(), z.unknown()).nullable(), created_at: z.string() }).passthrough()),
  references: z.array(z.object({ id: z.string(), finding_id: z.string(), reference_type: z.string(), reference_value: z.string(), url: z.string().nullable(), created_at: z.string() }).passthrough()),
  events: z.array(z.object({ id: z.string(), finding_id: z.string(), event_type: z.string(), actor_user_id: z.string().nullable(), reason: z.string().nullable(), metadata_json: z.record(z.string(), z.unknown()).nullable(), created_at: z.string() }).passthrough()),
}).passthrough();

export const findingTrendSchema = z.object({
  data: z.array(z.object({ date: z.string(), count: z.number() })),
  days: z.number(),
}).passthrough();

export type OrgStats = z.infer<typeof orgStatsSchema>;
export type FindingDetail = z.infer<typeof findingDetailSchema>;
export type FindingTrend = z.infer<typeof findingTrendSchema>;

// ── Pagination helper ───────────────────────────────────────────────

export function paginated<T extends z.ZodTypeAny>(itemSchema: T) {
  return z.object({
    items: z.array(itemSchema),
    total: z.number(),
  });
}

// ── Inferred types (exported for callers to use) ────────────────────

export type Organization = z.infer<typeof organizationSchema>;
export type Project = z.infer<typeof projectSchema>;
export type Repository = z.infer<typeof repositorySchema>;
export type Scan = z.infer<typeof scanSchema>;
export type ShadowReview = z.infer<typeof shadowReviewSchema>;
export type ShadowReviewResult = z.infer<typeof shadowReviewResultSchema>;
export type ScanDetail =z.infer<typeof scanDetailSchema>;
export type Finding = z.infer<typeof findingSchema>;
export type FindingEvent = z.infer<typeof findingEventSchema>;
export type Member = z.infer<typeof memberSchema>;
export type Export = z.infer<typeof exportSchema>;
export type AuditLog = z.infer<typeof auditLogSchema>;
export type Notification = z.infer<typeof notificationSchema>;
export type GitHubIntegration = z.infer<typeof githubIntegrationSchema>;
export type SuppressionRule = z.infer<typeof suppressionRuleSchema>;
export type ScanSchedule = z.infer<typeof scanScheduleSchema>;
export type Scorecard = z.infer<typeof scorecardSchema>;
export type FindingStats = z.infer<typeof findingStatsSchema>;
