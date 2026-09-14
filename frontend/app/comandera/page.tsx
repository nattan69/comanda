'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, getStoredStaff } from '@/lib/api';

/**
 * COMANDERA — l'app dels cambrers (PWA). Login PIN optimitzat per mòbil/PDA:
 * teclat gran, un dit, i amb la informació del torn a la vista.
 * Contracte: POST /api/v1/staff/login { pin, device_name } → token + staff.
 */
export default function ComanderaLogin() {
  const router = useRouter();
  const [pin, setPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getStoredStaff()) router.replace('/comandera/sala');
  }, [router]);

  const submit = async (valor?: string) => {
    const p = valor ?? pin;
    if (p.length < 4) { setError('El PIN té 4 dígits'); return; }
    setLoading(true); setError(null);
    try {
      await api.login(p, 'Comandera');
      router.replace('/comandera/sala');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PIN incorrecte');
      setPin('');
    } finally { setLoading(false); }
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