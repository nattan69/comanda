"""
Servei de numeració de tiquets (per tipus i any natural).

Cada tipus de tiquet té la seva pròpia seqüència correlativa, reinicialitzada
cada any. La Z té la seva pròpia seqüència anual (tipus `Z`).
"""

from datetime import date
from sqlalchemy.orm import Session

from ..models.models import TicketSequence

# Tipus de tiquet (codi → mètode de pagament associat, si n'hi ha).
TICKET_TYPES = ("COM", "EF", "TG", "RC", "INV", "NUL", "Z")


def _get_or_create_sequence(db: Session, ticket_type: str, year: int) -> TicketSequence:
    seq = (
        db.query(TicketSequence)
        .filter(TicketSequence.ticket_type == ticket_type, TicketSequence.year == year)
        .first()
    )
    if not seq:
        seq = TicketSequence(ticket_type=ticket_type, year=year, counter=0)
        db.add(seq)
        db.flush()
    return seq


def next_ticket_number(db: Session, ticket_type: str, year: int | None = None) -> tuple[int, str]:
    """Retorna (nº correlatiu, codi de tiquet) del tipus donat per a l'any.

    El codi té format `TIPUS-AAAA-NNNN` (ex. `COM-2026-0001`). Incrementa el
    comptador de la seqüència de forma idempotent (una fila per tipus i any).
    """
    year = year or date.today().year
    seq = _get_or_create_sequence(db, ticket_type, year)
    seq.counter = (seq.counter or 0) + 1
    db.flush()
    return seq.counter, f"{ticket_type}-{year}-{seq.counter:04d}"


def ticket_code(ticket_type: str, number: int, year: int | None = None) -> str:
    """Formata un codi de tiquet a partir del tipus, número i any."""
    year = year or date.today().year
    return f"{ticket_type}-{year}-{number:04d}"
