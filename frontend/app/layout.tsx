import './globals.css';
import { Inter } from 'next/font/google';
import Link from 'next/link';
import { getT } from '@/lib/i18n';
import { LayoutDashboard, ClipboardList, Languages, Calculator } from 'lucide-react';
import LogoutLink from '@/components/LogoutLink';
import RoomCharge from '@/components/RoomCharge';

const inter = Inter({ subsets: ['latin'] });

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const t = getT('ca'); // Default language

  return (
    <html lang="ca">
      <body className={inter.className}>
        <div className="flex min-h-screen">
          {/* Sidebar Navigation */}
          <nav className="w-64 bg-brand-navy border-r border-brand-gold/20 flex flex-col">
            <div className="p-6 border-b border-brand-gold/20">
              <h1 className="text-2xl font-bold text-brand-gold tracking-tight">Comanda</h1>
              <p className="text-xs text-gray-400">TPV Bar/Restaurant</p>
            </div>

            <div className="flex-1 p-4 space-y-2">
              <Link 
                href="/sala" 
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group"
              >
                <LayoutDashboard size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
                <span>{t.nav.sala}</span>
              </Link>
              <Link 
                href="/comandes" 
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group"
              >
                <ClipboardList size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
                <span>{t.nav.comandes}</span>
              </Link>
            </div>

            <div className="p-4 border-t border-brand-gold/20 space-y-2">
              <a href="/carta" className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group">
                <ClipboardList size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
                <span>{t.nav.carta || 'Carta'}</span>
              </a>
              <a href="/tancament" className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group">
                <Calculator size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
                <span>{t.nav.tancament || 'Tancament del dia'}</span>
              </a>
              <div className="flex items-center gap-2 text-xs text-gray-400 px-3 py-2 bg-brand-dark rounded-md">
                <Languages size={14} />
                <span>ca | es | en</span>
              </div>
              <LogoutLink />
            </div>
          </nav>

          <main className="flex-1 overflow-auto">
            <RoomCharge />
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
