'use client';

import { LiquidacionsCambrers } from '@/lib/api';

/**
 * LIQUIDACIONS DELS CAMBRERS — el full que l'ENCARREGAT repassa abans de
 * firmar el tancament (decisió Tomeu 18/09/2026).
 *
 * Per cada cambrer del centre es veu:
 *   · venda i nombrere de comandes
 *   · EFECTIU ESPERAT vs EFECTIU ENTREGAT
 *   · errors que ha assumit i el DESQUADRE PENDENT
 *   · targetes i crèdits PER BONS (els certifica Jornada — no es compten a mà)
 *
 * I els torns que quedaren OBERTS surten remarcats: un torn sense tancar és
 * exactament el que fa que la caixa no quadri.
 */
export default function PanellLiquidacionsCambrers({
  dades,
}: {
  dades?: LiquidacionsCambrers | null;
}) {
  if (!dades) return null;

  const e = (v?: string | number | null) =>
    v == null || v === ''
      ? '—'
      : `${Number(v).toLocaleString('ca-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;

  const color = (v?: string | null) => {
    if (v == null) return '#9aa7b8';
    const n = Number(v);
    if (Math.abs(n) < 0.005) return '#22c55e';
    return n < 0 ? '#fca5a5' : '#fbbf24';
  };

  const th = 'text-left text-xs font-semibold py-2 px-2';
  const td = 'py-2 px-2 text-sm tabular-nums';

  return (
    <div className="mt-5 rounded-2xl p-5" style={{ background: '#141429', border: '1px solid rgba(226,176,74,.25)' }}>
      <div className="flex items-baseline justify-between mb-1">
        <h3 className="font-bold" style={{ color: '#e2b04a' }}>
          👤 Liquidació dels cambrers
        </h3>
        <span className="text-xs" style={{ color: '#9aa7b8' }}>
          per repassar abans de firmar
        </span>
      </div>

      {/* --- TORNS SENSE TANCAR (el que fa que la caixa no quadri) --- */}
      {dades.count_oberts > 0 && (
        <div className="mt-3 rounded-xl p-3" style={{ background: 'rgba(251,191,36,.12)' }}>
          <div className="text-sm font-bold" style={{ color: '#fbbf24' }}>
            ⚠️ {dades.count_oberts} cambrer(s) amb el torn ENCARA OBERT — {e(dades.total_obert_efectiu_esperat)} d'efectiu sense entregar
          </div>
          <div className="text-xs mt-1" style={{ color: '#9aa7b8' }}>
            {dades.torns_oberts.map((t) => t.staff_name).join(' · ')}
          </div>
          <div className="text-xs mt-1" style={{ color: '#9aa7b8' }}>
            Si no han fet el logout, la seva liquidació no està quadrada.
          </div>
        </div>
      )}

      {/* --- TAULA DE LIQUIDACIONS --- */}
      {dades.count === 0 ? (
        <p className="text-sm mt-3" style={{ color: '#9aa7b8' }}>
          Encara no hi ha cap torn tancat avui.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(226,176,74,.2)', color: '#9aa7b8' }}>
                <th className={th}>Cambrer</th>
                <th className={th}>Punt de venda</th>
                <th className={`${th} text-right`}>Efectiu esperat</th>
                <th className={`${th} text-right`}>Entregat</th>
                <th className={`${th} text-right`}>Errors</th>
                <th className={`${th} text-right`}>Pendent</th>
                <th className={`${th} text-right`}>Per bons</th>
              </tr>
            </thead>
            <tbody>
              {dades.cambrers.map((c) => (
                <tr key={c.shift_id} style={{ borderBottom: '1px solid rgba(255,255,255,.05)' }}>
                  <td className={td} style={{ color: '#e5e9f0' }}>
                    {c.staff_name}
                    {c.observacions && (
                      <div className="text-xs" style={{ color: '#9aa7b8' }}>{c.observacions}</div>
                    )}
                  </td>
                  <td className={td} style={{ color: '#9aa7b8' }}>{c.center_name || '—'}</td>
                  <td className={`${td} text-right`} style={{ color: '#e5e9f0' }}>{e(c.efectiu_esperat)}</td>
                  <td className={`${td} text-right`} style={{ color: '#e5e9f0' }}>{e(c.efectiu_entregat)}</td>
                  <td className={`${td} text-right`} style={{ color: '#e5e9f0' }}>{e(c.errors)}</td>
                  <td className={`${td} text-right font-bold`} style={{ color: color(c.desquadre_pendent) }}>
                    {c.desquadre_pendent == null ? '—' : e(c.desquadre_pendent)}
                  </td>
                  <td className={`${td} text-right`} style={{ color: '#86efac' }}>
                    {e(c.per_bons?.total)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr style={{ borderTop: '1px solid rgba(226,176,74,.3)' }}>
                <td className={`${td} font-bold`} style={{ color: '#e2b04a' }} colSpan={2}>
                  TOTAL ({dades.count} cambrers)
                </td>
                <td className={`${td} text-right font-bold`} style={{ color: '#e2b04a' }}>{e(dades.total_efectiu_esperat)}</td>
                <td className={`${td} text-right font-bold`} style={{ color: '#e2b04a' }}>{e(dades.total_efectiu_entregat)}</td>
                <td className={`${td} text-right font-bold`} style={{ color: '#e2b04a' }}>{e(dades.total_errors)}</td>
                <td className={`${td} text-right font-bold`} style={{ color: color(dades.total_desquadre_pendent) }}>
                  {e(dades.total_desquadre_pendent)}
                </td>
                <td className={td} />
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      <div className="text-xs mt-3" style={{ color: '#9aa7b8' }}>
        <b style={{ color: '#86efac' }}>Per bons</b> = targetes de crèdit i crèdits a habitació,
        certificats per Jornada: no es demanen al cambrer ni es compten a mà.
      </div>
    </div>
  );
}
