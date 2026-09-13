# Integracio Jornada -> Comanda

> Especificacio tecnica d'integracio entre Jornada (control horari standalone)
> i Comanda (TPV). Per a na Maria (backend Comanda) i equip Jornada.
>
> Data: 06/09/2026 | Autor: Lucia | Estat: tot decidit, llest per implementar

---

## 1. Context

**Jornada** es una excisió de Jornals: només control horari (fitxatges, torns,
jornades) + portal de l'empleat. Es ven a empreses que ja tenen el seu propi
programari de RRHH i només necessiten aquestes dues peces.

**Comanda** es el TPV (punt de venda) per a bars i restaurants. Te gestio de
personal amb login per PIN i sessions per dispositiu (PDA/mobil).

**Objectiu de la integracio:** quan una empresa te Jornada + Comanda, el TPV
sap qui esta de servei en temps real. Els cambrers fitxen a Jornada i Comanda
ho reflecteix automaticament. Si l'empresa NO te Jornada, Comanda funciona
sol amb el seu login per PIN propi.

---

## 2. Patro d'integracio

Seguim el **mateix patro que la integracio Ariadna -> Comanda** (reserves):

- **Push model**: es Jornada qui envia dades a Comanda (no al reves)
- **Autenticacio**: API key via header `X-API-Key`
- **Idempotencia**: per `external_id` + `source` (si ja existeix, es retorna
  l'existant en lloc de duplicar)
- **Endpoints**: nous endpoints dins `/api/v1/integrations/` al backend de Comanda

```
Jornada (control horari)                  Comanda (TPV)
┌────────────────────┐    POST /integrations/staff-sync    ┌──────────────┐
│  - Fichatges       │  ──────────────────────────────────> │  - Staff     │
│  - Torns           │    POST /integrations/fichajes       │  - Taules    │
│  - Jornades        │  ──────────────────────────────────> │  - Comandes  │
│  - Empleats        │                                     │  - VeriFactu  │
└────────────────────┘    X-API-Key: <comanda_api_key>     └──────────────┘
```

---

## 3. Canvis al model de dades de Comanda

### 3.1. Modificar `Staff` (afegir camps d'integracio)

Camples nous al model `Staff` existent (`backend/app/models/models.py`):

```python
# --- Integracio amb Jornada ---
external_id = Column(String, index=True)    # empleado_id a Jornada
source = Column(String, default='manual')   # manual, jornada
shift_status = Column(String, default='off_shift')  # off_shift, on_shift, break
```

> Seguir el mateix patro que `Reservation` (que ja te `external_id`, `source`,
> `created_by` per a la integracio amb Ariadna).

> **Decisio 1 (Tomeu):** Els Staff sincronitzats des de Jornada **no tenen
> PIN**. La identitat ve de Jornada. El PIN es nomes per a empreses que
> usen Comanda en standalone (sense Jornada). El camp `pin` queda com
> `NULL` pels Staff amb `source='jornada'`.

### 3.2. Nou model `FichajeEvent`

Registra els esdeveniments de fitxatge rebuts de Jornada. Es com un log
d'events — l'estat actual del `shift_status` de Staff es deriva de l'ultim event.

```python
class FichajeEvent(Base):
    __tablename__ = 'fichaje_events'
    id = uuid_pk()
    staff_id = Column(UUID(as_uuid=True), ForeignKey('staff.id', ondelete='CASCADE'), nullable=False)
    external_id = Column(String, index=True)  # ID del fichaje a Jornada — idempotencia
    event_type = Column(String, nullable=False)  # clock_in, clock_out, break_start, break_end
    timestamp = Column(DateTime(timezone=True), nullable=False)  # quan va passar a Jornada
    device = Column(String)  # dispositiu desde el que es va fitxar
    source = Column(String, default='jornada')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    staff = relationship("Staff")
```

> No esborram els events: son historial. L'estat actual es consulta ordenant
> per `timestamp desc` i agafant el primer.

---

## 4. Nous endpoints a Comanda

Tots dins del router `integrations` (`backend/app/api/routes/integrations.py`),
ja existent. Utilitzen la mateixa funcio `_check_api_key` que la integracio
amb Ariadna.

### 4.1. POST /api/v1/integrations/staff-sync

Sincronitza un empleat de Jornada amb el Staff de Comanda.

**Request:**
```json
{
  "external_id": "42",
  "full_name": "Pere Llull",
  "email": "pere@restaurant.com",
  "phone": "+34600123456",
  "role": "waiter",
  "is_active": true
}
```

| Camp | Tipus | Obligatoria | Descripcio |
|---|---|---|---|
| `external_id` | string | si | `empleado_id` a Jornada (clau d'idempotencia) |
| `full_name` | string | si | Nom complet |
| `email` | string | no | Correu |
| `phone` | string | no | Telefon |
| `role` | string | no | Rol: `admin`, `manager`, `waiter`, `kitchen`, `bar` (per defecte `waiter`) |
| `is_active` | bool | no | Si esta actiu (per defecte `true`) |

**Logica:**
1. Buscar `Staff` per `external_id` + `source='jornada'`
2. Si existeix: actualitzar camps (merge)
3. Si no existeix: crear nou Staff amb `source='jornada'`, **sense PIN**
   (`pin=NULL`). La identitat ve de Jornada, no cal login per PIN al TPV.
4. Retornar `StaffOut`

**Response (201 Created o 200 OK):**
```json
{
  "id": "uuid-del-staff",
  "full_name": "Pere Llull",
  "email": "pere@restaurant.com",
  "phone": "+34600123456",
  "role": "waiter",
  "pin": null,
  "is_active": true,
  "external_id": "42",
  "source": "jornada",
  "shift_status": "off_shift",
  "created_at": "2026-09-06T11:00:00Z"
}
```

### 4.2. POST /api/v1/integrations/fichajes

Rep un esdeveniment de fitxatge de Jornada (entrada, sortida, pausa).

**Request:**
```json
{
  "external_id": "fich-2026-09-06-001",
  "staff_external_id": "42",
  "event_type": "clock_in",
  "timestamp": "2026-09-06T10:30:00+02:00",
  "device": "PDA-Recepcio"
}
```

| Camp | Tipus | Obligatoria | Descripcio |
|---|---|---|---|
| `external_id` | string | si | ID unic del fichaje a Jornada (idempotencia) |
| `staff_external_id` | string | si | `empleado_id` a Jornada (per trobar el Staff) |
| `event_type` | string | si | `clock_in`, `clock_out`, `break_start`, `break_end` |
| `timestamp` | datetime | si | Quan va passar (ISO 8601 amb timezone) |
| `device` | string | no | Dispositiu desde el que es va fitxar |

**Logica:**
1. Idempotencia: buscar `FichajeEvent` per `external_id`. Si existeix, retornar
   200 OK amb l'existant (no duplicar).
2. Buscar `Staff` per `external_id` (=`staff_external_id`) + `source='jornada'`.
   Si no existeix: error 404.
3. Crear `FichajeEvent`.
4. Actualitzar `Staff.shift_status` segons `event_type`:
   - `clock_in` → `on_shift`
   - `clock_out` → `off_shift`
   - `break_start` → `break`
   - `break_end` → `on_shift`
5. Retornar `FichajeEventOut`.

**Response (201 Created o 200 OK):**
```json
{
  "id": "uuid-del-event",
  "staff_id": "uuid-del-staff",
  "external_id": "fich-2026-09-06-001",
  "event_type": "clock_in",
  "timestamp": "2026-09-06T10:30:00+02:00",
  "device": "PDA-Recepcio",
  "source": "jornada",
  "created_at": "2026-09-06T11:00:01Z"
}
```

### 4.3. GET /api/v1/integrations/shifts

Retorna el personal que esta de servei ara (o per una data concreta).
Es l'unic endpoint de consulta (pull).

**Query params:**
| Param | Tipus | Descripcio |
|---|---|---|
| `date` | date (opcional) | Per defecte avui. Filtra per la jornada d'aquella data. |
| `status` | string (opcional) | Filtra per `shift_status`: `on_shift`, `off_shift`, `break` |

**Response (200 OK):**
```json
[
  {
    "staff_id": "uuid-1",
    "full_name": "Pere Llull",
    "external_id": "42",
    "shift_status": "on_shift",
    "last_event": {
      "event_type": "clock_in",
      "timestamp": "2026-09-06T10:30:00+02:00"
    }
  },
  {
    "staff_id": "uuid-2",
    "full_name": "Maria Antònia",
    "external_id": "17",
    "shift_status": "break",
    "last_event": {
      "event_type": "break_start",
      "timestamp": "2026-09-06T13:00:00+02:00"
    }
  }
]
```

---

## 5. Schemas Pydantic (nous)

Afegir a `backend/app/schemas/schemas.py`:

```python
# ============================================================
# INTEGRACIO JORNADA
# ============================================================
class StaffSyncCreate(BaseModel):
    external_id: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "waiter"
    is_active: bool = True


class StaffSyncOut(StaffOut):
    external_id: Optional[str] = None
    source: str = "manual"
    shift_status: str = "off_shift"


class FichajeCreate(BaseModel):
    external_id: str
    staff_external_id: str
    event_type: str  # clock_in, clock_out, break_start, break_end
    timestamp: datetime
    device: Optional[str] = None


class FichajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    staff_id: UUID
    external_id: str
    event_type: str
    timestamp: datetime
    device: Optional[str] = None
    source: str
    created_at: Optional[datetime] = None


class ShiftSummary(BaseModel):
    staff_id: UUID
    full_name: str
    external_id: Optional[str] = None
    shift_status: str
    last_event: Optional[dict] = None
```

---

## 6. Configuracio

### 6.1. Comanda (.env)

> **Decisio 3 (Tomeu):** API keys **separades per integracio**. Cada
> integracio te la seva clau independent. Es pot revocar/desactivar una
> sense afectar les altres, i els logs identifiquen quina integracio va
> fer cada crida.

Adaptar `config.py` i `_check_api_key`:

```python
# config.py
ARIADNA_API_KEY = os.getenv("ARIADNA_API_KEY", "")
JORNADA_API_KEY  = os.getenv("JORNADA_API_KEY", "")
```

```python
# integrations.py — _check_api_key adaptat per multiples claus
def _check_api_key(api_key: str = Header(...)):
    valid_keys = {v for v in [config.ARIADNA_API_KEY, config.JORNADA_API_KEY] if v}
    # en dev sense cap clau configurada, tot permitit (patro existent)
    if valid_keys and api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="API key invalida")
    return api_key  # retornar per poder logar quina clau s'ha usat
```

```
# .env de Comanda
ARIADNA_API_KEY=clau-ariadna-xxx
JORNADA_API_KEY=clau-jornada-yyy
```

### 6.2. Jornada (.env)

Jornada necessita saber on es Comanda i amb quina API key:

```
COMANDA_API_URL=http://localhost:8000/api/v1
COMANDA_API_KEY=clau-jornada-yyy   # = JORNADA_API_KEY de Comanda
```

---

## 7. Banda de Jornada (pendent d'implementar)

Jornada ha d'enviar events a Comanda quan passin certes coses.

> **Decisio 4 (Tomeu):** Els fichajes s'envien **en temps real** (webhook
> immediat a l'instant del fitxatge). No hi ha batch ni tasques
> programades. Quan un empleat fitxa a Jornada, l'event va a Comanda
> de seguida perque el TPV sap qui esta de servei en temps real.

### 7.1. Webhook de staff-sync

Disparar quan:
- Es crea un empleat nou a Jornada
- Es modifica un empleat (canvi de nom, email, rol)
- Es dona de baixa un empleat (`is_active=false`)

### 7.2. Webhook de fichajes

Disparar quan:
- Un empleat fitxa entrada (`clock_in`)
- Un empleat fitxa sortida (`clock_out`)
- Un empleat comença/acaba pausa (`break_start`/`break_end`)

### 7.3. Retrys i fiabilitat

- Si Comanda no respon (timeout, 5xx), Jornada ha de reintentar amb backoff
  exponencial (3 intents: 1s, 5s, 30s).
- Idempotencia per `external_id` garanteix que els retrys no dupliquin.
- Jornada pot emmagatzemar els enviaments pendents en una cua i processar-los
  en segon pla.

---

## 8. Mode standalone (sense Jornada)

Si l'empresa no te Jornada:
- El `source` de tots els Staff es `manual`
- El login es fa per PIN al TPV (com ja funciona ara)
- `shift_status` queda en `off_shift` per defecte (es pot actualitzar manualment
  o simplement ignorar)
- Cap endpoint d'integracio es crida

**No s'altera el flux existent.** La integracio es 100% optativa.

---

## 9. Mapeig de rols Jornada -> Comanda

Jornada te rols dins del context de RRHH. Comanda te rols de restaurant.
Cal un mapeig:

| Rol Jornada (RRHH) | Rol Comanda (TPV) | Notes |
|---|---|---|
| Administrador | admin | |
| RRHH / Gerent | manager | |
| Cambrer / Servei | waiter | |
| Cuina | kitchen | |
| Bar | bar | |
| Altres | waiter | Per defecte, si no coincideix |

> **Decisio 2 (Tomeu):** El mapeig de rols **es fa a la banda de Jornada**.
> Jornada envia ja el rol traduït al format de Comanda (`admin`, `manager`,
> `waiter`, `kitchen`, `bar`). Comanda no ha de traduir res — rep el camp
> `role` directament i l'usa tal qual.

---

## 10. Seguretat

1. **API keys separades per integracio**: cada integracio (Ariadna, Jornada)
   te la seva clau independent. Tots els endpoints d'integracio requereixen
   `X-API-Key`. Si no hi ha cap clau configurada, es permet en mode dev
   (mateix patro que Ariadna). Si una clau es compromet, es pot rotar nomes
   la afectada sense tocar les altres.
2. **No hi ha auth de sessio**: els endpoints d'integracio NO passen per
   l'autenticacio per PIN/DeviceSession. Nomes per API key.
3. **Rate limiting**: considerar limitar les crides (per exemple, 60/min)
   per evitar abusos.

---

## 11. Tests

Seguir el patro de `verify_e2e.py`:

1. Crear staff via staff-sync → verificar que es crea amb `source='jornada'`
2. Tornar a cridar staff-sync amb el mateix `external_id` → verificar idempotencia
   (no es duplica)
3. Enviar fichaje `clock_in` → verificar `shift_status=on_shift`
4. Enviar fichaje `clock_out` → verificar `shift_status=off_shift`
5. Tornar a enviar el mateix fichaje → verificar idempotencia
6. Consultar GET /shifts → verificar que retorna el personal en servei
7. Verificar que sense API key (mode dev) funciona
8. Verificar que amb API key incorrecta retorna 401

---

## 12. Roadmap d'implementacio

### Fase 1: Model i schemas (na Maria)
- [ ] Adaptar `config.py`: afegir `ARIADNA_API_KEY` + `JORNADA_API_KEY` (separades)
- [ ] Adaptar `_check_api_key` per acceptar conjunt de claus valides
- [ ] Afegir camps a `Staff` (`external_id`, `source`, `shift_status`)
- [ ] Crear model `FichajeEvent`
- [ ] Crear schemas Pydantic (`StaffSyncCreate/Out`, `FichajeCreate/Out`, `ShiftSummary`)
- [ ] `create_all` o migracio Alembic

### Fase 2: Endpoints (na Maria)
- [ ] `POST /integrations/staff-sync` amb idempotencia
- [ ] `POST /integrations/fichajes` amb idempotencia + update de shift_status
- [ ] `GET /integrations/shifts`
- [ ] Tests e2e

### Fase 3: Banda de Jornada
- [ ] Configurar `COMANDA_API_URL` + `COMANDA_API_KEY`
- [ ] Mapeig de rols RRHH -> Comanda (es fa a Jornada abans d'enviar)
- [ ] Webhook de staff-sync (create/update/deactivate) — temps real
- [ ] Webhook de fichajes (clock_in/out, break_start/end) — temps real
- [ ] Retrys amb backoff
- [ ] Cua d'enviaments pendents (per quan Comanda no estigui disponible)

### Fase 4: Validacio i posada en marxa (Jornada→Comanda)
- [ ] Provar amb dades reals
- [ ] Documentar la configuracio final

### Fase 5: Integracio Comanda→PMS (multi-proveidor)
- [ ] Crear `pms_adapter/base.py` (interficie abstracta: `post_room_charge`, `post_fiscal`, `verify_guest`)
- [ ] Crear `pms_adapter/factory.py` (selecciona segons `PMS_PROVIDER`)
- [ ] Crear `pms_adapter/internal.py` (stub — fins que el PMS de Conceptes estigui llest)
- [ ] Crear `pms_adapter/mews.py` (basat en `Ariadna/.../pms_adapter/mews.py`)
- [ ] Afegir `PMS_PROVIDER`, `PMS_API_URL`, `PMS_API_KEY` a `config.py`
- [ ] Afegir camps a `Payment` (`guest_name`, `room_number`, `pms_posted`, `pms_response`, `pms_posted_at`)
- [ ] Afegir metode de pagament `room_charge` al TPV (UI: demanar nom + habitacio)
- [ ] Implementar flux: cambrer selecciona "carregar a habitacio" → adapter.post_room_charge → confirmacio/error
- [ ] Post fiscal: enviar tiquets VeriFactu al PMS per comptabilitat
- [ ] Tests e2e (amb InternalAdapter stub + opcionalment Mews sandbox)

---

## 13. Decisions (resoltes per en Tomeu, 06/09/2026)

1. **PIN per a personal sincronitzat** — **RESOLTA: No.**
   Els Staff sincronitzats des de Jornada no tenen PIN. La identitat ve de
   Jornada. El PIN es nomes per a empreses que usen Comanda en standalone.

2. **Mapeig de rols** — **RESOLTA: A Jornada.**
   Jornada envia el rol ja traduït al format de Comanda. Comanda rep i usa
   directament.

3. **API key compartida o separada** — **RESOLTA: Separades.**
   Cada integracio te la seva clau (`ARIADNA_API_KEY`, `JORNADA_API_KEY`).
   `_check_api_key` accepta un conjunt de claus valides. Permet revocar
   una integracio sense afectar les altres i auditar quina clau va fer
   cada crida.

4. **Temps real vs batch** — **RESOLTA: Temps real.**
   Webhook immediat a l'instant del fitxatge. No hi ha batch.

5. **Bidireccionalitat** — **RESOLTA: No a Jornada, si al PMS.**
   Comanda **no** envia res a Jornada. Pero Comanda **si** ha d'enviar al
   PMS (veure seccio 14): crets d'habitacio, comptabilitat, etc.

---

## 14. Integracio Comanda -> PMS (nova necessitat)

> Sorgit de la decisio 5: Comanda ha d'enviar dades al PMS (Property
> Management System) per a crets d'habitacio, comptabilitat, etc.

### 14.1. Context

Actualment **Ariadna** ja te un adapter de PMS:
`D:\projectes\Ariadna\backend\app\services\pms_adapter\` amb:
- `base.py` — interficie base del adapter
- `mews.py` — implementacio per a Mews

Ara **Comanda** necessita una via similar per enviar al PMS:
- **Crets d'habitacio (room charges):** un client del restaurant carrega
  el consum a la seva habitacio. Comanda ha d'enviar la factura al PMS
  perquè l'afegeixi al compte de l'habitacio.
- **Comptabilitat:** Comanda ha de poder enviar tiquets/factures al PMS
  per a la comptabilitat de l'hotel.

### 14.2. Patro proposat

Seguir el mateix patro que Ariadna — crear un `pms_adapter` a Comanda:

```
Comanda (TPV)                              PMS (Mews/altres)
┌──────────────┐    POST /room-charges     ┌──────────────┐
│  - Comandes  │  ──────────────────────>  │  - Compte    │
│  - Pagaments │  POST /folio-posts        │    habitacio │
│  - VeriFactu │                           │  - Comptab.  │
└──────────────┘  X-API-Key / OAuth         └──────────────┘
```

### 14.3. Que s'envia

> **Decisio (Tomeu):** La vinculacio comanda <-> reserva es fa amb
> **nom del client + numero d'habitacio**. Comanda no necessita saber
> l'ID intern de la reserva al PMS — nomes qui es el client i a quina
> habitacio va. El PMS es qui fa el matching (busca la reserva per
> nom + habitacio i posta el cret al compte corresponent).

| Esdeveniment | Quan | Dades enviades |
|---|---|---|
| Room charge | Un client carrega a habitacio | `guest_name`, `room_number`, `amount`, `items`, `staff_id`, `timestamp` |
| Post fiscal | Tiquet/factura VeriFactu emes | `fiscal_record_id`, `hash`, `total`, `iva`, `timestamp` |

**Flux room charge:**
1. Al TPV, el cambrer selecciona "Cargar a habitacio" com a metode de pagament
2. El TPV demana nom del client + numero d'habitacio
3. Comanda envia el room charge al PMS amb aquestes dades
4. El PMS busca la reserva per nom + habitacio, verifica que son guests, i posta el cret al folio de l'habitacio
5. El PMS retorna confirmacio (ok / error: no trobat, no es guest, check-out ja fet, etc.)

> Si el PMS no troba el guest o l'habitacio no coincideix, Comanda ha de
> mostrar l'error al cambrer perque verifiqui les dades o demani un altre
> metode de pagament.

### 14.4. Arquitectura: adapter multi-proveidor

> **Decisio (Tomeu):** Comanda s'ha de poder connectar via API al PMS
> **propi** (el PMS de Conceptes, en previsio) **o a un PMS extern**
> (Mews, Cloudbeds, etc.). L'adapter ha de ser multi-proveidor desde
> el principi.

El patro es `base.py` (interficie abstracta) + un adapter per proveidor
+ `factory.py` que selecciona quin usar segons la configuracio:

```
                    ┌──────────────────┐
                    │  PMSAdapterBase  │  (interficie abstracta)
                    │  - post_room_charge()
                    │  - post_fiscal()
                    │  - verify_guest()
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────┴──────┐ ┌────┴──────┐ ┌─────┴───────┐
    │ InternalAdapter│ │ MewsAdapter│ │  AltresAdapt.│
    │ (PMS Conceptes) │ │ (extern)   │ │  (futurs)   │
    └────────────────┘ └───────────┘ └─────────────┘
```

```python
# backend/app/services/pms_adapter/base.py

from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import datetime

class PMSAdapterBase(ABC):
    """Interficie abstracta. Cada PMS implementa aquest contracte."""

    @abstractmethod
    def post_room_charge(
        self,
        guest_name: str,
        room_number: str,
        amount: Decimal,
        items: list[dict],      # [{name, qty, price}, ...]
        staff_id: str,
        timestamp: datetime,
    ) -> dict:
        """Posta un cret d'habitacio al PMS.
        Retorna: {'success': bool, 'message': str, 'folio_id': str | None}
        """

    @abstractmethod
    def post_fiscal(
        self,
        fiscal_record_id: str,
        hash: str,
        total: Decimal,
        iva: Decimal,
        timestamp: datetime,
    ) -> dict:
        """Posta un registre fiscal al PMS per comptabilitat.
        Retorna: {'success': bool, 'message': str}
        """

    @abstractmethod
    def verify_guest(
        self,
        guest_name: str,
        room_number: str,
    ) -> bool:
        """Verifica que un guest esta checked-in a l'habitacio.
        Opcional: alguns PMS no tenen aquest endpoint i es valida al post_room_charge.
        """
```

```python
# backend/app/services/pms_adapter/factory.py

def get_pms_adapter() -> PMSAdapterBase:
    provider = config.PMS_PROVIDER  # 'internal' | 'mews' | ...
    if provider == 'internal':
        from .internal import InternalAdapter
        return InternalAdapter(
            base_url=config.PMS_API_URL,
            api_key=config.PMS_API_KEY,
        )
    elif provider == 'mews':
        from .mews import MewsAdapter
        return MewsAdapter(
            base_url=config.PMS_API_URL,
            api_key=config.PMS_API_KEY,
        )
    raise ValueError(f"PMS provider desconegut: {provider}")
```

**Configuracio (.env de Comanda):**
```
# Quan l'hotel te el PMS propi de Conceptes:
PMS_PROVIDER=internal
PMS_API_URL=http://localhost:8001/api/v1
PMS_API_KEY=clau-pms-intern

# Quan l'hotel te Mews (extern):
PMS_PROVIDER=mews
PMS_API_URL=https://www.mews.com/api/connector
PMS_API_KEY=token-mews-xxx
```

> Si `PMS_PROVIDER` no esta configurat, la integracio PMS esta
> desactivada — Comanda funciona com a TPV standalone sense room charges.
> Es 100% optativa, igual que la integracio amb Jornada.

### 14.4.1. Canvis al model de Comanda per PMS

El model `Payment` actual necessita suportar "carregar a habitacio"
com a metode de pagament:

```python
# Nous camps a Payment (o sub-taula RoomChargePayment)
payment_method = Column(String)  # afegir 'room_charge' als existents
guest_name = Column(String, nullable=True)      # nom del client
room_number = Column(String, nullable=True)     # numero d'habitacio
pms_posted = Column(Boolean, default=False)     # si s'ha postat al PMS
pms_response = Column(JSON, nullable=True)      # resposta del PMS (per audit)
pms_posted_at = Column(DateTime(timezone=True), nullable=True)
```

> Quan `payment_method == 'room_charge'`, el cambrer introdueix
> `guest_name` + `room_number` al TPV. Comanda crida el `pms_adapter`
> per postar el cret. Si el PMS confirma, `pms_posted=True`. Si falla,
> el cambrer pot canviar a un altre metode de pagament.

### 14.5. Pendents

- ~~Com es vincula una comanda de restaurant amb una reserva d'hotel?~~
  **RESOLT (Tomeu):** nom del client + numero d'habitacio. El PMS fa el matching.
- ~~Quin PMS(s) cal suportar?~~
  **RESOLT (Tomeu):** Tots. Adapter multi-proveidor — `PMS_PROVIDER=internal`
  per al PMS propi de Conceptes, `PMS_PROVIDER=mews` per a Mews, etc.
  Cada hotel configura el seu.
- ~~Es pot reutilitzar l'adapter d'Ariadna?~~
  **RESOLT:** independent a Comanda (diferent context: TPV vs recepcio),
  pero seguint el mateix patro. Ariadna serveix de referencia.
- ~~Sync o async?~~
  **RESOLT (Tomeu): Sync.** El cambrer ha de rebre confirmacio del PMS
  abans de tancar la comanda. Si falla, canvia de metode de pagament.
- ~~verify_guest abans de post_room_charge?~~
  **RESOLT (Tomeu): Si.** Si el PMS ho suporta, es verifica que el guest
  esta checked-in abans de postar. Evita crets a habitacions buides o
  guests que ja han sortit.

> Tots els pendents de la seccio 14 estan resolts. Na Maria pot comencar
> a implementar: `base.py` + `factory.py` + `internal.py` (stub) + canvis
> a `Payment`. Per al `MewsAdapter`, mirar
> `Ariadna/backend/app/services/pms_adapter/mews.py` com a referencia.

---

## 15. Registre de moviments entre centres (ampliació 14/09/2026)

> **Decisió (Tomeu, 14/09):** Si el cambrer fitxa amb Jornada, Jornada és la
> font de veritat del **registre de moviments**: qui està de servei, **en quin
> centre** (punt de venda) i des de quan. Comanda rep aquests fitxatges i els
> reflecteix — no duplica el fitxatge.

### 15.1. El centre al fitxatge

El `FichajeCreate` porta un camp nou `center_external_id` (el `center_id` de
Jornada). Comanda el resol contra `Center.external_id` i el desa al
`FichajeEvent.center_id`. Així un fitxatge d'entrada al Menjador "Sa Calobra"
diu "Pere ha entrat a Sa Calobra"; un fitxatge posterior al Lobby Bar
"Formentor" és el **moviment entre centres**.

```
Pep clock_in  → Menjador "Sa Calobra"   → Comanda: Pep està a Sa Calobra
Pep clock_in  → Lobby Bar "Formentor"   → Comanda: Pep s'ha mogut a Formentor
Pep clock_out → (fora de servei)         → Comanda: Pep ja no hi és
```

### 15.2. Canvis respecte al disseny inicial

- **`Center`** guanya `external_id` + `source` (com `Staff`), per poder-hi
  referenciar des de Jornada.
- **`FichajeEvent`** guanya `center_id` (FK a `centers`, nullable).
- **Nou endpoint** `POST /integrations/centers-sync`: sincronitza centres de
  Jornada (idempotent per `external_id` + `source='jornada'`).
- **Derivació del torn** (`Shift`): un `clock_in` amb centre obre el torn del
  cambrer en aquell centre (si no n'hi ha cap d'obert); un `clock_out` el tanca.
  La **liquidació de caixa** es fa a part, al TPV — no al fitxatge.

### 15.3. Separació de conceptes (clau)

| Sistema | Responsabilitat |
|---|---|
| **Jornada** | Fitxatges laborals: *qui*, *en quin centre*, *quan* (registre de moviments) |
| **Comanda** | Vendes i caixa: *què* ha venut, *quant* efectiu ha de liquidar |

Jornada no sap de vendes ni efectiu; Comanda no duplica el fitxatge.

---

_Aquest document es una guia d'implementacio. Totes les decisions estan
resoltes (en Tomeu, 06/09/2026). Llest per implementar.
Codis i noms de camps en castella per convenio del projecte._
