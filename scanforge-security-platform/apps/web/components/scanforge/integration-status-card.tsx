"use client";

import { Github, AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getIntegrationHealth } from "@/lib/governance/member-policy";

interface IntegrationStatusCardProps {
  rawIntegration: unknown;
  onConnect: () => void;
  onDisconnect?: () => void;
  connecting?: boolean;
  message?: { type: "success" | "error"; text: string } | null;
  className?: string;
}

export function IntegrationStatusCard({
  rawIntegration,
  onConnect,
  onDisconnect,
  connecting = false,
  message,
  className,
}: IntegrationStatusCardProps) {
  const health = getIntegrationHealth(rawIntegration);

  return (
    <div className={cn("card-serif p-6", className)}>
      <div className="mb-4 flex items-center gap-2">
        <Github className="h-5 w-5 text-text-secondary" />
        <h2 className="text-lg font-semibold font-display text-text-primary">Integrations</h2>
      </div>
      {message && (
        <p className={cn("mb-3 text-sm", message.type === "success" ? "text-success" : "text-danger")}>
          {message.text}
        </p>
      )}
      <div className="flex items-center justify-between rounded-[10px] border border-border bg-background p-4">
        <div className="flex items-start gap-3">
          {health.status === "connected" ? (
            <CheckCircle2 className="h-5 w-5 text-success mt-0.5" />
          ) : health.status === "error" ? (
            <AlertCircle className="h-5 w-5 text-warning mt-0.5" />
          ) : (
            <XCircle className="h-5 w-5 text-text-tertiary mt-0.5" />
          )}
          <div>
            <p className="text-sm font-medium text-text-primary">GitHub App</p>
            <p className="mt-1 text-sm text-text-tertiary">{health.message}</p>
            {health.status === "connected" && "accountLogin" in health && (
              <p className="mt-1 text-xs text-text-secondary">
                Connected as <strong>{(health as { accountLogin: string }).accountLogin}</strong>
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={health.status === "connected" ? "success" : "outline"} className="text-xs">
            {health.status === "connected" ? "Active" : health.status === "error" ? "Warning" : "Disconnected"}
          </Badge>
          {health.status === "connected" && onDisconnect ? (
            <Button variant="ghost" size="sm" className="text-danger hover:text-danger" onClick={onDisconnect}>
              Disconnect
            </Button>
          ) : health.status !== "connected" ? (
            <Button onClick={onConnect} disabled={connecting}>
              {connecting ? "Redirecting..." : "Connect GitHub"}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
