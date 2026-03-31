import { accountViewPaths } from "@neondatabase/auth/react/ui/server";

import { AccountViewClient } from "@/components/auth/account-view-client";

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
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-10">
      <div className="rounded-xl border border-border bg-surface p-6">
        <AccountViewClient path={path} />
      </div>
    </main>
  );
}
