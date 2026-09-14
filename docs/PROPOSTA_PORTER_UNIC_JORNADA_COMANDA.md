# PROPOSTA TÈCNICA — Porter únic: Jornada com a porta d'entrada de Comanda
### Un sol PIN pel cambrer. El centre ve del fitxatge, no d'un selector manual.
*Proposta de Flavia, aprovada per Tomeu el 14/09/2026. Per a na Maria (backend Comanda/Jornada).*

---

## 1. El problema actual (un forat, no una hipòtesi)

De la feina feta els dies 13-14/09 al backend de Comanda (`integrations.py`):

```python
# POST /api/v1/integrations/staff-sync  →  sincronitza empleat de Jornada a Comanda
staff = Staff(
    full_name=payload.full_name, ...,
    pin=None,                  # ← SENSE PIN: la identitat ve de Jornada
    external_id=payload.external_id,
    source="jornada",
)
```

I el login de Comanda només accepta una via:

```python
# staff.py — login()
staff = db.query(Staff).filter(Staff.pin == payload.pin, Staff.is_active == True).first()
```

**Conseqüència**: un cambrer sincronitzat des de Jornada (`pin=None`) **no pot entrar a Comanda**. Avui això és un bloqueig real, no una millora d'UX: si una empresa té Jornada + Comanda, els cambrers que vénen de Jornada es queden fora del TPV.

*(El mateix passa, per cert, amb el `pin` del model: `Column(String)` sense unicitat garantida — dos cambrers podrien compartir PIN i el `.first()` donaria la sessió a un d'ells arbitràriament.)*

---

## 2. La idea (aprovada per Tomeu)

> Fer servir el **mateix login** del portal de l'empleat de Jornada per entrar també a la Comandera, **sense carregar el mòbil del cambrer** amb dues apps ni fer-li recordar dos PINs.

**Reformulada com a arquitectura**: Jornada fa de **porter (IdP)** i Comanda **accepta el seu testimoni**.

```
  Cambrer (PDA / mòbil / SoftPOS)
        │
        │  1.  Posa el PIN al portal de Jornada  (el seu ÚNIC login)
        ▼
   ┌──────────┐
   │ JORNADA  │  2.  valida el PIN  (ja ho fa: portal_empleat/service.login_pin)
   │  porter  │  3.  emet un token curt (JWT, ~15 min) amb:
   └────┬─────┘      { empleado_id, nom, centre_on_està_fitxat }
        │
        │  4.  la Comandera bescanvia el token
        ▼
   ┌──────────┐
   │ COMANDA  │  5.  valida el token contra Jornada
   │   TPV    │  6.  troba el Staff per external_id + source='jornada'
   └──────────┘  7.  emet la seva pròpia sessió de dispositiu (com avui)
                     → i deriva el torn del centre del fitxatge
```

**Un PIN. Una icona. Zero fricció.**

---

## 3. Per què això i no "afegir una cridada dins el portal de Jornada"

| Criteri | Cridada dins el portal | **Porter únic (exchange)** |
|---|---|---|
| PINs a recordar | 2 (Jornada + Comanda) | **1** |
| On viu la lògica del TPV | Duplicada dins Jornada | Al seu lloc (Comanda) |
| Manteniment | Cada canvi del TPV → 2 apps | **1 sol lloc** |
| UX del cambrer | Barreja fitxar i vendre a la mateixa pantalla | Cada app fa la seva feina, ben feta |
| Pes al mòbil | L'app de RRHH sencera carregada | La Comandera, lleugera (PWA) |

Si el TPV queda dins el portal de Jornada, s'acaba amb un monstre que ni és fitxador ni és TPV. **El cambrer ha de tenir una icona i un PIN.**

---

## 4. El guany col·lateral (i gros): el centre deixa de ser manual

Jornada **ja sap** en quin centre està el cambrer (feina del 13-14/09: `fichajes` amb `center_external_id`; `clock_in` amb centre obre el torn en aquell centre; `clock_out` el tanca).

Per tant, el token d'exchange pot portar:

```json
{ "empleado_id": 42, "nom": "Pere Sastre", "centre_fitxat": "Lobby Bar Formentor" }
```

**I Comanda ja no ha de preguntar res.** Es passa del forat actual del ShiftBar («tria el teu punt de venda») a:

> «Ja estàs fitxat al Lobby Bar → torn obert allà.»

Automàtic. Tres beneficis el mateix moviment:

1. **S'elimina el pas manual** de triar centre.
2. **S'elimina la cursa del torn** detectada a la prova de càrrega del 14/09 (3 torns duplicats per check-then-insert a `shift_service.open_shift`): el torn no el crea el cambrer a Comanda, **es deriva d'una única escriptura** (el fitxatge de Jornada).
3. **Coherència total**: Jornada = *qui, en quin centre, quan* · Comanda = *vendes i caixa*. La separació de conceptes que ja teníem documentada (`INTEGRACIO_JORNADA.md` §15.3) es compleix al 100%.

---

## 5. Els riscos i com es tanquen

| Risc | Mitigació |
|---|---|
| **Si Jornada cau, no es pot entrar a Comanda** | El token de Comanda ja emès val la seva durada; el cambrer que ja està dins no en surt. Només afecta *entrades noves* |
| **Un client que només té Comanda (sense Jornada)** | **Mantenir el login per PIN de Comanda** com a via alternativa. El porter és un *camí addicional*, mai l'únic |
| Jornada i Comanda en xarxes diferents | Han de viure al **mateix servidor local de l'establiment** — l'arquitectura que ja hem decidit (`ARQUITECTURA DE DESPLEGAMENT — Conceptes`). L'exchange és **LAN: instantani i sense cost** |
| Token robat / reutilitzat | Token curt (≤15 min), d'un sol ús, lligat a `staff_id` + dispositiu |

---

## 6. Camí d'implementació proposat (per fases, sense sobre-enginyar)

### FASE 1 — Destapar el forat (mínim, sense tocar arquitectura) · *prioritat alta*
Objectiu: que els cambrers sincronitzats de Jornada **puguin entrar** ja.

1. **Jornada**: `POST /api/v1/portal/login` → a més del que ja retorna, retorna un **`comanda_token`** (JWT curt, firmat; claims: `empleado_id`, `nom`, `centre_fitxat`) quan el client demana accés a Comanda.
2. **Comanda**: nou `POST /api/v1/staff/session-exchange { jornada_token }` que:
   - valida el token contra Jornada (clau compartida o JWKS de Jornada),
   - busca `Staff` per `external_id` + `source='jornada'`,
   - emet la sessió de dispositiu normal (com el login actual).
3. **Comandera**: si arriba amb `?jornada_token=...`, bescanvia'l i entra directament a `/comandera/sala`.

*Verificació*: un empleat sincronitzat de Jornada entra a la Comandera amb el seu PIN de fitxatge.

### FASE 2 — El centre automàtic · *el guany gros*
4. El token porta `centre_fitxat`; la Comandera **obre el torn allà directament** (sense selector).
5. Si el cambrer no està fitxat → cau al selector actual (compatible enrere).

*Verificació*: Pere fitxa al Lobby Bar a Jornada → obre la Comandera → torn obert al Lobby Bar, sense tocar res.

### FASE 3 — Robustesa
6. **Unicitat de PIN** a `Staff` (Comanda) i a `Empleado` (Jornada): restricció d'unicitat, o bé `UniqueConstraint` parcial al torn obert (`staff_id WHERE status='open'`) per tancar la cursa definitivament.
7. Cua local de reintents a Comanda per si Jornada no respon en el moment de l'exchange (entrada diferida quan torni la línia).

---

## 7. Contracte concret (perquè es pugui picar sense endevinar)

### Jornada emet
```
POST /api/v1/portal/login          (ja existeix — s'amplia)
  body:  { pin: "2345", scope: "comanda" }
  200:   { empleado_id, nombre, comanda_token: "<JWT>" }
```
Claims del JWT: `iss=jornada`, `aud=comanda`, `sub=<empleado_id>`, `name`, `center_external_id`, `exp` (≤15 min).

### Comanda bescanvia
```
POST /api/v1/staff/session-exchange
  body:  { jornada_token: "<JWT>", device_name: "Comandera" }
  200:   { token, staff: {...} }      ← igual que el login actual
  401:   token invàlid o caducat
  404:   empleat no sincronitzat (cal cridar /integrations/staff-sync)
```

**Nota d'idempotència**: si el mateix cambrer bescanvia dues vegades, es reutilitza la sessió de dispositiu oberta per a aquell `staff_id` + dispositiu (evita sessions orfes).

---

## 8. Resum en una frase (per a la conversa amb el client)

> «El cambrer fitxa amb el seu PIN a l'entrada, i amb **el mateix PIN** obre la comanda al seu mòbil — i el sistema ja sap a quin bar està treballant. Una sola app, un sol codi.»

---
*Document viu. Referències: `INTEGRACIO_JORNADA.md` §15 (separació de conceptes), `ARQUITECTURA DE DESPLEGAMENT — Conceptes` (local vs núvol), prova de càrrega del 14/09 (`scripts/prova_servei_real.py`, cursa del torn).*
