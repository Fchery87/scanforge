import type { Metadata, Viewport } from 'next';
import { Cormorant_Garamond, IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google';
import { AppProvider } from '@/components/providers/app-provider';
import { scanForgeBodyClassName, scanForgeMetaThemeColor } from '@/lib/design-system';
import './globals.css';

const cormorantGaramond = Cormorant_Garamond({
  weight: ['500', '600'],
  subsets: ['latin'],
  variable: '--font-cormorant-garamond',
  display: 'swap',
});

const ibmPlexSans = IBM_Plex_Sans({
  weight: ['400', '500', '600'],
  subsets: ['latin'],
  variable: '--font-ibm-plex-sans',
  display: 'swap',
});

const ibmPlexMono = IBM_Plex_Mono({
  weight: ['400', '500'],
  subsets: ['latin'],
  variable: '--font-ibm-plex-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'ScanForge — Repository Security Platform',
  description:
    'Automated security scanning and vulnerability management for your code repositories.',
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
        lang='en'
        suppressHydrationWarning
        className={`${cormorantGaramond.variable} ${ibmPlexSans.variable} ${ibmPlexMono.variable}`}
      >
      <body className={scanForgeBodyClassName}>
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
