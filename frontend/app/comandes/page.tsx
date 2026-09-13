'use client';
import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { api, Category, MenuItem } from '@/lib/api';
import { getT, Lang } from '@/lib/i18n';
import { Plus, ShoppingCart } from 'lucide-react';

function OrdersPageInner() {
  const searchParams = useSearchParams();
  const tableId = searchParams.get('table');
  const [lang] = useState<Lang>('ca');
  const t = getT(lang);

  const [categories, setCategories] = useState<Category[]>([]);
  const [items, setItems] = useState<MenuItem[]>([]);
  const [cart, setCart] = useState<any[]>([]);

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
              <div key={idx} className="flex justify-between items-center text-sm">
                <div className="flex-1">
                  <span className="font-medium">{item.name}</span>
                  <span className="ml-2 text-gray-400">x{item.quantity}</span>
                </div>
                <span className="font-bold">{(item.price * item.quantity).toFixed(2)} €</span>
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
                await api.createOrder(tableId!, cart);
                alert('Comanda enviada a cuina!');
                setCart([]);
              }}
            >
              {t.comandes.confirm}
            </button>
          </div>
        </div>
      </div>
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
