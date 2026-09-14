'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, apiCarta, getStoredStaff, Center, Shift } from '@/lib/api';
import { useComandaWs } from '@/lib/useComandaWs';

/**
 * COMANDERA · Sala — visió mòbil: les taules grans, un dit.
 * El capdamunt mostra el cambrer i el seu torn (centre); si no té torn,
 * el pot obrir triant el centre (contracte: POST /shifts/open).
 */

type Taula = {
  id: string;
  number: number;
  area_id?: string;
  status?: string;
  seats?: number;
};

export default function ComanderaSala() {
  const router = useRouter();
  const [taules, setTaules] = useState<Taula[]>([]);
  const [centres, setCentres] = useState<Center[]>([]);
  const [torn, setTorn] = useState<Shift | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const staff = typeof window !== 'undefined' ? getStoredStaff() : null;

  const carrega = async () => {
    try {
      const [t, cs, ss] = await Promise.all([api.getTables(), apiCarta.getCenters(), api.getShifts()]);
      setTaules(t as Taula[]);
      setCentres(cs);
      const jo = getStoredStaff();
      const meu = jo ? (ss as Shift[]).find((s) => s.staff_id === jo.id && !s.closed_at) : null;
      setTorn(meu || null);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Error carregant');
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!getStoredStaff()) { router.replace('/comandera'); return; }
    carrega();
  }, [router]);

  // en viu: si entra o es cobra una comanda, refresquem les taules
  useComandaWs({
    onOrderCreated: () => { api.getTables().then((t) => setTaules(t as Taula[])).catch(() => {}); },
    onOrderPaid: () => { api.getTables().then((t) => setTaules(t as Taula[])).catch(() => {}); },
  });

  const obreTorn = async (centerId: string) => {
    const jo = getStoredStaff();
    if (!jo) return;
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/shifts/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('comanda-token') || ''}` },
        body: JSON.stringify({ staff_id: jo.id, center_id: centerId }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => null);
        throw new Error(typeof b?.detail === 'string' ? b.detail : `Error ${res.status}`);
      }
      carrega();
    } catch (e) { setMsg(e instanceof Error ? e.message : 'Error obrint torn'); }
  };

  const centreNom = (id?: string | null) => centres.find((c) => c.id === id)?.name || '—';
  const ocupada = (t: Taula) => t.status === 'occupied';

  if (loading) {
    return <div className="p-6 text-center text-gray-400">Carregant…</div>;
  }

  return (
    <div className="pb-24" style={{ background: '#0f1729', minHeight: '100vh' }}>
      {/* capçalera del cambrer */}
      <div className="px-4 pt-5 pb-4" style={{ background: '#1a1a2e' }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-400">Cambrer</div>
            <div className="text-lg font-bold" style={{ color: '#e2b04a' }}>{staff?.name || '—'}</div>
          </div>
          <button onClick={() => { localStorage.removeItem('comanda-token'); localStorage.removeItem('comanda-staff'); router.replace('/comandera'); }}
            className="text-xs px-3 py-2 rounded-lg" style={{ background: 'rgba(255,255,255,.08)', color: '#e5e9f0' }}>
            Sortir
          </button>
        </div>

        {torn ? (
          <div className="mt-3 text-sm" style={{ color: '#9aa7b8' }}>
            🟢 Torn obert a <span className="font-bold" style={{ color: '#e5e9f0' }}>{centreNom(torn.center_id)}</span>
          </div>
        ) : (
          <div className="mt-3">
            <div className="text-sm mb-2" style={{ color: '#9aa7b8' }}>Tria el teu punt de venda per obrir torn:</div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {centres.map((c) => (
                <button key={c.id} onClick={() => obreTorn(c.id)}
                  className="shrink-0 px-4 py-2 rounded-xl text-sm font-semibold"
                  style={{ background: '#e2b04a', color: '#1a1a2e' }}>
                  {c.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {msg && <div className="mx-4 mt-3 px-4 py-2 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{msg}</div>}

      {/* taules, botons grans */}
      <div className="p-4">
        <div className="text-sm mb-3" style={{ color: '#9aa7b8' }}>{taules.length} taules</div>
        <div className="grid grid-cols-3 gap-3">
          {taules.map((t) => (
            <button key={t.id} onClick={() => router.push(`/comandera/taula/${t.id}`)}
              className="rounded-2xl py-5 flex flex-col items-center justify-center transition active:scale-95"
              style={{
                background: ocupada(t) ? 'rgba(226,176,74,.18)' : 'rgba(255,255,255,.06)',
                border: `2px solid ${ocupada(t) ? '#e2b04a' : 'rgba(255,255,255,.1)'}`,
                minHeight: 92,
              }}>
              <span className="text-2xl font-bold" style={{ color: ocupada(t) ? '#e2b04a' : '#e5e9f0' }}>
                {t.number}
              </span>
              <span className="text-[11px] mt-1" style={{ color: '#9aa7b8' }}>
                {ocupada(t) ? 'ocupada' : 'lliure'}{t.seats ? ` · ${t.seats}p` : ''}
              </span>
            </button>
          ))}
          {taules.length === 0 && (
            <div className="col-span-3 text-center py-10 text-gray-500 text-sm">
              No hi ha taules configurades
            </div>
          )}
        </div>
      </div>
    </div>
  );
}