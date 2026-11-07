export function safeAuthDestination(value: string | null): string {
  const fallback = "/dashboard";
  if (!value || !value.startsWith("/") || value.startsWith("//")) return fallback;
  try {
    if (/[\\\u0000-\u0020]/.test(decodeURIComponent(value))) return fallback;
    const url = new URL(value, "https://scanforge.invalid");
    const path = url.pathname;
    if (url.origin !== "https://scanforge.invalid" || !(path === "/dashboard" || path.startsWith("/dashboard/") || path === "/notifications" || path === "/profile")) return fallback;
    return url.pathname + url.search + url.hash;
  } catch {
    return fallback;
  }
}
