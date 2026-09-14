'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, apiTable, CompteTaula, ComandaDelCompte } from '@/lib/api';

/**
 * MODAL DE LA TAULA (doble clic al pla de sala) — decisions Tomeu 14-15/09/2026.
 *
 * Desglossament del COMPTE obert amb:
 *   · una o DIVERSES comandes (quan s'ha dividit el compte)
 *   · MODIFICAR una línia (quantitat)      → PATCH
 *   · ANUL·LAR una línia                   → void
 *   · ✂️ MOURE línies a una altra comanda  → tiquets separats (compartir compte)
 *   · COBRAR (una comanda o tot el compte)
 *   · AFEGIR articles
 *
 * COMPARTIR EL COMPTE (allò que faltava):
 *   Es marquen les línies que vol separar (les del client que paga a part), es
 *   prem «✂️ Mou a una altra comanda» i s'hi crea una comanda nova. A partir
 *   d'aquí es poden COBRAR PER SEPARAT: cada comanda té el seu tiquet.
 */
export default function ModalTaula({
  tableId, tableNumber, onTancar, onRefresca, onCobrar, onAfegir,
}: {
  tableId: string;
  tableNumber: string;
  onTancar: () => void;
  onRefresca: () => void;
  onCobrar: (orderId: string) => void;
  onAfegir: (tableId: string) => void;
}) {
  const [compte, setCompte] = useState<CompteTaula | null>(null);
  const [carregant, setCarregant] = useState(true);
  const [editable, setEditable] = useState<string | null>(null);
  const [novaQty, setNovaQty] = useState(1);
  const [ocupat, setOcupat] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  //: línies marcades per moure a una altra comanda (compartir el compte)
  const [marcades, setMarcades] = useState<Set<string>>(new Set());
  const [modeMoure, setModeMoure] = useState(false);

  const carrega = useCallback(async () => {
    try {
      setCompte(await apiTable.getCompte(tableId));
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error carregant el compte' });
    } finally { setCarregant(false); }
  }, [tableId]);

  useEffect(() => { void carrega(); }, [carrega]);

  const refrescaTot = async () => { await carrega(); onRefresca(); };

  const modifica = async (orderId: string, lineId: string, qty: number) => {
    setOcupat(true); setMsg(null);
    try {
      await apiTable.updateLine(orderId, lineId, qty);
      setMsg({ ok: true, text: 'Línia modificada ✅' });
      setEditable(null);
      await refrescaTot();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error modificant' });
    } finally { setOcupat(false); }
  };

  const anulla = async (orderId: string, lineId: string) => {
    setOcupat(true); setMsg(null);
    try {
      await apiTable.voidLine(orderId, lineId);
      setMsg({ ok: true, text: 'Línia anul·lada ✅' });
      await refrescaTot();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error anul·lant' });
    } finally { setOcupat(false); }
  };

  /** Mou les línies marcades a una comanda NOVA (tiquet separat). */
  const mou = async (origenId: string) => {
    const ids = Array.from(marcades);
    if (!ids.length) return;
    setOcupat(true); setMsg(null);
    try {
      await apiTable.moureLinies(origenId, ids);
      setMsg({ ok: true, text: '✂️ Comanda separada — ara es poden cobrar per separat' });
      setMarcades(new Set());
      setModeMoure(false);
      await refrescaTot();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error movent les línies' });
    } finally { setOcupat(false); }
  };

  const alternaMarca = (lineId: string) => {
    setMarcades((m) => {
      const n = new Set(m);
      if (n.has(lineId)) n.delete(lineId); else n.add(lineId);
      return n;
    });
  };

  const pendent = compte?.total_pendent ?? 0;
  const nComandes = compte?.comandes.length ?? 0;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      style={{ background: 'rgba(0,0,0,.65)' }} onClick={onTancar}>
      <div className="w-full sm:max-w-2xl rounded-t-2xl sm:rounded-2xl max-h-[90vh] overflow-y-auto"
        style={{ background: '#1a1a2e', border: '1px solid rgba(226,176,74,.3)' }}
        onClick={(e) => e.stopPropagation()}>

        {/* capçalera */}
        <div className="sticky top-0 z-10 px-5 py-4 flex items-center justify-between"
          style={{ background: '#1a1a2e', borderBottom: '1px solid rgba(226,176,74,.2)' }}>
          <div>
            <div className="text-xl font-bold" style={{ color: '#e2b04a' }}>Taula {tableNumber}</div>
            <div className="text-xs" style={{ color: '#9aa7b8' }}>
              {compte?.open
                ? (nComandes > 1
                    ? `compte compartit · ${nComandes} comandes`
                    : 'comanda oberta')
                : 'sense comanda oberta'}
            </div>
          </div>
          <button onClick={onTancar} className="text-2xl px-2" style={{ color: '#9aa7b8' }}>×</button>
        </div>

        {msg && (
          <div className="mx-5 mt-3 px-4 py-2 rounded-lg text-sm"
            style={{ background: msg.ok ? 'rgba(34,197,94,.15)' : 'rgba(239,68,68,.15)',
                     color: msg.ok ? '#86efac' : '#fca5a5' }}>
            {msg.text}
          </div>
        )}

        {carregant ? (
          <div className="px-5 py-10 text-center text-sm" style={{ color: '#9aa7b8' }}>Carregant el compte…</div>
        ) : compte?.open ? (
          <>
            {/* ---------- BARRA D'ACCIONS DE COMPTE ---------- */}
            <div className="px-5 pt-4 flex items-center gap-2 flex-wrap">
              {nComandes > 1 && (
                <span className="text-xs px-2 py-1 rounded-lg"
                  style={{ background: 'rgba(226,176,74,.15)', color: '#e2b04a' }}>
                  ✂️ {nComandes} comandes separades
                </span>
              )}
              <button onClick={() => { setModeMoure((v) => !v); setMarcades(new Set()); }}
                className="ml-auto px-3 py-2 rounded-xl text-sm font-semibold"
                style={{
                  background: modeMoure ? '#e2b04a' : 'rgba(226,176,74,.15)',
                  color: modeMoure ? '#1a1a2e' : '#e2b04a',
                  border: '1px solid rgba(226,176,74,.35)',
                }}>
                {modeMoure ? '✕ Cancel·lar selecció' : '✂️ Compartir el compte'}
              </button>
            </div>

            {modeMoure && (
              <div className="mx-5 mt-3 px-4 py-3 rounded-xl text-sm"
                style={{ background: 'rgba(226,176,74,.08)', color: '#e2b04a' }}>
                Marca les línies que vol separar i prem <b>Mou a una altra comanda</b>.
                Es crearà un tiquet a part, que després podràs cobrar per separat.
                {marcades.size > 0 && (
                  <div className="mt-3">
                    <button onClick={() => mou(compte.comandes[0].id)} disabled={ocupat}
                      className="w-full py-2.5 rounded-xl font-bold disabled:opacity-40"
                      style={{ background: '#e2b04a', color: '#1a1a2e' }}>
                      ✂️ Mou {marcades.size} {marcades.size === 1 ? 'línia' : 'línies'} a una altra comanda
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* ---------- LES COMANDES ---------- */}
            {compte.comandes.map((c: ComandaDelCompte, idx) => (
              <div key={c.id} className="mx-5 mt-4 rounded-2xl overflow-hidden"
                style={{ border: '1px solid rgba(255,255,255,.1)' }}>

                {/* capçalera de la comanda */}
                <div className="px-4 py-2.5 flex items-center justify-between"
                  style={{ background: 'rgba(255,255,255,.05)' }}>
                  <div className="flex items-center gap-2">
                    <span className="font-bold" style={{ color: '#e5e9f0' }}>
                      Comanda nº {c.comanda_number}
                    </span>
                    {nComandes > 1 && (
                      <span className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: 'rgba(226,176,74,.15)', color: '#e2b04a' }}>
                        tiquet {idx + 1} de {nComandes}
                      </span>
                    )}
                  </div>
                  <span className="font-bold" style={{ color: '#e2b04a' }}>{c.pending_amount.toFixed(2)}€</span>
                </div>

                {/* línies */}
                <div className="px-4 py-3 space-y-2">
                  {c.lines.map((l) => {
                    const marcada = marcades.has(l.id);
                    return (
                      <div key={l.id} className="rounded-xl px-3 py-2.5"
                        style={{
                          background: marcada ? 'rgba(226,176,74,.12)' : 'rgba(255,255,255,.04)',
                          border: marcada ? '1px solid #e2b04a' : '1px solid transparent',
                        }}>
                        <div className="flex items-center justify-between gap-2">
                          {/* casella per seleccionar (mode compartir) */}
                          {modeMoure && l.status !== 'cancelled' && (
                            <input type="checkbox" checked={marcada}
                              onChange={() => alternaMarca(l.id)}
                              className="w-5 h-5 shrink-0 accent-amber-400" />
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="font-semibold truncate" style={{ color: '#e5e9f0' }}>{l.name}</div>
                            <div className="text-xs" style={{ color: '#9aa7b8' }}>
                              {l.unit_price.toFixed(2)}€ · IVA {l.vat_rate ?? '—'}%
                              {l.modifications?.length ? ` · ${l.modifications.join(', ')}` : ''}
                              {l.status === 'cancelled' ? ' · ANUL·LADA' : ''}
                            </div>
                          </div>
                          {editable === l.id ? (
                            <div className="flex items-center gap-1 shrink-0">
                              <button onClick={() => setNovaQty(Math.max(1, novaQty - 1))}
                                className="w-8 h-8 rounded-lg font-bold"
                                style={{ background: 'rgba(255,255,255,.1)', color: '#e5e9f0' }}>−</button>
                              <span className="w-7 text-center font-bold" style={{ color: '#e2b04a' }}>{novaQty}</span>
                              <button onClick={() => setNovaQty(novaQty + 1)}
                                className="w-8 h-8 rounded-lg font-bold"
                                style={{ background: '#e2b04a', color: '#1a1a2e' }}>+</button>
                              <button onClick={() => modifica(c.id, l.id, novaQty)} disabled={ocupat}
                                className="px-3 h-8 rounded-lg text-sm font-semibold"
                                style={{ background: '#22c55e', color: '#052e16' }}>✓</button>
                              <button onClick={() => setEditable(null)}
                                className="px-2 h-8 rounded-lg text-sm" style={{ color: '#9aa7b8' }}>✕</button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 shrink-0">
                              <span className="text-lg font-bold" style={{ color: '#e2b04a' }}>{l.quantity}×</span>
                              <span className="font-bold" style={{ color: '#e5e9f0' }}>{l.amount.toFixed(2)}€</span>
                              <button onClick={() => { setEditable(l.id); setNovaQty(l.quantity); }}
                                disabled={l.status === 'cancelled' || modeMoure}
                                className="px-2 py-1 rounded-lg text-xs disabled:opacity-30"
                                style={{ background: 'rgba(255,255,255,.08)', color: '#e5e9f0' }}>✎</button>
                              <button onClick={() => anulla(c.id, l.id)}
                                disabled={l.status === 'cancelled' || ocupat || modeMoure}
                                className="px-2 py-1 rounded-lg text-xs disabled:opacity-30"
                                style={{ background: 'rgba(239,68,68,.18)', color: '#fca5a5' }}>🗑</button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {c.lines.length === 0 && (
                    <div className="text-center py-4 text-sm" style={{ color: '#64748b' }}>
                      Aquesta comanda no té línies
                    </div>
                  )}
                </div>

                {/* cobrar aquesta comanda (tiquet) */}
                {nComandes > 1 && (
                  <div className="px-4 pb-3">
                    <button onClick={() => onCobrar(c.id)} disabled={c.pending_amount <= 0}
                      className="w-full py-2.5 rounded-xl font-bold text-sm disabled:opacity-40"
                      style={{ background: '#22c55e', color: '#052e16' }}>
                      💰 Cobrar només aquesta comanda ({c.pending_amount.toFixed(2)}€)
                    </button>
                  </div>
                )}
              </div>
            ))}

            {/* ---------- TOTALS ---------- */}
            <div className="px-5 py-4 space-y-1" style={{ borderTop: '1px solid rgba(255,255,255,.08)' }}>
              <div className="flex justify-between text-lg font-bold" style={{ color: '#e2b04a' }}>
                <span>PENDENT DE COBRAR{nComandes > 1 ? ' (tot el compte)' : ''}</span>
                <span>{pendent.toFixed(2)}€</span>
              </div>
            </div>

            {/* ---------- ACCIONS ---------- */}
            <div className="px-5 pb-5 flex gap-3">
              <button onClick={() => onAfegir(tableId)}
                className="flex-1 rounded-xl font-semibold"
                style={{ height: 48, background: 'rgba(226,176,74,.18)', color: '#e2b04a' }}>
                + Afegir articles
              </button>
              <button onClick={() => onCobrar(compte.comandes[0].id)} disabled={pendent <= 0}
                className="flex-1 rounded-xl font-bold disabled:opacity-40"
                style={{ height: 48, background: '#22c55e', color: '#052e16' }}>
                💰 Cobrar {nComandes > 1 ? 'tot' : ''} {pendent.toFixed(2)}€
              </button>
            </div>
          </>
        ) : (
          <div className="px-5 py-10 text-center">
            <div className="text-4xl mb-3">🍽️</div>
            <div className="text-sm mb-5" style={{ color: '#9aa7b8' }}>Aquesta taula no té cap comanda oberta</div>
            <button onClick={() => onAfegir(tableId)}
              className="px-6 rounded-xl font-bold"
              style={{ height: 48, background: '#e2b04a', color: '#1a1a2e' }}>
              + Prendre comanda
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
