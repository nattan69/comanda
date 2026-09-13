'use client';

import { useState } from 'react';
import { apiRoom, RoomInfo } from '@/lib/api';

/**
 * Panell de ROOM CHARGE (càrrec a habitació) — decisió Tomeu 13/09.
 * En informar el nº d'habitació mostra: titular de la reserva, règim (meal_plan)
 * i estat del crèdit (full/limited/none + límit + saldo del foli).
 * Casos: habitació inexistent · habitació sense client checked-in · sense nom.
 */

const REGIM: Record<string, string> = {
  room_only: 'Només habitació',
  bed_breakfast: 'Habitació + esmorzar',
  half_board: 'Migpensió',
  full_board: 'Pensió completa',
  all_inclusive: 'Tot inclòs',
};

export default function RoomCharge() {
  const [room, setRoom] = useState('');
  const [info, setInfo] = useState<RoomInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const consulta = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const n = room.trim();
    if (!n) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const r = await apiRoom.roomInfo(n);
      if (!r.room_found) setError('🚪 Habitació inexistent');
      else if (!r.reservation_found) setError('🛏️ Habitació sense client checked-in');
      else setInfo(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error consultant');
    } finally {
      setLoading(false);
    }
  };

  const creditColor: Record<string, string> = {
    full: 'bg-green-500/15 text-green-300',
    limited: 'bg-amber-500/15 text-amber-300',
    none: 'bg-red-500/15 text-red-300',
  };

  return (
    <div className="bg-brand-dark border border-brand-gold/20 rounded-xl p-5 max-w-md">
      <h3 className="font-bold text-white mb-3">🛎️ Càrrec a habitació</h3>
      <form onSubmit={consulta} className="flex gap-2">
        <input
          value={room}
          onChange={(e) => setRoom(e.target.value)}
          inputMode="numeric"
          placeholder="Nº habitació"
          className="flex-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15"
        />
        <button type="submit" disabled={loading}
          className="px-4 py-2 rounded-lg bg-brand-gold text-brand-dark font-bold text-sm disabled:opacity-40">
          {loading ? '…' : 'Veure'}
        </button>
      </form>

      {error && <div className="mt-3 p-3 rounded-lg bg-red-500/15 text-red-300 text-sm">{error}</div>}

      {info && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Habitació {room}</div>
              {info.guest_name && (
                <div className="text-lg font-bold text-brand-gold">{info.guest_name}</div>
              )}
            </div>
            <span className={`text-xs px-2 py-1 rounded-full ${creditColor[info.credit_type || 'none']}`}>
              crèdit {info.credit_type === 'full' ? 'complet' : info.credit_type === 'limited' ? `limitat ${info.credit_limit}€` : 'cap'}
            </span>
          </div>

          <div className="text-sm text-gray-300">
            🍽️ <span className="text-white">{REGIM[info.meal_plan || ''] || info.meal_plan}</span>
            {info.meal_plan_price && info.meal_plan_price !== '0' && (
              <span className="text-gray-400"> ({info.meal_plan_price}€/persona)</span>
            )}
          </div>

          <div className="flex items-center justify-between text-sm border-t border-white/10 pt-3">
            <span className="text-gray-400">Saldo del foli</span>
            <span className="font-mono text-white">{parseFloat(info.folio_balance || '0').toFixed(2)} €</span>
          </div>
        </div>
      )}
    </div>
  );
}