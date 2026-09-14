'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { getT, Lang, translations } from '@/lib/i18n';

/**
 * CONTEXT D'IDIOMA GLOBAL (decisió Tomeu 14/09/2026).
 * Abans cada pàgina tenia l'idioma fix a 'ca' — ara el selector del header
 * el canvia per a tota l'app i queda recordat.
 */

type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** Traduccions de l'idioma actiu. */
  t: ReturnType<typeof getT>;
};

const IdiomaCtx = createContext<Ctx | null>(null);

const CLAU = 'comanda-idioma';

export function IdiomaProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>('ca');

  useEffect(() => {
    const desat = typeof window !== 'undefined'
      ? (localStorage.getItem(CLAU) as Lang | null)
      : null;
    if (desat && desat in translations) setLangState(desat);
  }, []);

  const setLang = (l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(CLAU, l); } catch { /* privat */ }
  };

  return (
    <IdiomaCtx.Provider value={{ lang, setLang, t: getT(lang) }}>
      {children}
    </IdiomaCtx.Provider>
  );
}

export function useIdioma(): Ctx {
  const c = useContext(IdiomaCtx);
  // Fora del provider (p. ex. la Comandera), degradació neta a català
  if (!c) return { lang: 'ca', setLang: () => {}, t: getT('ca') };
  return c;
}
