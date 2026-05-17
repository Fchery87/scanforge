"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Bell, CheckCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHeader } from "@/components/scanforge/page-header";
import { NotificationItem } from "@/components/scanforge/notification-item";
import { EmptyState } from "@/components/scanforge/empty-state";
import { SkeletonList } from "@/components/scanforge/loading-skeleton";
import { summarizeNotificationGroups, getNotificationTypeLabel } from "@/lib/notifications/groups";
import { resolveNotificationRoute } from "@/lib/notifications/routes";

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [typeFilter, setTypeFilter] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const limit = 20;

  useEffect(() => {
    api.notifications.list(page * limit, limit, unreadOnly)
      .then((res) => {
        const items = (res.items ?? []).filter((n: any) =>
          !typeFilter || n.notification_type?.includes(typeFilter)
        );
        setNotifications(items);
        setTotal(res.total ?? 0);
        setLoading(false);
      }).catch(() => setLoading(false));
  }, [page, typeFilter, unreadOnly]);

  async function handleNotifClick(n: any) {
    if (!n.is_read) {
      await api.notifications.markRead([n.id]).catch(() => {});
      setNotifications((prev) =>
        prev.map((notif) => notif.id === n.id ? { ...notif, is_read: true } : notif)
      );
    }
    const destination = resolveNotificationRoute(n);
    if (destination) router.push(destination);
  }

  async function markAllRead() {
    await api.notifications.markAllRead();
    setNotifications(notifications.map((n) => ({ ...n, is_read: true })));
  }

  const groups = summarizeNotificationGroups(notifications);
  const _totalUnread = groups.reduce((sum, g) => sum + g.unreadCount, 0);

  return (
    <div>
      <PageHeader
        eyebrow="Inbox"
        title="Notifications"
        description={`${total} total notification${total !== 1 ? "s" : ""} across scan activity, findings, exports, and member changes.`}
        actions={
          <Button variant="outline" size="sm" onClick={markAllRead}>
            <CheckCheck className="h-3.5 w-3.5" /> Mark All Read
          </Button>
        }
      />

      {!loading && groups.length > 0 && (
        <div className="card-serif mb-6 flex flex-wrap gap-3 p-4">
          {groups.map((g) => (
            <div key={g.type} className="flex items-center gap-2 rounded-[8px] border border-border bg-background px-3 py-2 text-sm">
              <span className="font-medium">{getNotificationTypeLabel(g.type)}</span>
              <span className="text-text-secondary">·</span>
              <span className="text-text-secondary">{g.count} total</span>
              {g.unreadCount > 0 && (
                <>
                  <span className="text-text-secondary">·</span>
                  <span className="font-medium text-primary">{g.unreadCount} unread</span>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="card-serif mb-6 flex flex-wrap items-center gap-3 p-4">
        <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v === "all" ? "" : v); setPage(0); }}>
          <SelectTrigger className="h-11 w-44 bg-background">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="scan">{getNotificationTypeLabel("scan")}</SelectItem>
            <SelectItem value="finding">{getNotificationTypeLabel("finding")}</SelectItem>
            <SelectItem value="secret">{getNotificationTypeLabel("secret")}</SelectItem>
            <SelectItem value="member">{getNotificationTypeLabel("member")}</SelectItem>
            <SelectItem value="export">{getNotificationTypeLabel("export")}</SelectItem>
          </SelectContent>
        </Select>

        <label className="flex items-center gap-2 rounded-[8px] border border-border bg-background px-3 py-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => { setUnreadOnly(e.target.checked); setPage(0); }}
            className="h-4 w-4 rounded border-border bg-surface text-primary focus:ring-primary"
          />
          Unread only
        </label>
      </div>

      {loading ? (
        <SkeletonList rows={5} />
      ) : notifications.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="All caught up"
          description="You have no notifications"
        />
      ) : (
        <div className="card-serif overflow-hidden">
          {notifications.map((n) => (
            <NotificationItem
              key={n.id}
              id={n.id}
              title={n.title}
              body={n.body}
              type={n.notification_type}
              isRead={n.is_read}
              createdAt={n.created_at}
              link={n.link}
              onClick={() => handleNotifClick(n)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
