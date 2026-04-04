import { NextRequest } from 'next/server';
import { auth } from '@/lib/auth/server';

const authMiddleware = auth.middleware({
  loginUrl: '/auth/sign-in',
});

export default function proxy(request: NextRequest) {
  const result = authMiddleware(request);

  return result;
}

export const config = {
  matcher: ['/dashboard/:path*', '/notifications', '/profile'],
};
