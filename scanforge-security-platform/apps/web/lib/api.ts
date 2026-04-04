"use client";

import { authClient } from "@/lib/auth/client";
import { getApiAccessToken } from "@/lib/auth/api-token";

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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
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
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  
  organizations: {
    list: (skip = 0, limit = 20) =>
      request<{ items: any[]; total: number }>(`/organizations?skip=${skip}&limit=${limit}`),
    previewSlug: (slug: string) =>
      request<{ requested_slug: string; available_slug: string; adjusted: boolean }>(
        `/organizations/slug-preview?${new URLSearchParams({ slug }).toString()}`
      ),
    create: (data: { name: string; slug: string }) =>
      request<any>("/organizations", { method: "POST", body: JSON.stringify(data) }),
    get: (id: string) => request<any>(`/organizations/${id}`),
    update: (id: string, data: { name?: string; slug?: string }) =>
      request<any>(`/organizations/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    stats: (orgId: string) =>
      request<any>(`/organizations/${orgId}/stats`),
    delete: (orgId: string) =>
      request<any>(`/organizations/${orgId}`, { method: "DELETE" }),
  },

  github: {
    getInstallUrl: (orgId: string) =>
      request<{ url: string }>(`/organizations/${orgId}/github/install-url`),
    getOAuthAuthorizeUrl: (orgId: string) =>
      request<{ url: string }>(`/organizations/${orgId}/github/oauth/authorize`),
    oauthCallback: (code: string, state: string) =>
      request<any>("/github/oauth/callback", {
        method: "POST",
        body: JSON.stringify({ code, state }),
      }),
    installCallback: (installationId: string, state: string) =>
      request<any>("/github/install/callback", {
        method: "POST",
        body: JSON.stringify({ installation_id: installationId, state }),
      }),
    connect: (orgId: string, data: { installation_id: string; state: string; account_login?: string; account_type?: string }) =>
      request<any>(`/organizations/${orgId}/github/connect`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    getIntegration: (orgId: string) =>
      request<any>(`/organizations/${orgId}/github/integration`),
    listRepositories: (orgId: string) =>
      request<{ items: any[]; total: number }>(`/organizations/${orgId}/github/repositories`),
    disconnect: (orgId: string) =>
      request<void>(`/organizations/${orgId}/github/integration`, { method: "DELETE" }),
  },

  projects: {
    list: (orgId: string, skip = 0, limit = 20) =>
      request<{ items: any[]; total: number }>(`/organizations/${orgId}/projects?skip=${skip}&limit=${limit}`),
    create: (orgId: string, data: { name: string; slug: string; description?: string }) =>
      request<any>(`/organizations/${orgId}/projects`, { method: "POST", body: JSON.stringify({ ...data, organization_id: orgId }) }),
    get: (orgId: string, projectId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}`),
  },

  repositories: {
    list: (orgId: string, projectId: string) =>
      request<{ items: any[]; total: number }>(`/organizations/${orgId}/projects/${projectId}/repositories`),
    get: (orgId: string, projectId: string, repoId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}`),
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
      request<any>(`/organizations/${orgId}/projects/${projectId}/repositories`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    remove: (orgId: string, projectId: string, repoId: string) =>
      request<void>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}`, {
        method: "DELETE",
      }),
  },

  scans: {
    list: (orgId: string, projectId: string, skip = 0, limit = 20) =>
      request<{ items: any[]; total: number }>(`/organizations/${orgId}/projects/${projectId}/scans?skip=${skip}&limit=${limit}`),
    create: (orgId: string, projectId: string, data: { repository_id: string; trigger_type: string; branch_name?: string; scan_type?: string }) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/scans`, { method: "POST", body: JSON.stringify(data) }),
    get: (orgId: string, projectId: string, scanId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/scans/${scanId}`),
    cancel: (orgId: string, projectId: string, scanId: string, reason?: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/scans/${scanId}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    delete: (orgId: string, projectId: string, scanId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/scans/${scanId}`, {
        method: "DELETE",
      }),
  },

  findings: {
    list: (orgId: string, projectId: string, params: Record<string, string> = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request<{ items: any[]; total: number }>(
        `/organizations/${orgId}/projects/${projectId}/findings${qs ? "?" + qs : ""}`
      );
    },
    get: (orgId: string, projectId: string, findingId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}`),
    stats: (orgId: string, projectId: string, params: Record<string, string> = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request<any>(
        `/organizations/${orgId}/projects/${projectId}/findings/stats${qs ? "?" + qs : ""}`
      );
    },
    suppress: (orgId: string, projectId: string, findingId: string, reason: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/suppress`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    resolve: (orgId: string, projectId: string, findingId: string, fixedVersion?: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/resolve`, {
        method: "POST",
        body: JSON.stringify({ fixed_version: fixedVersion }),
      }),
    reopen: (orgId: string, projectId: string, findingId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/reopen`, {
        method: "POST",
      }),
    acceptRisk: (orgId: string, projectId: string, findingId: string, reason: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/accept-risk`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    markDuplicate: (orgId: string, projectId: string, findingId: string, reason: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/mark-duplicate`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    updateTriage: (
      orgId: string,
      projectId: string,
      findingId: string,
      data: { assignee_user_id?: string | null; due_date?: string | null }
    ) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/triage`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    events: (orgId: string, projectId: string, findingId: string) =>
      request<any[]>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/events`),
    bulk: (orgId: string, projectId: string, data: { finding_ids: string[]; action: string; reason: string }) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/bulk`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    trend: (orgId: string, projectId: string, days = 30) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/findings/trend?days=${days}`),
  },

  exports: {
    list: (orgId: string, projectId: string) =>
      request<{ items: any[]; total: number }>(`/organizations/${orgId}/projects/${projectId}/exports`),
    create: (orgId: string, projectId: string, data: { export_type: string; format: string; title?: string; filters?: Record<string, string> }) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/exports`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  auditLogs: {
    listOrg: (orgId: string, skip = 0, limit = 50) =>
      request<{ items: any[]; total: number }>(`/organizations/${orgId}/audit-logs?skip=${skip}&limit=${limit}`),
    listProject: (orgId: string, projectId: string, skip = 0, limit = 50) =>
      request<{ items: any[]; total: number }>(
        `/organizations/${orgId}/projects/${projectId}/audit-logs?skip=${skip}&limit=${limit}`
      ),
  },

  notifications: {
    list: (skip = 0, limit = 20, unreadOnly = false) =>
      request<{ items: any[]; total: number }>(
        `/notifications?skip=${skip}&limit=${limit}&unreadOnly=${unreadOnly}`
      ),
    unreadCount: () => request<{ unread_count: number }>("/notifications/unread-count"),
    markRead: (ids: string[]) =>
      request<{ marked_read: number }>("/notifications/mark-read", {
        method: "POST",
        body: JSON.stringify({ notification_ids: ids }),
      }),
    markAllRead: () => request<{ marked_read: number }>("/notifications/mark-all-read", { method: "POST" }),
  },

  scorecard: {
    get: (orgId: string, projectId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/scorecard`),
  },

  schedules: {
    list: (orgId: string, projectId: string, repoId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules`),
    create: (orgId: string, projectId: string, repoId: string, data: {
      repository_id: string; schedule_type: string; cron_expression?: string; scan_type?: string;
    }) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (orgId: string, projectId: string, repoId: string, scheduleId: string, data: any) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules/${scheduleId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    remove: (orgId: string, projectId: string, repoId: string, scheduleId: string) =>
      request<any>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules/${scheduleId}`, {
        method: "DELETE",
      }),
  },

  suppressionRules: {
    list: (orgId: string) =>
      request<any>(`/organizations/${orgId}/suppression-rules`),
    create: (orgId: string, data: any) =>
      request<any>(`/organizations/${orgId}/suppression-rules`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (orgId: string, ruleId: string, data: any) =>
      request<any>(`/organizations/${orgId}/suppression-rules/${ruleId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    remove: (orgId: string, ruleId: string) =>
      request<any>(`/organizations/${orgId}/suppression-rules/${ruleId}`, {
        method: "DELETE",
      }),
  },

  members: {
    list: (orgId: string, skip = 0, limit = 50) =>
      request<any>(`/organizations/${orgId}/members?skip=${skip}&limit=${limit}`),
    invite: (orgId: string, data: { email: string; role: string }) =>
      request<any>(`/organizations/${orgId}/members`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    updateRole: (orgId: string, userId: string, role: string) =>
      request<any>(`/organizations/${orgId}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
    remove: (orgId: string, userId: string) =>
      request<any>(`/organizations/${orgId}/members/${userId}`, {
        method: "DELETE",
      }),
  },

  users: {
    me: () => request<any>("/users/me"),
  },
};

export type { };
