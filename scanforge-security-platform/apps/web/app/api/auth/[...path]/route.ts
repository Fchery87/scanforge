import { auth } from "@/lib/auth/server";

// Defer handler invocation to request time so the build does not need
// NEON_AUTH_COOKIE_SECRET. The secret check still fires on first actual request.
export function GET(request: Request, context: unknown) {
  return auth.handler().GET(request, context as any);
}
export function POST(request: Request, context: unknown) {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(request.url).pathname);
  } catch {
    return Response.json({ error: "Invalid authentication path" }, { status: 400 });
  }
  if (/^\/api\/auth\/sign-up(?:\/|$)/.test(pathname)) {
    return Response.json({ error: "Private beta access is by invitation" }, { status: 403 });
  }
  return auth.handler().POST(request, context as any);
}
