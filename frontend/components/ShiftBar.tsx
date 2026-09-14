'use client';

import { useEffect, useState } from 'react';
import { api, apiCarta, Center, Staff, Shift, getStoredStaff, API_URL_FETCH } from '@/lib/api';

/**
 * Selector de centre + torn (contracte Maria): el cambrer tria el punt de venda
 * i s'obre el torn amb POST /shifts/open { staff_id, center_id }.
 * Mostra el torn obert actual i permet tancar-lo.
 */
export default function ShiftBar({ onCenter }: { onCenter?: (id: string | null) => void }) {
  const [centres, setCentres] = useState<Center[]>([]);
  const [shift, setShift] = useState<Shift | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const carrega = async () => {
    setLoading(true);
    try {
      const [cs, ss] = await Promise.all([apiCarta.getCenters(), api.getShifts()]);
      setCentres(cs);
      const staff = getStoredStaff();
      const meus = staff ? ss.filter((s) => s.staff_id === staff.id && !s.closed_at) : [];
      setShift(meus[0] || null);
    } catch { /* sense sessió */ }
    finally { setLoading(false); }
  };

  useEffect(() => { carrega(); }, []);

  const obre = async (centerId: string) => {
    const staff = getStoredStaff();
    if (!staff) { setMsg('Fes login primer'); return; }
    try {
      const res = await fetch(`${API_URL_FETCH}/shifts/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('comanda-token') || ''}` },
        body: JSON.stringify({ staff_id: staff.id, center_id: centerId }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => null);
        throw new Error(typeof b?.detail === 'string' ? b.detail : `Error ${res.status}`);
      }
      setShift(await res.json());
      setMsg('Torn obert ✅');
      onCenter?.(centerId);
    } catch (e) { setMsg(e instanceof Error ? e.message : 'Error obrint torn'); }
  };

  const tanca = async () => {
    if (!shift) return;
    try {
      const res = await fetch(`${API_URL_FETCH}/shifts/${shift.id}/close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('comanda-token') || ''}` },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => null);
        throw new Error(typeof b?.detail === 'string' ? b.detail : `Error ${res.status}`);
      }
      setShift(null);
      setMsg('Torn tancat ✅');
      onCenter?.(null);
    } catch (e) { setMsg(e instanceof Error ? e.message : 'Error tancant torn'); }
  };

  const centreNom = (id?: string | null) => centres.find((c) => c.id === id)?.name || '—';

  if (loading) return null;

  return (
    <div className="flex items-center gap-3 flex-wrap text-sm">
      {shift ? (
        <span className="text-sm text-gray-300">
          🟢 Torn obert a <b className="text-brand-gold">{centreNom(shift.center_id)}</b>
          <button onClick={tanca} className="ml-3 text-xs text-gray-400 hover:text-red-300 underline">tancar torn</button>
        </span>
      ) : (
        <span className="text-sm text-gray-400">
          Tria el teu punt de venda:
          <select onChange={(e) => e.target.value && obre(e.target.value)} defaultValue=""
            className="ml-2 bg-white/5 text-white text-sm p-2 rounded border border-white/15">
            <option value="">— tria —</option>
            {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </span>
      )}
      {msg && <span className="text-xs text-brand-gold">{msg}</span>}
    </div>
  );
}