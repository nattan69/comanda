from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Integer, Date, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..db import Base
import uuid

# Helper para UUIDs compatibles con SQLite y Postgres
def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# ============================================================
# PERSONAL (cambreros)
# ============================================================
class Staff(Base):
    __tablename__ = 'staff'
    id = uuid_pk()
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True)
    phone = Column(String)
    role = Column(String, nullable=False)  # admin, manager, waiter, kitchen, bar
    pin = Column(String)  # PIN de acceso rápido al TPV (hash en producción)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============================================================
# SESIONES DE DISPOSITIVO (PDA / móvil / tablet por camarero)
# ============================================================
class DeviceSession(Base):
    __tablename__ = 'device_sessions'
    id = uuid_pk()
    staff_id = Column(UUID(as_uuid=True), ForeignKey('staff.id', ondelete='CASCADE'), nullable=False)
    device_name = Column(String)  # "PDA Pep", "iPhone Maria", "Tablet barra"...
    token = Column(String, unique=True, nullable=False)  # token de sesión (UUID)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())

    staff = relationship("Staff")


# ============================================================
# SALA Y MESAS
# ============================================================
class Area(Base):
    __tablename__ = 'areas'
    id = uuid_pk()
    name = Column(String, nullable=False)  # terraza, interior, barra...
    position_x = Column(Integer, default=0)
    position_y = Column(Integer, default=0)
    surcharge_percent = Column(Numeric(5, 2), default=0)  # recargo de terraza, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Table(Base):
    __tablename__ = 'tables'
    id = uuid_pk()
    area_id = Column(UUID(as_uuid=True), ForeignKey('areas.id', ondelete='SET NULL'))
    number = Column(String, nullable=False)  # "1", "2", "T1"...
    seats = Column(Integer, default=4)
    position_x = Column(Integer, default=0)
    position_y = Column(Integer, default=0)
    shape = Column(String, default='square')  # square, round, rectangle
    status = Column(String, default='available')  # available, occupied, reserved, needs_cleaning, blocked
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============================================================
# MENÚ
# ============================================================
class MenuCategory(Base):
    __tablename__ = 'menu_categories'
    id = uuid_pk()
    name = Column(String, nullable=False)  # entrantes, principales, bebidas...
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MenuItem(Base):
    __tablename__ = 'menu_items'
    id = uuid_pk()
    category_id = Column(UUID(as_uuid=True), ForeignKey('menu_categories.id', ondelete='SET NULL'))
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    vat_rate = Column(Numeric(5, 2), default=10.0)  # IVA: 10% hostelería, 21% bebidas alcohólicas
    kitchen_station = Column(String, default='main')  # main, grill, fry, bar, dessert
    allergens = Column(JSON)  # ["gluten", "lactosa", ...]
    is_available = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============================================================
# RESERVAS
# ============================================================
class Reservation(Base):
    __tablename__ = 'reservations'
    id = uuid_pk()
    table_id = Column(UUID(as_uuid=True), ForeignKey('tables.id', ondelete='SET NULL'))
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String)
    customer_email = Column(String)
    party_size = Column(Integer, default=2, nullable=False)
    reservation_date = Column(Date, nullable=False)
    reservation_time = Column(String, nullable=False)  # "20:30"
    status = Column(String, default='confirmed')  # pending, confirmed, seated, cancelled, no_show
    notes = Column(Text)
    # --- Integración con Ariadna (recepción de reservas multicanal) ---
    source = Column(String, default='manual')  # manual, phone, email, whatsapp, telegram, web, ariadna
    external_id = Column(String)  # ID de la reserva en el sistema de origen (Ariadna) — idempotencia
    created_by = Column(String, default='staff')  # staff, ariadna, web
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============================================================
# COMANDAS / PEDIDOS
# ============================================================
class Order(Base):
    __tablename__ = 'orders'
    id = uuid_pk()
    table_id = Column(UUID(as_uuid=True), ForeignKey('tables.id', ondelete='SET NULL'))
    staff_id = Column(UUID(as_uuid=True), ForeignKey('staff.id', ondelete='SET NULL'))
    order_type = Column(String, default='dine_in')  # dine_in, takeaway, delivery
    status = Column(String, default='open')  # open, sent_to_kitchen, served, paid, cancelled
    total_amount = Column(Numeric(10, 2), default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    notes = Column(Text)
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = 'order_items'
    id = uuid_pk()
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey('menu_items.id', ondelete='SET NULL'))
    name_snapshot = Column(String)  # nombre del artículo en el momento del pedido
    price_snapshot = Column(Numeric(10, 2))  # precio en el momento del pedido
    quantity = Column(Integer, default=1, nullable=False)
    vat_rate = Column(Numeric(5, 2), default=10.0)
    status = Column(String, default='pending')  # pending, sent, preparing, ready, served, cancelled
    modifications = Column(JSON)  # ["sin cebolla", "poco hecho", ...]
    seat_number = Column(Integer)  # para división de cuenta por comensal
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="items")


# ============================================================
# PAGOS
# ============================================================
class Payment(Base):
    __tablename__ = 'payments'
    id = uuid_pk()
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    method = Column(String, nullable=False)  # cash, card, bizum, split
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default='completed')  # pending, completed, refunded, failed
    paid_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# FISCAL (VeriFactu) — registro de facturación inalterable
# ============================================================
class FiscalRecord(Base):
    __tablename__ = 'fiscal_records'
    id = uuid_pk()
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id', ondelete='SET NULL'))
    # Identificador único del registro de facturación (VeriFactu)
    record_id = Column(String, unique=True, nullable=False)
    # Hash encadenado: hash del registro anterior + datos de este registro
    chain_hash = Column(String, nullable=False)
    previous_chain_hash = Column(String)
    # Datos del tique/factura serializados (JSON canónico)
    payload_json = Column(JSON, nullable=False)
    # Tipo de registro: alta, anulación, rectificación
    record_type = Column(String, default='alta')  # alta, anulacion, rectificacion
    # Fecha y hora de emisión (obligatorio VeriFactu)
    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Firma electrónica (en producción: firma con certificado)
    signature = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# CIERRE DEL DÍA (volcado diario para el PMS/Estada)
# ============================================================
class DayClosure(Base):
    """Tancament del dia del TPV: ventes + pagaments per mètode.

    És el volcat diari que Estada (PMS) consumirà per al quadrament de caixa
    del night audit (targetes, efectiu, transferències...). Una fila per data
    de negoci (idempotent).
    """
    __tablename__ = 'day_closures'
    id = uuid_pk()
    closure_date = Column(Date, nullable=False, unique=True)  # data de negoci
    status = Column(String, default='completed')  # completed | failed
    total_sales = Column(Numeric(12, 2), default=0)
    orders_count = Column(Integer, default=0)
    summary = Column(JSON)  # payments_by_method, orders_by_type, vat_breakdown...
    external_id = Column(String)  # idempotència cap a Estada/Compta
    emitted_to_pms = Column(Boolean, default=False)  # volcat a Estada fet?
    emitted_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
