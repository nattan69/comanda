"""Interfície abstracta del PMS adapter (room charges de Comanda → PMS)."""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional


class PMSAdapterBase(ABC):
    """Contracte que ha d'implementar cada PMS (Estada intern, Mews, etc.)."""

    @abstractmethod
    def verify_room(self, room_number: str) -> dict:
        """Consulta el règim i crèdit d'una habitació (per al cambrer).

        Retorna un dict amb: room_found, reservation_found, guest_name,
        meal_plan (règim), meal_plan_price, credit_type, credit_limit,
        folio_balance.
        """

    @abstractmethod
    def post_room_charge(
        self,
        external_id: str,
        room_number: str,
        amount: Decimal,
        items: list,
        guest_name: Optional[str] = None,
        staff_id: Optional[str] = None,
        timestamp=None,
    ) -> dict:
        """Posta un càrrec d'habitació al PMS (l'afegeix al foli del client).

        Retorna un dict amb: success, folio_id, folio_item_id, reservation_id,
        error, message.
        """
