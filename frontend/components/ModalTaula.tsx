'use client';

import { useState } from 'react';
import { api, apiTable, TableComanda } from '@/lib/api';

/**
 * MODAL DE LA TAULA (doble clic al pla de sala) — decisió Tomeu 14/09/2026.
 * Desglossament de la comanda oberta amb CRUD:
 *   · MODIFICAR una línia (quantitat)  → PATCH
 *   · ANUL·LAR una línia               → void
 *   · COBRAR la comanda                 → ModalCobrar (reutilitzat)
 *   · AFEGIR articles (si la taula és buida) → porta a la presa de comanda
 */
export default function ModalTaula({
  tableId, tableNumber, comanda, onTancar, onRefresca, onCobrar, onAfegir,
}: {
  tableId: string;
  tableNumber: string;
  comanda: TableComanda;
  onTancar: () => void;
  onRefresca: () => void;
  onCobrar: (orderId: string) => void;
  onAfegir: (tableId: string) => void;
}) {
  const [editable, setEditable] = useState<string | null>(null);
  const [novaQty, setNovaQty] = useState(1);
  const [ocupat, setOcupat] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const pendent = comanda.pending_amount ?? 0;

  const modifica = async (lineId: string, qty: number) => {
    setOcupat(true); setMsg(null);
    try {
      await apiTable.updateLine(comanda.order_id!, lineId, qty);
      setMsg({ ok: true, text: 'Línia modificada ✅' });
      setEditable(null);
      onRefresca();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error modificant' });
    } finally { setOcupat(false); }
  };

  const anulla = async (lineId: string) => {
    setOcupat(true); setMsg(null);
    try {
      await apiTable.voidLine(comanda.order_id!, lineId);
      setMsg({ ok: true, text: 'Línia anul·lada ✅' });
      onRefresca();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error anul·lant' });
    } finally { setOcupat(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      style={{ background: 'rgba(0,0,0,.65)' }} onClick={onTancar}>
      <div className="w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl max-h-[88vh] overflow-y-auto"
        style={{ background: '#1a1a2e', border: '1px solid rgba(226,176,74,.3)' }}
        onClick={(e) => e.stopPropagation()}>

        {/* capçalera */}
        <div className="sticky top-0 px-5 py-4 flex items-center justify-between"
          style={{ background: '#1a1a2e', borderBottom: '1px solid rgba(226,176,74,.2)' }}>
          <div>
            <div className="text-xl font-bold" style={{ color: '#e2b04a' }}>Taula {tableNumber}</div>
            <div className="text-xs" style={{ color: '#9aa7b8' }}>
              {comanda.open ? `comanda oberta · ${comanda.status}` : 'sense comanda oberta'}
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

        {comanda.open ? (
          <>
            {/* línies */}
            <div className="px-5 py-4 space-y-2">
              {comanda.lines.map((l) => (
                <div key={l.id} className="rounded-xl px-4 py-3"
                  style={{ background: 'rgba(255,255,255,.05)' }}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex-1">
                      <div className="font-semibold" style={{ color: '#e5e9f0' }}>{l.name}</div>
                      <div className="text-xs" style={{ color: '#9aa7b8' }}>
                        {l.unit_price.toFixed(2)}€ · IVA {l.vat_rate ?? '—'}%
                        {l.modifications?.length ? ` · ${l.modifications.join(', ')}` : ''}
                        {l.status === 'cancelled' ? ' · ANUL·LADA' : ''}
                      </div>
                    </div>
                    {editable === l.id ? (
                      <div className="flex items-center gap-2">
                        <button onClick={() => setNovaQty(Math.max(1, novaQty - 1))}
                          className="w-8 h-8 rounded-lg font-bold"
                          style={{ background: 'rgba(255,255,255,.1)', color: '#e5e9f0' }}>−</button>
                        <span className="w-8 text-center font-bold" style={{ color: '#e2b04a' }}>{novaQty}</span>
                        <button onClick={() => setNovaQty(novaQty + 1)}
                          className="w-8 h-8 rounded-lg font-bold"
                          style={{ background: '#e2b04a', color: '#1a1a2e' }}>+</button>
                        <button onClick={() => modifica(l.id, novaQty)} disabled={ocupat}
                          className="px-3 h-8 rounded-lg text-sm font-semibold"
                          style={{ background: '#22c55e', color: '#052e16' }}>✓</button>
                        <button onClick={() => setEditable(null)}
                          className="px-2 h-8 rounded-lg text-sm" style={{ color: '#9aa7b8' }}>✕</button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold" style={{ color: '#e2b04a' }}>{l.quantity}×</span>
                        <span className="font-bold" style={{ color: '#e5e9f0' }}>{l.amount.toFixed(2)}€</span>
                        <button onClick={() => { setEditable(l.id); setNovaQty(l.quantity); }}
                          disabled={l.status === 'cancelled'}
                          className="px-2 py-1 rounded-lg text-xs"
                          style={{ background: 'rgba(255,255,255,.08)', color: '#e5e9f0' }}>✎</button>
                        <button onClick={() => anulla(l.id)} disabled={l.status === 'cancelled' || ocupat}
                          className="px-2 py-1 rounded-lg text-xs disabled:opacity-30"
                          style={{ background: 'rgba(239,68,68,.18)', color: '#fca5a5' }}>🗑</button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {comanda.lines.length === 0 && (
                <div className="text-center py-6 text-sm" style={{ color: '#64748b' }}>Cap article a la comanda</div>
              )}
            </div>

            {/* totals */}
            <div className="px-5 py-3 space-y-1" style={{ borderTop: '1px solid rgba(255,255,255,.08)' }}>
              <div className="flex justify-between text-sm" style={{ color: '#9aa7b8' }}>
                <span>Total</span><span>{comanda.total_amount.toFixed(2)}€</span>
              </div>
              {comanda.discount_amount > 0 && (
                <div className="flex justify-between text-sm" style={{ color: '#9aa7b8' }}>
                  <span>Descompte</span><span>−{comanda.discount_amount.toFixed(2)}€</span>
                </div>
              )}
              {comanda.paid_amount > 0 && (
                <div className="flex justify-between text-sm" style={{ color: '#86efac' }}>
                  <span>Ja cobrat</span><span>{comanda.paid_amount.toFixed(2)}€</span>
                </div>
              )}
              <div className="flex justify-between text-lg font-bold" style={{ color: '#e2b04a' }}>
                <span>PENDENT DE COBRAR</span><span>{pendent.toFixed(2)}€</span>
              </div>
            </div>

            {/* accions */}
            <div className="px-5 py-4 flex gap-3" style={{ borderTop: '1px solid rgba(255,255,255,.08)' }}>
              <button onClick={() => onAfegir(tableId)}
                className="flex-1 rounded-xl font-semibold"
                style={{ height: 48, background: 'rgba(226,176,74,.18)', color: '#e2b04a' }}>
                + Afegir articles
              </button>
              <button onClick={() => onCobrar(comanda.order_id!)} disabled={pendent <= 0}
                className="flex-1 rounded-xl font-bold disabled:opacity-40"
                style={{ height: 48, background: '#22c55e', color: '#052e16' }}>
                💰 Cobrar {pendent.toFixed(2)}€
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
