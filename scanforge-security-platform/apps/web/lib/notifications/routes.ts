export interface NotificationRouteInput {
  link?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  metadata_json?: Record<string, unknown> | null;
}

export function resolveNotificationRoute(notification: NotificationRouteInput): string | null {
  if (notification.link) return notification.link;

  if (notification.target_type === "scan") {
    const orgId = typeof notification.metadata_json?.org_id === "string"
      ? notification.metadata_json.org_id
      : null;
    const projectId = typeof notification.metadata_json?.project_id === "string"
      ? notification.metadata_json.project_id
      : null;
    const scanId = notification.target_id;

    if (orgId && projectId && scanId) {
      return `/dashboard/${orgId}/projects/${projectId}/scans/${scanId}`;
    }
  }

  return null;
}
