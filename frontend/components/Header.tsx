'use client';

import { useEffect, useState } from 'react';
import { apiCarta, apiEstablishment, Center } from '@/lib/api';
import { useIdioma } from '@/lib/idioma';
import { Lang } from '@/lib/i18n';

/**
 * HEADER DE L'APP (decisió Tomeu 14/09/2026).
 * Conté, d'esquerra a dreta:
 *   · 🏪 «Tria el punt de venda» — el centre actiu del cambrer
 *   · 🌐 Selector d'idioma (CA / ES / EN) — global, es recorda
 *   · 🕐 Data i hora en viu (es refresca cada segon)
 *
 * La data/hora també és la que va als tiquets (es genera al servidor en
 * imprimir/cobrar, amb el rellotge del dispositiu com a referència visual).
 */
export default function Header() {
  const { lang, setLang } = useIdioma();
  const [centres, setCentres] = useState<Center[]>([]);
  const [centre, setCentre] = useState<string>('');
  // Nom de la PROPIETAT/Hotel (decisió Tomeu 14/09/2026): ex. «Hotel Sa Ràpita ****»
  const [hotel, setHotel] = useState<string>('');
  const [ara, setAra] = useState<Date | null>(null);

  // rellotge en viu (1 s). Null al primer render per evitar desajust d'hidratació.
  useEffect(() => {
    setAra(new Date());
    const t = setInterval(() => setAra(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // nom de l'establiment (la propietat)
  useEffect(() => {
    apiEstablishment.getActiu()
      .then((e) => setHotel([e.name, e.category].filter(Boolean).join(' ')))
      .catch(() => {});
  }, []);

  // centres + el que ja tenia triat
  useEffect(() => {
    apiCarta.getCenters().then((cs) => {
      setCentres(cs);
      const desat = typeof window !== 'undefined' ? localStorage.getItem('comanda-centre') : null;
      setCentre(desat || (cs[0]?.id ?? ''));
    }).catch(() => {});
  }, []);

  const triaCentre = (id: string) => {
    setCentre(id);
    try { localStorage.setItem('comanda-centre', id); } catch { /* privat */ }
  };

  const dataHora = ara
    ? `${ara.toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })}  ${ara.toLocaleTimeString('ca-ES')}`
    : '';

  const IDIOMES: { codi: Lang; etiqueta: string }[] = [
    { codi: 'ca', etiqueta: 'CA' },
    { codi: 'es', etiqueta: 'ES' },
    { codi: 'en', etiqueta: 'EN' },
  ];

  return (
    <header className="flex items-center gap-3 flex-wrap px-5 py-3"
      style={{ background: '#141429', borderBottom: '1px solid rgba(226,176,74,.2)' }}>

      {/* PROPIETAT / HOTEL */}
      {hotel && (
        <div className="flex items-center gap-2 pr-3 mr-1"
          style={{ borderRight: '1px solid rgba(226,176,74,.2)' }}>
          <span className="text-base font-bold" style={{ color: '#e2b04a' }}>🏨</span>
          <span className="text-sm font-bold" style={{ color: '#e5e9f0' }}>{hotel}</span>
        </div>
      )}

      {/* PUNT DE VENDA */}
      <div className="flex items-center gap-2">
        <span className="text-lg" aria-hidden>🏪</span>
        <select
          value={centre}
          onChange={(e) => triaCentre(e.target.value)}
          className="rounded-xl px-3 py-2 text-sm font-semibold outline-none"
          style={{ background: 'rgba(255,255,255,.07)', color: '#e5e9f0', border: '1px solid rgba(226,176,74,.25)' }}
          aria-label="Tria el punt de venda">
          {centres.length === 0 && <option value="">Tria el punt de venda</option>}
          {centres.map((c) => (
            <option key={c.id} value={c.id} style={{ background: '#1a1a2e' }}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1" />

      {/* IDIOMA */}
      <div className="flex items-center rounded-xl overflow-hidden"
        style={{ border: '1px solid rgba(226,176,74,.25)' }}>
        {IDIOMES.map((i) => (
          <button key={i.codi} onClick={() => setLang(i.codi)}
            className="px-3 py-2 text-xs font-bold transition"
            style={{
              background: lang === i.codi ? '#e2b04a' : 'rgba(255,255,255,.04)',
              color: lang === i.codi ? '#1a1a2e' : '#9aa7b8',
            }}
            aria-pressed={lang === i.codi}>
            {i.etiqueta}
          </button>
        ))}
      </div>

      {/* DATA I HORA */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl"
        style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(226,176,74,.25)' }}>
        <span aria-hidden>🕐</span>
        <span className="text-sm font-semibold tabular-nums" style={{ color: '#e5e9f0' }}>
          {dataHora || '\u00A0'}
        </span>
      </div>
    </header>
  );
}
