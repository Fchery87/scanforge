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
import { cn } from "@/lib/utils";

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
    if (n.link) router.push(n.link);
  }

  async function markAllRead() {
    await api.notifications.markAllRead();
    setNotifications(notifications.map((n) => ({ ...n, is_read: true })));
  }

  return (
    <div>
      <PageHeader
        title="Notifications"
        description={`${total} total notification${total !== 1 ? "s" : ""}`}
        actions={
          <Button variant="outline" size="sm" onClick={markAllRead}>
            <CheckCheck className="h-3.5 w-3.5" /> Mark All Read
          </Button>
        }
      />

      <div className="flex items-center gap-3 mb-6">
        <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v === "all" ? "" : v); setPage(0); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="scan">Scan</SelectItem>
            <SelectItem value="finding">Finding</SelectItem>
            <SelectItem value="secret">Secret</SelectItem>
            <SelectItem value="member">Member</SelectItem>
            <SelectItem value="export">Export</SelectItem>
          </SelectContent>
        </Select>

        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
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
        <div className="rounded-xl border border-border bg-surface overflow-hidden">
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
