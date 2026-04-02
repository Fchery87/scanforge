import { redirect } from "next/navigation";

// NOTE: resolveHomeRoute is imported for documentation only.
// Session resolution happens client-side in this app's architecture.
// The actual auth redirect is handled by the dashboard layout middleware.
// import { resolveHomeRoute } from "@/lib/page-surface/route-entry";

export default function HomePage() {
  redirect("/dashboard");
}
