import { AuthViewClient } from "@/components/auth/auth-view-client";

export const dynamicParams = false;

const AUTH_PATHS = [
  "sign-in",
  "sign-up",
  "forgot-password",
  "reset-password",
  "email-otp",
  "magic-link",
  "sign-out",
] as const;

export function generateStaticParams() {
  return AUTH_PATHS.map((path) => ({ path }));
}

export default async function AuthPage({
  params,
}: {
  params: Promise<{ path: string }>;
}) {
  const { path } = await params;

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center justify-center px-6 py-12">
      <div className="w-full rounded-xl border border-border bg-surface p-6">
        <AuthViewClient path={path} />
      </div>
    </main>
  );
}
