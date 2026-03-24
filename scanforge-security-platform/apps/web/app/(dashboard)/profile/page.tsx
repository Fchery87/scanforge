"use client";

import { useState } from "react";
import { User, Mail, Bell } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/scanforge/page-header";
import { cn } from "@/lib/utils";

const NOTIF_PREFS = [
  { key: "notify_critical", label: "Notify on critical findings", description: "Get alerted when new critical vulnerabilities are detected" },
  { key: "notify_scan_complete", label: "Notify when scan completes", description: "Receive updates when security scans finish" },
  { key: "notify_new_member", label: "Notify on new team members", description: "Know when someone joins your organization" },
  { key: "notify_weekly_report", label: "Send weekly security digest", description: "Summary of findings and fixes each week" },
];

export default function ProfilePage() {
  const [prefs, setPrefs] = useState<Record<string, boolean>>({
    notify_critical: true,
    notify_scan_complete: false,
    notify_new_member: true,
    notify_weekly_report: false,
  });

  const togglePref = (key: string) => {
    setPrefs((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div>
      <PageHeader
        title="Profile"
        description="Manage your account and notification preferences"
      />

      {/* Profile Card */}
      <div className="flex items-center gap-5 rounded-xl border border-border bg-surface p-6 mb-8 animate-fade-up">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-secondary/20 text-primary">
          <User size={28} strokeWidth={1.5} />
        </div>
        <div>
          <h2 className="text-lg font-semibold font-display">User</h2>
          <p className="flex items-center gap-1.5 text-sm text-text-tertiary mt-0.5">
            <Mail className="h-3.5 w-3.5" /> Configure authentication to see user details
          </p>
        </div>
      </div>

      {/* Notification Preferences */}
      <div className="rounded-xl border border-border bg-surface animate-fade-up stagger-1">
        <div className="flex items-center gap-2 px-6 py-4 border-b border-border">
          <Bell className="h-4 w-4 text-text-secondary" />
          <h3 className="text-sm font-semibold font-display">Notification Preferences</h3>
        </div>
        <div className="divide-y divide-border/50">
          {NOTIF_PREFS.map((pref) => (
            <div key={pref.key} className="flex items-center justify-between px-6 py-4">
              <div>
                <Label htmlFor={pref.key} className="text-sm font-medium text-text-primary cursor-pointer">
                  {pref.label}
                </Label>
                <p className="text-xs text-text-tertiary mt-0.5">{pref.description}</p>
              </div>
              <Switch
                id={pref.key}
                checked={prefs[pref.key]}
                onCheckedChange={() => togglePref(pref.key)}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
