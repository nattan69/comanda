/**
 * Client API de Comanda — API REAL (sense mocks).
 * Backend: FastAPI a /api/v1 (ports dev: back 8000, front 3001).
 * Auth: login per PIN de cambrer (staff/login) → token Bearer.
 * Impressió: els tiquets ESC/POS es baixen com a bytes i s'envien
 *   directament a la impressora — MAI transformar-los (CP858).
 *
 * (Refactor Tomeu+Maria 13/09: fora MOCK_*, connexió real.)
 */

export type Area = { id: string; name: string };
export type Table = {
  id: string;
  number: number;
  area_id?: string;
  area?: string;
  status: 'free' | 'occupied' | string;
  seats?: number;
};
export type MenuCategory = { id: string; name: string; sort_order?: number };
export type MenuItem = {
  id: string;
  category_id: string;
  name: string;
  price: number;
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

const API_BASE_URL =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) ||
  'http://localhost:8000/api/v1';

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
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...authHeaders(),
    },
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
  // ---------- Auth (PIN) ----------
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
  async getAreas(): Promise<Area[]> {
    return apiRequest<Area[]>('/tables/areas');
  },
  async getTables(): Promise<Table[]> {
    return apiRequest<Table[]>('/tables');
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
  }): Promise<Order> {
    return apiRequest<Order>('/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
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