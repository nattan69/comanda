'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * Client WebSocket del temps real de Comanda (contracte Maria 13/09).
 * Endpoint: /api/v1/ws — ws:// a dev, wss:// a prod (seguint location.host).
 * Esdeveniments: order.created · order.paid.
 * Auto-reconnexió exponencial (1s→8s) — els reconnects no perden res que passi després.
 */

export type WsEvent = {
  type: 'order.created' | 'order.paid' | string;
  payload: {
    order_id?: string;
    ticket_code?: string;
    table_id?: string | null;
    center_id?: string | null;
    payment_id?: string;
    method?: string;
    amount?: string | number;
    total_amount?: string | number;
  };
};

type Handlers = {
  onOrderCreated?: (e: WsEvent) => void;
  onOrderPaid?: (e: WsEvent) => void;
  /** La comanda s'ha enviat explícitament a cuina (botó «Enviar a cuina»). */
  onOrderSentToKitchen?: (e: WsEvent) => void;
  onStatus?: (status: 'connectant' | 'viu' | 'caigut') => void;
};

export function useComandaWs(handlers: Handlers) {
  const [status, setStatus] = useState<'connectant' | 'viu' | 'caigut'>('connectant');
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number | null>(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // handlers a refs per no re-connectar en cada render
  const h = useRef(handlers);
  h.current = handlers;

  useEffect(() => {
    let cancelled = false;

    const connecta = () => {
      if (cancelled) return;
      const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${proto}//${window.location.host}/api/v1/ws`;
      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          setStatus('viu');
          retryRef.current = null;
        };
        ws.onmessage = (msg) => {
          try {
            const ev: WsEvent = JSON.parse(msg.data as string);
            if (ev.type === 'order.created') h.current.onOrderCreated?.(ev);
            else if (ev.type === 'order.paid') h.current.onOrderPaid?.(ev);
            else if (ev.type === 'order.sent_to_kitchen') h.current.onOrderSentToKitchen?.(ev);
          } catch { /* missatge no JSON — ignora */ }
        };
        ws.onclose = () => {
          if (cancelled) return;
          setStatus('caigut');
          const delay = Math.min(8000, 1000 * 2 ** (retryRef.current ?? 0));
          timerRef.current = setTimeout(connecta, delay);
          retryRef.current = (retryRef.current ?? 0) + 1;
        };
        ws.onerror = () => ws.close();
      } catch {
        setStatus('caigut');
        timerRef.current = setTimeout(connecta, 3000);
      }
    };

    connecta();
    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, []);

  return status;
}

/** Badge de connexió pel header: ● viu (verd) / connectant (ambar) / caigut (vermell). */
export function WsBadge({ status }: { status: 'connectant' | 'viu' | 'caigut' }) {
  const colors = {
    viu: 'bg-green-500/20 text-green-300',
    connectant: 'bg-amber-500/20 text-amber-300',
    caigut: 'bg-red-500/20 text-red-300',
  };
  const label = { viu: 'en viu', connectant: 'connectant…', caigut: 'desconnectat' };
  return (
    <span className={`text-xs px-2 py-1 rounded-full ${colors[status]}`}>
      ● {label[status]}
    </span>
  );
}