'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, apiTable, Table, Area, TableComanda } from '@/lib/api';
import { useComandaWs, WsBadge } from '@/lib/useComandaWs';
import PlaSala from '@/components/PlaSala';
import GestioAreas from '@/components/GestioAreas';
import PanellCambrers from '@/components/PanellCambrers';
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
  //: Gestió de zones (crear/editar/esborrar les zones del punt de venda)
  const [gestioOberta, setGestioOberta] = useState(false);
  //: Centre actiu (el del selector «Tria el punt de venda» del header).
  //: La distribució del pla de sala és PER CENTRE (decisió Tomeu 14/09/2026):
  //: en canviar de centre, es recarrega el pla d'aquell punt de venda.
  const [centreActiu, setCentreActiu] = useState<string>('');

  // El header escriu el centre triat a localStorage i emet un esdeveniment.
  useEffect(() => {
    const llegeix = () => {
      const c = typeof window !== 'undefined' ? localStorage.getItem('comanda-centre') : null;
      setCentreActiu(c || '');
    };
    llegeix();
    const onCanvi = () => llegeix();
    window.addEventListener('comanda:centre', onCanvi);
    window.addEventListener('storage', onCanvi);
    return () => {
      window.removeEventListener('comanda:centre', onCanvi);
      window.removeEventListener('storage', onCanvi);
    };
  }, []);

  const refresca = useCallback(async () => {
    try {
      // només el pla del CENTRE actiu
      const [t, a] = await Promise.all([
        api.getTables(centreActiu || undefined),
        api.getAreas(centreActiu || undefined),
      ]);
      setTaules(t);
      setArees(a);
      // si l'àrea activa no és d'aquest centre, triam la primera del centre
      setAreaActiva((act) => (a.some((x) => x.id === act) ? act : (a[0]?.id ?? '')));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Error carregant el pla de sala');
    } finally { setCarregant(false); }
  }, [centreActiu]);

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

      {/* FRAME DE CAMBRERS DE SERVEI (decisió Tomeu 14/09/2026) */}
      <PanellCambrers centerId={areaActiva ? arees.find(a=>a.id===areaActiva)?.center_id : undefined} />

      {msg && (
        <div className="mb-4 px-4 py-2 rounded-lg text-sm"
          style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{msg}</div>
      )}

      {/* selector d'àrees + gestió de zones */}
      <div className="flex gap-2 overflow-x-auto pb-3 mb-2 items-center">
        {arees.length > 0 && (
          <button onClick={() => setAreaActiva('')}
            className="shrink-0 px-4 py-2 rounded-xl text-sm font-semibold"
            style={{
              background: areaActiva === '' ? '#e2b04a' : 'rgba(255,255,255,.07)',
              color: areaActiva === '' ? '#1a1a2e' : '#e5e9f0',
            }}>
            Totes ({(taules || []).length})
          </button>
        )}
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
        {/* GESTIÓ DE ZONES: crear/editar/esborrar les zones del punt de venda */}
        <button onClick={() => setGestioOberta(true)}
          title="Gestionar les zones del punt de venda (barra, interior, terrassa...)"
          className="shrink-0 px-3 py-2 rounded-xl text-sm font-semibold ml-auto"
          style={{ background: 'rgba(226,176,74,.15)', color: '#e2b04a',
                   border: '1px solid rgba(226,176,74,.35)' }}>
          ⚙️ Zones
        </button>
      </div>

      {carregant ? (
        <div className="py-16 text-center text-sm" style={{ color: '#9aa7b8' }}>Carregant el pla de sala…</div>
      ) : (
        <PlaSala
          taules={taules}
          arees={arees}
          areaActiva={areaActiva}
          onRefresca={refresca}
          onObrirTaula={obrirTaula}
          onCanviaEstat={async (t, estat) => {
            try {
              await apiTable.setEstat(t.id, estat);
              await refresca();
            } catch (e) {
              setMsg(e instanceof Error ? e.message : 'Error canviant l\'estat');
            }
          }}
        />
      )}

      {/* modal de la taula (doble clic) */}
      {taulaOberta && (
        <ModalTaula
          tableId={taulaOberta.id}
          tableNumber={String(taulaOberta.number)}
          onTancar={tancarModal}
          onRefresca={() => { void refresca(); }}
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
