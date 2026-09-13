'use client';

import { useEffect, useState, useMemo } from 'react';
import { apiCarta, MenuItem, Family, IncomeCategory, Center } from '@/lib/api';
import FitxaArticle from '@/components/FitxaArticle';

/**
 * Gestió de la CARTA — articles amb 3 nivells (decisió Tomeu 13/09):
 *   família (carta) · categoria d'ingrés (comptable, amb compte PGC) · departament.
 * + agrupació per família/departament + articles inherents de pensió.
 */

type Filtre = { familia: string; ingres: string; centre: string; grup: 'cap' | 'familia' | 'centre' };

const PENSIONS = ['berenar', 'dinar', 'sopar'];

export default function CartaPage() {
  const [items, setItems] = useState<MenuItem[]>([]);
  const [families, setFamilies] = useState<Family[]>([]);
  const [ingressos, setIngressos] = useState<IncomeCategory[]>([]);
  const [centres, setCentres] = useState<Center[]>([]);
  const [filtre, setFiltre] = useState<Filtre>({ familia: '', ingres: '', centre: '', grup: 'cap' });
  const [form, setForm] = useState({ name: '', price: '', vat: '10', family_id: '', income_category_id: '', center_id: '' });
  const [novaFamilia, setNovaFamilia] = useState('');
  const [fitxa, setFitxa] = useState<MenuItem | null>(null);
  const [sort, setSort] = useState<{ col: string; dir: 'asc' | 'desc' } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const carrega = async () => {
    setLoading(true);
    try {
      const [i, f, ic, c] = await Promise.all([
        apiCarta.getItems(), apiCarta.getFamilies(),
        apiCarta.getIncomeCategories(), apiCarta.getCenters(),
      ]);
      setItems(i); setFamilies(f); setIngressos(ic); setCentres(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error carregant');
    } finally { setLoading(false); }
  };

  useEffect(() => { carrega(); }, []);

  const esPensio = (n: string) => PENSIONS.some((p) => n.toLowerCase().includes(p));

  const filtrats = useMemo(() => {
    const l = items.filter((it) =>
      (!filtre.familia || it.family_id === filtre.familia) &&
      (!filtre.ingres || it.income_category_id === filtre.ingres) &&
      (!filtre.centre || (it as MenuItem & { center_id?: string }).center_id === filtre.centre));
    if (!sort) return l;
    const nom = (ll: { id: string; name: string }[], id?: string | null) =>
      ll.find((x) => x.id === id)?.name || '';
    const val = (it: MenuItem): string | number => {
      switch (sort.col) {
        case 'name': return it.name.toLowerCase();
        case 'price': return it.price ?? 0;
        case 'vat': return (it as MenuItem & { vat_rate?: number }).vat_rate ?? 0;
        case 'family': return nom(families, it.family_id);
        case 'ingres': return nom(ingressos, it.income_category_id);
        case 'centre': return nom(centres, (it as MenuItem & { center_id?: string }).center_id);
        default: return it.name.toLowerCase();
      }
    };
    return [...l].sort((a, b) => {
      const va = val(a), vb = val(b);
      const cmp = typeof va === 'number' && typeof vb === 'number'
        ? va - vb : String(va).localeCompare(String(vb), 'ca');
      return sort.dir === 'asc' ? cmp : -cmp;
    });
  }, [items, filtre, sort, families, ingressos, centres]);

  const agrupats = useMemo(() => {
    if (filtre.grup === 'cap') return null;
    const key = (it: MenuItem) =>
      filtre.grup === 'familia'
        ? families.find((f) => f.id === it.family_id)?.name || 'Sense família'
        : centres.find((c) => c.id === (it as MenuItem & { center_id?: string }).center_id)?.name || 'General';
    const grups: Record<string, MenuItem[]> = {};
    filtrats.forEach((it) => { (grups[key(it)] ||= []).push(it); });
    return Object.entries(grups).sort((a, b) => a[0].localeCompare(b[0]));
  }, [filtrats, filtre.grup, families, centres]);

  const alta = async () => {
    if (!form.name.trim() || !form.price) { setError('Nom i preu obligatoris'); return; }
    setError(null);
    try {
      await apiCarta.createItem({
        name: form.name.trim(), price: parseFloat(form.price),
        vat_rate: parseFloat(form.vat) || 10,
        family_id: form.family_id || null,
        income_category_id: form.income_category_id || null,
        center_id: form.center_id || null,
      });
      setForm({ ...form, name: '', price: '' });
      carrega();
    } catch (e) { setError(e instanceof Error ? e.message : 'Error creant'); }
  };

  const novaFam = async () => {
    if (!novaFamilia.trim()) return;
    try { await apiCarta.createFamily(novaFamilia.trim(), families.length + 1); setNovaFamilia(''); carrega(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Error creant família'); }
  };

  const nom = (llista: { id: string; name: string }[], id?: string | null) =>
    llista.find((x) => x.id === id)?.name || '—';

  const ordena = (col: string) =>
    setSort((s) => (s?.col === col ? { col, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { col, dir: 'asc' }));

  const cap = (col: string, label: string) => (
    <th className={col === 'price' ? 'text-right' : ''} style={{ cursor: 'pointer', userSelect: 'none' }}
      onClick={() => ordena(col)} title="Ordenar">
      {label}{sort?.col === col && <span className="ml-1 text-brand-gold">{sort.dir === 'asc' ? '▲' : '▼'}</span>}
    </th>
  );

  const select = (value: string, onChange: (v: string) => void, opcions: { id: string; name: string }[], label: string) => (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="bg-white/5 text-white text-sm p-2 rounded border border-white/15">
      <option value="">{label}</option>
      {opcions.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
    </select>
  );

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-brand-gold">Gestió de la carta</h1>
      {error && <div className="p-3 rounded-lg bg-red-500/15 text-red-300 text-sm">{error}</div>}

      {/* Filtres + agrupació */}
      <div className="flex flex-wrap gap-3 items-center bg-brand-dark border border-brand-gold/20 rounded-xl p-4">
        {select(filtre.familia, (v) => setFiltre({ ...filtre, familia: v }), families, 'Totes les famílies')}
        {select(filtre.ingres, (v) => setFiltre({ ...filtre, ingres: v }), ingressos, 'Totes les categories')}
        {select(filtre.centre, (v) => setFiltre({ ...filtre, centre: v }), centres, 'Tots els departaments')}
        <select value={filtre.grup} onChange={(e) => setFiltre({ ...filtre, grup: e.target.value as Filtre['grup'] })}
          className="bg-white/5 text-white text-sm p-2 rounded border border-white/15">
          <option value="cap">Sense agrupar</option>
          <option value="familia">Agrupar per família</option>
          <option value="centre">Agrupar per departament</option>
        </select>
        <span className="text-xs text-gray-400 ml-auto">{filtrats.length} articles</span>
      </div>

      {/* Nova família ràpid */}
      <div className="flex gap-2 items-center">
        <input value={novaFamilia} onChange={(e) => setNovaFamilia(e.target.value)}
          placeholder="Nova família (ex. Licors, Gelats…)"
          className="bg-white/5 text-white text-sm p-2 rounded border border-white/15 flex-1 max-w-xs" />
        <button onClick={novaFam} className="px-3 py-2 text-sm rounded bg-white/10 hover:bg-white/20 text-white">+ família</button>
      </div>

      {/* Alta d'article */}
      <div className="bg-brand-dark border border-brand-gold/20 rounded-xl p-4 grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Nom de l'article" className="col-span-2 bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
        <input value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })}
          placeholder="Preu €" type="number" step="0.01"
          className="bg-white/5 text-white text-sm p-2 rounded border border-white/15" />
        {select(form.income_category_id, (v) => setForm({ ...form, income_category_id: v }), ingressos, 'Ingrés')}
        {select(form.family_id, (v) => setForm({ ...form, family_id: v }), families, 'Família')}
        {select(form.center_id, (v) => setForm({ ...form, center_id: v }), centres, 'Departament')}
        <button onClick={alta} className="px-4 py-2 rounded-lg bg-brand-gold text-brand-dark font-bold text-sm hover:brightness-110">
          + Afegir
        </button>
      </div>

      {/* Taula (agrupada o plana) */}
      {loading ? <p className="text-gray-400">Carregant…</p> : agrupats ? (
        agrupats.map(([grup, llista]) => (
          <div key={grup}>
            <h2 className="text-lg font-bold text-brand-gold mt-4 mb-2">{grup} <span className="text-xs text-gray-500">({llista.length})</span></h2>
            <Taula items={llista} families={families} ingressos={ingressos} centres={centres} nom={nom} esPensio={esPensio}
              cap={cap} onDbl={setFitxa} sort={sort} />
          </div>
        ))
      ) : (
        <Taula items={filtrats} families={families} ingressos={ingressos} centres={centres} nom={nom} esPensio={esPensio}
          cap={cap} onDbl={setFitxa} sort={sort} />
      )}

      {fitxa && (
        <FitxaArticle item={fitxa} families={families} ingressos={ingressos} centres={centres}
          onClose={() => setFitxa(null)} onSaved={carrega} />
      )}
    </div>
  );
}

function Taula({ items, families, ingressos, centres, nom, esPensio, cap, onDbl, sort }: {
  items: MenuItem[]; families: Family[]; ingressos: IncomeCategory[]; centres: Center[];
  nom: (l: { id: string; name: string }[], id?: string | null) => string;
  esPensio: (n: string) => boolean;
  cap: (col: string, label: string) => React.ReactNode;
  onDbl: (it: MenuItem) => void;
  sort: { col: string; dir: 'asc' | 'desc' } | null;
}) {
  return (
    <table className="w-full text-sm bg-brand-dark border border-brand-gold/20 rounded-xl overflow-hidden">
      <thead>
        <tr className="text-left text-gray-400 border-b border-brand-gold/20">
          {cap('name', 'Article')}
          {cap('price', 'Preu')}
          {cap('vat', 'IVA')}
          {cap('family', 'Família')}
          {cap('ingres', 'Cat. ingrés')}
          {cap('centre', 'Departament')}
          <th />
        </tr>
      </thead>
      <tbody>
        {items.map((it) => (
          <tr key={it.id} onDoubleClick={() => onDbl(it)} title="Doble clic: editar"
            className="border-b border-white/5 hover:bg-white/5 cursor-pointer">
            <td className="p-3">
              {it.name}
              {esPensio(it.name) && <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-brand-gold/20 text-brand-gold">pensió</span>}
            </td>
            <td className="text-right font-mono">{it.price?.toFixed(2)} €</td>
            <td className="text-gray-400">{(it as MenuItem & { vat_rate?: number }).vat_rate ?? 10}%</td>
            <td>{nom(families, it.family_id)}</td>
            <td>{nom(ingressos, it.income_category_id)}</td>
            <td>{nom(centres, (it as MenuItem & { center_id?: string }).center_id)}</td>
            <td className="text-right">
              <span className={`text-xs px-2 py-0.5 rounded-full ${(it as MenuItem & { is_available?: boolean }).is_available !== false ? 'bg-green-500/15 text-green-300' : 'bg-red-500/15 text-red-300'}`}>
                {(it as MenuItem & { is_available?: boolean }).is_available !== false ? 'actiu' : 'inactiu'}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}