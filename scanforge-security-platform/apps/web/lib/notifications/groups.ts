export interface NotificationGroup {
  type: string;
  count: number;
  unreadCount: number;
  latestAt?: string;
}

export function summarizeNotificationGroups(notifications: Array<{
  id: string;
  notification_type: string;
  is_read: boolean;
  created_at?: string;
}>): NotificationGroup[] {
  const map = new Map<string, NotificationGroup>();
  for (const n of notifications) {
    const type = n.notification_type ?? "unknown";
    const existing = map.get(type);
    if (existing) {
      existing.count++;
      if (!n.is_read) existing.unreadCount++;
      if (n.created_at && (!existing.latestAt || n.created_at > existing.latestAt)) {
        existing.latestAt = n.created_at;
      }
    } else {
      map.set(type, {
        type,
        count: 1,
        unreadCount: n.is_read ? 0 : 1,
        latestAt: n.created_at,
      });
    }
  }
  return Array.from(map.values()).sort((a, b) => (b.latestAt ?? "").localeCompare(a.latestAt ?? ""));
}

export function getNotificationTypeLabel(type: string): string {
  switch (type) {
    case "finding": return "Finding";
    case "scan": return "Scan";
    case "secret": return "Secret";
    case "member": return "Member";
    case "export": return "Export";
    default: return type;
  }
}
