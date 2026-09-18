'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, apiCarta, getStoredStaff } from '@/lib/api';

/**
 * COMANDERA — l'app dels cambrers (PWA). Login optimitzat per mòbil/PDA:
 * teclat gran, un dit, i amb la informació del torn a la vista.
 *
 * DUES VIES D'ENTRADA (porter únic, decisió Tomeu 14/09/2026):
 *  1. PIN directe de Comanda (sempre disponible — clients sense Jornada)
 *  2. ?jornada_token=... → el token que emet el portal de Jornada/Jornals al
 *     fitxar. El bescanviem i entram directament. Un sol PIN pel cambrer.
 */

function LoginComandera() {
  const router = useRouter();
  const params = useSearchParams();
  const [pin, setPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Via 2: arribam amb un token del porter de Jornada → bescanvi directe
  useEffect(() => {
    const jornadaToken = params.get('jornada_token') || params.get('comanda_token');
    if (!jornadaToken) {
      if (getStoredStaff()) router.replace('/comandera/sala');
      return;
    }
    (async () => {
      setLoading(true);
      try {
        const res = await api.sessionExchange(jornadaToken, 'Comandera');
        // netejar el token de la URL (no ha de quedar a l'historial)
        window.history.replaceState({}, '', '/comandera');
        if (res.center_external_id) {
          sessionStorage.setItem('comandera-centre-fitxat', res.center_external_id);
        }
        // El porter ja ha fitxat el cambrer: el torn es DERIVA d'allà, així que
        // no cal obrir-ne cap a mà. Si no en té, n'obrim un de local.
        await obreTorn();
        router.replace('/comandera/sala');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'El token de Jornada no és vàlid');
      } finally { setLoading(false); }
    })();
  }, [params, router]);

  const submit = async (valor?: string) => {
    const p = valor ?? pin;
    if (p.length < 4) { setError('El PIN té 4 dígits'); return; }
    setLoading(true); setError(null);
    try {
      await api.login(p, 'Comandera');
      // OBRIR EL TORN en entrar (decisió Tomeu 18/09/2026): sense torn obert el
      // cambrer no compta al panell de servei i les seves comandes no queden
      // lligades enlloc → la LIQUIDACIÓ del logout sortiria a zero.
      await obreTorn();
      router.replace('/comandera/sala');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PIN incorrecte');
      setPin('');
    } finally { setLoading(false); }
  };

  /** Obre el torn del cambrer al primer punt de venda (si no en té cap d'obert). */
  const obreTorn = async () => {
    const jo = getStoredStaff();
    if (!jo?.id) return;
    try {
      const existent = await api.elMeuTorn(jo.id);
      if (existent) {
        // El centre del torn mana (pot ser el del fitxatge a Jornada).
        try { localStorage.setItem('comanda-centre', existent.center_id || ''); } catch { /* privat */ }
        return;
      }
      const centres = await apiCarta.getCenters();
      const cid = centres[0]?.id;
      if (!cid) return;
      const t = await api.openShift(jo.id, cid);
      try { localStorage.setItem('comanda-centre', t.center_id || cid); } catch { /* privat */ }
    } catch {
      // Si ja en tenia un (doble clic), no és cap error: hi som de servei.
    }
  };

  const digit = (d: string) => {
    const nou = pin.length >= 4 ? pin : pin + d;
    setPin(nou);
    setError(null);
    // auto-enviament al 4t dígit (un dit, zero clics extra)
    if (nou.length === 4) setTimeout(() => submit(nou), 150);
  };

  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center px-6"
      style={{ background: '#1a1a2e', touchAction: 'manipulation' }}>
      <div className="text-center mb-8">
        <div className="text-3xl font-bold" style={{ color: '#e2b04a' }}>Comandera</div>
        <div className="text-sm text-gray-400 mt-1">Posa el teu PIN per començar</div>
      </div>

      {/* punts del PIN */}
      <div className="flex gap-4 mb-8">
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className="w-5 h-5 rounded-full border-2 transition"
            style={{
              background: pin.length > i ? '#e2b04a' : 'transparent',
              borderColor: pin.length > i ? '#e2b04a' : '#4a5568',
            }} />
        ))}
      </div>

      {error && <div className="mb-4 px-4 py-2 rounded-lg text-sm"
        style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{error}</div>}

      {/* teclat gran per al polze */}
      <div className="grid grid-cols-3 gap-3 w-full max-w-xs">
        {['1','2','3','4','5','6','7','8','9'].map((d) => (
          <button key={d} type="button" onClick={() => digit(d)} disabled={loading}
            className="rounded-2xl text-3xl font-semibold transition active:scale-95"
            style={{ height: 72, background: 'rgba(255,255,255,.06)', color: '#fff' }}>
            {d}
          </button>
        ))}
        <button type="button" onClick={() => setPin('')}
          className="rounded-2xl text-sm transition active:scale-95"
          style={{ height: 72, background: 'rgba(255,255,255,.04)', color: '#9aa7b8' }}>ESBORRA</button>
        <button type="button" onClick={() => digit('0')} disabled={loading}
          className="rounded-2xl text-3xl font-semibold transition active:scale-95"
          style={{ height: 72, background: 'rgba(255,255,255,.06)', color: '#fff' }}>0</button>
        <button type="button" onClick={() => setPin((p) => p.slice(0, -1))}
          className="rounded-2xl text-2xl transition active:scale-95"
          style={{ height: 72, background: 'rgba(255,255,255,.04)', color: '#9aa7b8' }}>⌫</button>
      </div>

      <button onClick={() => submit()} disabled={loading || pin.length < 4}
        className="w-full max-w-xs mt-6 rounded-2xl font-bold text-lg transition disabled:opacity-30"
        style={{ height: 60, background: '#e2b04a', color: '#1a1a2e' }}>
        {loading ? 'Entrant…' : 'Entrar'}
      </button>

      <p className="text-xs text-gray-500 mt-8 text-center">
        Afegeix-la a la pantalla d&apos;inici per tenir-la com una app
      </p>
    </div>
  );
}
/**
 * Next.js exigeix un límit de Suspense al voltant de useSearchParams
 * (en cas contrari el build de producció falla amb "useSearchParams()
 * should be wrapped in a suspense boundary").
 */
export default function ComanderaLoginPage() {
  return (
    <Suspense fallback={
      <div className="fixed inset-0 flex items-center justify-center"
        style={{ background: '#1a1a2e', color: '#9aa7b8' }}>
        Carregant…
      </div>
    }>
      <LoginComandera />
    </Suspense>
  );
}
