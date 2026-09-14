from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


# ============================================================
# STAFF
# ============================================================
class StaffBase(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "waiter"
    pin: Optional[str] = None
    is_active: bool = True


class StaffCreate(StaffBase):
    pass


class StaffOut(StaffBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: Optional[datetime] = None


# ============================================================
# AUTENTICACIÓN POR PIN (login de camarero en su dispositivo)
# ============================================================
class StaffLogin(BaseModel):
    pin: str
    device_name: Optional[str] = None


class DeviceSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    staff_id: UUID
    device_name: Optional[str] = None
    token: str
    is_active: bool
    created_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None


class LoginResponse(BaseModel):
    token: str
    staff: StaffOut
    session: DeviceSessionOut


# ============================================================
# TABLES / AREAS
# ============================================================
class AreaBase(BaseModel):
    name: str
    position_x: int = 0
    position_y: int = 0
    surcharge_percent: float = 0


class AreaCreate(AreaBase):
    pass


class AreaOut(AreaBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class TableBase(BaseModel):
    area_id: Optional[UUID] = None
    number: str
    seats: int = 4
    position_x: int = 0
    position_y: int = 0
    shape: str = "square"
    status: str = "available"
    is_active: bool = True


class TableCreate(TableBase):
    pass


class TableUpdate(BaseModel):
    area_id: Optional[UUID] = None
    number: Optional[str] = None
    seats: Optional[int] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    shape: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class TableOut(TableBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


# ============================================================
# MENU
# ============================================================
class MenuCategoryBase(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True


class MenuCategoryCreate(MenuCategoryBase):
    pass


class MenuCategoryOut(MenuCategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class MenuItemBase(BaseModel):
    category_id: Optional[UUID] = None
    income_category_id: Optional[UUID] = None  # FK a income_categories (menjar, beguda, varis, drogueria, amenities...)
    family_id: Optional[UUID] = None  # FK a families (lactis, sucs, whiskies, aperitius, snacks, cerveses, carns, peixos...)
    center_id: Optional[UUID] = None  # departament on es ven (Recepció, Minimarket...)
    name: str
    description: Optional[str] = None
    price: float
    vat_rate: float = 10.0
    kitchen_station: str = "main"
    allergens: Optional[List[str]] = None
    is_available: bool = True
    is_active: bool = True


class IncomeCategoryCreate(BaseModel):
    name: str
    account_code: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class IncomeCategoryOut(IncomeCategoryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class FamilyCreate(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True


class FamilyOut(FamilyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemOut(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class MenuItemUpdate(BaseModel):
    """PATCH parcial: només els camps enviats s'actualitzen (exclude_unset)."""
    category_id: Optional[UUID] = None
    income_category_id: Optional[UUID] = None
    family_id: Optional[UUID] = None
    center_id: Optional[UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    vat_rate: Optional[float] = None
    available: Optional[bool] = None


# ============================================================
# RESERVATIONS
# ============================================================
class ReservationBase(BaseModel):
    table_id: Optional[UUID] = None
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    party_size: int = 2
    reservation_date: date
    reservation_time: str
    status: str = "confirmed"
    notes: Optional[str] = None
    source: str = "manual"
    external_id: Optional[str] = None
    created_by: str = "staff"


class ReservationCreate(ReservationBase):
    pass


class ReservationOut(ReservationBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: Optional[datetime] = None


# ============================================================
# ORDERS
# ============================================================
class OrderItemCreate(BaseModel):
    menu_item_id: Optional[UUID] = None
    name_snapshot: Optional[str] = None
    price_snapshot: Optional[float] = None
    quantity: int = 1
    vat_rate: float = 10.0
    modifications: Optional[List[str]] = None
    seat_number: Optional[int] = None


class OrderItemOut(OrderItemCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str


class OrderCreate(BaseModel):
    table_id: Optional[UUID] = None
    staff_id: Optional[UUID] = None
    shift_id: Optional[UUID] = None
    center_id: Optional[UUID] = None
    order_type: str = "dine_in"
    notes: Optional[str] = None
    items: List[OrderItemCreate] = []


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    table_id: Optional[UUID] = None
    staff_id: Optional[UUID] = None
    order_type: str
    status: str
    total_amount: float
    discount_amount: float
    notes: Optional[str] = None
    room_number: Optional[str] = None
    ticket_code: Optional[str] = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    items: List[OrderItemOut] = []


# ============================================================
# PAYMENTS
# ============================================================
class PaymentCreate(BaseModel):
    order_id: UUID
    method: str
    amount: float
    guest_name: Optional[str] = None
    room_number: Optional[str] = None
    invited_by: Optional[str] = None
    reason: Optional[str] = None
    card_reference: Optional[str] = None


class PaymentRequest(BaseModel):
    """Body de pagament via endpoint (l'order_id ve de la URL)."""
    method: str  # cash, card, bizum, room_charge, house
    amount: float
    guest_name: Optional[str] = None  # room_charge
    room_number: Optional[str] = None  # room_charge
    invited_by: Optional[str] = None  # house
    reason: Optional[str] = None  # house
    card_reference: Optional[str] = None  # card (SoftPOS): referència de la transacció


class PaymentOut(PaymentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    ticket_code: Optional[str] = None
    paid_at: Optional[datetime] = None


# ============================================================
# FISCAL
# ============================================================
class FiscalRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_id: Optional[UUID] = None
    record_id: str
    chain_hash: str
    previous_chain_hash: Optional[str] = None
    record_type: str
    issued_at: datetime


# ============================================================
# CIERRE DEL DÍA
# ============================================================
class DayClosureRunRequest(BaseModel):
    closure_date: Optional[date] = None  # per defecte: avui


class DayClosureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    closure_date: date
    status: str
    total_sales: float
    orders_count: int
    summary: Optional[dict] = None
    emitted_to_pms: bool = False
    emitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================
# ANUL·LACIONS
# ============================================================
class VoidCreate(BaseModel):
    amount: float
    reason: Optional[str] = None
    authorized_by_id: Optional[UUID] = None  # el cap/manager que autoritza


class VoidOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_id: UUID
    amount: float
    reason: Optional[str] = None
    authorized_by_id: Optional[UUID] = None
    ticket_code: Optional[str] = None
    authorized_at: Optional[datetime] = None


class ShiftOpen(BaseModel):
    staff_id: UUID
    center_id: UUID


class ShiftClose(BaseModel):
    cash_declared: Optional[float] = None


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    staff_id: UUID
    center_id: UUID
    status: str
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    cash_declared: Optional[float] = None
    card_total: Optional[float] = None
    liquidation: Optional[dict] = None


# ============================================================
# INTEGRACIÓ JORNADA
# ============================================================
class StaffSyncCreate(BaseModel):
    external_id: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "waiter"
    is_active: bool = True


class StaffSyncOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    pin: Optional[str] = None
    is_active: bool
    external_id: Optional[str] = None
    source: str = "manual"
    shift_status: str = "off_shift"


class CenterSyncCreate(BaseModel):
    external_id: str
    name: str
    establishment_id: UUID


class CenterSyncOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    establishment_id: UUID
    external_id: Optional[str] = None
    source: str = "manual"
    active: bool


class FichajeCreate(BaseModel):
    external_id: str
    staff_external_id: str
    event_type: str  # clock_in, clock_out, break_start, break_end
    center_external_id: Optional[str] = None  # centre on s'ha fitxat (moviments entre centres)
    timestamp: datetime
    device: Optional[str] = None


class FichajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    staff_id: UUID
    external_id: str
    event_type: str
    center_id: Optional[UUID] = None
    timestamp: datetime
    device: Optional[str] = None
    source: str
    created_at: Optional[datetime] = None


class ShiftSummary(BaseModel):
    staff_id: UUID
    full_name: str
    external_id: Optional[str] = None
    shift_status: str
    center_id: Optional[UUID] = None
    last_event: Optional[dict] = None
