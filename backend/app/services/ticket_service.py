"""
Servei de numeració de tiquets.

POLÍTICA (corregida per Tomeu): una SOLA seqüència correlativa per a TOTS els
tiquets normals (comanda, efectiu, targeta, crèdit/habitació, nul) i una
seqüència A PART per a les invitacions (house). La Z (tancament) té la seva
pròpia seqüència anual.

Seqüències:
- `TICKET` → tots els tiquets normals (codis `T-AAAA-NNNN`).
- `INV`    → invitacions / house (codis `INV-AAAA-NNNN`).
- `Z`      → tancament de caixa (codis `Z-AAAA-NNNN`, anual).

Totes reinicialitzades per any natural.
"""

from datetime import date
from sqlalchemy.orm import Session

from ..models.models import TicketSequence

# Seqüències de numeració existents.
SEQUENCES = ("TICKET", "INV", "Z")

# Prefix del codi imprès per a cada seqüència.
PREFIX = {
    "TICKET": "T",
    "INV": "INV",
    "Z": "Z",
}


def _get_or_create_sequence(db: Session, seq_type: str, year: int) -> TicketSequence:
    seq = (
        db.query(TicketSequence)
        .filter(TicketSequence.ticket_type == seq_type, TicketSequence.year == year)
        .first()
    )
    if not seq:
        seq = TicketSequence(ticket_type=seq_type, year=year, counter=0)
        db.add(seq)
        db.flush()
    return seq


def next_ticket_number(db: Session, seq_type: str, year: int | None = None) -> tuple[int, str]:
    """Retorna (nº correlatiu, codi de tiquet) de la seqüència donada.

    `seq_type` ha de ser una de `SEQUENCES` (`TICKET`, `INV`, `Z`). El codi té
    format `PREFIX-AAAA-NNNN` (ex. `T-2026-0001`, `INV-2026-0001`,
    `Z-2026-0001`). Incrementa el comptador idempotent (una fila per seqüència
    i any).
    """
    if seq_type not in SEQUENCES:
        raise ValueError(f"Seqüència desconeguda: {seq_type}")
    year = year or date.today().year
    seq = _get_or_create_sequence(db, seq_type, year)
    seq.counter = (seq.counter or 0) + 1
    db.flush()
    return seq.counter, f"{PREFIX[seq_type]}-{year}-{seq.counter:04d}"


def ticket_code(seq_type: str, number: int, year: int | None = None) -> str:
    """Formata un codi de tiquet a partir de la seqüència, número i any."""
    year = year or date.today().year
    return f"{PREFIX[seq_type]}-{year}-{number:04d}"
