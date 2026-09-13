'use client';
import React, { useEffect, useState } from 'react';
import { api, Table, Area } from '@/lib/api';
import { useComandaWs, WsBadge } from '@/lib/useComandaWs';
import { getT, Lang } from '@/lib/i18n';
import { MapPin } from 'lucide-react';

export default function SalaPage() {
  const [lang] = useState<Lang>('ca');
  const t = getT(lang);
  const [tables, setTables] = useState<Table[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);

  // Temps real (WebSocket): el pla de sala es refresca en viu
  const wsStatus = useComandaWs({
    onOrderCreated: () => { api.getTables().then(setTables).catch(() => {}); },
    onOrderPaid: () => { api.getTables().then(setTables).catch(() => {}); },
  });

  useEffect(() => {
    async function load() {
      const [tData, aData] = await Promise.all([api.getTables(), api.getAreas()]);
      setTables(tData);
      setAreas(aData);
    }
    load();
  }, []);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-brand-gold">{t.sala.title}</h1>
        <WsBadge status={wsStatus} />
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {areas.map(area => (
          <div key={area.id} className="card">
            <div className="flex items-center gap-2 mb-4 text-xl font-semibold text-brand-gold">
              <MapPin size={20} />
              <span>{area.name}</span>
            </div>
            
            <div className="grid grid-cols-3 gap-4">
              {tables.filter(t => t.area === area.id).map(table => (
                <button
                  key={table.id}
                  onClick={() => window.location.href = `/comandes?table=${table.id}`}
                  className={`aspect-square flex flex-col items-center justify-center rounded-lg border-2 transition-all 
                    ${table.status === 'free' 
                      ? 'border-brand-gold text-white hover:bg-brand-gold/20' 
                      : 'border-red-500 text-red-500 bg-red-500/10'}`}
                >
                  <span className="text-lg font-bold">{table.number}</span>
                  <span className="text-xs">{t.sala.status_free === 'Lliure' ? (table.status === 'free' ? t.sala.status_free : t.sala.status_occupied) : (table.status === 'free' ? t.sala.status_free : t.sala.status_occupied)}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
