'use client';

import { useEffect, useState } from 'react';
import { apiTable, Area } from '@/lib/api';

/**
 * GESTIÓ D'ÀREES (zones) DEL PUNT DE VENDA — decisió Tomeu 15/09/2026.
 *
 * Per què cal:
 *   Un punt de venda (bar, restaurant, xibiu...) té DIVERSES zones: barra,
 *   interior, terrassa, menjador... Fins ara les àrees només es podien crear
 *   per API, així que els centres es quedaven amb una sola zona i no es podia
 *   ajustar la sala a la realitat del local.
 *
 * Què fa:
 *   · Llista les zones del centre actiu (nom + recàrrec + quantes taules té)
 *   · Crear-ne de noves (nom, recàrrec de terrassa..., posició)
 *   · Reanomenar-les i canviar-ne el recàrrec
 *   · Esborrar-les (només si no tenen taules, per no deixar taules òrfenes)
 */
export default function GestioAreas({
  centerId,
  onTancar,
  onCanvi,
}: {
  centerId?: string;
  onTancar: () => void;
  onCanvi: () => void;
}) {
  const [arees, setArees] = useState<Area[]>([]);
  const [carregant, setCarregant] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [editant, setEditant] = useState<string | null>(null);
  const [esborrant, setEsborrant] = useState<string | null>(null);

  // formulari de nova zona
  const [nouNom, setNouNom] = useState('');
  const [nouRecarrec, setNouRecarrec] = useState('0');
  const [creant, setCreant] = useState(false);

  const carrega = async () => {
    try {
      setArees(await apiTable.getAreas(centerId));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Error carregant les zones');
    } finally {
      setCarregant(false);
    }
  };
  useEffect(() => { void carrega(); /* eslint-disable-next-line */ }, [centerId]);

  const crear = async () => {
    const nom = nouNom.trim();
    if (!nom) return;
    setCreant(true); setMsg(null);
    try {
      await apiTable.createArea({
        name: nom,
        center_id: centerId || null,
        surcharge_percent: parseFloat(nouRecarrec) || 0,
        position_x: 0,
        position_y: 0,
      });
      setNouNom(''); setNouRecarrec('0');
      await carrega();
      onCanvi();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'No s\'ha pogut crear la zona');
    } finally { setCreant(false); }
  };

  const desa = async (a: Area, nom: string, recarrec: string) => {
    setMsg(null);
    try {
      await apiTable.updateArea(a.id, {
        name: nom.trim() || a.name,
        surcharge_percent: parseFloat(recarrec) || 0,
      });
      setEditant(null);
      await carrega();
      onCanvi();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'No s\'ha pogut desar');
    }
  };

  const esborra = async (a: Area) => {
    setMsg(null);
    try {
      await apiTable.deleteArea(a.id);
      setEsborrant(null);
      await carrega();
      onCanvi();
    } catch (e) {
      // el backend rebutja si té taules — missatge clar
      setMsg(e instanceof Error ? e.message : 'No s\'ha pogut esborrar la zona');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,.7)' }} onClick={onTancar}>
      <div className="w-full max-w-lg rounded-2xl p-6 max-h-[85vh] overflow-y-auto"
        style={{ background: '#141429', border: '1px solid rgba(226,176,74,.3)' }}
        onClick={(e) => e.stopPropagation()}>

        <div className="flex items-center justify-between mb-1">
          <h2 className="text-xl font-bold" style={{ color: '#e2b04a' }}>🗺️ Zones del punt de venda</h2>
          <button onClick={onTancar} className="text-2xl leading-none px-2" style={{ color: '#9aa7b8' }}>×</button>
        </div>
        <p className="text-xs mb-5" style={{ color: '#9aa7b8' }}>
          Les zones (barra, interior, terrassa...) d&apos;aquest punt de venda. Cada zona té les seves taules.
        </p>

        {msg && (
          <div className="mb-4 px-3 py-2 rounded-lg text-sm"
            style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{msg}</div>
        )}

        {/* ---------- LLISTA DE ZONES ---------- */}
        {carregant ? (
          <div className="py-6 text-center text-sm" style={{ color: '#9aa7b8' }}>Carregant…</div>
        ) : arees.length === 0 ? (
          <div className="py-6 text-center text-sm rounded-xl"
            style={{ background: 'rgba(255,255,255,.04)', color: '#9aa7b8' }}>
            Aquest punt de venda encara no té cap zona.<br />Crea&apos;n una a baix 👇
          </div>
        ) : (
          <div className="space-y-2 mb-5">
            {arees.map((a) => {
              const n = a.table_count ?? 0;
              return (
                <div key={a.id} className="rounded-xl px-3 py-3"
                  style={{ background: 'rgba(255,255,255,.05)' }}>
                  {editant === a.id ? (
                    <FormEdicio area={a} onDesa={desa} onCancel={() => setEditant(null)} />
                  ) : (
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-semibold truncate" style={{ color: '#e5e9f0' }}>
                          {a.name}
                          {Number(a.surcharge_percent) > 0 && (
                            <span className="ml-2 text-xs px-2 py-0.5 rounded-full"
                              style={{ background: 'rgba(226,176,74,.2)', color: '#e2b04a' }}>
                              +{a.surcharge_percent}%
                            </span>
                          )}
                        </div>
                        <div className="text-xs mt-0.5" style={{ color: '#9aa7b8' }}>
                          {n} {n === 1 ? 'taula' : 'taules'}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button onClick={() => setEditant(a.id)}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold"
                          style={{ background: 'rgba(255,255,255,.08)', color: '#e5e9f0' }}>
                          ✎ Editar
                        </button>
                        {esborrant === a.id ? (
                          <>
                            <span className="text-xs" style={{ color: '#fca5a5' }}>Segur?</span>
                            <button onClick={() => esborra(a)}
                              className="px-3 py-1.5 rounded-lg text-xs font-bold"
                              style={{ background: '#ef4444', color: '#fff' }}>Sí</button>
                            <button onClick={() => setEsborrant(null)}
                              className="px-2 py-1.5 rounded-lg text-xs" style={{ color: '#9aa7b8' }}>No</button>
                          </>
                        ) : (
                          <button onClick={() => setEsborrant(a.id)}
                            disabled={n > 0}
                            title={n > 0 ? 'Té taules: mou-les o esborra-les abans' : 'Esborrar la zona'}
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-30"
                            style={{ background: 'rgba(239,68,68,.18)', color: '#fca5a5' }}>
                            🗑
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ---------- CREAR ZONA ---------- */}
        <div className="rounded-xl p-4" style={{ background: 'rgba(226,176,74,.07)', border: '1px dashed rgba(226,176,74,.35)' }}>
          <div className="text-sm font-bold mb-3" style={{ color: '#e2b04a' }}>➕ Nova zona</div>
          <label className="block mb-3">
            <span className="text-xs block mb-1" style={{ color: '#9aa7b8' }}>Nom de la zona</span>
            <input value={nouNom} onChange={(e) => setNouNom(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void crear(); }}
              placeholder="Barra, Interior, Terrassa, Menjador…"
              className="w-full rounded-lg px-3 py-2 text-sm outline-none"
              style={{ background: 'rgba(255,255,255,.07)', color: '#e5e9f0', border: '1px solid rgba(226,176,74,.25)' }} />
          </label>
          <label className="block mb-4">
            <span className="text-xs block mb-1" style={{ color: '#9aa7b8' }}>
              Recàrrec (%) — per terrassa o zones amb servei extra; deixa 0 si no en té
            </span>
            <input value={nouRecarrec} onChange={(e) => setNouRecarrec(e.target.value)}
              type="number" min="0" step="0.5" inputMode="decimal"
              className="w-28 rounded-lg px-3 py-2 text-sm outline-none"
              style={{ background: 'rgba(255,255,255,.07)', color: '#e5e9f0', border: '1px solid rgba(226,176,74,.25)' }} />
          </label>
          <button onClick={crear} disabled={creant || !nouNom.trim()}
            className="w-full py-2.5 rounded-xl font-bold text-sm disabled:opacity-40"
            style={{ background: '#e2b04a', color: '#1a1a2e' }}>
            {creant ? 'Creant…' : 'Crear la zona'}
          </button>
        </div>

        <p className="text-xs mt-4" style={{ color: '#64748b' }}>
          💡 Després de crear una zona, ves a <b>✥ Editar disposició</b> al pla de sala per afegir-hi
          taules i arrossegar-les al seu lloc.
        </p>
      </div>
    </div>
  );
}

/** Formulari d'edició d'una zona (nom + recàrrec). */
function FormEdicio({
  area,
  onDesa,
  onCancel,
}: {
  area: Area;
  onDesa: (a: Area, nom: string, recarrec: string) => void;
  onCancel: () => void;
}) {
  const [nom, setNom] = useState(area.name);
  const [recarrec, setRecarrec] = useState(String(area.surcharge_percent ?? 0));
  return (
    <div className="space-y-2">
      <input value={nom} onChange={(e) => setNom(e.target.value)} autoFocus
        className="w-full rounded-lg px-3 py-2 text-sm outline-none"
        style={{ background: 'rgba(255,255,255,.08)', color: '#e5e9f0', border: '1px solid rgba(226,176,74,.3)' }} />
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-xs" style={{ color: '#9aa7b8' }}>
          Recàrrec %
          <input value={recarrec} onChange={(e) => setRecarrec(e.target.value)}
            type="number" min="0" step="0.5" inputMode="decimal"
            className="w-20 rounded-lg px-2 py-1.5 text-sm outline-none"
            style={{ background: 'rgba(255,255,255,.08)', color: '#e5e9f0', border: '1px solid rgba(226,176,74,.3)' }} />
        </label>
        <div className="ml-auto flex gap-1">
          <button onClick={() => onDesa(area, nom, recarrec)}
            className="px-3 py-1.5 rounded-lg text-xs font-bold"
            style={{ background: '#e2b04a', color: '#1a1a2e' }}>Desar</button>
          <button onClick={onCancel}
            className="px-3 py-1.5 rounded-lg text-xs" style={{ color: '#9aa7b8' }}>Cancel·lar</button>
        </div>
      </div>
    </div>
  );
}
