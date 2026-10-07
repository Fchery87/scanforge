import { AuthViewClient } from "@/components/auth/auth-view-client";
import { ScanForgeLogo } from "@/components/scanforge/logo";
import { getAuthPageDescription } from "@/lib/page-surface/auth-titles";

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

export default async function AuthPage({ params }: { params: Promise<{ path: string }> }) {
  const { path } = await params;
  const description = getAuthPageDescription(path);

  return (
    <main className="flex min-h-screen items-center justify-center px-5 py-10">
      <section className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2 text-text-primary">
          <ScanForgeLogo className="h-4 w-4" />
          <span className="text-sm font-medium">ScanForge</span>
        </div>
        <p className="mb-5 max-w-[36ch] text-sm leading-relaxed text-text-secondary">{description}</p>
        <AuthViewClient path={path} />
      </section>
    </main>
  );
}
