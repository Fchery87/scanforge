"use client";

import { AlertTriangle, Shield, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

interface NotificationItemProps {
  id: string;
  title: string;
  body?: string;
  type: string;
  isRead: boolean;
  createdAt: string;
  link?: string;
  onClick?: () => void;
  className?: string;
}

function TypeIcon({ type }: { type: string }) {
  if (type.includes("secret") || type.includes("finding")) {
    return <AlertTriangle className="h-4 w-4 text-warning" />;
  }
  if (type.includes("scan")) {
    return <Activity className="h-4 w-4 text-primary" />;
  }
  return <Shield className="h-4 w-4 text-text-tertiary" />;
}

export function NotificationItem({ title, body, type, isRead, createdAt, onClick, className }: NotificationItemProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-start gap-3 px-4 py-3 border-b border-border/50 transition-colors",
        !isRead && "bg-primary/[0.03]",
        onClick && "cursor-pointer hover:bg-surface-hover",
        className
      )}
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-elevated flex-shrink-0 mt-0.5">
        <TypeIcon type={type} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn("text-sm", !isRead ? "text-text-primary font-medium" : "text-text-secondary")}>
          {title}
        </p>
        {body && (
          <p className="text-xs text-text-tertiary mt-0.5 line-clamp-2">{body}</p>
        )}
        <p className="text-[11px] text-text-tertiary font-mono mt-1">
          {new Date(createdAt).toLocaleString()}
        </p>
      </div>
      {!isRead && (
        <div className="h-2 w-2 rounded-full bg-primary flex-shrink-0 mt-2" />
      )}
    </div>
  );
}
