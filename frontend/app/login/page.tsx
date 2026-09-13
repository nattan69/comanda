'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, getStoredStaff } from '@/lib/api';

/**
 * Login per PIN (cambrers) — contracte: POST /api/v1/staff/login {pin, device_name}.
 * El token va a localStorage (comanda-token) i el staff a comanda-staff.
 */
export default function LoginPage() {
  const router = useRouter();
  const [pin, setPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // ja amb sessió → sala
  if (typeof window !== 'undefined' && getStoredStaff()) {
    router.replace('/sala');
  }

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (pin.length < 4) { setError('El PIN té 4 dígits'); return; }
    setLoading(true);
    setError(null);
    try {
      await api.login(pin, 'TPV web');
      router.replace('/sala');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PIN incorrecte');
      setPin('');
    } finally {
      setLoading(false);
    }
  };

  const digit = (d: string) => {
    setPin((p) => (p.length >= 4 ? p : p + d));
    setError(null);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-navy">
      <form onSubmit={submit} className="bg-brand-dark border border-brand-gold/30 rounded-2xl p-8 w-full max-w-xs text-center shadow-xl">
        <h1 className="text-2xl font-bold text-brand-gold mb-1">Comanda</h1>
        <p className="text-xs text-gray-400 mb-6">TPV Bar/Restaurant — introdueix el teu PIN</p>

        <div className="flex justify-center gap-3 mb-6" aria-label="PIN introduït">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className={`w-4 h-4 rounded-full border-2 ${pin.length > i ? 'bg-brand-gold border-brand-gold' : 'border-gray-500'}`} />
          ))}
        </div>

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        <div className="grid grid-cols-3 gap-3 mb-4">
          {['1','2','3','4','5','6','7','8','9'].map((d) => (
            <button key={d} type="button" onClick={() => digit(d)}
              className="py-4 rounded-xl bg-white/5 hover:bg-white/15 active:bg-brand-gold/30 text-2xl font-semibold text-white transition">
              {d}
            </button>
          ))}
          <button type="button" onClick={() => setPin('')}
            className="py-4 rounded-xl bg-white/5 hover:bg-white/15 text-sm text-gray-300 transition">C</button>
          <button type="button" onClick={() => digit('0')}
            className="py-4 rounded-xl bg-white/5 hover:bg-white/15 active:bg-brand-gold/30 text-2xl font-semibold text-white transition">0</button>
          <button type="button" onClick={() => setPin((p) => p.slice(0, -1))}
            className="py-4 rounded-xl bg-white/5 hover:bg-white/15 text-xl text-gray-300 transition">⌫</button>
        </div>

        <button type="submit" disabled={loading || pin.length < 4}
          className="w-full py-3 rounded-xl bg-brand-gold text-brand-dark font-bold disabled:opacity-40 hover:brightness-110 transition">
          {loading ? 'Entrant…' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}