'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { api, apiCarta, getStoredStaff, MenuItem, MenuCategory, Order } from '@/lib/api';
import { useComandaWs } from '@/lib/useComandaWs';

/**
 * COMANDERA · Taula — prendre la comanda des del mòbil/PDA.
 * Carta en graella (un dit), carretó flotant i enviament a cuina.
 * Contracte: POST /orders { table_id, staff_id, shift_id, center_id, items:[{menu_item_id, quantity}] }
 */

type Linia = { item: MenuItem; qty: number };

export default function ComanderaTaula() {
  const router = useRouter();
  const params = useParams();
  const taulaId = String(params?.id || '');

  const [items, setItems] = useState<MenuItem[]>([]);
  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [catActiva, setCatActiva] = useState<string>('');
  const [carret, setCarret] = useState<Linia[]>([]);
  const [comanda, setComanda] = useState<Order | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [enviant, setEnviant] = useState(false);
  const [tornId, setTornId] = useState<string | null>(null);
  //: CHECK «Taules obertes» (decisió Tomeu 14/09/2026): si està HABILITAT,
  //: el centre permet comptes de taula amb rondes acumulatives (es paga al final);
  //: si NO, cada consumició s'ha de cobrar i no s'acumula res.
  //: El valor ve del CENTRE (política del punt de venda), no és una tria puntual.
  const [taulesObertes, setTaulesObertes] = useState(true);

  //: CHECK «Imprimir a cuina» (decisió Tomeu 14/09/2026): en enviar la comanda,
  //: s'imprimeix el TIQUET DE CUINA (només els plats i les modificacions,
  //: sense imports) a la impressora tèrmica del departament.
  const [imprimirCuina, setImprimirCuina] = useState(true);

  const staff = typeof window !== 'undefined' ? getStoredStaff() : null;

  useEffect(() => {
    (async () => {
      try {
        const [it, cat, shifts] = await Promise.all([api.getItems(), api.getCategories(), api.getShifts()]);
        setItems(it);
        setCategories(cat);
        if (cat[0]) setCatActiva(cat[0].id);
        const jo = getStoredStaff();
        const meu = jo ? shifts.find((s) => s.staff_id === jo.id && !s.closed_at) : null;
        setTornId(meu?.id || null);
        // si la taula ja té comanda oberta, la carreguem
        const totes = await api.getOrders();
        const oberta = totes.find((o) => o.table_id === taulaId && o.status !== 'paid' && o.status !== 'closed');
        if (oberta) setComanda(oberta);

        // política de taules obertes del centre on som
        try {
          const idCentre = localStorage.getItem('comanda-centre');
          if (idCentre) {
            const cen = await apiCarta.getCenter(idCentre);
            setTaulesObertes(cen.allows_open_tables !== false);
          }
        } catch { /* sense política → per defecte permet */ }
      } catch (e) {
        setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error carregant la carta' });
      }
    })();
  }, [taulaId]);

  // en viu: si la comanda d'aquesta taula canvia (altre cambrer la modifica), refresca
  useComandaWs({
    onOrderCreated: () => {
      api.getOrders().then((totes) => {
        const oberta = totes.find((o) => o.table_id === taulaId && o.status !== 'paid' && o.status !== 'closed');
        setComanda(oberta || null);
      }).catch(() => {});
    },
  });

  const visibles = useMemo(
    () => items.filter((i) => !catActiva || i.category_id === catActiva),
    [items, catActiva],
  );

  const total = carret.reduce((s, l) => s + l.item.price * l.qty, 0);
  const unitats = carret.reduce((s, l) => s + l.qty, 0);

  const afegir = (item: MenuItem) => {
    setCarret((c) => {
      const i = c.findIndex((l) => l.item.id === item.id);
      if (i >= 0) { const n = [...c]; n[i] = { ...n[i], qty: n[i].qty + 1 }; return n; }
      return [...c, { item, qty: 1 }];
    });
  };
  const treure = (itemId: string) => {
    setCarret((c) => {
      const i = c.findIndex((l) => l.item.id === itemId);
      if (i < 0) return c;
      const n = [...c];
      if (n[i].qty > 1) n[i] = { ...n[i], qty: n[i].qty - 1 };
      else n.splice(i, 1);
      return n;
    });
  };

  const enviar = async () => {
    if (!carret.length || !staff) return;
    setEnviant(true); setMsg(null);
    try {
      // Política: sense taules obertes no es pot acumular sobre un compte pendent
      if (!taulesObertes && comanda) {
        setMsg({ ok: false, text: '⛔ Aquest punt de venda no permet taules obertes: cal cobrar la comanda abans de fer-ne més.' });
        setEnviant(false);
        return;
      }
      const linies = carret.map((l) => ({ menu_item_id: l.item.id, quantity: l.qty }));
      let ordreId = comanda?.id || null;
      const eraNova = !comanda;

      if (comanda) {
        await api.addItems(comanda.id, linies);
      } else {
        const o = await api.createOrder({ table_id: taulaId, items: linies });
        setComanda(o);
        ordreId = o?.id || null;
      }
      setCarret([]);

      // ENVIAMENT A CUINA (decisió Tomeu 14/09/2026): els plats van a la cuina
      // (KDS) i, si el check està marcat, s'imprimeix el tiquet de cuina.
      let text = eraNova ? 'Comanda enviada' : 'Afegit a la comanda';
      if (ordreId) {
        try {
          await api.enviarCuina(ordreId, imprimirCuina);
          text += ' · cuina avisada 🍳';
          if (imprimirCuina) text += ' i impresa';
        } catch {
          text += " · (no s'ha pogut avisar la cuina)";
        }
      }
      setMsg({ ok: true, text: text + ' ✅' });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error enviant' });
    } finally { setEnviant(false); }
  };

  const cobrar = async () => {
    if (!comanda) return;
    router.push(`/comandes?table=${taulaId}`);
  };

  const imprimir = async () => {
    if (!comanda) return;
    try {
      const { imprimeixTicket } = await import('@/lib/printer');
      await imprimeixTicket(comanda.id);
      setMsg({ ok: true, text: 'Tiquet enviat a la impressora 🖨️' });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : 'Error imprimint' });
    }
  };

  return (
    <div className="pb-40" style={{ background: '#0f1729', minHeight: '100vh' }}>
      {/* capçalera */}
      <div className="sticky top-0 z-10 px-4 py-3 flex items-center gap-3" style={{ background: '#1a1a2e' }}>
        <button onClick={() => router.push('/comandera/sala')}
          className="text-2xl leading-none px-2" style={{ color: '#e2b04a' }}>←</button>
        <div className="flex-1">
          <div className="text-lg font-bold" style={{ color: '#e2b04a' }}>Taula {taulaId.slice(0, 6)}</div>
          {comanda && <div className="text-xs" style={{ color: '#9aa7b8' }}>comanda oberta</div>}
        </div>
        {comanda && (
          <button onClick={imprimir} className="text-xl px-2" title="Imprimir">🖨️</button>
        )}
      </div>

      {msg && (
        <div className="mx-4 mt-3 px-4 py-2 rounded-lg text-sm"
          style={{ background: msg.ok ? 'rgba(34,197,94,.15)' : 'rgba(239,68,68,.15)', color: msg.ok ? '#86efac' : '#fca5a5' }}>
          {msg.text}
        </div>
      )}

      {/* categories */}
      <div className="flex gap-2 overflow-x-auto px-4 py-3">
        {categories.map((c) => (
          <button key={c.id} onClick={() => setCatActiva(c.id)}
            className="shrink-0 px-4 py-2 rounded-full text-sm font-semibold transition"
            style={{
              background: catActiva === c.id ? '#e2b04a' : 'rgba(255,255,255,.07)',
              color: catActiva === c.id ? '#1a1a2e' : '#e5e9f0',
            }}>
            {c.name}
          </button>
        ))}
      </div>

      {/* articles en graella */}
      <div className="grid grid-cols-2 gap-3 px-4">
        {visibles.map((it) => {
          const alCarret = carret.find((l) => l.item.id === it.id)?.qty || 0;
          return (
            <div key={it.id} className="rounded-2xl p-4 flex flex-col justify-between"
              style={{ background: 'rgba(255,255,255,.06)', border: alCarret ? '2px solid #e2b04a' : '2px solid transparent', minHeight: 100 }}>
              <div>
                <div className="text-sm font-semibold" style={{ color: '#e5e9f0' }}>{it.name}</div>
                <div className="text-xs mt-1" style={{ color: '#9aa7b8' }}>{it.price?.toFixed(2)} €</div>
              </div>
              <div className="flex items-center justify-between mt-3">
                {alCarret > 0 ? (
                  <>
                    <button onClick={() => treure(it.id)}
                      className="w-10 h-10 rounded-xl text-xl font-bold"
                      style={{ background: 'rgba(255,255,255,.1)', color: '#e5e9f0' }}>−</button>
                    <span className="text-lg font-bold" style={{ color: '#e2b04a' }}>{alCarret}</span>
                    <button onClick={() => afegir(it)}
                      className="w-10 h-10 rounded-xl text-xl font-bold"
                      style={{ background: '#e2b04a', color: '#1a1a2e' }}>+</button>
                  </>
                ) : (
                  <button onClick={() => afegir(it)}
                    className="w-full h-10 rounded-xl font-bold"
                    style={{ background: 'rgba(226,176,74,.2)', color: '#e2b04a' }}>+ Afegir</button>
                )}
              </div>
            </div>
          );
        })}
        {visibles.length === 0 && (
          <div className="col-span-2 text-center py-10 text-gray-500 text-sm">Sense articles en aquesta categoria</div>
        )}
      </div>

      {/* carretó flotant */}
      {unitats > 0 && (
        <div className="fixed bottom-0 left-0 right-0 p-4" style={{ background: '#1a1a2e' }}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm" style={{ color: '#9aa7b8' }}>{unitats} articles</span>
            <span className="text-xl font-bold" style={{ color: '#e2b04a' }}>{total.toFixed(2)} €</span>
          </div>
          <label className="flex items-center gap-3 mb-3 cursor-pointer select-none">
            <input type="checkbox" checked={imprimirCuina} onChange={(e) => setImprimirCuina(e.target.checked)}
              className="w-5 h-5 accent-amber-400" />
            <span className="text-sm" style={{ color: '#e5e9f0' }}>
              🖨️ Imprimir la comanda a la CUINA
            </span>
          </label>
          <label className="flex items-center gap-3 mb-3 select-none"
            title={taulesObertes ? 'Aquest punt de venda permet acumular rondes a la taula' : 'Cada consumició s\'ha de cobrar'}>
            <input type="checkbox" checked={taulesObertes} disabled
              className="w-5 h-5 accent-amber-400" />
            <span className="text-sm" style={{ color: taulesObertes ? '#e5e9f0' : '#fca5a5' }}>
              {taulesObertes ? '🪑 Taules obertes (rondes acumulatives)' : '🪑 Taules obertes DESACTIVADES — cal cobrar cada comanda'}
            </span>
            {!taulesObertes && comanda && (
              <span className="ml-auto text-xs font-bold" style={{ color: '#fca5a5' }}>
                pendent {parseFloat(String(comanda.total || 0)).toFixed(2)}€
              </span>
            )}
          </label>
          <button onClick={enviar} disabled={enviant}
            className="w-full rounded-2xl font-bold text-lg disabled:opacity-40"
            style={{ height: 56, background: '#e2b04a', color: '#1a1a2e' }}>
            {enviant ? 'Enviant…' : 'Enviar a cuina'}
          </button>
        </div>
      )}

      {/* si ja hi ha comanda oberta, botó de cobrar sempre visible */}
      {unitats === 0 && comanda && (
        <div className="fixed bottom-0 left-0 right-0 p-4" style={{ background: '#1a1a2e' }}>
          <button onClick={cobrar}
            className="w-full rounded-2xl font-bold text-lg"
            style={{ height: 56, background: '#22c55e', color: '#052e16' }}>
            💰 Cobrar la comanda
          </button>
        </div>
      )}
    </div>
  );
}