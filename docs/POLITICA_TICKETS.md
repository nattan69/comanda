# Política de tiquets — Comanda TPV

> Document de negoci. Defineix els tipus de tiquet, la numeració, les
> transicions d'estat i el tractament al tancament de caixa (la Z).
> Decisions de Tomeu (14/09/2026).

---

## 1. Tipus de tiquet i numeració

Cada tipus de tiquet té la **seva pròpia seqüència** (numeració independent,
correlativa, reinicialitzada per any natural).

| Tipus | Codi | Descripció | Tiquet físic |
|---|---|---|---|
| **Comanda** | `COM` | Tiquet de consum (items de la carta). | Tiquet de comanda |
| **Efectiu** | `EF` | Pagament en efectiu. | Tiquet de caixa |
| **Targeta** | `TG` | Pagament amb targeta (datàfon/TPV). | Justificant de TPV |
| **Crèdit** (room charge) | `RC` | Consum carregat a l'habitació de l'hotel → foli del PMS. | Tiquet de càrrec |
| **Invitació** | `INV` | Cortesia de la casa (no es cobra, no es declara IVA). | Tiquet d'invitació |
| **Nul** | `NUL` | Anul·lació autoritzada per un cap. | Tiquet d'anul·lació |

**Z (tancament de caixa):** seqüència **anual independent** de la dels tiquets
(`Z-AAAA-NNN`, ex. `Z-2026-001`, `Z-2026-002`...). Una Z per dia de negoci.

---

## 2. Crèdits

El **crèdit** és el **càrrec a habitació (room charge)**: el client de l'hotel
consumeix al bar/restaurant i l'import va al **foli de la seva habitació**
(Estada, el PMS), no es cobra al moment. Es distingeix de la resta de mètodes
perquè el cobrament el fa el PMS al tancament de l'estada.

- `Order.room_number` lliga la comanda a l'habitació.
- El mètode de pagament és `room_charge` (tiquet `RC`).

---

## 3. Transicions d'estat d'una comanda

```
open ──► sent_to_kitchen ──► served ──► paid ──► (tancada)
  │                                      │
  └────────────► cancelled ◄─────────────┘  (anul·lació NUL, autoritzada per un cap)
```

- **open** → comanda creada (taula oberta).
- **sent_to_kitchen** → enviada a cuina.
- **served** → servida.
- **paid** → pagada i tancada (té tiquet de pagament: EF/TG/RC/INV).
- **cancelled** → anul·lada (té tiquet NUL autoritzat per un cap).

---

## 4. Taules obertes al tancament del dia

Al tancament (la Z), les comandes encara **obertes** es **tanquen forçosament**
i queden com a **pendents de cobrament**:

- Una comanda `open`/`sent_to_kitchen`/`served` a final de dia → es tanca amb
  un **tiquet de crèdit pendent** (es cobrarà al dia següent).
- Aquests pendents queden registrats a la Z com a línia a part (no es computen
  com a venda tancada, però queden inventariats).

---

## 5. Tractament a la Z (tancament de caixa)

La Z mostra, en aquest ordre:

1. **Vendes declarables** (efectiu, targeta, room charge) — amb IVA.
2. **Descomptes** i vendes netes.
3. **Pagaments per mètode** (efectiu, targeta, room charge...).
4. **Invitacions** (`house`) — **a part**, fora del total i de l'IVA.
5. **Anul·lacions** (`NUL`) — a part, amb autoritzador i motiu.
6. **Càrrecs a habitacions** (room charges) agrupats per habitació.
7. **Pendents de cobrament** (taules tancades forçosament).
8. **Desglossament d'IVA** per tipus.

---

## 6. Regles d'or

- **Les invitacions no declaren IVA**: van sempre a part, fora del total.
- **Cap anul·lació sense autorització d'un cap** (manager): tot `NUL` registra
  qui l'ha autoritzat i el motiu.
- **Cap tiquet es pot esborrar**: només anul·lar (NUL) o corregir.
- **La numeració és per tipus i anual**: es reinicia cada any natural.
