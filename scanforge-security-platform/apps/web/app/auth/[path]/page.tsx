import { AuthViewClient } from "@/components/auth/auth-view-client";
import { ScanForgeLogo } from "@/components/scanforge/logo";

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
    <main className="mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-6 py-10 lg:grid-cols-[0.95fr_0.75fr]">
      <section className="card-serif hidden p-10 lg:block">
        <div className="mb-8 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
          <ScanForgeLogo className="h-6 w-6" />
        </div>
        <p className="section-title mb-3">Authentication</p>
        <h1 className="max-w-[10ch] font-display text-[3.5rem] leading-[0.95] tracking-[-0.05em] text-text-primary">
          Secure access for security operations.
        </h1>
        <p className="mt-5 max-w-[48ch] text-sm leading-relaxed text-text-secondary">
          Sign in to manage repositories, review findings, run scans, and govern access across your ScanForge workspace.
        </p>
      </section>

      <section className="card-serif mx-auto w-full max-w-md p-6 md:p-8">
        <div className="mb-6 lg:hidden">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
            <ScanForgeLogo className="h-5 w-5" />
          </div>
          <p className="section-title mb-2">Authentication</p>
          <h1 className="font-display text-[2.4rem] leading-none tracking-[-0.05em] text-text-primary">Welcome back</h1>
        </div>
        <AuthViewClient path={path} />
      </section>
    </main>
  );
}
