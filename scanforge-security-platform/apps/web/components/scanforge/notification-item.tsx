"use client";

import { useState } from "react";
import { AlertTriangle, Shield, Scan, Key, User, FileText, Archive, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface NotificationItemProps {
  id: string;
  title: string;
  body?: string;
  type: string;
  isRead: boolean;
  createdAt: string;
  link?: string;
  onClick?: () => void;
  onMarkRead?: () => void;
  onArchive?: () => void;
  className?: string;
}

const TYPE_CONFIG: Record<string, { icon: typeof Shield; color: string; bgColor: string }> = {
  scan: { icon: Scan, color: "text-primary", bgColor: "bg-primary/10" },
  finding: { icon: AlertTriangle, color: "text-warning", bgColor: "bg-warning/10" },
  secret: { icon: Key, color: "text-danger", bgColor: "bg-danger/10" },
  member: { icon: User, color: "text-success", bgColor: "bg-success/10" },
  export: { icon: FileText, color: "text-severity-info", bgColor: "bg-severity-info/10" },
  default: { icon: Shield, color: "text-text-tertiary", bgColor: "bg-surface-elevated" },
};

function TypeIcon({ type }: { type: string }) {
  const config = TYPE_CONFIG[type] || TYPE_CONFIG.default;
  const Icon = config.icon;

  return (
    <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg flex-shrink-0", config.bgColor)}>
      <Icon className={cn("h-4 w-4", config.color)} />
    </div>
  );
}

function TimeAgo({ date }: { date: string }) {
  const now = new Date();
  const then = new Date(date);
  const diffInSeconds = Math.floor((now.getTime() - then.getTime()) / 1000);

  if (diffInSeconds < 60) return <span>Just now</span>;
  if (diffInSeconds < 3600) return <span>{Math.floor(diffInSeconds / 60)}m ago</span>;
  if (diffInSeconds < 86400) return <span>{Math.floor(diffInSeconds / 3600)}h ago</span>;
  return <span>{Math.floor(diffInSeconds / 86400)}d ago</span>;
}

export function NotificationItem({
  title,
  body,
  type,
  isRead,
  createdAt,
  onClick,
  onMarkRead,
  onArchive,
  className,
}: NotificationItemProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <TooltipProvider delayDuration={200}>
      <div
        onClick={onClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={cn(
          "group relative flex items-start gap-3 border-b border-border/60 px-4 py-4 transition-all duration-200",
          !isRead ? "bg-primary/[0.04]" : "hover:bg-surface-hover/45",
          onClick && "cursor-pointer",
          className
        )}
      >
        {/* Unread indicator */}
        {!isRead && (
          <div className="absolute left-0 top-1/2 h-9 w-1 -translate-y-1/2 rounded-r-full bg-primary" />
        )}

        <TypeIcon type={type} />

        <div className="flex-1 min-w-0">
          <p className={cn("text-sm leading-relaxed", !isRead ? "font-medium text-text-primary" : "text-text-secondary")}>
            {title}
          </p>
          {body && (
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-tertiary">{body}</p>
          )}
          <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">
            <TimeAgo date={createdAt} />
          </p>
        </div>

        {/* Quick actions on hover */}
        <div
          className={cn(
            "flex items-center gap-1 transition-all duration-200",
            isHovered ? "opacity-100 translate-x-0" : "opacity-0 translate-x-2"
          )}
        >
          {!isRead && onMarkRead && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onMarkRead();
                  }}
                  className="p-1.5 hover:bg-surface-hover rounded-md transition-colors"
                >
                  <Check className="h-3.5 w-3.5 text-text-tertiary hover:text-success" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top">Mark as read</TooltipContent>
            </Tooltip>
          )}

          {onArchive && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onArchive();
                  }}
                  className="p-1.5 hover:bg-surface-hover rounded-md transition-colors"
                >
                  <Archive className="h-3.5 w-3.5 text-text-tertiary hover:text-primary" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top">Archive</TooltipContent>
            </Tooltip>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
