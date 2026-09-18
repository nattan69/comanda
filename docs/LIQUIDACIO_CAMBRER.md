# Liquidació del cambrer, X i Z — contracte tècnic

> Decisió Tomeu 18/09/2026 · Comanda (TPV)

## 1. La regla

**El cambrer que duu moviments NO surt sense quadrar.**

En prémer *Sortir* a la Comandera, si el torn té moviments (vendes, invitacions,
nuls, taules obertes), s'obre un **modal de liquidació** que demana:

| Camp | Qui el posa | Què és |
|---|---|---|
| **Efectiu entregat** | el cambrer | el que posa a caixa |
| **Errors** | el cambrer | diferències que assumeix com a seves |

I el sistema li dona **PER BONS** (llegit, no editable) el que ja certifica Jornada,
perquè no s'hagi de posar a sumar a mà:

| Per bons | Font |
|---|---|
| Targetes de crèdit | pagaments `card` del torn |
| Crèdits a habitació | pagaments `room_charge` del torn |

Si el torn no duu cap moviment, el cambrer surt directament (sense modal).

### Desquadre — dues xifres, no una

```
desquadre          = efectiu_entregat - efectiu_esperat     (negatiu = falta diners)
desquadre_pendent  = desquadre + errors                     (0 = tot justificat)
```

## 2. Documents que s'imprimeixen (impressora TÈRMICA de tiquets, 80 mm)

Són **documents separats**, per imprimir-los, **signar-los** i ficar-los **dins el
sobre** amb els doblers i els justificants.

| Document | Endpoint | Qui el firma |
|---|---|---|
| Liquidació del cambrer | `GET /shifts/{shift_id}/liquidacio` | el cambrer |
| Full de moviments del torn | `GET /shifts/{shift_id}/moviments` | el cambrer |
| Liquidació dels cambrers del centre | `GET /shifts/liquidacio/centre?data=AAAA-MM-DD` | l'encarregat |
| **Tiquet de la X** | `GET /closure/{data}/x-ticket` | l'encarregat |
| **Tiquet de la Z** | `GET /closure/{data}/z-ticket` | l'encarregat |

Tots accepten `?format=text` (per veure'ls o imprimir-los en un full) o
`?format=escpos` (**bytes crus** per a la impressora tèrmica).

Tots surten de `app/services/liquidacio_service.py`.

### Contingut del sobre (al full de liquidació)

Doblers (efectiu) · Nuls · Invitacions · Crèdits a habitació · Targetes — amb el
detall de cada justificatiu (nº de tiquet, hora, import, motiu i habitació).

## 3. La X i la Z duen la liquidació de TOTS els cambrers

L'encarregat la **repassa i la firma**. `closure_service._liquidacions_de_cambrers()`
retorna:

```json
{
  "cambrers":   [ { staff_name, efectiu_esperat, efectiu_entregat, errors,
                    desquadre, desquadre_pendent, observacions, per_bons } ],
  "count": 3,
  "total_efectiu_esperat": "...", "total_efectiu_entregat": "...",
  "total_errors": "...", "total_desquadre_pendent": "...",
  "torns_oberts":      [ ... ],     ← els cambrers que NO han fet logout
  "count_oberts": 1,
  "total_obert_efectiu_esperat": "..."
}
```

**Els torns oberts surten remarcats**: un torn sense tancar és exactament el que fa
que la caixa no quadri. La pantalla de tancament avisa abans de fer la Z.

## 4. BONYS GROSSOS trobats i arreglats (18/09/2026)

### 4a. Les comandes es creaven SENSE `shift_id`

El front no enviava mai `shift_id`, i `create_order` el desava tal qual. Com que la
liquidació filtra per torn, **hauria sortit sempre 0,00 €**.

**Arreglat en dues capes:**

1. El **cambrer es pren de la SESSIÓ**, no del cos: `staff_id = payload.staff_id or sessio.staff_id`
   (la ruta ja té `require_auth`). Així cap comanda pot quedar òrfena de cambrer.
2. El **torn es DERIVA** del torn obert del cambrer (`shift_service.torn_obert_de`), i
   el centre també se'n deriva si no ve informat.

La Comandera, a més, obre el torn en fer login (`POST /shifts/open`) i té
`GET /shifts/obert?staff_id=` per saber a quin torn i centre està.

### 4b. El NUL no tancava la comanda

El nul s'enregistra amb import **0**, així que `paid_total >= total` mai no es
complia i **la comanda quedava Oberta per sempre** — sortia com a taula sense cobrar
a la liquidació del cambrer i a la Z.

**Arreglat:** `if method in ("anul", "null") or paid_total >= total: order.status = "paid"`.
Un nul és una anul·lació de consumició: la comanda queda tancada i fora de la venda.

### 4c. `verify_e2e.py` estava trencat des de la capa d'autenticació

Cridava tots els endpoints sense Bearer → `401 Autenticació requerida`. Ara fa login
per PIN primer, i corre contra una **BD temporal pròpia** (no toca la demo).

## 5. Pitfalls d'impressió (80 mm / CP858)

- **El renderitzador genèric de tiquets posa en NEGRETA tota línia que comenci per
  `TOTAL`** — se'n menjaria les línies de signatura. `liquidacio_service` té el seu
  propi renderitzador (`render_escpos`).
- **Les línies de punts es CALCULEN, no s'escriuen a mà.** Escrites a mà se surten de
  la ratlla i la impressora les talla.
- **El guió llarg `—` NO és a CP858**: surt com a brossa. Fer servir `-`.
- Tot el text passa per `_encode_escpos` (CP858), que viu a `receipt_service.py`.
- Amplada: **48 caràcters**. Els noms llargs es tallen amb `_talla()`.

## 6. Proves

```bash
cd backend
python3 verify_e2e.py                        # flux complet (login → comanda → fiscal → Ariadna)
python3 scripts/prova_liquidacio_cambrer.py  # torn derivat, per bons, nuls, desquadre, Z amb tots
python3 scripts/prova_documents_liquidacio.py # els 5 documents, signatura, amplada, ESC/POS
```

Les tres han de passar. La segona i la tercera fan servir BD temporal.

## 7. Front

| Fitxer | Què fa |
|---|---|
| `components/BotoSortirCambrer.tsx` | botó Sortir + modal de liquidació + impressió |
| `components/PanellLiquidacionsCambrers.tsx` | taula de liquidacions per a l'encarregat |
| `app/tancament/page.tsx` | botons d'imprimir X / Z / liquidacions |
| `app/comandera/page.tsx` | obre el torn en fer login |
| `lib/printer.ts` | `imprimeixLiquidacioCambrer` · `imprimeixMovimentsCambrer` · `imprimeixLiquidacioCentre` · `imprimeixX` · `imprimeixZ` · `obreDocumentText` (pla B) |
