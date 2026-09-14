import './globals.css';
import { Inter } from 'next/font/google';
import type { Metadata, Viewport } from 'next';
import AppShell from '@/components/AppShell';
import RegistraSW from '@/components/RegistraSW';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Comanda — Conceptes',
  description: 'TPV per a bar i restaurant: sala, comandes, cobraments i tancament.',
  manifest: '/manifest.webmanifest',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#1a1a2e',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ca">
      <body className={inter.className}>
        <AppShell>{children}</AppShell>
        <RegistraSW />
      </body>
    </html>
  );
}