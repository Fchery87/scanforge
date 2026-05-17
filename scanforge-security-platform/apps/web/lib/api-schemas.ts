import { z } from "zod";

export const organizationSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
  created_by_user_id: z.string().uuid(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const scanSchema = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
  repository_id: z.string().uuid(),
  trigger_type: z.string(),
  scan_type: z.string(),
  status: z.string(),
  branch_name: z.string().nullable().optional(),
  commit_sha: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const findingSchema = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
  repository_id: z.string().uuid(),
  category: z.string(),
  severity: z.string(),
  status: z.string(),
  title: z.string(),
  canonical_fingerprint: z.string(),
  first_seen_at: z.string(),
  last_seen_at: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export function paginated<T extends z.ZodTypeAny>(itemSchema: T) {
  return z.object({
    items: z.array(itemSchema),
    total: z.number(),
  });
}

export type Organization = z.infer<typeof organizationSchema>;
export type Scan = z.infer<typeof scanSchema>;
export type Finding = z.infer<typeof findingSchema>;
