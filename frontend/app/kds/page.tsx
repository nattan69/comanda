'use client';

import { useEffect, useState } from 'react';
import { useKds } from '@/lib/useKds';
import { api, apiCarta, Center } from '@/lib/api';

/**
 * KDS — Pantalla de Cuina (Kitchen Display System).
 * Pantalla gran i fosca per posar a la cuina: les comandes entren soles
 * (WebSocket) i es marca com a preparada amb un toc.
 * Pensada per veure's de lluny: xifres i lletra grans, colors forts.
 */
export default function Kds() {
  const { cua, status, marcarPreparada } = useKds();
  const [centres, setCentres] = useState<Center[]>([]);
  const [filtre, setFiltre] = useState<string>('');
  const [ara, setAra] = useState(Date.now());

  useEffect(() => {
    apiCarta.getCenters().then(setCentres).catch(() => {});
  }, []);

  // rellotge per mostrar el temps transcorregut de cada comanda
  useEffect(() => {
    const t = setInterval(() => setAra(Date.now()), 10000);
    return () => clearInterval(t);
  }, []);

  const visibles = filtre ? cua.filter((c) => c.centre === filtre) : cua;
  const minut = (t: number) => Math.floor((ara - t) / 60000);
  const colorTemps = (min: number) =>
    min < 5 ? '#86efac' : min < 12 ? '#fcd34d' : '#fca5a5';
  const nomCentre = (id?: string | null) => centres.find((c) => c.id === id)?.name || '';

  return (
    <div className="min-h-screen p-5" style={{ background: '#0b1220' }}>
      {/* capçalera */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold" style={{ color: '#e2b04a' }}>🍳 Cuina</h1>
          <span className="text-sm px-3 py-1 rounded-full"
            style={{
              background: status === 'viu' ? 'rgba(34,197,94,.15)' : status === 'connectant' ? 'rgba(252,211,77,.15)' : 'rgba(239,68,68,.15)',
              color: status === 'viu' ? '#86efac' : status === 'connectant' ? '#fcd34d' : '#fca5a5',
            }}>
            {status === 'viu' ? '● en viu' : status === 'connectant' ? 'connectant…' : 'desconnectat'}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => setFiltre('')}
            className="px-4 py-2 rounded-xl text-sm font-semibold"
            style={{ background: filtre === '' ? '#e2b04a' : 'rgba(255,255,255,.07)', color: filtre === '' ? '#1a1a2e' : '#e5e9f0' }}>
            Tots ({cua.length})
          </button>
          {centres.map((c) => {
            const n = cua.filter((x) => x.centre === c.id).length;
            return (
              <button key={c.id} onClick={() => setFiltre(c.id)}
                className="px-4 py-2 rounded-xl text-sm font-semibold"
                style={{ background: filtre === c.id ? '#e2b04a' : 'rgba(255,255,255,.07)', color: filtre === c.id ? '#1a1a2e' : '#e5e9f0' }}>
                {c.name} ({n})
              </button>
            );
          })}
        </div>
      </div>

      {/* cua de comandes */}
      {visibles.length === 0 ? (
        <div className="text-center py-24">
          <div className="text-6xl mb-4">✅</div>
          <div className="text-xl" style={{ color: '#9aa7b8' }}>Cap comanda pendent</div>
          <div className="text-sm mt-2" style={{ color: '#64748b' }}>
            Les comandes noves apareixeran aquí tot soles
          </div>
        </div>
      ) : (
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
          {visibles.sort((a, b) => a.creada - b.creada).map((c) => {
            const min = minut(c.creada);
            return (
              <div key={c.id} className="rounded-2xl p-5 flex flex-col"
                style={{ background: 'rgba(255,255,255,.05)', border: `2px solid ${colorTemps(min)}` }}>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-2xl font-bold" style={{ color: '#e5e9f0' }}>
                      {/* El NOMBRE de taula (M1, T3...), no l'UUID! */}
                      Taula {c.table_number ?? '—'}
                      {c.comanda_number ? (
                        <span className="ml-2 text-base" style={{ color: '#e2b04a' }}>
                          #{c.comanda_number}
                        </span>
                      ) : null}
                    </div>
                    {nomCentre(c.centre) && (
                      <div className="text-xs mt-1" style={{ color: '#9aa7b8' }}>{nomCentre(c.centre)}</div>
                    )}
                    {/* Cambrer: per si la cuina ha d'aclarir alguna cosa (Tomeu 14/09/2026) */}
                    {c.staff_name && (
                      <div className="text-xs mt-0.5" style={{ color: '#e2b04a' }}>
                        👤 {c.staff_name}
                      </div>
                    )}
                  </div>
                  <div className="text-2xl font-bold" style={{ color: colorTemps(min) }}>
                    {min}′
                  </div>
                </div>

                <div className="flex-1 space-y-2 mb-4">
                  {c.items.length > 0 ? c.items.map((it, i) => (
                    <div key={i} className="flex items-baseline gap-3 flex-wrap">
                      <span className="text-2xl font-bold" style={{ color: '#e2b04a', minWidth: 40 }}>
                        {it.quantity}×
                      </span>
                      <div className="flex-1">
                        <span className="text-lg" style={{ color: '#e5e9f0' }}>{it.name}</span>
                        {/* Modificacions: «sense ceba», «poc fet»... — la cuina les ha de veure */}
                        {Array.isArray(it.modifications) && it.modifications.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-2">
                            {it.modifications.map((m, j) => (
                              <span key={j} className="px-2 py-0.5 rounded-lg text-sm font-bold"
                                style={{ background: 'rgba(239,68,68,.18)', color: '#fca5a5' }}>
                                {m}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )) : (
                    <div className="text-sm" style={{ color: '#64748b' }}>carregant detall…</div>
                  )}
                </div>

                <button onClick={() => marcarPreparada(c.id)}
                  className="w-full rounded-xl font-bold text-lg transition active:scale-95"
                  style={{ height: 56, background: '#22c55e', color: '#052e16' }}>
                  ✓ Preparada
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}