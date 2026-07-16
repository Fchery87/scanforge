import { z } from "zod";

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
  id: z.string(),
  project_id: z.string(),
  repository_id: z.string(),
  category: z.string(),
  severity: z.string(),
  status: z.string(),
  title: z.string(),
  canonical_fingerprint: z.string(),
  primary_scanner: z.string().optional(),
  risk_score: z.number().nullable().optional(),
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
  scope: z.record(z.unknown()).optional(),
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
  organization_id: z.string(),
  project_id: z.string().optional(),
  metrics: z.record(z.unknown()).optional(),
  generated_at: z.string().optional(),
}).passthrough();

export const findingStatsSchema = z.object({
  total: z.number(),
  open: z.number(),
  fixed: z.number(),
  suppressed: z.number(),
  by_severity: z.record(z.number()).optional(),
  by_category: z.record(z.number()).optional(),
}).passthrough();

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
