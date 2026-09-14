'use client';
import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { api, MenuCategory, MenuItem } from '@/lib/api';
import { useIdioma } from '@/lib/idioma';
import { Plus, ShoppingCart, CreditCard, Printer, Undo2 } from 'lucide-react';
import ModalCobrar from '@/components/ModalCobrar';
import ModalVoid from '@/components/ModalVoid';
import { imprimeixTicket } from '@/lib/printer';
import { getStoredStaff } from '@/lib/api';

function OrdersPageInner() {
  const searchParams = useSearchParams();
  const tableId = searchParams.get('table');
  const { lang, t } = useIdioma();

  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [items, setItems] = useState<MenuItem[]>([]);
  const [cart, setCart] = useState<any[]>([]);
  const [orderId, setOrderId] = useState<string | null>(null);       // comanda enviada d'aquesta taula
  const [orderTotal, setOrderTotal] = useState(0);                    // total de la comanda enviada (fix total=0)
  const [modal, setModal] = useState<'cobrar' | 'void' | null>(null);
  const [printing, setPrinting] = useState(false);

  useEffect(() => {
    async function load() {
      const [cData, iData] = await Promise.all([api.getCategories(), api.getItems()]);
      setCategories(cData);
      setItems(iData);
    }
    load();
  }, []);

  const addToCart = (item: MenuItem) => {
    setCart(prev => {
      const existing = prev.find(i => i.id === item.id);
      if (existing) {
        return prev.map(i => i.id === item.id ? { ...i, quantity: i.quantity + 1 } : i);
      }
      return [...prev, { ...item, quantity: 1 }];
    });
  };

  const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

  /** Posa/treu una modificació d'una línia del carret («fora ceba», «poc fet»...). */
  const alternaMod = (idx: number, mod: string) => {
    setCart((c) => c.map((l, i) => {
      if (i !== idx) return l;
      const mods: string[] = l.mods || [];
      return { ...l, mods: mods.includes(mod) ? mods.filter((m) => m !== mod) : [...mods, mod] };
    }));
  };

  return (
    <div className="p-6 flex flex-col md:flex-row gap-8">
      <div className="flex-1">
        <h1 className="text-3xl font-bold mb-8 text-brand-gold">{t.comandes.title}</h1>
        <div className="mb-6 p-4 card inline-block">
          <span className="font-bold">Taula: </span>
          <span className="text-brand-gold">{tableId || 'No seleccionada'}</span>
        </div>

        <div className="space-y-8">
          {categories.map(cat => (
            <div key={cat.id}>
              <h2 className="text-xl font-semibold mb-4 border-b border-brand-gold/30 pb-2">{cat.name}</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {items.filter(i => i.category_id === cat.id).map(item => (
                  <button
                    key={item.id}
                    onClick={() => addToCart(item)}
                    className="card text-left hover:bg-brand-navy/80 transition-colors flex justify-between items-center group"
                  >
                    <div>
                      <div className="font-medium">{item.name}</div>
                      <div className="text-sm text-gray-400">{item.price.toFixed(2)} €</div>
                    </div>
                    <Plus size={20} className="text-brand-gold opacity-0 group-hover:opacity-100 transition-opacity" />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="w-full md:w-80">
        <div className="card sticky top-6">
          <div className="flex items-center gap-2 text-xl font-bold mb-6 text-brand-gold">
            <ShoppingCart size={24} />
            <span>{t.comandes.menu}</span>
          </div>

          <div className="space-y-4 mb-6 max-h-[60vh] overflow-y-auto">
            {cart.length === 0 && <p className="text-gray-500 text-center py-4">Comanda buida</p>}
            {cart.map((item, idx) => (
              <div key={idx} className="rounded-xl px-3 py-2 bg-white/5">
                <div className="flex justify-between items-center text-sm">
                  <div className="flex-1">
                    <span className="font-medium">{item.name}</span>
                    <span className="ml-2 text-gray-400">x{item.quantity}</span>
                  </div>
                  <span className="font-bold">{(item.price * item.quantity).toFixed(2)} €</span>
                </div>

                {/* MODIFICACIONS (decisió Tomeu 14/09/2026): «fora ceba» d'un toc.
                    Van al tiquet de cuina i al KDS. */}
                {(item.mods || []).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {(item.mods as string[]).map((m) => (
                      <button key={m} onClick={() => alternaMod(idx, m)}
                        className="px-2 py-0.5 rounded-lg text-xs font-bold"
                        style={{ background: 'rgba(239,68,68,.2)', color: '#fca5a5' }}>
                        {m} ✕
                      </button>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap gap-1 mt-2">
                  {MODS_TPV.map((m) => {
                    const triat = (item.mods || []).includes(m);
                    return (
                      <button key={m} onClick={() => alternaMod(idx, m)}
                        className="px-2 py-1 rounded-lg text-[11px]"
                        style={{
                          background: triat ? 'rgba(226,176,74,.25)' : 'rgba(255,255,255,.06)',
                          color: triat ? '#e2b04a' : '#9aa7b8',
                          border: triat ? '1px solid #e2b04a' : '1px solid transparent',
                        }}>
                        {m}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-brand-gold/30 pt-4 space-y-4">
            <div className="flex justify-between text-xl font-bold">
              <span>{t.comandes.total}</span>
              <span className="text-brand-gold">{total.toFixed(2)} €</span>
            </div>
            <button 
              className="btn-primary w-full py-3"
              disabled={cart.length === 0 || !tableId}
              onClick={async () => {
                const o = await api.createOrder({
                  table_id: tableId,
                  items: cart.map(i => ({
                    menu_item_id: i.id,
                    quantity: i.quantity,
                    // les modificacions del plat («sense ceba»...) van a la cuina
                    modifications: (i.mods || []).length ? i.mods : null,
                  })),
                });
                // avisem la CUINA (KDS) amb els plats i les modificacions
                try { await api.enviarCuina(String((o as any)?.id), false); } catch { /* el KDS ja rebrà order.created */ }
                alert('Comanda enviada a cuina!');
                setOrderTotal(total);  // guardar el total abans de buidar el carret
                setOrderId((o as any)?.id ?? null);
                setCart([]);
              }}
            >
              {t.comandes.confirm}
            </button>

            {orderId && (
              <div className="grid grid-cols-3 gap-2 mt-3">
                <button onClick={() => setModal('cobrar')}
                  className="py-3 rounded-xl bg-green-500/90 hover:bg-green-500 text-white font-bold text-sm flex items-center justify-center gap-2 transition">
                  <CreditCard size={18} /> Cobrar
                </button>
                <button onClick={() => setModal('void')}
                  className="py-3 rounded-xl bg-red-500/80 hover:bg-red-500 text-white font-bold text-sm flex items-center justify-center gap-2 transition">
                  <Undo2 size={18} /> Anul·lar
                </button>
                <button
                  disabled={printing}
                  onClick={async () => {
                    setPrinting(true);
                    try { await imprimeixTicket(orderId); alert('Tiquet enviat a la impressora'); }
                    catch (e) { alert(e instanceof Error ? e.message : 'Error imprimint'); }
                    finally { setPrinting(false); }
                  }}
                  className="py-3 rounded-xl bg-white/10 hover:bg-white/20 text-white font-bold text-sm flex items-center justify-center gap-2 transition disabled:opacity-40">
                  <Printer size={18} /> {printing ? '…' : 'Imprimir'}
                </button>
              </div>
            )}
          </div>
          </div>
        </div>
      {modal === 'cobrar' && orderId && (
        <ModalCobrar orderId={orderId} total={orderTotal}
          onClose={() => setModal(null)}
          onPaid={() => { setModal(null); alert('Cobrament registrat ✅'); setOrderId(null); }} />
      )}
      {modal === 'void' && orderId && (
        <ModalVoid orderId={orderId} total={orderTotal}
          onClose={() => setModal(null)}
          onVoid={() => { setModal(null); alert('Càrrec anul·lat'); }} />
      )}
    </div>
  );
}

export default function OrdersPage() {
  return (
    <Suspense fallback={<div className="p-6 text-gray-400">Carregant...</div>}>
      <OrdersPageInner />
    </Suspense>
  );
}
