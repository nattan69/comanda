'use client';

import { useState, useEffect } from 'react';
import { MenuItem, Family, IncomeCategory, Center, apiCarta } from '@/lib/api';

/**
 * Fitxa d'article (doble clic a /carta) — editar i guardar.
 * PATCH /menu/items/{id} amb tots els camps.
 */

export default function FitxaArticle({
  item, families: famProp, ingressos: ingProp, centres: cenProp, onClose, onSaved,
}: {
  item: MenuItem;
  families: Family[];
  ingressos: IncomeCategory[];
  centres: Center[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    name: item.name,
    price: String(item.price),
    vat_rate: String((item as MenuItem & { vat_rate?: number }).vat_rate ?? 10),
    family_id: item.family_id || '',
    income_category_id: item.income_category_id || '',
    center_id: (item as MenuItem & { center_id?: string }).center_id || '',
    description: (item as MenuItem & { description?: string }).description || '',
    is_available: (item as MenuItem & { is_available?: boolean }).is_available !== false,
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Les llistes poden arribar buides (error de càrrega a la pàgina pare, ex. 401 de
  // require_auth amb sessió vella) → les recarreguem nosaltres mateixos un cop.
  const [families, setFamilies] = useState<Family[]>(famProp || []);
  const [ingressos, setIngressos] = useState<IncomeCategory[]>(ingProp || []);
  const [centres, setCentres] = useState<Center[]>(cenProp || []);
  const [carregant, setCarregant] = useState(false);

  useEffect(() => {
    if (famProp.length || ingProp.length) return; // la pare ja ens ho va donar
    setCarregant(true);
    (async () => {
      try {
        const [f, ic, c] = await Promise.all([
          apiCarta.getFamilies(), apiCarta.getIncomeCategories(), apiCarta.getCenters(),
        ]);
        setFamilies(f); setIngressos(ic); setCentres(c);
      } catch { /* error mostrat als selects — l'usuari veu que no hi ha res */ }
      finally { setCarregant(false); }
    })();
  }, []);

  const guardar = async () => {
    if (!form.name.trim() || !form.price) { setError('Nom i preu obligatoris'); return; }
    setSaving(true);
    setError(null);
    try {
      await apiCarta.updateItem(item.id, {
        name: form.name.trim(),
        price: parseFloat(form.price),
        vat_rate: parseFloat(form.vat_rate) || 10,
        family_id: form.family_id || null,
        income_category_id: form.income_category_id || null,
        center_id: form.center_id || null,
        description: form.description || null,
        is_available: form.is_available,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error guardant');
    } finally { setSaving(false); }
  };

  const sel = (value: string, onChange: (v: string) => void, opcions: { id: string; name: string }[], label: string) => (
    <label className="block">
      <span className="text-xs text-gray-400">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15">
        <option value="">{carregant ? 'carregant…' : '— cap —'}</option>
        {opcions.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </label>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}>
      <div className="bg-brand-navy border border-brand-gold/30 rounded-2xl p-6 w-full max-w-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-bold text-brand-gold">Fitxa de l'article</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">✕</button>
        </div>

        {error && <div className="mb-4 p-3 rounded-lg bg-red-500/15 text-red-300 text-sm">{error}</div>}

        <div className="space-y-4">
          <label className="block">
            <span className="text-xs text-gray-400">Nom</span>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
          </label>
          <label className="block">
            <span className="text-xs text-gray-400">Descripció</span>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
              className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-gray-400">Preu (€)</span>
              <input type="number" step="0.01" value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
                className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">IVA (%)</span>
              <input type="number" step="0.5" value={form.vat_rate}
                onChange={(e) => setForm({ ...form, vat_rate: e.target.value })}
                className="w-full mt-1 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {sel(form.income_category_id, (v) => setForm({ ...form, income_category_id: v }), ingressos, 'Categoria d\'ingrés')}
            {sel(form.family_id, (v) => setForm({ ...form, family_id: v }), families, 'Família')}
          </div>
          {sel(form.center_id, (v) => setForm({ ...form, center_id: v }), centres, 'Departament')}

          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input type="checkbox" checked={form.is_available}
              onChange={(e) => setForm({ ...form, is_available: e.target.checked })}
              className="w-4 h-4 accent-[#e2b04a]" />
            Disponible a la carta
          </label>
        </div>

        <div className="flex gap-3 justify-end mt-6">
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg text-gray-300 hover:bg-white/10 text-sm">Cancel·la</button>
          <button onClick={guardar} disabled={saving}
            className="px-5 py-2 rounded-lg bg-brand-gold text-brand-dark font-bold text-sm hover:brightness-110 disabled:opacity-40">
            {saving ? 'Guardant…' : '💾 Guardar'}
          </button>
        </div>
      </div>
    </div>
  );
}