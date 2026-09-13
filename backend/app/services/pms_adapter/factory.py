"""Factory del PMS adapter segons la configuració (PMS_PROVIDER)."""
from ...config import settings
from .base import PMSAdapterBase


def get_pms_adapter() -> PMSAdapterBase | None:
    """Retorna l'adapter PMS configurat, o None si la integració està desactivada.

    `PMS_PROVIDER` buit → integració desactivada (Comanda funciona com a TPV
    standalone sense room charges). `internal` → Estada (PMS propi).
    """
    provider = (settings.PMS_PROVIDER or "").strip().lower()
    if not provider:
        return None
    if provider == "internal":
        from .internal import InternalAdapter

        return InternalAdapter(settings.PMS_API_URL, settings.PMS_API_KEY)
    raise ValueError(f"PMS provider desconegut: {provider}")
