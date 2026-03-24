"use client";

import { X, FileText, Clock, Link2, CheckCircle, Pause } from "lucide-react";
import { cn } from "@/lib/utils";
import { SeverityBadge } from "@/components/scanforge/severity-badge";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

interface FindingDrawerProps {
  finding: any;
  onClose: () => void;
  onResolve: () => void;
  onSuppress: () => void;
  className?: string;
}

export function FindingDrawer({ finding, onClose, onResolve, onSuppress, className }: FindingDrawerProps) {
  if (!finding) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          "fixed right-0 top-0 bottom-0 z-50 w-full max-w-xl bg-surface border-l border-border shadow-2xl animate-slide-in-right flex flex-col",
          className
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-border">
          <div className="flex-1 min-w-0 pr-4">
            <div className="flex items-center gap-2 mb-2">
              <SeverityBadge severity={finding.severity} />
              <StatusBadge status={finding.status} showIcon={false} />
            </div>
            <h2 className="text-base font-semibold font-display text-text-primary leading-snug">
              {finding.title}
            </h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="flex-shrink-0">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="details" className="flex-1 flex flex-col min-h-0">
          <div className="px-5 pt-3">
            <TabsList className="w-full">
              <TabsTrigger value="details" className="flex-1">Details</TabsTrigger>
              <TabsTrigger value="instances" className="flex-1">Instances</TabsTrigger>
              <TabsTrigger value="history" className="flex-1">History</TabsTrigger>
            </TabsList>
          </div>

          <ScrollArea className="flex-1">
            <TabsContent value="details" className="p-5 space-y-4 mt-0">
              <div>
                <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">Description</h4>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {finding.description || "No description available."}
                </p>
              </div>

              <Separator />

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">Category</span>
                  <p className="text-sm text-text-primary capitalize mt-1">{finding.category?.replace(/_/g, " ")}</p>
                </div>
                <div>
                  <span className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">Scanner</span>
                  <p className="text-sm text-text-primary mt-1">{finding.scanner || "—"}</p>
                </div>
                <div>
                  <span className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">First Seen</span>
                  <p className="text-sm text-text-primary mt-1 font-mono">
                    {finding.first_seen_at ? new Date(finding.first_seen_at).toLocaleString() : "—"}
                  </p>
                </div>
                <div>
                  <span className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">Last Seen</span>
                  <p className="text-sm text-text-primary mt-1 font-mono">
                    {finding.last_seen_at ? new Date(finding.last_seen_at).toLocaleString() : "—"}
                  </p>
                </div>
              </div>

              {finding.file_path && (
                <>
                  <Separator />
                  <div>
                    <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">Location</h4>
                    <div className="flex items-center gap-2 rounded-lg bg-surface-elevated px-3 py-2">
                      <FileText className="h-4 w-4 text-text-tertiary flex-shrink-0" />
                      <span className="text-sm font-mono text-text-primary truncate">
                        {finding.file_path}
                        {finding.line_number && `:${finding.line_number}`}
                      </span>
                    </div>
                  </div>
                </>
              )}
            </TabsContent>

            <TabsContent value="instances" className="p-5 mt-0">
              <p className="text-sm text-text-tertiary">Instance details would appear here.</p>
            </TabsContent>

            <TabsContent value="history" className="p-5 mt-0">
              <p className="text-sm text-text-tertiary">Finding history timeline would appear here.</p>
            </TabsContent>
          </ScrollArea>
        </Tabs>

        {/* Footer Actions */}
        <div className="flex items-center gap-2 p-4 border-t border-border bg-surface">
          {finding.status === "open" && (
            <>
              <Button onClick={onResolve} variant="default" className="flex-1">
                <CheckCircle className="h-4 w-4 mr-1.5" /> Resolve
              </Button>
              <Button onClick={onSuppress} variant="outline" className="flex-1">
                <Pause className="h-4 w-4 mr-1.5" /> Suppress
              </Button>
            </>
          )}
          {finding.status !== "open" && (
            <p className="text-xs text-text-tertiary flex-1 text-center">
              Finding is {finding.status}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
