import { accountViewPaths } from "@neondatabase/auth/react/ui/server";

import { AccountViewClient } from "@/components/auth/account-view-client";
import { ScanForgeLogo } from "@/components/scanforge/logo";

export const dynamicParams = false;

export function generateStaticParams() {
  return Object.values(accountViewPaths).map((path) => ({ path }));
}

export default async function AccountPage({
  params,
}: {
  params: Promise<{ path: string }>;
}) {
  const { path } = await params;

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
          <ScanForgeLogo className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">Account</h1>
        </div>
      </div>
      <div className="rounded-md border border-border p-6 md:p-8">
        <AccountViewClient path={path} />
      </div>
    </main>
  );
}
