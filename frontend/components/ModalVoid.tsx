'use client';

import { useState } from 'react';
import { api } from '@/lib/api';

/**
 * Modal d'ANUL·LACIÓ — POST /orders/{id}/void { amount, reason?, authorized_by_id? }.
 * El tiquet d'anul·lació surt del backend (barrat ANUL·LAT + motiu).
 */
export default function ModalVoid({
  orderId, total, onClose, onVoid,
}: {
  orderId: string;
  total: number;
  onClose: () => void;
  onVoid: () => void;
}) {
  const [amount, setAmount] = useState(total.toFixed(2));
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const anular = async () => {
    setSaving(true); setError(null);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/orders/${orderId}/void`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${localStorage.getItem('comanda-token') || ''}`,
          },
          body: JSON.stringify({
            amount: parseFloat(amount),
            reason: reason.trim() || null,
          }),
        });
      if (!res.ok) {
        const b = await res.json().catch(() => null);
        throw new Error(typeof b?.detail === 'string' ? b.detail : `Error ${res.status}`);
      }
      onVoid();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error anul·lant');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className="bg-brand-navy border border-red-500/30 rounded-2xl p-6 w-full max-w-sm shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-bold text-red-400">⚠️ Anul·lar càrrec</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">✕</button>
        </div>

        {error && <div className="mb-4 p-3 rounded-lg bg-red-500/15 text-red-300 text-sm">{error}</div>}

        <label className="block mb-4">
          <span className="text-xs text-gray-400">Import a anul·lar (€)</span>
          <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
            className="w-full mt-1 bg-white/5 text-white text-lg font-mono p-3 rounded border border-white/15" />
        </label>

        <label className="block mb-6">
          <span className="text-xs text-gray-400">Motiu (consta al tiquet d'anul·lació)</span>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2}
            placeholder="ex. error d'introducció, producte esgotat…"
            className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
        </label>

        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-gray-300 hover:bg-white/10 text-sm">Cancel·la</button>
          <button onClick={anular} disabled={saving}
            className="px-5 py-2 rounded-lg bg-red-500 text-white font-bold text-sm hover:bg-red-400 disabled:opacity-40">
            {saving ? 'Anul·lant…' : '🗑️ Anul·lar'}
          </button>
        </div>
      </div>
    </div>
  );
}