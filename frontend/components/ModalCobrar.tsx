'use client';

import { useState } from 'react';
import { api } from '@/lib/api';

/**
 * Modal de COBRAMENT (decisió Tomeu 13/09) — contracte backend:
 * POST /orders/{id}/pay { method, amount, room_number?, guest_name?,
 *   invited_by?, reason?, card_reference? }
 * method ∈ cash | card | bizum | room_charge | house
 * Crèdit limitat: el PMS rebutja amb credit_denied si supera el límit → mostrem l'error.
 * Room charge: panell amb nº habitació → info (titular/règim/crèbit/saldo) i bloqueig
 * per marge insuficient abans d'enviar.
 */

const METODES = [
  { id: 'cash', label: '💵 Efectiu' },
  { id: 'card', label: '💳 Targeta' },
  { id: 'bizum', label: '📲 Bizum' },
  { id: 'room_charge', label: '🛏️ Habitació' },
  { id: 'house', label: '🏠 Casa (invitat)' },
];

export default function ModalCobrar({
  orderId, total, onClose, onPaid,
}: {
  orderId: string;
  total: number;
  onClose: () => void;
  onPaid: (paymentId?: string) => void;
}) {
  const [method, setMethod] = useState('cash');
  const [amount, setAmount] = useState(total.toFixed(2));
  const [room, setRoom] = useState('');
  const [guest, setGuest] = useState('');
  const [cardRef, setCardRef] = useState('');
  const [reason, setReason] = useState('');
  const [roomInfo, setRoomInfo] = useState<{
    guest_name?: string | null; credit_type?: string; credit_limit?: string; folio_balance?: string;
  } | null>(null);
  const [avís, setAvís] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const consultaRoom = async (n: string) => {
    setRoomInfo(null); setAvís(null);
    if (!n.trim()) return;
    try {
      const r = await fetch(`/api/v1/orders/room-info?room_number=${encodeURIComponent(n.trim())}`);
      const data = await r.json();
      if (!data.room_found) { setAvís('🚪 Habitació inexistent'); return; }
      if (!data.reservation_found) { setAvís('🛏️ Habitació sense client checked-in'); return; }
      setRoomInfo(data);
      const saldo = parseFloat(data.folio_balance || '0');
      const limit = data.credit_type === 'limited' ? parseFloat(data.credit_limit || '0') : Infinity;
      const nou = saldo + (parseFloat(amount) || 0);
      if (nou > limit) {
        setAvís(`⛔ Crèdit insuficient: saldo ${saldo.toFixed(2)}€ + ${amount}€ supera el límit ${limit.toFixed(2)}€ — el PMS rebutjarà (credit_denied)`);
      } else if (data.credit_type === 'limited' && nou > limit * 0.8) {
        setAvís(`⚠️ Marge reduït: et queden ${(limit - nou).toFixed(2)}€ de crèdit`);
      }
    } catch { setAvís('Error consultant la habitació'); }
  };

  const cobrar = async () => {
    setSaving(true); setError(null);
    try {
      const payload: Record<string, unknown> = {
        method, amount: parseFloat(amount),
      };
      if (method === 'room_charge') payload.room_number = room.trim();
      if (method === 'room_charge' && roomInfo?.guest_name) payload.guest_name = roomInfo.guest_name;
      if (method === 'house') payload.invited_by = guest.trim() || null;
      if (method === 'card' && cardRef.trim()) payload.card_reference = cardRef.trim();
      if (method === 'house' && reason.trim()) payload.reason = reason.trim();

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/orders/${orderId}/pay`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('comanda-token') || ''}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const d = body?.detail;
        throw new Error(
          typeof d === 'string' ? d
          : d?.code === 'credit_denied' ? '⛔ Crèdit rebutjat pel PMS (credit_denied)'
          : JSON.stringify(d || res.status));
      }
      const data = await res.json().catch(() => ({}));
      onPaid(data?.payment_id || data?.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error cobrant');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className="bg-brand-navy border border-brand-gold/30 rounded-2xl p-6 w-full max-w-md shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-bold text-brand-gold">Cobrar comanda</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">✕</button>
        </div>

        {error && <div className="mb-4 p-3 rounded-lg bg-red-500/15 text-red-300 text-sm">{error}</div>}

        {/* Mètodes */}
        <div className="grid grid-cols-2 gap-2 mb-4">
          {METODES.map((m) => (
            <button key={m.id} onClick={() => setMethod(m.id)}
              className={`p-3 rounded-xl border text-sm font-semibold transition ${
                method === m.id ? 'bg-brand-gold text-brand-dark border-brand-gold' : 'bg-white/5 text-white border-white/15 hover:bg-white/10'
              }`}>
              {m.label}
            </button>
          ))}
        </div>

        {/* Import */}
        <label className="block mb-4">
          <span className="text-xs text-gray-400">Import (€)</span>
          <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
            className="w-full mt-1 bg-white/5 text-white text-lg font-mono p-3 rounded border border-white/15" />
        </label>

        {/* Camps segons mètode */}
        {method === 'room_charge' && (
          <div className="space-y-3 mb-4">
            <label className="block">
              <span className="text-xs text-gray-400">Nº habitació</span>
              <input value={room} onChange={(e) => { setRoom(e.target.value); consultaRoom(e.target.value); }}
                inputMode="numeric" placeholder="ex. 109"
                className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
            </label>
            {roomInfo && (
              <div className="p-3 rounded-lg bg-white/5 text-sm space-y-1">
                <div className="text-brand-gold font-bold">{roomInfo.guest_name || 'Sense nom'}</div>
                <div className="text-gray-300 text-xs">
                  crèdit {roomInfo.credit_type === 'full' ? 'complet' : roomInfo.credit_type === 'limited' ? `limitat ${roomInfo.credit_limit}€` : 'cap'} · saldo foli {parseFloat(roomInfo.folio_balance || '0').toFixed(2)}€
                </div>
              </div>
            )}
            {avís && <div className="p-3 rounded-lg bg-amber-500/15 text-amber-300 text-xs">{avís}</div>}
          </div>
        )}

        {method === 'card' && (
          <label className="block mb-4">
            <span className="text-xs text-gray-400">Referència de la targeta (opcional)</span>
            <input value={cardRef} onChange={(e) => setCardRef(e.target.value)}
              className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
          </label>
        )}

        {method === 'house' && (
          <label className="block mb-4">
            <span className="text-xs text-gray-400">Convidat per / motiu</span>
            <input value={guest} onChange={(e) => setGuest(e.target.value)} placeholder="ex. Direcció, visita comercial"
              className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
          </label>
        )}

        <div className="flex gap-3 justify-end mt-2">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-gray-300 hover:bg-white/10 text-sm">Cancel·la</button>
          <button onClick={cobrar} disabled={saving || (!!avís && avís.startsWith('⛔'))}
            className="px-5 py-2 rounded-lg bg-brand-gold text-brand-dark font-bold text-sm hover:brightness-110 disabled:opacity-40">
            {saving ? 'Cobrant…' : `💰 Cobrar ${parseFloat(amount || '0').toFixed(2)} €`}
          </button>
        </div>
      </div>
    </div>
  );
}