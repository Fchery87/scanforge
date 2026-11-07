"use client";

import { type ZodType } from "zod";
import type { components } from "@/lib/api-types";

import { authClient } from "@/lib/auth/client";
import { getApiAccessToken } from "@/lib/auth/api-token";
import {
  auditLogSchema,
  exportSchema,
  findingSchema,
  findingStatsSchema,
  findingDetailSchema,
  findingEventsSchema,
  findingTrendSchema,
  githubIntegrationSchema,
  githubRepoListSchema,
  healthSchema,
  memberSchema,
  notificationSchema,
  notificationCountSchema,
  markedReadSchema,
  orgStatsSchema,
  onboardingChecklistSchema,
  organizationSlugPreviewSchema,
  organizationSchema,
  userSchema,
  paginated,
  projectSchema,
  repositorySchema,
  scanDetailSchema,
  scanScheduleSchema,
  scanSchema,
  scorecardSchema,
  shadowCandidateLabelSchema,
  shadowReviewSchema,
  suppressionRuleSchema,
  urlSchema,
} from "@/lib/api-schemas";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getAuthorizationHeader(): Promise<Record<string, string>> {
  const token = await getApiAccessToken(authClient);

  if (!token) {
    throw new ApiError("Not authenticated", 401);
  }

  return {
    Authorization: `Bearer ${token}`,
  };
}

async function request<T>(path: string, options: RequestInit = {}, schema?: ZodType<T>): Promise<T> {
  const authHeader = await getAuthorizationHeader();
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new ApiError(error.detail ?? `HTTP ${res.status}`, res.status);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const data = (await res.json()) as T;
  if (schema) {
    const result = schema.safeParse(data);
    if (!result.success) {
      console.error("[api] Invalid response contract", {
        method: options.method ?? "GET",
        issueCodes: result.error.issues.map((issue) => issue.code),
      });
      return data;
    }
    return result.data;
  }
  return data;
}

export const api = {
  health: () => request("/health", {}, healthSchema),

  organizations: {
    list: (skip = 0, limit = 20) =>
      request(`/organizations?skip=${skip}&limit=${limit}`, {}, paginated(organizationSchema)),
    previewSlug: (slug: string) =>
      request<components["schemas"]["OrganizationSlugPreview"]>(
        `/organizations/slug-preview?${new URLSearchParams({ slug }).toString()}`,
        {},
        organizationSlugPreviewSchema,
      ),
    create: (data: { name: string; slug: string }) =>
      request("/organizations", { method: "POST", body: JSON.stringify(data) }, organizationSchema),
    get: (id: string) => request(`/organizations/${id}`, {}, organizationSchema),
    update: (id: string, data: { name?: string; slug?: string }) =>
      request(`/organizations/${id}`, { method: "PATCH", body: JSON.stringify(data) }, organizationSchema),
    stats: (orgId: string) =>
      request<components["schemas"]["OrgStatsResponse"]>(`/organizations/${orgId}/stats`, {}, orgStatsSchema),
    delete: (orgId: string) =>
      request<void>(`/organizations/${orgId}`, { method: "DELETE" }),
  },

  github: {
    getInstallUrl: (orgId: string) =>
      request<components["schemas"]["GitHubInstallUrlResponse"]>(`/organizations/${orgId}/github/install-url`, {}, urlSchema),
    getOAuthAuthorizeUrl: (orgId: string) =>
      request<components["schemas"]["GitHubInstallUrlResponse"]>(`/organizations/${orgId}/github/oauth/authorize`, {}, urlSchema),
    oauthCallback: (code: string, state: string) =>
      request(`/github/oauth/callback`, {
        method: "POST",
        body: JSON.stringify({ code, state }),
      }, githubIntegrationSchema),
    installCallback: (installationId: string, state: string) =>
      request(`/github/install/callback`, {
        method: "POST",
        body: JSON.stringify({ installation_id: installationId, state }),
      }, githubIntegrationSchema),
    connect: (orgId: string, data: { installation_id: string; state: string; account_login?: string; account_type?: string }) =>
      request(`/organizations/${orgId}/github/connect`, {
        method: "POST",
        body: JSON.stringify(data),
      }, githubIntegrationSchema),
    getIntegration: (orgId: string) =>
      request(`/organizations/${orgId}/github/integration`, {}, githubIntegrationSchema.nullable()),
    listRepositories: (orgId: string) =>
      request<{ items: Array<{ id: string; full_name: string }>; total: number }>(
        `/organizations/${orgId}/github/repositories`,
        {},
        githubRepoListSchema,
      ),
    disconnect: (orgId: string) =>
      request<void>(`/organizations/${orgId}/github/integration`, { method: "DELETE" }),
  },

  projects: {
    list: (orgId: string, skip = 0, limit = 20) =>
      request(`/organizations/${orgId}/projects?skip=${skip}&limit=${limit}`, {}, paginated(projectSchema)),
    create: (orgId: string, data: { name: string; slug: string; description?: string }) =>
      request(`/organizations/${orgId}/projects`, { method: "POST", body: JSON.stringify({ ...data, organization_id: orgId }) }, projectSchema),
    get: (orgId: string, projectId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}`, {}, projectSchema),
  },

  repositories: {
    list: (orgId: string, projectId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/repositories`, {}, paginated(repositorySchema)),
    get: (orgId: string, projectId: string, repoId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}`, {}, repositorySchema),
    create: (orgId: string, projectId: string, data: {
      provider: string;
      external_repo_id?: string;
      owner_name: string;
      repo_name: string;
      full_name: string;
      default_branch?: string;
      clone_url?: string;
      html_url?: string;
    }) =>
      request(`/organizations/${orgId}/projects/${projectId}/repositories`, {
        method: "POST",
        body: JSON.stringify(data),
      }, repositorySchema),
    remove: (orgId: string, projectId: string, repoId: string) =>
      request<void>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}`, {
        method: "DELETE",
      }),
  },

  scans: {
    list: (orgId: string, projectId: string, skip = 0, limit = 20) =>
      request(`/organizations/${orgId}/projects/${projectId}/scans?skip=${skip}&limit=${limit}`, {}, paginated(scanSchema)),
    create: (orgId: string, projectId: string, data: { repository_id: string; trigger_type: string; branch_name?: string; scan_type?: string }) =>
      request(`/organizations/${orgId}/projects/${projectId}/scans`, { method: "POST", body: JSON.stringify(data) }, scanSchema),
    get: (orgId: string, projectId: string, scanId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/scans/${scanId}`, {}, scanDetailSchema),
    shadowReview: (orgId: string, projectId: string, scanId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/scans/${scanId}/shadow-review`, {}, shadowReviewSchema),
    labelShadowCandidate: (orgId: string, projectId: string, scanId: string, candidateId: string, label: string) =>
      request(
        `/organizations/${orgId}/projects/${projectId}/scans/${scanId}/shadow-review/candidates/${candidateId}/label`,
        { method: "PUT", body: JSON.stringify({ label }) },
        shadowCandidateLabelSchema,
      ),
    cancel: (orgId: string, projectId: string, scanId: string, reason?: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/scans/${scanId}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }, scanSchema),
    delete: (orgId: string, projectId: string, scanId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/scans/${scanId}`, {
        method: "DELETE",
      }, scanSchema),
  },

  findings: {
    list: (orgId: string, projectId: string, params: Record<string, string> = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request(
        `/organizations/${orgId}/projects/${projectId}/findings${qs ? "?" + qs : ""}`,
        {},
        paginated(findingSchema),
      );
    },
    get: (orgId: string, projectId: string, findingId: string) =>
      request<components["schemas"]["FindingDetailResponse"]>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}`, {}, findingDetailSchema),
    stats: (orgId: string, projectId: string, params: Record<string, string> = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request(
        `/organizations/${orgId}/projects/${projectId}/findings/stats${qs ? "?" + qs : ""}`,
        {},
        findingStatsSchema,
      );
    },
    suppress: (orgId: string, projectId: string, findingId: string, reason: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/suppress`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }, findingSchema),
    resolve: (orgId: string, projectId: string, findingId: string, fixedVersion?: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/resolve`, {
        method: "POST",
        body: JSON.stringify({ fixed_version: fixedVersion }),
      }, findingSchema),
    reopen: (orgId: string, projectId: string, findingId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/reopen`, {
        method: "POST",
      }, findingSchema),
    acceptRisk: (orgId: string, projectId: string, findingId: string, reason: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/accept-risk`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }, findingSchema),
    markDuplicate: (orgId: string, projectId: string, findingId: string, reason: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/mark-duplicate`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }, findingSchema),
    updateTriage: (
      orgId: string,
      projectId: string,
      findingId: string,
      data: { assignee_user_id?: string | null; due_date?: string | null }
    ) =>
      request(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/triage`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }, findingSchema),
    events: (orgId: string, projectId: string, findingId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/events`, {}, findingEventsSchema),
    bulk: (orgId: string, projectId: string, data: { finding_ids: string[]; action: string; reason: string }) =>
      request<void>(`/organizations/${orgId}/projects/${projectId}/findings/bulk`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    trend: (orgId: string, projectId: string, days = 30) =>
      request<{ data: Array<{ date: string; count: number }>; days: number }>(`/organizations/${orgId}/projects/${projectId}/findings/trend?days=${days}`, {}, findingTrendSchema),
  },

  exports: {
    list: (orgId: string, projectId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/exports`, {}, paginated(exportSchema)),
    create: (orgId: string, projectId: string, data: { export_type: string; format: string; title?: string; filters?: Record<string, string> }) =>
      request(`/organizations/${orgId}/projects/${projectId}/exports`, {
        method: "POST",
        body: JSON.stringify(data),
      }, exportSchema),
    download: (orgId: string, projectId: string, exportId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/exports/${exportId}`, {}, exportSchema),
  },

  auditLogs: {
    listOrg: (orgId: string, skip = 0, limit = 50) =>
      request(`/organizations/${orgId}/audit-logs?skip=${skip}&limit=${limit}`, {}, paginated(auditLogSchema)),
    listProject: (orgId: string, projectId: string, skip = 0, limit = 50) =>
      request(
        `/organizations/${orgId}/projects/${projectId}/audit-logs?skip=${skip}&limit=${limit}`,
        {},
        paginated(auditLogSchema),
      ),
  },

  notifications: {
    list: (skip = 0, limit = 20, unreadOnly = false) =>
      request(
        `/notifications?skip=${skip}&limit=${limit}&unreadOnly=${unreadOnly}`,
        {},
        paginated(notificationSchema),
      ),
    unreadCount: () => request("/notifications/unread-count", {}, notificationCountSchema),
    markRead: (ids: string[]) =>
      request("/notifications/mark-read", {
        method: "POST",
        body: JSON.stringify({ notification_ids: ids }),
      }, markedReadSchema),
    markAllRead: () => request("/notifications/mark-all-read", { method: "POST" }, markedReadSchema),
  },

  scorecard: {
    get: (orgId: string, projectId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/scorecard`, {}, scorecardSchema),
  },

  schedules: {
    list: (orgId: string, projectId: string, repoId: string) =>
      request(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules`, {}, scanScheduleSchema.array()),
    create: (orgId: string, projectId: string, repoId: string, data: {
      repository_id: string; schedule_type: string; cron_expression?: string; scan_type?: string;
    }) =>
      request(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules`, {
        method: "POST",
        body: JSON.stringify(data),
      }, scanScheduleSchema),
    update: (orgId: string, projectId: string, repoId: string, scheduleId: string, data: components["schemas"]["ScanScheduleUpdate"]) =>
      request(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules/${scheduleId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }, scanScheduleSchema),
    remove: (orgId: string, projectId: string, repoId: string, scheduleId: string) =>
      request<void>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules/${scheduleId}`, {
        method: "DELETE",
      }),
  },

  suppressionRules: {
    list: (orgId: string) =>
      request(`/organizations/${orgId}/suppression-rules`, {}, paginated(suppressionRuleSchema)),
    create: (orgId: string, data: { reason: string; pattern?: string } & Record<string, unknown>) =>
      request(`/organizations/${orgId}/suppression-rules`, {
        method: "POST",
        body: JSON.stringify(data),
      }, suppressionRuleSchema),
    update: (orgId: string, ruleId: string, data: Record<string, unknown>) =>
      request(`/organizations/${orgId}/suppression-rules/${ruleId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }, suppressionRuleSchema),
    remove: (orgId: string, ruleId: string) =>
      request<void>(`/organizations/${orgId}/suppression-rules/${ruleId}`, {
        method: "DELETE",
      }),
  },

  members: {
    list: (orgId: string, skip = 0, limit = 50) =>
      request(`/organizations/${orgId}/members?skip=${skip}&limit=${limit}`, {}, paginated(memberSchema)),
    invite: (orgId: string, data: { email: string; role: string }) =>
      request(`/organizations/${orgId}/members`, {
        method: "POST",
        body: JSON.stringify(data),
      }, memberSchema),
    updateRole: (orgId: string, userId: string, role: string) =>
      request(`/organizations/${orgId}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }, memberSchema),
    remove: (orgId: string, userId: string) =>
      request<void>(`/organizations/${orgId}/members/${userId}`, {
        method: "DELETE",
      }),
  },

  users: {
    me: () => request(`/users/me`, {}, userSchema),
  },

  onboarding: {
    get: (orgId?: string) => {
      const query = orgId ? `?${new URLSearchParams({ org_id: orgId }).toString()}` : "";
      return request<components["schemas"]["OnboardingChecklistResponse"]>(`/onboarding${query}`, {}, onboardingChecklistSchema);
    },
  },
};

export type { };
