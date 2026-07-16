import { NextRequest } from 'next/server';
import { auth } from '@/lib/auth/server';

// Defer middleware creation to first request so the build does not need
// NEON_AUTH_COOKIE_SECRET. The proxy is invoked at runtime after auth is configured.
let _middleware: any = null;
function getMiddleware() {
  if (!_middleware) {
    _middleware = auth.middleware({
      loginUrl: '/auth/sign-in',
    });
  }
  return _middleware;
}

export default function proxy(request: NextRequest) {
  return getMiddleware()(request);
}

export const config = {
  matcher: ['/dashboard/:path*', '/notifications', '/profile'],
};
