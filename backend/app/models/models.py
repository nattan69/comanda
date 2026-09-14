from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Integer, Date, Text, JSON, Index, text
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
    # --- Integració amb Jornada ---
    external_id = Column(String, index=True)  # empleado_id a Jornada
    source = Column(String, default='manual')  # manual, jornada
    shift_status = Column(String, default='off_shift')  # off_shift, on_shift, break
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


class IncomeCategory(Base):
    """Categoria d'ingrés (comptable) dels articles.

    Llista configurable: menjar, beguda, varis, drogueria, amenities, etc.
    Cada una pot enllaçar amb el compte comptable PGC corresponent (7050,
    7052, 7055...) per al volcat del tancament a Compta.
    """
    __tablename__ = 'income_categories'
    id = uuid_pk()
    name = Column(String, nullable=False)  # menjar, beguda, varis, drogueria, amenities...
    account_code = Column(String)  # compte PGC opcional (7050, 7052, 7055...)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Family(Base):
    """Família de producte de la carta (subcategorització comercial).

    Llista configurable: lactis, sucs, whiskies, aperitius, snacks, cerveses,
    carns, peixos, etc.
    """
    __tablename__ = 'families'
    id = uuid_pk()
    name = Column(String, nullable=False)  # lactis, sucs, whiskies, aperitius, snacks...
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MenuItem(Base):
    __tablename__ = 'menu_items'
    id = uuid_pk()
    category_id = Column(UUID(as_uuid=True), ForeignKey('menu_categories.id', ondelete='SET NULL'))
    # Categoria d'ingrés (comptable): FK a income_categories (menjar, beguda,
    # varis, drogueria, amenities...). Enllaça amb la categoria d'ingrés del
    # tancament/Compta.
    income_category_id = Column(UUID(as_uuid=True), ForeignKey('income_categories.id', ondelete='SET NULL'))
    # Família de producte: FK a families (lactis, sucs, whiskies, aperitius,
    # snacks, cerveses, carns, peixos...).
    family_id = Column(UUID(as_uuid=True), ForeignKey('families.id', ondelete='SET NULL'))
    # Departament (centre) on es ven l'article: ex. Recepció (trànsfer, late
    # check out, sauna...), Minimarket (aftersun, pack cerveses...). Null per
    # als articles generals de bar/restaurant.
    center_id = Column(UUID(as_uuid=True), ForeignKey('centers.id', ondelete='SET NULL'))
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
    # Torn i centre on s'ha pres la comanda (per la liquidació personal i la
    # capçalera del tiquet).
    shift_id = Column(UUID(as_uuid=True), ForeignKey('shifts.id', ondelete='SET NULL'))
    center_id = Column(UUID(as_uuid=True), ForeignKey('centers.id', ondelete='SET NULL'))
    order_type = Column(String, default='dine_in')  # dine_in, takeaway, delivery
    status = Column(String, default='open')  # open, sent_to_kitchen, served, paid, cancelled
    total_amount = Column(Numeric(10, 2), default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    notes = Column(Text)
    # Càrrec a habitació (room charge): número d'habitació de l'hotel a qui es
    # carrega el consum. Quan és None, el client paga directament al TPV.
    room_number = Column(String)
    # Codi del tiquet de comanda (numeració per tipus: COM-AAAA-NNNN).
    ticket_code = Column(String)
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
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
    method = Column(String, nullable=False)  # cash, card, bizum, split, house, room_charge
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default='completed')  # pending, completed, refunded, failed
    # Codi del tiquet de pagament (seqüència TICKET per EF/TG/RC, INV per house).
    ticket_code = Column(String)
    # Room charge (càrrec a habitació): dades del client i de l'habitació.
    guest_name = Column(String)
    room_number = Column(String)
    # Invitació (house): qui convida i per quin motiu.
    invited_by = Column(String)  # Direcció, Central, Comercial, Att. clients, Personal...
    reason = Column(String)  # motiu de la invitació (o de l'anul·lació)
    # SoftPOS (targeta): referència de la transacció del banc per conciliar.
    card_reference = Column(String)  # ex. ID/autorització del TPV virtual
    # Room charge: resultat del post al PMS (Estada/Mews).
    pms_posted = Column(Boolean, default=False)  # el càrrec s'ha postat al foli del PMS?
    pms_response = Column(JSON)  # resposta del PMS (per audit)
    paid_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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
    pms_response = Column(JSON)  # resposta del PMS al volcat (per audit)
    emitted_to_compta = Column(Boolean, default=False)  # volcat a Compta fet?
    compta_response = Column(JSON)  # resposta de Compta al volcat (per audit)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# ANUL·LACIONS (autoritzades per un cap)
# ============================================================
class Void(Base):
    """Anul·lació d'una comanda (o part), autoritzada per un cap/manager.

    Les anul·lacions queden registrades amb qui les ha autoritzat (un cap) i el
    motiu, perquè surtin al tancament del dia (la Z) com a línia a part.
    """
    __tablename__ = 'voids'
    id = uuid_pk()
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)  # import anul·lat
    reason = Column(String)  # motiu de l'anul·lació
    authorized_by_id = Column(UUID(as_uuid=True), ForeignKey('staff.id', ondelete='SET NULL'))  # el cap que autoritza
    # Codi del tiquet d'anul·lació (NUL-AAAA-NNNN).
    ticket_code = Column(String)
    authorized_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# SEQÜÈNCIES DE TIQUETS (numeració per tipus, anual)
# ============================================================
class TicketSequence(Base):
    """Comptador de numeració de tiquets per tipus i any natural.

    Cada tipus de tiquet (COM, EF, TG, RC, INV, NUL) té la seva pròpia
    seqüència correlativa, reinicialitzada cada any. La Z té la seva pròpia
    seqüència anual (tipus `Z`).
    """
    __tablename__ = 'ticket_sequences'
    id = uuid_pk()
    ticket_type = Column(String, nullable=False)  # COM, EF, TG, RC, INV, NUL, Z
    year = Column(Integer, nullable=False)
    counter = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# ESTABLIMENT (empresa/hotel) — dades fiscals
# ============================================================
class Establishment(Base):
    """L'establiment (empresa/hotel): dades fiscals per a la capçalera del tiquet.

    Ex. Hotel Sa Ràpita ****, Conceptes Hotels, Carrer llarg 25, 07000 Campos,
    NIF A07100324.
    """
    __tablename__ = 'establishments'
    id = uuid_pk()
    name = Column(String, nullable=False)  # nom comercial: "Hotel Sa Ràpita"
    legal_name = Column(String)  # raó social: "Conceptes Hotels"
    category = Column(String)  # categoria/estrelles: "****"
    address = Column(String)  # "Carrer llarg, 25"
    city = Column(String)  # "Campos"
    province = Column(String)  # "Illes Balears"
    postal_code = Column(String)  # "07000"
    nif = Column(String)  # "A07100324"
    phone = Column(String)
    email = Column(String)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# CENTRES (punts de venda) dins un establiment
# ============================================================
class Center(Base):
    """Centre (punt de venda) dins un establiment, on el cambrer es loggeja.

    Ex. Menjador "Sa Calobra", Lobby Bar "Formentor", Xibiu "Es Trenc".
    """
    __tablename__ = 'centers'
    id = uuid_pk()
    name = Column(String, nullable=False)  # "Menjador Sa Calobra", "Lobby Bar Formentor"...
    establishment_id = Column(UUID(as_uuid=True), ForeignKey('establishments.id', ondelete='CASCADE'), nullable=False)
    # --- Integració amb Jornada ---
    external_id = Column(String, index=True)  # center_id a Jornada
    source = Column(String, default='manual')  # manual, jornada
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# TORNS (shift) del cambrer
# ============================================================
class Shift(Base):
    """Torn d'un cambrer dins UN departament.

    Cicle: login (obrir torn) → treball → liquidació personal → logout
    (tancar torn). Per canviar de departament cal tancar el torn i obrir-ne
    un altre. La liquidació és personal (per cambrer).
    """
    __tablename__ = 'shifts'
    id = uuid_pk()
    staff_id = Column(UUID(as_uuid=True), ForeignKey('staff.id', ondelete='CASCADE'), nullable=False)
    center_id = Column(UUID(as_uuid=True), ForeignKey('centers.id', ondelete='CASCADE'), nullable=False)
    status = Column(String, nullable=False, default='open')  # open, closed
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Liquidació personal (completada al tancar el torn)
    cash_declared = Column(Numeric(10, 2))  # efectiu que el cambrer declara entregar
    card_total = Column(Numeric(10, 2))  # total de targetes del torn (calculat pel sistema)
    liquidation = Column(JSON)  # resum del torn (vendes, pagaments, invitacions, anul·lacions, desquadre)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Invariant de BD: UN SOL torn obert per cambrer (evita la cursa del
    # check-then-insert que duplicava torns amb concurrència).
    __table_args__ = (
        Index(
            "uq_shifts_open_per_staff",
            "staff_id",
            unique=True,
            sqlite_where=text("status = 'open'"),
            postgresql_where=text("status = 'open'"),
        ),
    )


# ============================================================
# FITXATGES (esdeveniments rebuts de Jornada)
# ============================================================
class FichajeEvent(Base):
    """Esdeveniment de fitxatge rebut de Jornada (control horari).

    És un log d'events — l'estat actual (`shift_status` del Staff) es deriva de
    l'últim event. Porta el centre on s'ha fitxat perquè Comanda sàpiga en quin
    punt de venda està cada cambrer (registre de moviments entre centres).
    """
    __tablename__ = 'fichaje_events'
    id = uuid_pk()
    staff_id = Column(UUID(as_uuid=True), ForeignKey('staff.id', ondelete='CASCADE'), nullable=False)
    external_id = Column(String, index=True)  # ID del fichaje a Jornada — idempotencia
    event_type = Column(String, nullable=False)  # clock_in, clock_out, break_start, break_end
    center_id = Column(UUID(as_uuid=True), ForeignKey('centers.id', ondelete='SET NULL'))  # centre on s'ha fitxat
    timestamp = Column(DateTime(timezone=True), nullable=False)  # quan va passar a Jornada
    device = Column(String)  # dispositiu des del que es va fitxar
    source = Column(String, default='jornada')
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# CRÈDIT D'HABITACIÓ (room charge) — habilitació i topall
# ============================================================
class RoomCredit(Base):
    """Límit de crèdit per habitació (room charge).

    El càrrec a l'habitació només es permet si l'habitació el té **habilitat**
    i no està **topada** (el crèdit acumulat no supera el topall). La font de
    veritat del topall és el PMS (Estada); aquesta taula n'és la còpia local
    per validar ràpidament al TPV sense cridar el PMS a cada càrrec.
    """
    __tablename__ = 'room_credits'
    id = uuid_pk()
    room_number = Column(String, unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)  # habitació habilitada per crèdit
    credit_limit = Column(Numeric(10, 2), default=0)  # topall (0 = sense límit)
    current_balance = Column(Numeric(10, 2), default=0)  # crèdit acumulat
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
