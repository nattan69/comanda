'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, ClipboardList, Languages, Calculator } from 'lucide-react';
import LogoutLink from '@/components/LogoutLink';
import RoomCharge from '@/components/RoomCharge';
import ShiftBar from '@/components/ShiftBar';

/**
 * Shell de l'aplicació d'ESCRIPTORI (TPV): sidebar + main.
 * La COMANDERA (app dels cambrers) viu a /comandera i NO porta aquest shell:
 * té el seu propi layout mòbil polze-friendly.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname?.startsWith('/comandera')) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <nav className="w-64 shrink-0 h-screen bg-brand-navy border-r border-brand-gold/20 flex flex-col justify-center overflow-y-auto">
        <div className="px-6 py-8 border-b border-brand-gold/20">
          <h1 className="text-2xl font-bold text-brand-gold tracking-tight">Comanda</h1>
          <p className="text-xs text-gray-400">TPV Bar/Restaurant</p>
        </div>

        <div className="flex-1 p-4 space-y-4 my-6">
          <Link href="/sala" className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group">
            <LayoutDashboard size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
            <span>Sala</span>
          </Link>
          <Link href="/comandes" className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group">
            <ClipboardList size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
            <span>Comandes</span>
          </Link>
        </div>

        <div className="px-4 py-6 border-t border-brand-gold/20 space-y-2">
          <Link href="/carta" className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group">
            <ClipboardList size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
            <span>Carta</span>
          </Link>
          <Link href="/tancament" className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group">
            <Calculator size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
            <span>Tancament del dia</span>
          </Link>
          <Link href="/kds" className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group">
            <LayoutDashboard size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
            <span>KDS (cuina)</span>
          </Link>
          <Link href="/comandera" className="flex items-center gap-3 p-3 rounded-lg hover:bg-brand-gold/10 text-white transition-colors group">
            <LayoutDashboard size={20} className="text-brand-gold group-hover:scale-110 transition-transform" />
            <span>Comandera (cambrers)</span>
          </Link>
          <div className="flex items-center gap-2 text-xs text-gray-400 px-3 py-2 bg-brand-dark rounded-md">
            <Languages size={14} />
            <span>ca | es | en</span>
          </div>
          <LogoutLink />
        </div>
      </nav>

      <main className="flex-1 overflow-y-auto p-0">
        <ShiftBar />
        <RoomCharge />
        {children}
      </main>
    </div>
  );
}