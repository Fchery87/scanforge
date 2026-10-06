import { z } from "zod";
import type { components } from "./api-types";

// ── Core entity schemas (passthrough to tolerate API additions) ─────

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
  summary_json: z.record(z.unknown()).nullable().optional(),
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

export const scanDetailSchema = scanSchema.extend({
  scanner_runs: z.array(scannerRunSchema).optional(),
  error_message: z.string().nullable().optional(),
  summary_json: z.record(z.unknown()).nullable().optional(),
});

export const findingSchema = z.object({
  id: z.string(), project_id: z.string(), repository_id: z.string(),
  category: z.string(), severity: z.string(), status: z.string(), title: z.string(),
  description: z.string().nullable(), canonical_fingerprint: z.string(),
  primary_scanner: z.string().nullable(), confidence_score: z.number().nullable(),
  risk_score: z.number().nullable().optional(), fixed_version: z.string().nullable(),
  metadata_json: z.record(z.unknown()).nullable(), assignee_user_id: z.string().nullable().optional(),
  assignee_name: z.string().nullable().optional(), assignee_email: z.string().nullable().optional(),
  due_date: z.string().nullable().optional(), sla_status: z.record(z.unknown()).nullable().optional(),
  first_seen_at: z.string(), last_seen_at: z.string(), created_at: z.string(), updated_at: z.string(),
}).passthrough() satisfies z.ZodType<components["schemas"]["FindingResponse"]>;

export const findingEventSchema = z.object({
  id: z.string(), finding_id: z.string(), event_type: z.string(),
  actor_user_id: z.string().nullable(), reason: z.string().nullable(),
  metadata_json: z.record(z.unknown()).nullable(), created_at: z.string(),
}) satisfies z.ZodType<components["schemas"]["FindingEventResponse"]>;

export const findingInstanceSchema = z.object({
  id: z.string(), finding_id: z.string(), scan_id: z.string(), scanner_run_id: z.string().nullable(),
  path: z.string().nullable(), line_start: z.number().nullable(), line_end: z.number().nullable(),
  package_name: z.string().nullable(), installed_version: z.string().nullable(), fixed_version: z.string().nullable(),
  evidence_json: z.record(z.unknown()).nullable(), created_at: z.string(),
}) satisfies z.ZodType<components["schemas"]["FindingInstanceResponse"]>;

export const findingReferenceSchema = z.object({
  id: z.string(), finding_id: z.string(), reference_type: z.string(), reference_value: z.string(),
  url: z.string().nullable(), created_at: z.string(),
}) satisfies z.ZodType<components["schemas"]["FindingReferenceResponse"]>;

export const findingDetailSchema = findingSchema.extend({
  instances: z.array(findingInstanceSchema), references: z.array(findingReferenceSchema),
  events: z.array(findingEventSchema), remediation_guidance: z.record(z.unknown()).nullable().optional(),
}) satisfies z.ZodType<components["schemas"]["FindingDetailResponse"]>;

export const memberSchema = z.object({
  user_id: z.string(),
  user_name: z.string().nullable().optional(),
  user_email: z.string().nullable().optional(),
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
  scope: z.record(z.unknown()).optional(),
  created_at: z.string(),
}).passthrough();

export const scanScheduleSchema = z.object({
  id: z.string(), repository_id: z.string(), schedule_type: z.enum(["daily", "weekly", "on_push"]),
  scan_type: z.string(), cron_expression: z.string().nullable(), is_active: z.boolean(),
  last_run_at: z.string().nullable(), next_run_at: z.string().nullable(), created_by_user_id: z.string().nullable(),
  created_at: z.string(), updated_at: z.string(),
}) satisfies z.ZodType<components["schemas"]["ScanScheduleResponse"]>;

export const scorecardSchema = z.object({
  project_id: z.string(), overall_score: z.number(), security_score: z.number(), secrets_score: z.number(),
  dependency_score: z.number(), grade: z.string(), open_critical: z.number(), open_high: z.number(),
  open_medium: z.number(), open_low: z.number(), open_total: z.number(), fixed_30d: z.number(),
  new_this_week: z.number(), scan_count: z.number(), last_scan_at: z.string().nullable().optional(),
  risk_score_average: z.number().nullable().optional(), sla_overdue: z.number(),
  scanner_health: z.record(z.unknown()), policy_evaluation: z.record(z.unknown()).nullable().optional(),
}) satisfies z.ZodType<components["schemas"]["ScorecardResponse"]>;

export const findingStatsSchema = z.object({
  total: z.number(), open: z.number(), fixed: z.number(), suppressed: z.number(),
  by_severity: z.record(z.number()), by_category: z.record(z.number()),
}) satisfies z.ZodType<components["schemas"]["FindingStats"]>;

export const findingTrendSchema = z.object({
  data: z.array(z.object({ date: z.string(), count: z.number().int().nonnegative() })),
  days: z.number().int().positive(),
});

export const orgStatsSchema = z.object({
  project_count: z.number(), open_findings: z.number(), critical_findings: z.number(),
  scans_today: z.number(), scans_this_week: z.number(),
}) satisfies z.ZodType<components["schemas"]["OrgStatsResponse"]>;

export const userSchema = z.object({
  id: z.string(), auth_provider_user_id: z.string(), email: z.string(), name: z.string().nullable().optional(),
  avatar_url: z.string().nullable().optional(), is_active: z.boolean(), created_at: z.string(), updated_at: z.string(),
}) satisfies z.ZodType<components["schemas"]["UserResponse"]>;

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
export type ScanDetail = z.infer<typeof scanDetailSchema>;
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

export type FindingDetail = z.infer<typeof findingDetailSchema>;
export type User = z.infer<typeof userSchema>;
