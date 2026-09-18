'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, getStoredStaff, XPersonal } from '@/lib/api';

/**
 * SORTIR DE LA COMANDERA amb LIQUIDACIÓ PERSONAL (decisió Tomeu 18/09/2026).
 *
 * Regla: el cambrer que DUU MOVIMENTS (vendes, invitacions, nuls, taules
 * obertes) NO surt sense quadrar. En prémer Sortir:
 *
 *   1. Es demana la X PERSONAL del seu torn (què duu fet).
 *   2. Si no hi ha cap moviment → surt directament (sense molestar).
 *   3. Si n'hi ha → s'obre el MODAL DE LIQUIDACIÓ, que demana:
 *        · EFECTIU ENTREGAT — el que posa a caixa
 *        · ERRORS           — diferències que assumeix com a seves
 *      i li dona PER BONS (llegit, no editable) el que ja certifica Jornada:
 *        · TARGETES DE CRÈDIT
 *        · CRÈDITS A HABITACIÓ
 *      perquè no s'hagi de posar a sumar a mà.
 *   4. Es mostra el DESQUADRE en directe mentre escriu, i el desquadre
 *      PENDENT (el que queda sense justificar després dels errors).
 *   5. Si encara té TAULES Obertes, s'avisa: el seu saldo no està cobrat.
 *
 * En entregar, es tanca el torn (POST /shifts/{id}/close) i després la sessió.
 */
/**
 * QUÈ COMPTA COM A MOVIMENT (per deixar sortir sense quadrar).
 *
 * Vendes, efectiu, targetes, crèdits, invitacions/nuls, anul·lacions o taules
 * encara obertes. Amb res de tot això, el torn és buit i el cambrer surt
 * directament sense que el molestem amb el modal.
 */
function teMoviments(s?: XPersonal['summary'] | null): boolean {
  if (!s) return false;
  const n = (v: unknown) => Number(v || 0) || 0;
  return (
    n(s.gross_sales) > 0
    || n(s.cash_expected) > 0
    || n(s.card_total) > 0
    || n(s.room_charge_total) > 0
    || n(s.non_sale?.total) > 0
    || n(s.house?.total) > 0
    || (s.voids?.count || 0) > 0
    || (s.obertes?.count || 0) > 0
  );
}

export default function BotoSortirCambrer({
  className, style, label = 'Sortir',
  onExit,
}: {
  className?: string;
  style?: React.CSSProperties;
  label?: string;
  /** Què fer en acabar (per defecte: tornar al login de la Comandera). */
  onExit?: () => void;
}) {
  const router = useRouter();
  const [obrint, setObrint] = useState(false);
  const [x, setX] = useState<XPersonal | null>(null);
  const [tornId, setTornId] = useState<string | null>(null);
  const [entregat, setEntregat] = useState('');
  const [errors, setErrors] = useState('');
  const [obs, setObs] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [enviant, setEnviant] = useState(false);
  //: Quin dels dos fulls s'està imprimint (per bloquejar el botó mentre va).
  const [imprimirEstat, setImprimirEstat] = useState<'liquidacio' | 'moviments' | null>(null);
  const [avísImpres, setAvísImpres] = useState<string | null>(null);

  const surt = useCallback(async () => {
    await api.logoutServer().catch(() => { /* best effort */ });
    if (onExit) onExit();
    else router.replace('/comandera');
  }, [onExit, router]);

  /** Sortir: consultam el torn i, si duu feina, obrim el modal. */
  const obre = async () => {
    setObrint(true); setError(null);
    try {
      const jo = getStoredStaff();
      if (!jo?.id) { await surt(); return; }
      const torn = await api.elMeuTorn(jo.id);
      if (!torn) { await surt(); return; }
      const resum = await api.xPersonal(torn.id);
      setTornId(torn.id);
      setX(resum);
      setEntregat(Number(resum.summary.cash_expected || 0).toFixed(2));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No s\'ha pogut consultar el torn');
    } finally { setObrint(false); }
  };

  const n = (v: string | undefined) => Number(v || 0) || 0;
  const s = x?.summary;
  const esperat = n(s?.cash_expected);

  /** El torn és buit si no duu cap moviment (aleshores no cal quadrar res). */
  const duuMoviments = teMoviments(s);

  const entregatNum = entregat === '' ? null : Number(entregat);
  const errorsNum = n(errors);
  const desquadre = entregatNum === null ? null : entregatNum - esperat;
  const pendent = desquadre === null ? null : desquadre + errorsNum;

  const entrega = async () => {
    if (!tornId || entregatNum === null) return;
    setEnviant(true); setError(null);
    try {
      await api.closeShift(tornId, {
        cash_declared: entregatNum,
        errors: errorsNum,
        observations: obs,
      });
      await surt();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No s\'ha pogut tancar el torn');
    } finally { setEnviant(false); }
  };

  /**
   * IMPRIMEIX un dels dos fulls del sobre (decisió Tomeu 18/09/2026).
   *
   * Va a la IMPRESSORA TÈRMICA DE TIQUETS (mateixa que els tiquets, 80 mm).
   * Si no n'hi ha cap de configurada, s'obre el document per imprimir-lo en un
   * full normal: el paper s'ha de poder firmar igualment.
   */
  const imprimir = async (quin: 'liquidacio' | 'moviments') => {
    if (!tornId) return;
    setImprimirEstat(quin); setError(null); setAvísImpres(null);
    try {
      const { imprimeixLiquidacioCambrer, imprimeixMovimentsCambrer, obreDocumentText } =
        await import('@/lib/printer');
      try {
        if (quin === 'liquidacio') await imprimeixLiquidacioCambrer(tornId);
        else await imprimeixMovimentsCambrer(tornId);
        setAvísImpres('Enviat a la impressora de tiquets ✅');
      } catch {
        const url = quin === 'liquidacio'
          ? `/api/v1/shifts/${tornId}/liquidacio`
          : `/api/v1/shifts/${tornId}/moviments`;
        await obreDocumentText(url);
        setAvísImpres('Obert per imprimir en un full (sense tèrmica)');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No s\'ha pogut imprimir');
    } finally { setImprimirEstat(null); }
  };

  // ---------- MODAL ----------
  if (x) {
    const euros = (v: number) => `${v.toFixed(2)} €`;
    const colorDesq = pendent === null ? '#9aa7b8'
      : Math.abs(pendent) < 0.005 ? '#22c55e'
      : pendent < 0 ? '#fca5a5' : '#fbbf24';

    return (
      <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
        style={{ background: 'rgba(0,0,0,.7)' }}>
        <div className="w-full sm:max-w-md max-h-[92vh] overflow-y-auto rounded-t-3xl sm:rounded-3xl p-5"
          style={{ background: '#1a1a2e', border: '1px solid rgba(226,176,74,.3)' }}>

          <div className="flex items-start justify-between mb-1">
            <div>
              <div className="text-lg font-bold" style={{ color: '#e2b04a' }}>Liquidació del torn</div>
              <div className="text-xs mt-0.5" style={{ color: '#9aa7b8' }}>
                {x.staff_name || '—'}{x.center_name ? ` · ${x.center_name}` : ''}
              </div>
            </div>
            <button onClick={() => { setX(null); setError(null); }}
              className="text-xl leading-none px-2" style={{ color: '#9aa7b8' }}>✕</button>
          </div>

          {error && (
            <div className="mt-3 px-3 py-2 rounded-lg text-sm"
              style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{error}</div>
          )}

          {/* --- EFECTIU --- */}
          <div className="mt-4 rounded-2xl p-4" style={{ background: 'rgba(255,255,255,.05)' }}>
            <div className="flex items-baseline justify-between">
              <span className="text-sm" style={{ color: '#9aa7b8' }}>Efectiu que hauries de tenir</span>
              <span className="text-xl font-bold tabular-nums" style={{ color: '#e5e9f0' }}>{euros(esperat)}</span>
            </div>
            <label className="block mt-3">
              <span className="text-sm font-semibold" style={{ color: '#e2b04a' }}>Efectiu entregat</span>
              <input inputMode="decimal" value={entregat} onChange={(e) => setEntregat(e.target.value)}
                placeholder="0.00"
                className="w-full mt-1 rounded-xl px-3 py-3 text-2xl font-bold tabular-nums outline-none"
                style={{ background: 'rgba(255,255,255,.08)', color: '#fff', border: '1px solid rgba(226,176,74,.35)' }} />
            </label>
            <button onClick={() => setEntregat(esperat.toFixed(2))}
              className="mt-2 text-xs underline" style={{ color: '#9aa7b8' }}>
              Quadra exacte
            </button>
          </div>

          {/* --- PER BONS (Jornada) --- */}
          <div className="mt-3 rounded-2xl p-4" style={{ background: 'rgba(34,197,94,.08)' }}>
            <div className="text-xs font-bold mb-2" style={{ color: '#86efac' }}>
              ✅ PER BONS — no cal sumar-ho
            </div>
            {[
              ['Targetes de crèdit', n(s?.per_bons?.targeta_credit)],
              ['Crèdits a habitació', n(s?.per_bons?.carrec_habitacio)],
            ].map(([etq, val]) => (
              <div key={String(etq)} className="flex justify-between text-sm py-0.5">
                <span style={{ color: '#9aa7b8' }}>{etq}</span>
                <span className="tabular-nums" style={{ color: '#e5e9f0' }}>{euros(Number(val))}</span>
              </div>
            ))}
            <div className="flex justify-between text-sm font-bold pt-1 mt-1"
              style={{ borderTop: '1px solid rgba(34,197,94,.25)' }}>
              <span style={{ color: '#86efac' }}>Total per bons</span>
              <span className="tabular-nums" style={{ color: '#86efac' }}>{euros(n(s?.per_bons?.total))}</span>
            </div>
            <div className="text-xs mt-2" style={{ color: '#9aa7b8' }}>
              Ho certifica Jornada, per això no es demana.
            </div>
          </div>

          {/* --- ERRORS --- */}
          <div className="mt-3 rounded-2xl p-4" style={{ background: 'rgba(255,255,255,.05)' }}>
            <label className="block">
              <span className="text-sm font-semibold" style={{ color: '#e5e9f0' }}>Errors</span>
              <span className="text-xs ml-2" style={{ color: '#9aa7b8' }}>diferències que assumeixes</span>
              <input inputMode="decimal" value={errors} onChange={(e) => setErrors(e.target.value)}
                placeholder="0.00"
                className="w-full mt-1 rounded-xl px-3 py-2 text-lg tabular-nums outline-none"
                style={{ background: 'rgba(255,255,255,.08)', color: '#fff', border: '1px solid rgba(255,255,255,.15)' }} />
            </label>
            <input value={obs} onChange={(e) => setObs(e.target.value)}
              placeholder="Observacions (opcional)"
              className="w-full mt-2 rounded-xl px-3 py-2 text-sm outline-none"
              style={{ background: 'rgba(255,255,255,.05)', color: '#e5e9f0', border: '1px solid rgba(255,255,255,.12)' }} />
          </div>

          {/* --- DESQUADRE en directe --- */}
          <div className="mt-3 rounded-2xl p-4" style={{ background: 'rgba(255,255,255,.05)' }}>
            <div className="flex justify-between text-sm">
              <span style={{ color: '#9aa7b8' }}>Desquadre</span>
              <span className="tabular-nums font-bold" style={{ color: colorDesq }}>
                {desquadre === null ? '—' : (desquadre > 0 ? '+' : '') + euros(desquadre)}
              </span>
            </div>
            <div className="flex justify-between text-sm mt-1">
              <span style={{ color: '#9aa7b8' }}>Pendent (amb errors)</span>
              <span className="tabular-nums font-bold" style={{ color: colorDesq }}>
                {pendent === null ? '—' : (pendent > 0 ? '+' : '') + euros(pendent)}
              </span>
            </div>
            {pendent !== null && Math.abs(pendent) < 0.005 && (
              <div className="text-xs mt-2" style={{ color: '#86efac' }}>✅ Quadra</div>
            )}
            {pendent !== null && pendent < -0.005 && (
              <div className="text-xs mt-2" style={{ color: '#fca5a5' }}>
                ⚠️ Falten {euros(Math.abs(pendent))} per entregar
              </div>
            )}
          </div>

          {/* --- TAULES ENCARA OBERTES --- */}
          {(s?.obertes?.count || 0) > 0 && (
            <div className="mt-3 rounded-2xl p-4" style={{ background: 'rgba(251,191,36,.1)' }}>
              <div className="text-sm font-bold" style={{ color: '#fbbf24' }}>
                🪑 Tens {s?.obertes?.count} comanda(es) sense cobrar — {euros(n(s?.obertes?.total))}
              </div>
              <div className="text-xs mt-1" style={{ color: '#9aa7b8' }}>
                Aquest saldo no està cobrat: si surts ara, queda pendent al local.
              </div>
            </div>
          )}

          {/* --- NO-VENDA (traça) --- */}
          {n(s?.non_sale?.total) > 0 && (
            <div className="mt-3 text-xs px-1" style={{ color: '#9aa7b8' }}>
              Invitacions i nuls al torn: {euros(n(s?.non_sale?.total))} · no es declaren
            </div>
          )}

          {/* --- IMPRIMIR ELS DOS FULLS (per signar i ficar dins el sobre) --- */}
          <div className="mt-3 rounded-2xl p-4" style={{ background: 'rgba(255,255,255,.05)' }}>
            <div className="text-sm font-semibold mb-2" style={{ color: '#e5e9f0' }}>
              🖨️ Papers per al sobre
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => void imprimir('liquidacio')}
                disabled={imprimirEstat !== null}
                className="rounded-xl py-3 text-sm font-semibold disabled:opacity-40"
                style={{ background: 'rgba(226,176,74,.18)', color: '#e2b04a' }}>
                {imprimirEstat === 'liquidacio' ? '…' : 'Liquidació'}
              </button>
              <button onClick={() => void imprimir('moviments')}
                disabled={imprimirEstat !== null}
                className="rounded-xl py-3 text-sm font-semibold disabled:opacity-40"
                style={{ background: 'rgba(226,176,74,.18)', color: '#e2b04a' }}>
                {imprimirEstat === 'moviments' ? '…' : 'Moviments'}
              </button>
            </div>
            <div className="text-xs mt-2" style={{ color: '#9aa7b8' }}>
              S&apos;imprimeixen a la tèrmica de tiquets. Si no n&apos;hi ha, s&apos;obren
              per imprimir en un full.
            </div>
            {avísImpres && (
              <div className="text-xs mt-1" style={{ color: '#86efac' }}>{avísImpres}</div>
            )}
          </div>

          <button onClick={entrega} disabled={enviant || entregatNum === null}
            className="w-full mt-4 rounded-2xl font-bold text-lg disabled:opacity-40"
            style={{ height: 56, background: '#e2b04a', color: '#1a1a2e' }}>
            {enviant ? 'Tancant…' : 'Entregar i sortir'}
          </button>

          {!duuMoviments && (
            <button onClick={surt} disabled={enviant}
              className="w-full mt-2 rounded-2xl text-sm"
              style={{ height: 44, background: 'rgba(255,255,255,.06)', color: '#9aa7b8' }}>
              Sortir sense moviments
            </button>
          )}
        </div>
      </div>
    );
  }

  // ---------- BOTÓ ----------
  return (
    <button onClick={obre} disabled={obrint} className={className} style={style}>
      {obrint ? '…' : label}
    </button>
  );
}
