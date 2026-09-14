import { API_URL_FETCH } from '@/lib/api';
/**
 * Impressió ESC/POS — envia els bytes del backend DIRECTAMENT a la impressora.
 * (Tomeu+Maria 13/09: els bytes ja porten init, negreta, tall i CP858 — mai transformar.)
 *
 * Estratègies (per ordre):
 *  1. Impressora de xarxa — POST raw al port 9100 via passarel·la local (proxy-impressora).
 *     El navegador no pot obrir TCP cru → cal una passarel·la (ex: http://localhost:9100-print)
 *     o el servidor d'impressió del client. La configuració va a localStorage.
 *  2. WebUSB (Chrome/Android) — si l'usuari ha donat permís a la impressora USB.
 *  3. Fallback: obrir el tiquet en text pla en una finestra per imprimir des del navegador.
 */

const PRINTER_KEY = 'comanda-printer';

export type PrinterConfig = {
  mode: 'gateway' | 'webusb';
  gatewayUrl?: string; // ex: http://192.168.1.50:9100 → POST bytes
};

export function getPrinterConfig(): PrinterConfig {
  if (typeof window === 'undefined') return { mode: 'gateway', gatewayUrl: '' };
  const raw = localStorage.getItem(PRINTER_KEY);
  return raw ? JSON.parse(raw) : { mode: 'gateway', gatewayUrl: '' };
}

export function setPrinterConfig(cfg: PrinterConfig) {
  localStorage.setItem(PRINTER_KEY, JSON.stringify(cfg));
}

/** Envia els bytes ESC/POS a la impressora. Retorna com s'ha imprès. */
export async function printEscpos(bytes: ArrayBuffer): Promise<'gateway' | 'webusb'> {
  const cfg = getPrinterConfig();

  if (cfg.mode === 'gateway' && cfg.gatewayUrl) {
    const res = await fetch(cfg.gatewayUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: bytes,
    });
    if (!res.ok) throw new Error(`Impressora (gateway) ${res.status}`);
    return 'gateway';
  }

  // WebUSB — cal haver demanat el dispositiu abans (requestPrinter())
  const nav = navigator as Navigator & { usb?: any };
  if (nav.usb) {
    const devices = await nav.usb.getDevices();
    const printer = devices[0];
    if (printer) {
      await printer.open();
      // La majoria d'impressores tèrmiques USB exposen interface 0 amb bulk out 1
      await printer.selectConfiguration(1);
      await printer.claimInterface(0);
      await printer.transferOut(1, new Uint8Array(bytes));
      await printer.close();
      return 'webusb';
    }
  }

  throw new Error(
    'Cap impressora configurada. Configura la passarel·la (raw 9100) o demana permís WebUSB.',
  );
}

/** Demana permís WebUSB per a la impressora tèrmica (només Chrome). */
export async function requestPrinter(): Promise<boolean> {
  const nav = navigator as Navigator & { usb?: any };
  if (!nav.usb) return false;
  try {
    await nav.usb.requestDevice({ filters: [{ classCode: 7 }] }); // class 7 = printer
    return true;
  } catch {
    return false;
  }
}

/** Baixa el tiquet i l'imprimeix (combi util per les pàgines). */
export async function imprimeixTicket(
  orderId: string,
  opts?: { payment_id?: string; copy?: boolean },
): Promise<'gateway' | 'webusb'> {
  const bytes = await (await import('@/lib/api')).api.getTicketEscpos(orderId, opts);
  return printEscpos(bytes);
}
/**
 * Imprimeix el TIQUET DE SERVEI d'una comanda (sense dades fiscals).
 * És el paper que el cambrer duu a la taula: departament, nº de comanda,
 * saldo anterior, desglossament i import. (Decisió Tomeu 14/09/2026.)
 */
export async function imprimeixTiquetServei(
  orderId: string,
  inclouAnterior = true,
): Promise<'gateway' | 'webusb'> {
  const API = API_URL_FETCH;
  const token = typeof window !== 'undefined' ? localStorage.getItem('comanda-token') || '' : '';
  const res = await fetch(
    `${API}/orders/${orderId}/tiquet-servei?format=escpos&inclou_anterior=${inclouAnterior}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!res.ok) throw new Error(`Error ${res.status} generant el tiquet de servei`);
  return printEscpos(await res.arrayBuffer());
}

/**
 * Imprimeix el TIQUET DE CUINA d'una comanda (decisió Tomeu 14/09/2026).
 * Només plats i modificacions, sense imports — lletra gran per llegir de lluny.
 * El check «Imprimir la comanda a la CUINA» de la Comandera controla si es crida.
 */
export async function imprimeixTiquetCuina(orderId: string): Promise<'gateway' | 'webusb'> {
  const API = API_URL_FETCH;
  const token = typeof window !== 'undefined' ? localStorage.getItem('comanda-token') || '' : '';
  const res = await fetch(`${API}/orders/${orderId}/tiquet-cuina?format=escpos`,
    { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`Error ${res.status} generant el tiquet de cuina`);
  return printEscpos(await res.arrayBuffer());
}
