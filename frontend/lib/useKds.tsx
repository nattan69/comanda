'use client';

/**
 * Client del KDS (Kitchen Display System) — escolta el WebSocket de Comanda
 * i manté una cua de comandes pendents de preparar.
 *
 * Contracte (Maria 13/09): /api/v1/ws · events order.created · order.paid.
 *  - order.created → entra a la cua (si no hi és)
 *  - order.paid / anul·lada → surt de la cua (ja no cal preparar-la)
 *
 * La cua es guarda a localStorage perquè un refresc de pantalla no la perdi
 * (la cuina no pot quedar-se cega si algú recarrega el navegador).
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { api, Order } from '@/lib/api';
import { useComandaWs, WsEvent } from '@/lib/useComandaWs';

export type ComandaCuina = {
  id: string;
  table_id: string | null;
  ticket_code?: string;
  creada: number;          // timestamp per ordenar
  items: { name: string; quantity: number; modifications?: string[] | null; comanda_number?: number }[];
  total?: number;
  centre?: string | null;
  table_number?: string | number | null;
  comanda_number?: number;
};

const CLAU = 'kds-cua';

function carregaCua(): ComandaCuina[] {
  if (typeof window === 'undefined') return [];
  try {
    const brut = localStorage.getItem(CLAU);
    return brut ? (JSON.parse(brut) as ComandaCuina[]) : [];
  } catch {
    return [];
  }
}

function desaCua(cua: ComandaCuina[]) {
  if (typeof window === 'undefined') return;
  try { localStorage.setItem(CLAU, JSON.stringify(cua)); } catch { /* ple o privat */ }
}

export function useKds() {
  const [cua, setCua] = useState<ComandaCuina[]>([]);
  const cuaRef = useRef<ComandaCuina[]>([]);
  cuaRef.current = cua;

  // arrencar amb el que hi havia guardat
  useEffect(() => { setCua(carregaCua()); }, []);

  // persistir cada canvi
  useEffect(() => { desaCua(cua); }, [cua]);

  /** Carrega els detalls d'una comanda (items) i l'afegeix a la cua. */
  const afegeix = useCallback(async (ev: WsEvent) => {
    const id = ev.payload?.order_id;
    if (!id) return;
    if (cuaRef.current.some((c) => c.id === id)) return;   // ja hi és

    // Els PLATS VENEN AL PROPI ESDEVENIMENT (l'esdeveniment porta `items`):
    // la cuina ha de saber QUÈ preparar, i no pot esperar una segona crida.
    const itemsEvent = Array.isArray(ev.payload.items) ? ev.payload.items : [];
    const entrada: ComandaCuina = {
      id,
      table_id: ev.payload.table_id ?? null,
      ticket_code: ev.payload.ticket_code,
      creada: Date.now(),
      items: itemsEvent.map((i: any) => ({
        name: i.name || 'Article',
        quantity: i.quantity ?? 1,
        modifications: i.modifications ?? null,
        comanda_number: i.comanda_number,
      })),
      total: typeof ev.payload.total_amount === 'number' ? ev.payload.total_amount : undefined,
      centre: ev.payload.center_id ?? null,
      table_number: ev.payload.table_number ?? null,
      comanda_number: ev.payload.comanda_number,
    };
    setCua((c) => [...c, entrada]);

    // Si l'esdeveniment NO duia els plats (backend vell), els demanem.
    if (itemsEvent.length === 0) {
      try {
        const totes = await api.getOrders();
        const o = totes.find((x) => x.id === id);
        if (o) {
          setCua((c) => c.map((x) => (x.id === id ? {
            ...x,
            items: (o.items || []).map((i) => ({
              name: i.name || 'Article',
              quantity: i.quantity,
              modifications: (i as any).modifications ?? null,
            })),
            total: o.total ?? x.total,
            table_id: o.table_id ?? x.table_id,
          } : x)));
        }
      } catch { /* sense xarxa: la comanda ja és a la cua amb l'essencial */ }
    }
  }, []);

  /** Treu una comanda de la cua (servida o pagada). */
  const treure = useCallback((id: string) => {
    setCua((c) => c.filter((x) => x.id !== id));
  }, []);

  const buidar = useCallback(() => setCua([]), []);

  const wsStatus = useComandaWs({
    onOrderCreated: (ev) => { void afegeix(ev); },
    // Enviament explícit a cuina (botó «Enviar a cuina»)
    onOrderSentToKitchen: (ev) => { void afegeix(ev); },
    onOrderPaid: (ev) => {
      // pagada = servida → fora de la cua
      const id = ev.payload?.order_id;
      if (id) treure(id);
    },
  });

  /** Marcar manualment una comanda com a preparada (botó de la cuina). */
  const marcarPreparada = useCallback((id: string) => treure(id), [treure]);

  return { cua, status: wsStatus, marcarPreparada, treure, buidar };
}
