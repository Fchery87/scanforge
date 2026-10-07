import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import { AppProvider } from '@/components/providers/app-provider';
import { scanForgeBodyClassName, scanForgeMetaThemeColor } from '@/lib/design-system';
import './globals.css';

const geistSans = Geist({
  subsets: ['latin'],
  variable: '--font-geist-sans',
  display: 'swap',
});

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'ScanForge',
  description: 'Find open security issues in your repositories and decide what to do with each one.',
};

export const viewport: Viewport = {
  themeColor: scanForgeMetaThemeColor,
  colorScheme: 'dark',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable}`}
    >
      <body className={scanForgeBodyClassName}>
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
