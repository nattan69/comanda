'use client';

import { useEffect, useState } from 'react';
import { api, DayClosure, LiquidacionsCambrers } from '@/lib/api';
import PanellLiquidacionsCambrers from '@/components/PanellLiquidacionsCambrers';

/**
 * Tancament del dia — X (parcial, no reseteja) i Z (tancament oficial).
 * Contracte backend: POST /closure/x · POST /closure/run · GET /closure.
 *
 * La X i la Z duen la LIQUIDACIÓ DE TOTS ELS CAMBRERS del centre, perquè
 * l'encarregat la repassi abans de firmar el tancament (decisió Tomeu
 * 18/09/2026).
 */
export default function TancamentPage() {
  const [closures, setClosures] = useState<DayClosure[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  //: Liquidacions dels cambrers de l'últim informe emès (X o Z).
  const [liquidacions, setLiquidacions] = useState<LiquidacionsCambrers | null>(null);
  //: Avís de la darrera impressió.
  const [impressió, setImpressió] = useState<string | null>(null);

  /**
   * IMPRIMEIX A LA TÈRMICA DE TIQUETS (decisió Tomeu 18/09/2026).
   *
   * La Z i el full de liquidacions van a la MATEIXA impressora de 80 mm que
   * els tiquets. Si no n'hi ha cap de configurada, s'obre el document per
   * imprimir-lo en un full normal (s'ha de poder firmar igualment).
   */
  const imprimirDoc = async (quin: 'x' | 'z' | 'liquidacions' | 'refer-x') => {
    setImpressió(null);
    try {
      const { imprimeixX, imprimeixZ, imprimeixLiquidacioCentre, obreDocumentText } =
        await import('@/lib/printer');
      const avui = new Date().toISOString().slice(0, 10);

      if (quin === 'refer-x') { await fesX(); return; }

      try {
        if (quin === 'x') await imprimeixX(avui);
        else if (quin === 'z') await imprimeixZ(avui);
        else await imprimeixLiquidacioCentre(avui);
        setImpressió('Enviat a la impressora de tiquets ✅');
      } catch {
        const url = quin === 'x'
          ? `/api/v1/closure/${avui}/x-ticket`
          : quin === 'z'
            ? `/api/v1/closure/${avui}/z-ticket`
            : `/api/v1/shifts/liquidacio/centre?data=${avui}`;
        await obreDocumentText(url);
        setImpressió('Obert per imprimir en un full (sense tèrmica configurada)');
      }
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'No s\'ha pogut imprimir' });
    }
  };

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
      const r = await api.runClosureX() as { summary?: { liquidacions_cambrers?: LiquidacionsCambrers } };
      setLiquidacions(r?.summary?.liquidacions_cambrers ?? null);
      setMsg({ ok: true, text: 'Tancament X fet (no reseteja la caixa)' });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error al X' });
    } finally { setBusy(null); }
  };

  const fesZ = async () => {
    const nOberts = liquidacions?.count_oberts ?? 0;
    const avís = nOberts > 0
      ? `Atenció: ${nOberts} cambrer(s) tenen el torn ENCARA OBERT (la seva liquidació no està quadrada).\n\n`
      : '';
    if (!confirm(`${avís}Tancament Z: tanca el dia OFICIALMENT (reseteja). Segur?`)) return;
    setBusy('z');
    try {
      const r = await api.runClosureZ();
      setLiquidacions(r?.summary?.liquidacions_cambrers ?? null);
      setMsg({ ok: true, text: 'Tancament Z fet — dia tancat. Repassa les liquidacions dels cambrers.' });
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

      {/* IMPRESSIÓ A LA TÈRMICA DE TIQUETS (decisió Tomeu 18/09/2026):
          la Z i el full de liquidacions s'imprimeixen a la mateixa impressora
          de 80 mm que els tiquets, per firmar-los i arxivar-los. */}
      <div className="bg-brand-dark border border-brand-gold/20 rounded-2xl p-5">
        <h2 className="font-bold text-white mb-1">🖨️ Imprimir a la tèrmica de tiquets</h2>
        <p className="text-xs text-gray-400 mb-3">
          La Z duu la liquidació de tots els cambrers. Si falla la tèrmica,
          s&apos;obre el document per imprimir-lo en un full.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <button onClick={() => void imprimirDoc('x')} disabled={busy !== null}
            className="p-4 rounded-xl border border-brand-gold/40 bg-brand-gold/10 hover:border-brand-gold transition disabled:opacity-40 text-left">
            <div className="font-bold text-white text-sm">📋 Tiquet de la X</div>
            <div className="text-xs text-gray-400 mt-0.5">Pre-tancament — repassar abans de la Z</div>
          </button>
          <button onClick={() => void imprimirDoc('z')} disabled={busy !== null}
            className="p-4 rounded-xl border border-brand-gold/40 bg-brand-gold/10 hover:border-brand-gold transition disabled:opacity-40 text-left">
            <div className="font-bold text-white text-sm">🧾 Tiquet de la Z</div>
            <div className="text-xs text-gray-400 mt-0.5">Amb les liquidacions dels cambrers</div>
          </button>
          <button onClick={() => void imprimirDoc('liquidacions')} disabled={busy !== null}
            className="p-4 rounded-xl border border-brand-gold/40 bg-brand-gold/10 hover:border-brand-gold transition disabled:opacity-40 text-left">
            <div className="font-bold text-white text-sm">👤 Liquidació dels cambrers</div>
            <div className="text-xs text-gray-400 mt-0.5">El full que firma l&apos;encarregat</div>
          </button>
          <button onClick={() => void imprimirDoc('refer-x')} disabled={busy !== null}
            className="p-4 rounded-xl border border-white/15 bg-white/5 hover:border-white/40 transition disabled:opacity-40 text-left">
            <div className="font-bold text-white text-sm">🔄 Refer la X</div>
            <div className="text-xs text-gray-400 mt-0.5">Actualitzar les liquidacions</div>
          </button>
        </div>
        {impressió && (
          <div className="mt-3 text-xs text-green-300">{impressió}</div>
        )}
      </div>

      {/* LIQUIDACIÓ DE TOTS ELS CAMBRERS — l'encarregat la repassa aquí */}
      <PanellLiquidacionsCambrers dades={liquidacions} />

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