"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { FileText } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Button } from "@/components/ui/button";

export default function AuditLogPage() {
  const { org_id } = useParams<{ org_id: string }>();
  const [logs, setLogs] = useState<any>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const limit = 25;

  useEffect(() => {
    setLoading(true);
    api.auditLogs.listOrg(org_id as string, page * limit, limit).then((data) => {
      setLogs(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [org_id, page]);

  const items = logs?.items || [];
  const total = logs?.total || 0;

  return (
    <div>
      <PageHeader
        title="Audit Log"
        description="Track all organization activity and changes"
      />

      {loading && !logs ? (
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No audit logs yet"
          description="Activity will appear here as actions are taken"
        />
      ) : (
        <>
          <div className="rounded-lg border border-border overflow-hidden bg-surface">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>IP Address</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((log: any) => (
                  <TableRow key={log.id}>
                    <TableCell className="font-mono text-text-secondary text-sm">
                      {new Date(log.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          "inline-block px-2 py-0.5 rounded-md text-xs font-medium",
                          "bg-primary/10 text-primary"
                        )}
                        data-action={log.action}
                      >
                        {log.action}
                      </span>
                    </TableCell>
                    <TableCell className="text-text-secondary text-sm">
                      {log.actor_user_id?.slice(0, 8) || "system"}
                    </TableCell>
                    <TableCell>
                      {log.target_type && (
                        <span className="text-text-tertiary text-xs mr-2">{log.target_type}</span>
                      )}
                      {log.target_id && (
                        <code className="font-mono text-sm text-text-secondary">
                          {log.target_id.slice(0, 8)}
                        </code>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-sm text-text-secondary">
                      {log.ip_address || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex items-center justify-between mt-4 px-1">
            <Button
              variant="ghost"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </Button>
            <span className="text-text-secondary text-sm">
              {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
            </span>
            <Button
              variant="ghost"
              size="sm"
              disabled={(page + 1) * limit >= total}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
