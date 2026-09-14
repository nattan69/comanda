'use client';

import { useEffect, useState } from 'react';
import { apiShift, CambrerPanell } from '@/lib/api';

/**
 * FRAME DE CAMBRERS (decisió Tomeu 14/09/2026).
 * Va a dalt del cos i mostra els cambrers LOGUEATS al centre actiu amb:
 *   · quantes taules tenen obertes
 *   · quantes comandes duen
 *   · el SALDO PENDENT DE COBRAR de les seves taules
 * Així el responsable veu d'un cop d'ull qui està de servei i quant es deu.
 */
export default function PanellCambrers({ centerId }: { centerId?: string }) {
  const [cambrers, setCambrers] = useState<CambrerPanell[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const carrega = () => {
      apiShift.panell(centerId)
        .then(setCambrers)
        .catch((e) => setError(e instanceof Error ? e.message : 'Error'));
    };
    carrega();
    const t = setInterval(carrega, 30000); // refresc periòdic
    return () => clearInterval(t);
  }, [centerId]);

  const totalPendent = cambrers.reduce((s, c) => s + (c.saldo_pendent || 0), 0);

  if (error || cambrers.length === 0) {
    return (
      <div className="mx-6 mt-4 px-4 py-3 rounded-xl text-sm"
        style={{ background: 'rgba(255,255,255,.04)', color: '#64748b' }}>
        {error ? `No s'ha pogut carregar el panell: ${error}` : 'Cap cambrer de servei en aquest centre'}
      </div>
    );
  }

  return (
    <div className="mx-6 mt-4 rounded-xl overflow-hidden"
      style={{ background: 'rgba(255,255,255,.04)', border: '1px solid rgba(226,176,74,.2)' }}>
      <div className="flex items-center justify-between px-4 py-2"
        style={{ background: 'rgba(226,176,74,.08)', borderBottom: '1px solid rgba(226,176,74,.15)' }}>
        <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#e2b04a' }}>
          👥 Cambrers de servei · {cambrers[0]?.center_name ?? ''}
        </span>
        <span className="text-xs font-bold" style={{ color: '#e2b04a' }}>
          Pendent total: {totalPendent.toFixed(2)} €
        </span>
      </div>
      <div className="flex gap-3 px-4 py-3 overflow-x-auto">
        {cambrers.map((c) => (
          <div key={c.staff_id} className="shrink-0 rounded-xl px-4 py-3 min-w-[190px]"
            style={{ background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.08)' }}>
            <div className="font-bold text-sm" style={{ color: '#e5e9f0' }}>{c.staff_name}</div>
            <div className="text-xs mt-1" style={{ color: '#9aa7b8' }}>
              {c.taules_obertes} {c.taules_obertes === 1 ? 'taula' : 'taules'} · {c.comandes_obertes} comandes
            </div>
            <div className="text-base font-bold mt-1"
              style={{ color: c.saldo_pendent > 0 ? '#e2b04a' : '#86efac' }}>
              {c.saldo_pendent.toFixed(2)} €
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
