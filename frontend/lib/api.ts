/**
 * Client API de Comanda — API REAL (sense mocks).
 * Backend: FastAPI a /api/v1 (ports dev: back 8000, front 3001).
 * Auth: login per PIN de cambrer (staff/login) → token Bearer.
 * Impressió: els tiquets ESC/POS es baixen com a bytes i s'envien
 *   directament a la impressora — MAI transformar-los (CP858).
 *
 * (Refactor Tomeu+Maria 13/09: fora MOCK_*, connexió real.)
 */

/** Àrea de la sala: barra, interior, terrassa... amb recàrrec opcional. */
export type Area = {
  id: string;
  name: string;
  position_x: number;
  position_y: number;
  surcharge_percent?: number | string;
  center_id?: string;
};

/** Taula del pla de sala: posició REAL, forma, estat i saldo pendent. */
export type Table = {
  id: string;
  number: number | string;
  area_id?: string | null;
  area?: string;
  status: 'free' | 'available' | 'occupied' | 'reserved' | 'needs_cleaning' | 'blocked' | string;
  seats?: number;
  position_x?: number;
  position_y?: number;
  shape?: string;
  is_active?: boolean;
  // === Pla de sala (decisió Tomeu 14/09/2026) ===
  /** Saldo pendent de cobrar de la comanda oberta (0 si no n'hi ha). */
  pending_amount?: number;
  /** id de la comanda oberta de la taula, si en té. */
  open_order_id?: string | null;
  /** Total ja cobrat parcialment. */
  paid_amount?: number;
};

/** Desglossament d'una comanda per al modal del pla de sala. */
export type TableComanda = {
  table_id: string;
  open: boolean;
  order_id?: string;
  status?: string;
  total_amount: number;
  discount_amount: number;
  paid_amount: number;
  pending_amount: number;
  lines: {
    id: string;
    menu_item_id?: string | null;
    name: string;
    vat_rate?: number | null;
    quantity: number;
    unit_price: number;
    amount: number;
    status?: string;
    modifications?: string[] | null;
  }[];
  payments: { id: string; method: string; amount: number; created_at?: string }[];
};
export type MenuCategory = { id: string; name: string; sort_order?: number };
export type MenuItem = {
  id: string;
  category_id?: string | null;
  income_category_id?: string | null;
  family_id?: string | null;
  center_id?: string | null;
  name: string;
  description?: string | null;
  price: number;
  vat_rate?: number;
  available?: boolean;
};
export type OrderItem = {
  id: string;
  item_id: string;
  name?: string;
  quantity: number;
  price: number;
  status?: string;
};
export type Order = {
  id: string;
  table_id: string | null;
  status: string;
  items: OrderItem[];
  total?: number;
  created_at?: string;
};
export type Staff = {
  id: string;
  name: string;
  role?: string;
  center_id?: string | null;
};
export type Shift = {
  id: string;
  staff_id: string;
  center_id: string | null;
  opened_at: string;
  closed_at?: string | null;
};
export type DayClosure = {
  id: string;
  closure_date: string;
  status?: string;
  totals?: Record<string, number>;
  created_at?: string;
};

/**
 * URL base de l'API.
 *
 * ⚠️ MAI cau a `localhost` en producció (catch 14/09/2026): quan el front es
 * desplega a `comanda.sapedrera.eu` i es compila sense NEXT_PUBLIC_API_URL, el
 * navegador del cambrer intentava cridar EL SEU PROP localhost → res no
 * carregava (centres, taules...). El patró correcte (el d'Estada) és:
 *   · si hi ha NEXT_PUBLIC_API_URL → es fa servir
 *   · si no → RUTA RELATIVA (`/api/v1`), que va al mateix domini i el
 *     servidor de Caddy/túnel ja la reenvia al backend.
 */
export const API_BASE_URL =
  typeof window === 'undefined'
    // Al SERVIDOR (SSR) cal URL absoluta; mateix host que el backend.
    ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1')
    // Al NAVEGADOR va RELATIVA: el proxy de next.config.js la reenvia al backend.
    // (Mai localhost — al mòbil del cambrer no hi ha res allà.)
    : (process.env.NEXT_PUBLIC_API_URL || '/api/v1');

const TOKEN_KEY = 'comanda-token';
const STAFF_KEY = 'comanda-staff';

function authHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getStoredStaff(): Staff | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(STAFF_KEY);
  return raw ? (JSON.parse(raw) as Staff) : null;
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(STAFF_KEY);
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  // ⚠️ Content-Type: application/json OBLIGATORI quan hi ha cos.
  // Sense aquest header, FastAPI rep el cos com a text pla i respon
  // 422 "Input should be a valid dictionary" (catch de Tomeu 14/09/2026:
  // el guardar la disposició del pla de sala petava per aquí).
  // NO s'ha de posar si el cos és FormData (multipart): el navegador ha de
  // generar ell mateix el boundary.
  const esFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
    ...authHeaders(),
  };
  if (options.body != null && !esFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });
  if (response.status === 401) {
    logout();
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    throw new Error('Sessió expirada');
  }
  if (!response.ok) {
    let detail = `API error ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch { /* cos sense JSON */ }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  /**
   * ENVIA la comanda a CUINA (decisió Tomeu 14/09/2026): els plats van al KDS
   * de la cuina i, si `imprimir`, s'imprimeix el tiquet de cuina (només plats i
   * modificacions, sense imports) a la impressora del departament.
   */
  async enviarCuina(orderId: string, imprimir = true) {
    return apiRequest<{ ok: boolean; enviat: number; text: string }>(
      `/orders/${orderId}/enviar-cuina`,
      { method: 'POST', body: JSON.stringify({ imprimir }) },
    );
  },

  // ---------- Auth (PIN) ----------
  /**
   * Bescanvia un token del porter de Jornada/Jornals per una sessió de Comanda.
   * (Un sol PIN pel cambrer — decisió Tomeu 14/09/2026.)
   */
  /** Obre el torn d'un cambrer en un centre (contracte: POST /shifts/open). */
  async openShift(staffId: string, centerId: string): Promise<Shift> {
    return apiRequest<Shift>('/shifts/open', {
      method: 'POST',
      body: JSON.stringify({ staff_id: staffId, center_id: centerId }),
    });
  },

  async sessionExchange(jornadaToken: string, deviceName = 'Comandera'): Promise<{
    token: string; staff: Staff; center_external_id?: string | null; reused?: boolean;
  }> {
    const res = await fetch(`${API_BASE_URL}/staff/session-exchange`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jornada_token: jornadaToken, device_name: deviceName }),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => null);
      throw new Error(typeof b?.detail === 'string' ? b.detail : `Error ${res.status} bescanviant el token`);
    }
    const data = await res.json();
    localStorage.setItem('comanda-token', data.token);
    localStorage.setItem('comanda-staff', JSON.stringify(data.staff));
    return data;
  },

  async login(pin: string, deviceName?: string): Promise<{ token: string; staff: Staff }> {
    const data = await apiRequest<{ token: string; staff?: Staff; access_token?: string }>(
      '/staff/login',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin, device_name: deviceName }),
      },
    );
    const token = data.token || data.access_token || '';
    const staff = data.staff || (getStoredStaff() as unknown as Staff);
    localStorage.setItem(TOKEN_KEY, token);
    if (staff) localStorage.setItem(STAFF_KEY, JSON.stringify(staff));
    return { token, staff };
  },

  async logoutServer(): Promise<void> {
    try { await apiRequest('/staff/logout', { method: 'POST' }); } catch { /* best effort */ }
    logout();
  },

  // ---------- Staff / shifts ----------
  async getStaff(): Promise<Staff[]> {
    return apiRequest<Staff[]>('/staff');
  },
  async getShifts(): Promise<Shift[]> {
    return apiRequest<Shift[]>('/shifts');
  },

  // ---------- Sala ----------
  /** Àrees de la sala. El pla de sala és PER CENTRE (decisió Tomeu 14/09/2026). */
  async getAreas(centerId?: string): Promise<Area[]> {
    const q = centerId ? `?center_id=${encodeURIComponent(centerId)}` : '';
    return apiRequest<Area[]>(`/tables/areas${q}`);
  },
  /** Taules del pla de sala. Filtrat PER CENTRE (cada punt de venda el seu pla). */
  async getTables(centerId?: string): Promise<Table[]> {
    const q = centerId ? `?center_id=${encodeURIComponent(centerId)}` : '';
    return apiRequest<Table[]>(`/tables${q}`);
  },
  async setTableStatus(tableId: string, status: string): Promise<Table> {
    return apiRequest<Table>(`/tables/${tableId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
  },

  // ---------- Menú ----------
  async getCategories(): Promise<MenuCategory[]> {
    return apiRequest<MenuCategory[]>('/menu/categories');
  },
  async getItems(): Promise<MenuItem[]> {
    return apiRequest<MenuItem[]>('/menu/items');
  },

  // ---------- Orders ----------
  async getOrders(): Promise<Order[]> {
    return apiRequest<Order[]>('/orders');
  },
  async getOrder(orderId: string): Promise<Order> {
    return apiRequest<Order>(`/orders/${orderId}`);
  },
  async createOrder(payload: {
    table_id?: string | null;
    items: { menu_item_id: string; quantity: number }[];
    notes?: string;
    order_type?: string;
    /** Cambrer que pren la comanda (va al tiquet de cuina per si cal aclarir res). */
    staff_id?: string | null;
    center_id?: string | null;
    /** Ronda del compte de la taula (1, 2, 3...) — la calcula el backend. */
    comanda_number?: number;
  }): Promise<Order> {
    // El CAMBRER s'adjunta sempre que el tinguem: és qui ha pres la comanda i
    // qui pot aclarir qualsevol cosa a la cuina (decisió Tomeu 14/09/2026).
    const staff = getStoredStaff();
    const cos = { ...payload };
    if (!cos.staff_id && staff?.id) cos.staff_id = staff.id;
    if (!cos.center_id) {
      const c = typeof window !== 'undefined' ? localStorage.getItem('comanda-centre') : null;
      if (c) cos.center_id = c;
    }
    return apiRequest<Order>('/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cos),
    });
  },
  async addItems(orderId: string, items: { menu_item_id: string; quantity: number }[]): Promise<Order> {
    return apiRequest<Order>(`/orders/${orderId}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    });
  },
  async setOrderStatus(orderId: string, status: string): Promise<Order> {
    return apiRequest<Order>(`/orders/${orderId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
  },
  async payOrder(orderId: string, payload: Record<string, unknown>): Promise<unknown> {
    return apiRequest(`/orders/${orderId}/pay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  async voidOrderItem(orderId: string, payload: Record<string, unknown>): Promise<unknown> {
    return apiRequest(`/orders/${orderId}/void`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  // ---------- Impressió ESC/POS ----------
  /**
   * Baixa els bytes ESC/POS del tiquet. El caller els envia DIRECTAMENT a la
   * impressora (raw 9100 / WebUSB / passarel·la) — MAI transformar-los.
   */
  async getTicketEscpos(orderId: string, opts?: { payment_id?: string; copy?: boolean }): Promise<ArrayBuffer> {
    const params = new URLSearchParams({ format: 'escpos' });
    if (opts?.payment_id) params.set('payment_id', opts.payment_id);
    if (opts?.copy) params.set('copy', 'true');
    const response = await fetch(`${API_BASE_URL}/orders/${orderId}/ticket?${params}`, {
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error(`Ticket error ${response.status}`);
    return await response.arrayBuffer();
  },

  // ---------- Tancament del dia (X/Z) ----------
  async runClosureX(): Promise<unknown> {
    return apiRequest('/closure/x', { method: 'POST' });
  },
  async runClosureZ(date?: string): Promise<DayClosure> {
    return apiRequest<DayClosure>('/closure/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(date ? { closure_date: date } : {}),
    });
  },
  async getClosures(): Promise<DayClosure[]> {
    return apiRequest<DayClosure[]>('/closure');
  },
  async getClosure(id: string): Promise<DayClosure> {
    return apiRequest<DayClosure>(`/closure/${id}`);
  },
};
// ---------- Carta: famílies, categories d'ingrés, centres ----------
export type IncomeCategory = { id: string; name: string; account_code?: string; sort_order?: number; is_active?: boolean };
export type Family = { id: string; name: string; sort_order?: number; is_active?: boolean };
export type Center = { id: string; name: string; external_id?: string | null; source?: string | null;
  /** Si el punt de venda permet taules obertes amb rondes acumulatives. */
  allows_open_tables?: boolean };

export const apiCarta = {
  /** Un centre concret (per saber si permet taules obertes). */
  async getCenter(id: string): Promise<Center & { allows_open_tables?: boolean }> {
    return apiRequest<Center & { allows_open_tables?: boolean }>(`/centers/${id}`);
  },
  // articles amb els 3 nivells nous
  async getItems(): Promise<MenuItem[]> {
    return apiRequest<MenuItem[]>('/menu/items');
  },
  async createItem(payload: {
    name: string; price: number; vat_rate?: number;
    income_category_id?: string | null; family_id?: string | null;
    center_id?: string | null; description?: string | null;
  }): Promise<MenuItem> {
    return apiRequest<MenuItem>('/menu/items', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  async updateItem(itemId: string, payload: Record<string, unknown>): Promise<MenuItem> {
    return apiRequest<MenuItem>(`/menu/items/${itemId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  // gestió de famílies i categories (CRUD simple)
  async getFamilies(): Promise<Family[]> { return apiRequest<Family[]>('/menu/families'); },
  async createFamily(name: string, sortOrder = 0): Promise<Family> {
    return apiRequest<Family>('/menu/families', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, sort_order: sortOrder }),
    });
  },
  async getIncomeCategories(): Promise<IncomeCategory[]> { return apiRequest<IncomeCategory[]>('/menu/income-categories'); },
  async createIncomeCategory(name: string, accountCode?: string, sortOrder = 0): Promise<IncomeCategory> {
    return apiRequest<IncomeCategory>('/menu/income-categories', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, account_code: accountCode, sort_order: sortOrder }),
    });
  },
  async getCenters(): Promise<Center[]> { return apiRequest<Center[]>('/centers'); },
};

// ---------- Room charge (càrrec a habitació) ----------
export type RoomInfo = {
  room_found: boolean;
  reservation_found: boolean;
  guest_name?: string | null;
  meal_plan?: string;
  meal_plan_price?: string;
  credit_type?: 'full' | 'limited' | 'none' | string;
  credit_limit?: string;
  folio_balance?: string;
};

export const apiRoom = {
  /** Info de l'habitació per al room charge: titular, règim i crèdit (via Comanda, mai directe a Estada). */
  async roomInfo(roomNumber: string): Promise<RoomInfo> {
    return apiRequest<RoomInfo>(`/orders/room-info?room_number=${encodeURIComponent(roomNumber)}`);
  },
};


// ============================================================
// PLA DE SALA (decisió Tomeu 14/09/2026)
// ============================================================
export const apiTable = {
  /** Desglossament de la comanda oberta d'una taula (per al modal). */
  async getComanda(tableId: string): Promise<TableComanda> {
    return apiRequest<TableComanda>(`/tables/${tableId}/comanda`);
  },
  /**
   * Canvia l'ESTAT d'una taula (lliure/ocupada/reservada/per netejar/bloquejada):
   * són els colors del peu del pla de sala (decisió Tomeu 14/09/2026).
   */
  async setEstat(tableId: string, estat: string): Promise<Table> {
    return apiRequest<Table>(`/tables/${tableId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: estat }),
    });
  },
  /** Mou una taula a una nova posició (mode edició del pla de sala). */
  async moveTable(tableId: string, x: number, y: number): Promise<Table> {
    return apiRequest<Table>(`/tables/${tableId}`, {
      method: 'PATCH',
      body: JSON.stringify({ position_x: x, position_y: y }),
    });
  },
  /** Crea una taula nova. */
  async createTable(dades: { number: string; area_id?: string; seats?: number; position_x?: number;
                             position_y?: number; shape?: string }): Promise<Table> {
    return apiRequest<Table>('/tables', { method: 'POST', body: JSON.stringify(dades) });
  },
  /** Esborra una taula. */
  async deleteTable(tableId: string): Promise<void> {
    return apiRequest<void>(`/tables/${tableId}`, { method: 'DELETE' });
  },
  /** Canvia la quantitat d'una línia de comanda. */
  async updateLine(orderId: string, lineId: string, quantity: number) {
    return apiRequest(`/orders/${orderId}/items/${lineId}`, {
      method: 'PATCH', body: JSON.stringify({ quantity }),
    });
  },
  /** Anul·la una línia de comanda (queda amb traça). */
  async voidLine(orderId: string, lineId: string) {
    return apiRequest(`/orders/${orderId}/items/${lineId}/void`, { method: 'POST' });
  },
  /** Crea una àrea nova (barra, interior, terrassa...). */
  async createArea(dades: { name: string; position_x?: number; position_y?: number;
                            surcharge_percent?: number }): Promise<Area> {
    return apiRequest<Area>('/tables/areas', { method: 'POST', body: JSON.stringify(dades) });
  },
};


/** Cambrer logueat amb el saldo pendent de les seves taules (frame de dalt). */
export type CambrerPanell = {
  shift_id: string;
  staff_id: string;
  staff_name: string;
  center_id?: string | null;
  center_name?: string | null;
  opened_at?: string | null;
  taules_obertes: number;
  comandes_obertes: number;
  saldo_pendent: number;
};

export const apiShift = {
  /** Panell de cambrers de servei (opcionalment filtrat per centre). */
  async panell(centerId?: string): Promise<CambrerPanell[]> {
    const q = centerId ? `?center_id=${encodeURIComponent(centerId)}` : '';
    return apiRequest<CambrerPanell[]>(`/shifts/panell${q}`);
  },
};

export const apiEstablishment = {
  /**
   * TOTS els establiments/hotels que l'usuari pot triar.
   *
   * Avui només n'hi ha un per desplegament. Quan es configuri el ROL D'USUARIS
   * (decisió Tomeu 14/09/2026), el backend retornarà només els hotels que
   * l'usuari tingui permesos i aquest selector canviarà entre ells sense tocar
   * res del front.
   */
  async getTots(): Promise<{ id: string; name: string; category?: string | null }[]> {
    return apiRequest<{ id: string; name: string; category?: string | null }[]>('/establishments');
  },
  /** L'establiment actiu (nom, categoria... per a la capçalera). */
  async getActiu(): Promise<{ id: string; name: string; legal_name?: string; category?: string;
                              nif?: string; city?: string }> {
    const llista = await apiRequest<{ id: string; name: string; legal_name?: string;
      category?: string; nif?: string; city?: string }[]>('/establishments');
    return llista[0] || { id: '', name: '' };
  },
};

export const apiOrdersExt = {
  /** ENVIA la comanda a CUINA: els plats (KDS) i, si es vol, imprimeix el tiquet. */
  async enviarCuina(orderId: string, imprimir = true, lineIds?: string[]) {
    return apiRequest<{ ok: boolean; enviat: number; text: string }>(
      `/orders/${orderId}/enviar-cuina`,
      { method: 'POST', body: JSON.stringify({ imprimir, line_ids: lineIds || null }) },
    );
  },
  /** Tiquet de CUINA (només plats i modificacions, sense imports). */
  async tiquetCuina(orderId: string): Promise<string> {
    const res = await fetch(`${API_BASE_URL}/orders/${orderId}/tiquet-cuina?format=text`,
      { headers: authHeaders() });
    if (!res.ok) throw new Error(`Error ${res.status} generant el tiquet de cuina`);
    return res.text();
  },
  /** Tiquet de SERVEI (sense dades fiscals) per portar a taula. */
  async tiquetServei(orderId: string, inclouAnterior = true): Promise<string> {
    const q = `?inclou_anterior=${inclouAnterior}`;
    const res = await fetch(`${API_BASE_URL}/orders/${orderId}/tiquet-servei${q}`, { headers: authHeaders() });
    if (!res.ok) throw new Error(`Error ${res.status} generant el tiquet de servei`);
    return res.text();
  },
  /** Mou línies d'una comanda a una altra (tiquets separats). */
  async moureLinies(orderId: string, lineIds: string[], destiOrderId?: string) {
    return apiRequest(`/orders/${orderId}/moure-linies`, {
      method: 'POST',
      body: JSON.stringify({ line_ids: lineIds, desti_order_id: destiOrderId || null }),
    });
  },
};


/**
 * URL base de l'API per a les crides FETCH DIRECTES (les que no passen per
 * apiRequest). MAI ha de caure a localhost en producció: al navegador del
 * cambrer no hi ha res a localhost (catch 14/09/2026).
 *
 * · Al NAVEGADOR → ruta relativa '/api/v1' (el proxy de next.config.js la
 *   reenvia al backend, al mateix domini).
 * · Al SERVIDOR  → absoluta (localhost:8000), que és on viu el backend.
 * · Sempre es pot sobreescriure amb NEXT_PUBLIC_API_URL.
 */
export const API_URL_FETCH =
  typeof window === 'undefined'
    ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1')
    : (process.env.NEXT_PUBLIC_API_URL || '/api/v1');
