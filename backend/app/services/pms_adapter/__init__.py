"""pms_adapter: integració de room charges de Comanda cap al PMS."""
from .base import PMSAdapterBase
from .factory import get_pms_adapter

__all__ = ["PMSAdapterBase", "get_pms_adapter"]
