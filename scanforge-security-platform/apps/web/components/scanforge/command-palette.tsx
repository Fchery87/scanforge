"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { api } from "@/lib/api";

interface OrgHit { id: string; name: string; slug: string }
interface ProjectHit { orgId: string; id: string; name: string }
interface RepoHit { orgId: string; projectId: string; id: string; name: string }

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [orgs, setOrgs] = useState<OrgHit[]>([]);
  const [projects, setProjects] = useState<ProjectHit[]>([]);
  const [repos, setRepos] = useState<RepoHit[]>([]);
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((current) => !current);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  useEffect(() => {
    if (!open || orgs.length > 0) return;
    let cancelled = false;
    api.organizations.list(0, 20).then(async (res) => {
      const orgList: OrgHit[] = (res.items ?? []).map((org: any) => ({ id: org.id, name: org.name, slug: org.slug }));
      if (cancelled) return;
      setOrgs(orgList);
      const projectLists = await Promise.all(
        orgList.map((org) => api.projects.list(org.id, 0, 20).then((r) => r.items ?? []).catch(() => []))
      );
      if (cancelled) return;
      const projectHits: ProjectHit[] = projectLists.flatMap((items, index) =>
        items.map((project: any) => ({ orgId: orgList[index].id, id: project.id, name: project.name }))
      );
      setProjects(projectHits);
      const repoLists = await Promise.all(
        projectHits.map((project) =>
          api.repositories.list(project.orgId, project.id).then((r: any) => r.items ?? []).catch(() => [])
        )
      );
      if (cancelled) return;
      setRepos(repoLists.flatMap((items, index) =>
        items.map((repo: any) => ({
          orgId: projectHits[index].orgId,
          projectId: projectHits[index].id,
          id: repo.id,
          name: repo.full_name ?? repo.repo_name ?? repo.id,
        }))
      ));
    }).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [open, orgs.length]);

  const navigate = useCallback((href: string) => {
    setOpen(false);
    router.push(href);
  }, [router]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 items-center gap-2 rounded-md border border-border px-2.5 text-sm text-text-tertiary hover-fine:bg-surface-hover hover-fine:text-text-secondary"
      >
        <span>Search</span>
        <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-0.5 rounded border border-border bg-surface-elevated px-1.5 font-mono text-[10px] text-text-tertiary">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Organizations, projects, repositories" />
        <CommandList>
          <CommandEmpty>Nothing matches.</CommandEmpty>
          <CommandGroup heading="Pages">
            <CommandItem onSelect={() => navigate("/dashboard")}>Overview</CommandItem>
            <CommandItem onSelect={() => navigate("/notifications")}>Notifications</CommandItem>
            <CommandItem onSelect={() => navigate("/onboarding")}>Setup</CommandItem>
            <CommandItem onSelect={() => navigate("/profile")}>Profile</CommandItem>
          </CommandGroup>
          {orgs.length > 0 ? (
            <>
              <CommandSeparator />
              <CommandGroup heading="Organizations">
                {orgs.map((org) => (
                  <CommandItem key={org.id} onSelect={() => navigate(`/dashboard/${org.id}`)}>
                    {org.name}
                    <CommandShortcut className="font-mono text-[10px]">{org.slug}</CommandShortcut>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          ) : null}
          {projects.length > 0 ? (
            <>
              <CommandSeparator />
              <CommandGroup heading="Projects">
                {projects.map((project) => (
                  <CommandItem key={project.id} onSelect={() => navigate(`/dashboard/${project.orgId}/projects/${project.id}`)}>
                    {project.name}
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          ) : null}
          {repos.length > 0 ? (
            <>
              <CommandSeparator />
              <CommandGroup heading="Repositories">
                {repos.map((repo) => (
                  <CommandItem key={repo.id} onSelect={() => navigate(`/dashboard/${repo.orgId}/projects/${repo.projectId}/repositories/${repo.id}`)}>
                    {repo.name}
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          ) : null}
        </CommandList>
      </CommandDialog>
    </>
  );
}
