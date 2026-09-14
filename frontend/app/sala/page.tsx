'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, apiTable, Table, Area, TableComanda } from '@/lib/api';
import { useComandaWs, WsBadge } from '@/lib/useComandaWs';
import PlaSala from '@/components/PlaSala';
import ModalTaula from '@/components/ModalTaula';
import ModalCobrar from '@/components/ModalCobrar';

/**
 * SALA — PLA DE SALA CONFIGURABLE (decisió Tomeu 14/09/2026).
 * · Àrees: barra, interior, terrassa... (selector a dalt)
 * · Taules a la seva POSICIÓ REAL, movibles en mode edició
 * · Saldo pendent de cobrar damunt cada taula
 * · DOBLE CLIC → modal amb desglossament i CRUD (modificar/anul·lar/cobrar)
 * · En viu: el WebSocket refresca la sala quan entren o es cobren comandes
 */
export default function SalaPage() {
  const router = useRouter();
  const [taules, setTaules] = useState<Table[]>([]);
  const [arees, setArees] = useState<Area[]>([]);
  const [areaActiva, setAreaActiva] = useState<string>('');
  const [taulaOberta, setTaulaOberta] = useState<Table | null>(null);
  const [comanda, setComanda] = useState<TableComanda | null>(null);
  const [cobrant, setCobrant] = useState<{ id: string; total: number } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [carregant, setCarregant] = useState(true);

  const refresca = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([api.getTables(), api.getAreas()]);
      setTaules(t);
      setArees(a);
      if (!areaActiva && a.length) setAreaActiva(a[0].id);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Error carregant el pla de sala');
    } finally { setCarregant(false); }
  }, [areaActiva]);

  useEffect(() => { void refresca(); }, [refresca]);

  // En viu: comandes noves o cobraments → refresquem la sala sencera
  const wsStatus = useComandaWs({
    onOrderCreated: () => { void refresca(); },
    onOrderPaid: () => { void refresca(); },
  });

  /** Doble clic sobre una taula → obrim el modal amb el desglossament. */
  const obrirTaula = async (t: Table) => {
    setTaulaOberta(t);
    setComanda(null);
    try {
      const d = await apiTable.getComanda(t.id);
      setComanda(d);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Error carregant la comanda');
    }
  };

  const tancarModal = () => { setTaulaOberta(null); setComanda(null); };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <h1 className="text-3xl font-bold text-brand-gold">Sala</h1>
        <WsBadge status={wsStatus} />
      </div>

      {msg && (
        <div className="mb-4 px-4 py-2 rounded-lg text-sm"
          style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{msg}</div>
      )}

      {/* selector d'àrees */}
      {arees.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-3 mb-2">
          <button onClick={() => setAreaActiva('')}
            className="shrink-0 px-4 py-2 rounded-xl text-sm font-semibold"
            style={{
              background: areaActiva === '' ? '#e2b04a' : 'rgba(255,255,255,.07)',
              color: areaActiva === '' ? '#1a1a2e' : '#e5e9f0',
            }}>
            Totes ({(taules || []).length})
          </button>
          {arees.map((a) => {
            const n = taules.filter((t) => t.area_id === a.id).length;
            return (
              <button key={a.id} onClick={() => setAreaActiva(a.id)}
                className="shrink-0 px-4 py-2 rounded-xl text-sm font-semibold"
                style={{
                  background: areaActiva === a.id ? '#e2b04a' : 'rgba(255,255,255,.07)',
                  color: areaActiva === a.id ? '#1a1a2e' : '#e5e9f0',
                }}>
                {a.name} ({n})
                {Number(a.surcharge_percent) > 0 ? ` +${a.surcharge_percent}%` : ''}
              </button>
            );
          })}
        </div>
      )}

      {carregant ? (
        <div className="py-16 text-center text-sm" style={{ color: '#9aa7b8' }}>Carregant el pla de sala…</div>
      ) : (
        <PlaSala
          taules={taules}
          arees={arees}
          areaActiva={areaActiva}
          onRefresca={refresca}
          onObrirTaula={obrirTaula}
        />
      )}

      {/* modal de la taula (doble clic) */}
      {taulaOberta && (
        <ModalTaula
          tableId={taulaOberta.id}
          tableNumber={String(taulaOberta.number)}
          comanda={comanda || {
            table_id: taulaOberta.id, open: false, total_amount: 0,
            discount_amount: 0, paid_amount: 0, pending_amount: 0, lines: [], payments: [],
          }}
          onTancar={tancarModal}
          onRefresca={async () => {
            await refresca();
            try { setComanda(await apiTable.getComanda(taulaOberta.id)); } catch { /* */ }
          }}
          onCobrar={(orderId) => {
            const t = comanda?.pending_amount ?? 0;
            tancarModal();
            setCobrant({ id: orderId, total: t });
          }}
          onAfegir={(tableId) => { tancarModal(); router.push(`/comandes?table=${tableId}`); }}
        />
      )}

      {/* cobrament (reutilitza el ModalCobrar existent) */}
      {cobrant && (
        <ModalCobrar
          orderId={cobrant.id}
          total={cobrant.total}
          onClose={() => setCobrant(null)}
          onPaid={async () => { setCobrant(null); await refresca(); }}
        />
      )}
    </div>
  );
}
