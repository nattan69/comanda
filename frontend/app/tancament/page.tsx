'use client';

import { useEffect, useState } from 'react';
import { api, DayClosure } from '@/lib/api';

/**
 * Tancament del dia — X (parcial, no reseteja) i Z (tancament oficial).
 * Contracte backend: POST /closure/x · POST /closure/run · GET /closure.
 */
export default function TancamentPage() {
  const [closures, setClosures] = useState<DayClosure[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const carrega = async () => {
    setLoading(true);
    try { setClosures(await api.getClosures()); }
    catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error carregant' }); }
    finally { setLoading(false); }
  };

  useEffect(() => { carrega(); }, []);

  const fesX = async () => {
    setBusy('x');
    try {
      const r = await api.runClosureX();
      setMsg({ ok: true, text: 'Tancament X fet (no reseteja la caixa)' });
      console.log('X:', r);
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error al X' });
    } finally { setBusy(null); }
  };

  const fesZ = async () => {
    if (!confirm('Tancament Z: tanca el dia OFICIALMENT (reseteja). Segur?')) return;
    setBusy('z');
    try {
      const r = await api.runClosureZ();
      setMsg({ ok: true, text: 'Tancament Z fet — dia tancat' });
      console.log('Z:', r);
      carrega();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error al Z' });
    } finally { setBusy(null); }
  };

  const fmt = (n?: number) =>
    n == null ? '—' : `${n.toLocaleString('ca-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-brand-gold">Tancament del dia</h1>

      {msg && (
        <div className={`p-3 rounded-lg text-sm ${msg.ok ? 'bg-green-500/15 text-green-300' : 'bg-red-500/15 text-red-300'}`}>
          {msg.text}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <button onClick={fesX} disabled={busy !== null}
          className="p-6 rounded-2xl border border-brand-gold/30 bg-brand-dark hover:border-brand-gold transition disabled:opacity-40 text-left">
          <div className="text-3xl mb-2">🧾</div>
          <div className="font-bold text-white mb-1">Tancament X</div>
          <div className="text-xs text-gray-400">Arqueig parcial — lectura de caixa, no reseteja</div>
        </button>
        <button onClick={fesZ} disabled={busy !== null}
          className="p-6 rounded-2xl border border-red-500/40 bg-brand-dark hover:border-red-400 transition disabled:opacity-40 text-left">
          <div className="text-3xl mb-2">🔒</div>
          <div className="font-bold text-white mb-1">Tancament Z</div>
          <div className="text-xs text-gray-400">Tancament oficial del dia — reseteja la caixa</div>
        </button>
      </div>

      <div className="bg-brand-dark border border-brand-gold/20 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-white">Històric de tancaments</h2>
          <button onClick={carrega} className="text-xs text-brand-gold hover:underline">↻ refrescar</button>
        </div>
        {loading ? (
          <p className="text-gray-400 text-sm">Carregant…</p>
        ) : closures.length === 0 ? (
          <p className="text-gray-500 text-sm">Encara no hi ha tancaments.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-400 border-b border-brand-gold/20">
                <th className="py-2">Data</th>
                <th>Estat</th>
                <th className="text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {closures.map((c) => (
                <tr key={c.id} className="border-b border-white/5">
                  <td className="py-2">{c.closure_date}</td>
                  <td>{c.status || '—'}</td>
                  <td className="text-right font-mono">{fmt(c.totals?.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}