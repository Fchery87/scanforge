"use client";

import { useState } from "react";
import { Mail, RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getInviteStateDisplay } from "@/lib/governance/member-policy";

interface Invitation {
  id: string;
  email: string;
  role: string;
  status?: string;
  created_at?: string;
}

interface MemberInvitationsPanelProps {
  invitations: Invitation[];
  onResend?: (id: string) => void;
  onCancel?: (id: string) => void;
  className?: string;
}

export function MemberInvitationsPanel({
  invitations,
  onResend,
  onCancel,
  className,
}: MemberInvitationsPanelProps) {
  if (invitations.length === 0) return null;

  return (
    <div className={cn("space-y-2", className)}>
      <h3 className="text-sm font-medium text-text-secondary flex items-center gap-2">
        <Mail className="h-4 w-4" />
        Pending Invitations
      </h3>
      {invitations.map((invite) => {
        const display = getInviteStateDisplay(invite);
        return (
          <div key={invite.id} className="flex items-center justify-between rounded-[10px] border border-border bg-background px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                {invite.email[0].toUpperCase()}
              </div>
              <div>
                <p className="text-sm font-medium text-text-primary">{invite.email}</p>
                <p className="text-xs text-text-tertiary capitalize">{invite.role}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                variant={display.variant === "pending" ? "outline" : display.variant === "accepted" ? "success" : "danger"}
                className="text-xs"
              >
                {display.statusLabel}
              </Badge>
              {display.variant === "pending" && (
                <>
                  {onResend && (
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onResend(invite.id)} title="Resend">
                      <RefreshCw className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  {onCancel && (
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-text-tertiary hover:text-danger" onClick={() => onCancel(invite.id)} title="Cancel">
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
