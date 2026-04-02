"use client";

import { AlertTriangle, Clock, Shield, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { describeSuppressionScope, formatExpiryDisplay } from "@/lib/suppressions/rule-policy";

interface SuppressionImpactPreviewProps {
  ruleType: string;
  matchCriteria: Record<string, string>;
  projectId?: string | null;
  expiresAt?: string | null;
  isActive: boolean;
  className?: string;
}

export function SuppressionImpactPreview({
  ruleType,
  matchCriteria,
  projectId,
  expiresAt,
  isActive,
  className,
}: SuppressionImpactPreviewProps) {
  const scope = describeSuppressionScope({ project_id: projectId });
  const expiry = formatExpiryDisplay(expiresAt);

  return (
    <div className={cn("rounded-[10px] border border-border bg-background p-4 space-y-3", className)}>
      <div className="flex items-center gap-2">
        <Shield className="h-4 w-4 text-text-secondary" />
        <span className="text-sm font-medium text-text-primary">Rule Impact Preview</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant={scope === "organization" ? "default" : "outline"} className="text-xs flex items-center gap-1">
          {scope === "organization" ? <Globe className="h-3 w-3" /> : <Shield className="h-3 w-3" />}
          {scope}
        </Badge>
        <Badge variant="outline" className="text-xs">{ruleType}</Badge>
        <Badge variant={isActive ? "success" : "outline"} className="text-xs">
          {isActive ? "Active" : "Inactive"}
        </Badge>
      </div>
      <div className="text-xs text-text-secondary">
        <span className="font-medium">Matches:</span>{" "}
        {Object.entries(matchCriteria).map(([k, v]) => (
          <code key={k} className="px-1.5 py-0.5 rounded bg-surface-elevated font-mono text-[11px]">{k}: {v}</code>
        ))}
      </div>
      {expiry.isExpired && (
        <div className="flex items-center gap-1.5 text-xs text-danger">
          <Clock className="h-3.5 w-3.5" />
          Rule has expired
        </div>
      )}
      {expiry.isExpiringSoon && (
        <div className="flex items-center gap-1.5 text-xs text-warning">
          <AlertTriangle className="h-3.5 w-3.5" />
          Expires {expiry.label}
        </div>
      )}
    </div>
  );
}
