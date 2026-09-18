'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, apiCarta, getStoredStaff, Center, Area, Table } from '@/lib/api';
import { useComandaWs } from '@/lib/useComandaWs';
import BotoSortirCambrer from '@/components/BotoSortirCambrer';

/**
 * SALA DEL CAMBRER (Comandera) — decisió Tomeu 15/09/2026.
 *
 * Què havia passat:
 *   · Carregava `api.getTables()` SENSE centre → li arribaven les taules de TOTS
 *     els punts de venda, i per això entrava i li sortia el Xibiu (les primeres
 *     per ordre alfabètic/número), no el seu centre.
 *   · No tenia ZONES ni el PLANEJAMENT: era una versió rònica del TPV.
 *
 * Ara:
 *   · Es carrega NOMÉS el pla del centre del torn obert (el del fitxatge).
 *   · Es mostren les ZONES del centre, amb comptador de taules, igual que al TPV.
 *   · Es veu el saldo pendent de cada taula i la llegenda d'estats.
 *   · Disseny de mòbil de veritat: graella gran, un dit, sense sidebar.
 */
export default function ComanderaSala() {
  const router = useRouter();
  const [centres, setCentres] = useState<Center[]>([]);
  const [arees, setArees] = useState<Area[]>([]);
  const [taules, setTaules] = useState<Table[]>([]);
  const [areaActiva, setAreaActiva] = useState<string>('');
  const [centreId, setCentreId] = useState<string>('');
  const [tornId, setTornId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const staff = typeof window !== 'undefined' ? getStoredStaff() : null;

  /** Carrega el pla de sala DEL CENTRE indicat (només el seu). */
  const carrega = useCallback(async (cid: string) => {
    try {
      const [t, a] = await Promise.all([
        api.getTables(cid || undefined),
        api.getAreas(cid || undefined),
      ]);
      setTaules(t);
      setArees(a);
      setAreaActiva((act) => (a.some((x) => x.id === act) ? act : (a[0]?.id ?? '')));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Error carregant el pla de sala');
    }
  }, []);

  /** Arrencada: centres + torn del cambrer (el centre ve del torn/fitxatge). */
  useEffect(() => {
    if (!getStoredStaff()) { router.replace('/comandera'); return; }
    (async () => {
      try {
        const [cs, ss] = await Promise.all([apiCarta.getCenters(), api.getShifts()]);
        setCentres(cs);
        const jo = getStoredStaff();
        const meu = jo ? ss.find((s) => s.staff_id === jo.id && !s.closed_at) : null;
        if (meu?.center_id) {
          setCentreId(meu.center_id);
          setTornId(meu.id);
          await carrega(meu.center_id);
        } else if (meu) {
          // torn sense centre: agafem el del fitxatge o el primer
          const c = cs[0]?.id ?? '';
          setCentreId(c); setTornId(meu.id);
          await carrega(c);
        }
      } catch (e) {
        setMsg(e instanceof Error ? e.message : 'Error carregant');
      } finally {
        setLoading(false);
      }
    })();
  }, [router, carrega]);

  // en viu: si entra o es cobra una comanda, refresquem el pla del centre
  useComandaWs({
    onOrderCreated: () => { if (centreId) void carrega(centreId); },
    onOrderPaid: () => { if (centreId) void carrega(centreId); },
  });

  const centreNom = centres.find((c) => c.id === centreId)?.name || '—';
  const visibles = areaActiva ? taules.filter((t) => t.area_id === areaActiva) : taules;
  const pendent = (t: Table) => Number(t.pending_amount ?? 0);

  if (loading) {
    return <div className="p-6 text-center" style={{ color: '#9aa7b8', background: '#0f1729', minHeight: '100vh' }}>Carregant el teu pla de sala…</div>;
  }

  return (
    <div className="pb-28" style={{ background: '#0f1729', minHeight: '100vh' }}>

      {/* ---------- CAPÇALERA DEL CAMBRER ---------- */}
      <div className="px-4 pt-5 pb-4" style={{ background: '#1a1a2e', borderBottom: '1px solid rgba(226,176,74,.2)' }}>
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <div className="text-xs" style={{ color: '#9aa7b8' }}>Cambrer</div>
            <div className="text-lg font-bold truncate" style={{ color: '#e2b04a' }}>{staff?.name || '—'}</div>
            <div className="text-xs mt-0.5" style={{ color: '#9aa7b8' }}>
              🏪 {centreNom}{tornId ? ' · 🟢 torn obert' : ''}
            </div>
          </div>
          <BotoSortirCambrer
            className="shrink-0 text-xs px-3 py-2 rounded-lg"
            style={{ background: 'rgba(255,255,255,.08)', color: '#e5e9f0' }} />
        </div>
      </div>

      {msg && (
        <div className="mx-4 mt-3 px-3 py-2 rounded-lg text-sm"
          style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{msg}</div>
      )}

      {/* ---------- ZONES (igual que al TPV) ---------- */}
      {arees.length > 0 && (
        <div className="flex gap-2 overflow-x-auto px-4 py-3">
          <button onClick={() => setAreaActiva('')}
            className="shrink-0 px-4 py-2 rounded-xl text-sm font-semibold"
            style={{
              background: areaActiva === '' ? '#e2b04a' : 'rgba(255,255,255,.07)',
              color: areaActiva === '' ? '#1a1a2e' : '#e5e9f0',
            }}>
            Totes ({taules.length})
          </button>
          {arees.map((a) => {
            const n = taules.filter((t) => t.area_id === a.id).length;
            const act = areaActiva === a.id;
            return (
              <button key={a.id} onClick={() => setAreaActiva(a.id)}
                className="shrink-0 px-4 py-2 rounded-xl text-sm font-semibold"
                style={{
                  background: act ? '#e2b04a' : 'rgba(255,255,255,.07)',
                  color: act ? '#1a1a2e' : '#e5e9f0',
                }}>
                {a.name} ({n})
                {Number(a.surcharge_percent) > 0 ? ` +${a.surcharge_percent}%` : ''}
              </button>
            );
          })}
        </div>
      )}

      {/* ---------- GRAELLA DE TAULES (un dit, gran) ---------- */}
      {visibles.length === 0 ? (
        <div className="px-4 py-16 text-center text-sm rounded-2xl mx-4"
          style={{ background: 'rgba(255,255,255,.04)', color: '#9aa7b8' }}>
          {arees.length === 0
            ? 'Aquest punt de venda encara no té zones ni taules configurades.'
            : 'No hi ha taules en aquesta zona.'}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 px-4 py-2">
          {visibles.map((t) => {
            const p = pendent(t);
            const oberta = p > 0 || t.status === 'occupied';
            const color = t.status === 'reserved' ? '#3b82f6'
              : t.status === 'needs_cleaning' ? '#a855f7'
              : t.status === 'blocked' ? '#6b7280'
              : oberta ? '#e2b04a' : '#22c55e';
            return (
              <button key={t.id}
                onClick={() => router.push(`/comandera/taula/${t.id}`)}
                className="relative rounded-2xl p-4 text-center transition active:scale-95"
                style={{
                  background: 'rgba(255,255,255,.05)',
                  border: `2px solid ${color}`,
                  minHeight: 108,
                }}>
                <div className="font-bold" style={{ color, fontSize: 26, lineHeight: 1.1 }}>{t.number}</div>
                <div className="text-xs mt-1" style={{ color: '#9aa7b8' }}>{t.seats}p</div>
                {p > 0 && (
                  <div className="mt-2 inline-block px-2 py-0.5 rounded-full font-bold"
                    style={{ background: '#e2b04a', color: '#1a1a2e', fontSize: 12 }}>
                    {p.toFixed(2)}€
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* ---------- LLEGENDA d'estats (els colors) ---------- */}
      <div className="flex items-center gap-4 flex-wrap px-4 py-4 text-xs" style={{ color: '#9aa7b8' }}>
        {[['#22c55e', 'Lliure'], ['#e2b04a', 'Ocupada'], ['#3b82f6', 'Reservada'],
          ['#a855f7', 'Per netejar'], ['#6b7280', 'Bloquejada']].map(([c, nom]) => (
          <span key={nom} className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-full" style={{ background: c }} />{nom}
          </span>
        ))}
      </div>
    </div>
  );
}
