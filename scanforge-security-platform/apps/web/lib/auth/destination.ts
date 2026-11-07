export function safeAuthDestination(value: string | null): string {
  const fallback = "/dashboard";
  if (!value || !value.startsWith("/") || value.startsWith("//")) return fallback;
  try {
    const decoded = decodeURIComponent(value);
    if (/\s/.test(decoded) || decoded.includes("\\") || Array.from(decoded).some((char) => char <= "\u0020")) return fallback;
    const url = new URL(value, "https://scanforge.invalid");
    const path = url.pathname;
    if (url.origin !== "https://scanforge.invalid" || !(path === "/dashboard" || path.startsWith("/dashboard/") || path === "/notifications" || path === "/profile")) return fallback;
    return url.pathname + url.search + url.hash;
  } catch {
    return fallback;
  }
}
