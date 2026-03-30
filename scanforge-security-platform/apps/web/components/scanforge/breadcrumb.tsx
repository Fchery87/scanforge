"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface BreadcrumbProps {
  orgName?: string;
  projectName?: string;
  className?: string;
}

export function Breadcrumb({ orgName, projectName, className }: BreadcrumbProps) {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  const crumbs: { label: string; href?: string }[] = [];
  crumbs.push({ label: "ScanForge", href: "/dashboard" });

  let i = 0;
  if (segments[i] === "dashboard") {
    i++;
    if (segments[i]) {
      crumbs.push({ label: orgName ?? segments[i], href: `/dashboard/${segments[i]}` });
      i++;
    }
    if (segments[i] === "projects" && segments[i + 1]) {
      i++;
      crumbs.push({ label: projectName ?? segments[i], href: `/dashboard/${segments[1]}/projects/${segments[i]}` });
      i++;
    }
    // Remaining segments
    while (i < segments.length) {
      const label = segments[i].replace(/-/g, " ");
      crumbs.push({ label: label.charAt(0).toUpperCase() + label.slice(1) });
      i++;
    }
  } else {
    // Non-dashboard routes
    while (i < segments.length) {
      crumbs.push({ label: segments[i].replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) });
      i++;
    }
  }

  return (
    <nav className={cn("flex items-center gap-1 text-sm", className)}>
      {crumbs.map((crumb, idx) => (
        <span key={idx} className="flex items-center gap-1">
          {idx > 0 && <ChevronRight className="h-3.5 w-3.5 text-text-tertiary" />}
          {crumb.href && idx < crumbs.length - 1 ? (
            <Link
              href={crumb.href}
              className="text-text-tertiary hover:text-text-primary transition-colors hover:underline"
            >
              {crumb.label}
            </Link>
          ) : (
            <span className={idx === crumbs.length - 1 ? "text-text-primary font-bold" : "text-text-tertiary"}>
              {crumb.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}
