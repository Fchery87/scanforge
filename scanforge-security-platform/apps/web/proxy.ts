import { NextRequest } from 'next/server';
import { auth } from '@/lib/auth/server';

const authMiddleware = auth.middleware({
  loginUrl: '/auth/sign-in',
});

export default function proxy(request: NextRequest) {
  console.log('[Proxy] Processing request:', request.nextUrl.pathname);
  console.log(
    '[Proxy] Cookies:',
    request.headers.get('cookie')?.substring(0, 100),
  );

  const result = authMiddleware(request);

  console.log('[Proxy] Middleware result dispatched.');

  return result;
}

export const config = {
  matcher: ['/dashboard/:path*', '/notifications', '/profile'],
};
