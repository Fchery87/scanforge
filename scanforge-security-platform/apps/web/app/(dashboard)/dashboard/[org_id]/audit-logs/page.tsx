"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { FileText } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function AuditLogPage() {
  const { org_id } = useParams<{ org_id: string }>();
  const [logs, setLogs] = useState<any>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const limit = 25;

  useEffect(() => {
    setLoading(true);
    api.auditLogs.listOrg(org_id, page * limit, limit)
      .then((data) => {
        setLogs(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [org_id, page]);

  const items = logs?.items || [];
  const total = logs?.total || 0;

  return (
    <div>
      <PageHeader
        eyebrow="Governance"
        title="Audit Log"
        description="Review organization activity, ownership changes, and operational history."
      />

      {loading && !logs ? (
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No audit logs yet"
          description="Activity will appear here as actions are taken across the organization."
        />
      ) : (
        <>
          <div className="card-serif overflow-hidden">
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
                    <TableCell className="font-mono text-sm text-text-secondary">
                      {new Date(log.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{log.action}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-text-secondary">
                      {log.actor_user_id?.slice(0, 8) || "system"}
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-text-secondary">
                        {log.target_type ? <span className="mr-2 text-xs text-text-tertiary">{log.target_type}</span> : null}
                        {log.target_id ? <code className="font-mono">{log.target_id.slice(0, 8)}</code> : "—"}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm text-text-secondary">
                      {log.ip_address || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="mt-4 flex items-center justify-between px-1">
            <Button variant="ghost" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <span className="text-sm text-text-secondary">
              {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
            </span>
            <Button variant="ghost" size="sm" disabled={(page + 1) * limit >= total} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
