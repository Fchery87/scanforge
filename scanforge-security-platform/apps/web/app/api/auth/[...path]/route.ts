import { auth } from "@/lib/auth/server";

// Defer handler invocation to request time so the build does not need
// NEON_AUTH_COOKIE_SECRET. The secret check still fires on first actual request.
export function GET(request: Request, context: unknown) {
  return auth.handler().GET(request, context as any);
}
export function POST(request: Request, context: unknown) {
  return auth.handler().POST(request, context as any);
}
