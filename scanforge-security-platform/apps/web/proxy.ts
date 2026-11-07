import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/lib/auth/server';

let middleware: ReturnType<typeof auth.middleware> | undefined;

export default async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (!(pathname === '/dashboard' || pathname.startsWith('/dashboard/') || pathname === '/notifications' || pathname === '/profile')) {
    return NextResponse.next();
  }
  middleware ??= auth.middleware({ loginUrl: '/auth/sign-in' });
  const response = await middleware(request);
  const location = response.headers.get('location');
  if (location) {
    const destination = new URL(location, request.url);
    if (destination.origin === request.nextUrl.origin && destination.pathname === '/auth/sign-in') {
      destination.searchParams.set('redirectTo', pathname + search);
      response.headers.set('location', destination.toString());
    }
  }
  return response;
}

export const config = {
  matcher: ['/dashboard/:path*', '/notifications', '/profile'],
};
