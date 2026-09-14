'use client';

import { useEffect, useState } from 'react';
import { api, apiCarta, apiEstablishment, getStoredStaff, Center } from '@/lib/api';
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
  //: Els establiments/hotels que l'usuari pot triar (ara un; amb el ROL
  //: D'USUARIS configurat, tants com tingui permesos — Tomeu 14/09/2026).
  const [establiments, setEstabliments] = useState<
    { id: string; name: string; category?: string | null }[]>([]);
  const [idEstabliment, setIdEstabliment] = useState<string>('');
  //: Torn del cambrer al centre triat (el panell de cambrers compta els torns
  //: OBERTS — si no se n'obre cap, el panell surt buit). Catch 14/09/2026.
  const [torn, setTorn] = useState<{ id: string; center_name?: string | null } | null>(null);
  const [msgTorn, setMsgTorn] = useState<string | null>(null);
  const [ara, setAra] = useState<Date | null>(null);

  // rellotge en viu (1 s). Null al primer render per evitar desajust d'hidratació.
  useEffect(() => {
    setAra(new Date());
    const t = setInterval(() => setAra(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // establiments (la propietat) — un sol de moment; amb rols, els permesos
  useEffect(() => {
    apiEstablishment.getTots()
      .then((es) => {
        setEstabliments(es);
        const desat = typeof window !== 'undefined' ? localStorage.getItem('comanda-establiment') : null;
        const actiu = es.find((x) => x.id === desat)?.id || es[0]?.id || '';
        setIdEstabliment(actiu);
        const e = es.find((x) => x.id === actiu);
        if (e) setHotel([e.name, e.category].filter(Boolean).join(' '));
      })
      .catch(() => {});
  }, []);

  const triaEstabliment = (id: string) => {
    setIdEstabliment(id);
    try { localStorage.setItem('comanda-establiment', id); } catch { /* privat */ }
    const e = establiments.find((x) => x.id === id);
    if (e) setHotel([e.name, e.category].filter(Boolean).join(' '));
    try { window.dispatchEvent(new Event('comanda:establiment')); } catch { /* SSR */ }
  };

  // centres + el que ja tenia triat
  useEffect(() => {
    apiCarta.getCenters().then((cs) => {
      setCentres(cs);
      const desat = typeof window !== 'undefined' ? localStorage.getItem('comanda-centre') : null;
      const actiu = desat || (cs[0]?.id ?? '');
      setCentre(actiu);
      // obrim el torn del cambrer al centre actiu (perquè compti al panell)
      if (actiu) void obreTorn(actiu);
    }).catch(() => {});
  }, []);

  /**
   * OBRE EL TORN del cambrer al centre triat.
   *
   * Sense torn obert, el cambrer no compta com a «de servei» al panell de
   * cambrers i les comandes no queden lligades al seu torn. A l'escriptori això
   * no passava perquè el login no obria torn (catch de Tomeu 14/09/2026).
   */
  const obreTorn = async (id: string) => {
    const jo = getStoredStaff();
    if (!jo?.id || !id) return;
    try {
      const t = await api.openShift(jo.id, id);
      setTorn({ id: t.id, center_name: (t as { center_name?: string | null }).center_name });
      setMsgTorn(null);
    } catch (e) {
      const m = e instanceof Error ? e.message : '';
      // Si ja en tenia un d'obert, no és cap error: hi som de servei.
      setMsgTorn(m.includes('ja té un torn') ? null : (m || 'No s\'ha pogut obrir el torn'));
    }
  };

  const triaCentre = (id: string) => {
    setCentre(id);
    try { localStorage.setItem('comanda-centre', id); } catch { /* privat */ }
    // avisa la resta de l'app (el pla de sala recarrega el pla d'aquest centre)
    try { window.dispatchEvent(new Event('comanda:centre')); } catch { /* SSR */ }
    void obreTorn(id);
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

      {/* PROPIETAT / HOTEL — SELECT (decisió Tomeu 14/09/2026).
          Quan hi hagi el ROL D'USUARIS configurat, aquest selector permetrà
          triar entre els hotels que l'usuari tingui permesos. De moment només
          n'hi ha un (el de l'establiment actiu), però l'element ja és un select
          perquè no calgui canviar-lo després. */}
      <div className="flex items-center gap-2 pr-3 mr-1"
        style={{ borderRight: '1px solid rgba(226,176,74,.2)' }}>
        <span className="text-base font-bold" style={{ color: '#e2b04a' }}>🏨</span>
        {establiments.length > 0 ? (
          <select
            value={idEstabliment}
            onChange={(e) => triaEstabliment(e.target.value)}
            className="rounded-xl px-3 py-2 text-sm font-bold outline-none"
            style={{ background: 'rgba(226,176,74,.12)', color: '#e2b04a',
                     border: '1px solid rgba(226,176,74,.3)' }}
            aria-label="Hotel / propietat">
            {establiments.map((e) => (
              <option key={e.id} value={e.id} style={{ background: '#1a1a2e', color: '#e5e9f0' }}>
                {[e.name, e.category].filter(Boolean).join(' ')}
              </option>
            ))}
          </select>
        ) : (
          <span className="text-sm font-bold" style={{ color: '#e5e9f0' }}>{hotel}</span>
        )}
      </div>

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

      {/* estat del torn */}
      {torn ? (
        <span className="text-xs px-2 py-1 rounded-lg"
          style={{ background: 'rgba(34,197,94,.15)', color: '#86efac' }}>
          🟢 torn obert
        </span>
      ) : msgTorn ? (
        <span className="text-xs px-2 py-1 rounded-lg"
          style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>
          ⚠️ {msgTorn}
        </span>
      ) : null}

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
