import { FileText } from "lucide-react";
import { EmptyState } from "@/components/scanforge/empty-state";

export default function ExportsPage() {
  return <EmptyState icon={FileText} title="Reports unavailable" description="Reports are unavailable during the private beta." />;
}
