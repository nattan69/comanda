'use client';

import { useEffect, useRef, useState } from 'react';
import { api, apiTable, Table, Area, TableComanda, getStoredStaff } from '@/lib/api';

/**
 * PLA DE SALA — taules en la seva POSICIÓ REAL, movibles (decisió Tomeu 14/09/2026).
 *
 * · Les taules es pinten a la seva coordenada (position_x/y) dins l'àrea triada.
 * · Estat visual immediat: lliure / ocupada / reservada / per netejar.
 * · **SALDO PENDENT de cobrar** damunt cada taula (el que el cambrer necessita veure).
 * · Mode edició: arrossega les taules per ajustar-les al lloc real i es guarda.
 * · Doble clic → modal amb el desglossament i CRUD (afegir/anul·lar/cobrar).
 */

type Props = {
  taules: Table[];
  arees: Area[];
  areaActiva: string;
  onRefresca: () => void;
  onObrirTaula: (t: Table) => void;
  /** Canvia l'ESTAT d'una taula (lliure/ocupada/reservada/per netejar/bloquejada). */
  onCanviaEstat?: (t: Table, estat: string) => Promise<void> | void;
};

//: Els ESTATS que es poden triar (els colors del peu del pla de sala).
const ESTATS = [
  { id: 'available',      nom: 'Lliure',       emoji: '🟢' },
  { id: 'occupied',       nom: 'Ocupada',      emoji: '🟡' },
  { id: 'reserved',       nom: 'Reservada',    emoji: '🔵' },
  { id: 'needs_cleaning', nom: 'Per netejar',  emoji: '🧹' },
  { id: 'blocked',        nom: 'Bloquejada',   emoji: '⛔' },
] as const;

const COLOR_ESTAT: Record<string, { bg: string; border: string; text: string }> = {
  available:     { bg: 'rgba(34,197,94,.15)',  border: '#22c55e', text: '#86efac' },
  occupied:      { bg: 'rgba(226,176,74,.20)', border: '#e2b04a', text: '#e2b04a' },
  reserved:      { bg: 'rgba(59,130,246,.15)', border: '#3b82f6', text: '#93c5fd' },
  needs_cleaning:{ bg: 'rgba(148,163,184,.15)',border: '#94a3b8', text: '#cbd5e1' },
  blocked:       { bg: 'rgba(239,68,68,.15)',  border: '#ef4444', text: '#fca5a5' },
};

export default function PlaSala({ taules, arees, areaActiva, onRefresca, onObrirTaula, onCanviaEstat }: Props) {
  const [editMode, setEditMode] = useState(false);
  const [arrossegant, setArrossegant] = useState<string | null>(null);
  const [posLocal, setPosLocal] = useState<Record<string, { x: number; y: number }>>({});
  const [desplaç, setDesplaç] = useState({ x: 0, y: 0 });
  const [canvis, setCanvis] = useState(false);
  const [guardant, setGuardant] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  //: Taula de la qual s'està canviant l'estat (obre el menú de colors)
  const [canviantEstat, setCanviantEstat] = useState<string | null>(null);
  const llenç = useRef<HTMLDivElement>(null);

  const area = arees.find((a) => a.id === areaActiva);
  const visibles = taules.filter((t) => (areaActiva ? t.area_id === areaActiva : true));

  // posició efectiva: la local (si s'està arrossegant) o la del backend
  const pos = (t: Table) => posLocal[t.id] ?? { x: t.position_x, y: t.position_y };

  const mida = (t: Table) => {
    if (t.shape === 'rectangle') return { w: 130, h: 76 };
    if (t.shape === 'round') return { w: 84, h: 84 };
    return { w: 92, h: 92 };
  };

  // ---- arrossegar (només en mode edició) ----
  const començaArrossegament = (e: React.PointerEvent, t: Table) => {
    if (!editMode) return;
    e.preventDefault();
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    setArrossegant(t.id);
    setDesplaç({ x: e.clientX - pos(t).x, y: e.clientY - pos(t).y });
  };

  useEffect(() => {
    if (!arrossegant) return;
    const mou = (e: PointerEvent) => {
      const x = Math.max(0, Math.round(e.clientX - desplaç.x));
      const y = Math.max(0, Math.round(e.clientY - desplaç.y));
      setPosLocal((p) => ({ ...p, [arrossegant]: { x, y } }));
      setCanvis(true);
    };
    const deixa = () => setArrossegant(null);
    window.addEventListener('pointermove', mou);
    window.addEventListener('pointerup', deixa);
    return () => {
      window.removeEventListener('pointermove', mou);
      window.removeEventListener('pointerup', deixa);
    };
  }, [arrossegant, desplaç]);

  const guarda = async () => {
    setGuardant(true); setMsg(null);
    try {
      for (const [id, p] of Object.entries(posLocal)) {
        await apiTable.moveTable(id, p.x, p.y);
      }
      setPosLocal({});
      setCanvis(false);
      setEditMode(false);
      setMsg('✅ Disposició guardada');
      onRefresca();
    } catch (e) {
      setMsg(e instanceof Error ? `Error: ${e.message}` : 'Error guardant');
    } finally { setGuardant(false); }
  };

  const descarta = () => { setPosLocal({}); setCanvis(false); setEditMode(false); setMsg(null); };

  const ocupa = (t: Table) => t.status === 'occupied' || (t.pending_amount ?? 0) > 0;

  return (
    <div>
      {/* barra d'eines */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-3 text-sm">
          <span style={{ color: '#9aa7b8' }}>
            {visibles.length} {visibles.length === 1 ? 'taula' : 'taules'}
            {area ? ` · ${area.name}` : ''}
            {area && Number(area.surcharge_percent) > 0 ? ` (+${area.surcharge_percent}% recàrrec)` : ''}
          </span>
          {msg && <span style={{ color: msg.startsWith('✅') ? '#86efac' : '#fca5a5' }}>{msg}</span>}
        </div>
        <div className="flex items-center gap-2">
          {editMode ? (
            <>
              <button onClick={guarda} disabled={guardant || !canvis}
                className="px-4 py-2 rounded-xl text-sm font-semibold disabled:opacity-40"
                style={{ background: '#22c55e', color: '#052e16' }}>
                {guardant ? 'Guardant…' : '💾 Guardar disposició'}
              </button>
              <button onClick={descarta} className="px-4 py-2 rounded-xl text-sm"
                style={{ background: 'rgba(255,255,255,.08)', color: '#e5e9f0' }}>
                Descartar
              </button>
            </>
          ) : (
            <button onClick={() => { setEditMode(true); setMsg('🎯 Arrossega les taules per ajustar-les al lloc real'); }}
              className="px-4 py-2 rounded-xl text-sm font-semibold"
              style={{ background: 'rgba(226,176,74,.18)', color: '#e2b04a' }}>
              ✥ Editar disposició
            </button>
          )}
        </div>
      </div>

      {/* llenç de la sala */}
      <div ref={llenç}
        className="relative rounded-2xl"
        style={{
          minHeight: 420,
          background: 'rgba(255,255,255,.03)',
          border: editMode ? '2px dashed rgba(226,176,74,.5)' : '1px solid rgba(255,255,255,.08)',
          touchAction: editMode ? 'none' : 'auto',
          overflow: 'auto',
        }}>
        {visibles.map((t) => {
          const p = pos(t);
          const m = mida(t);
          const c = COLOR_ESTAT[t.status] || COLOR_ESTAT.available;
          const pendent = Number(t.pending_amount || 0);
          return (
            <div key={t.id}
              onPointerDown={(e) => començaArrossegament(e, t)}
              onDoubleClick={() => { if (!editMode) onObrirTaula(t); }}
              onContextMenu={(e) => { e.preventDefault(); if (!editMode) setCanviantEstat(t.id); }}
              title={editMode ? 'Arrossega per moure' : 'Doble clic per veure la comanda'}
              className="absolute flex flex-col items-center justify-center select-none"
              style={{
                left: p.x, top: p.y, width: m.w, height: m.h,
                background: c.bg, border: `2px solid ${c.border}`,
                borderRadius: t.shape === 'round' ? '50%' : t.shape === 'rectangle' ? 14 : 10,
                cursor: editMode ? (arrossegant === t.id ? 'grabbing' : 'grab') : 'pointer',
                transition: arrossegant === t.id ? 'none' : 'all .15s',
                boxShadow: ocupa(t) ? `0 0 0 3px rgba(226,176,74,.15)` : 'none',
              }}>
              <span className="font-bold" style={{ color: c.text, fontSize: 18, lineHeight: 1.1 }}>
                {t.number}
              </span>
              <span style={{ color: '#9aa7b8', fontSize: 10 }}>{t.seats}p</span>
              {/* botonet per canviar l'estat (els colors del peu) — sense doble clic ni clic llarg */}
              {!editMode && (
                <button
                  onClick={(e) => { e.stopPropagation(); setCanviantEstat(canviantEstat === t.id ? null : t.id); }}
                  title="Canviar l'estat de la taula"
                  className="absolute -top-2 -right-2 w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center"
                  style={{ background: c.border, color: '#1a1a2e', border: '2px solid #1a1a2e' }}>
                  ⌄
                </button>
              )}
              {pendent > 0 && (
                <span className="absolute -bottom-2 px-2 py-0.5 rounded-full font-bold"
                  style={{ background: '#e2b04a', color: '#1a1a2e', fontSize: 11 }}>
                  {pendent.toFixed(2)}€
                </span>
              )}

              {/* === MENÚ D'ESTATS (els colors del peu) ===
                  S'obre amb el botonet ⌄ de la taula. Permet posar-la lliure,
                  ocupada, reservada, per netejar o bloquejada — els mateixos
                  colors de la llegenda del peu (decisió Tomeu 14/09/2026). */}
              {!editMode && canviantEstat === t.id && (
                <div className="absolute z-30 flex flex-col gap-1 p-2 rounded-xl"
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    top: m.h + 6, left: 0, minWidth: 150,
                    background: '#141429', border: '1px solid rgba(226,176,74,.35)',
                    boxShadow: '0 8px 24px rgba(0,0,0,.5)',
                  }}>
                  <span className="text-[10px] uppercase font-bold px-1" style={{ color: '#9aa7b8' }}>
                    Estat de la taula
                  </span>
                  {ESTATS.map((e) => (
                    <button key={e.id}
                      onClick={async () => {
                        setCanviantEstat(null);
                        if (onCanviaEstat) await onCanviaEstat(t, e.id);
                      }}
                      className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-xs font-semibold"
                      style={{
                        background: t.status === e.id ? 'rgba(226,176,74,.2)' : 'transparent',
                        color: '#e5e9f0',
                      }}>
                      <span className="inline-block w-3 h-3 rounded-full shrink-0"
                        style={{ background: COLOR_ESTAT[e.id]?.border }} />
                      {e.emoji} {e.nom}
                      {t.status === e.id && <span className="ml-auto" style={{ color: '#e2b04a' }}>✓</span>}
                    </button>
                  ))}
                  {t.status === 'occupied' && (
                    <span className="text-[10px] px-1 mt-1" style={{ color: '#fca5a5' }}>
                      ⚠️ Està ocupada; alliberar-la no cobra la comanda
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {visibles.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-sm" style={{ color: '#64748b' }}>
            No hi ha taules en aquesta àrea
          </div>
        )}
      </div>

      {/* llegenda */}
      <div className="flex items-center gap-5 mt-4 flex-wrap text-xs" style={{ color: '#9aa7b8' }}>
        {Object.entries({ available: 'Lliure', occupied: 'Ocupada', reserved: 'Reservada', needs_cleaning: 'Per netejar', blocked: 'Bloquejada' }).map(([k, nom]) => (
          <span key={k} className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full" style={{ background: COLOR_ESTAT[k]?.border }} />
            {nom}
          </span>
        ))}
        <span className="flex items-center gap-2">
          <span className="px-2 rounded-full font-bold" style={{ background: '#e2b04a', color: '#1a1a2e', fontSize: 10 }}>0.00€</span>
          saldo pendent
        </span>
      </div>
    </div>
  );
}
