from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Base de Datos
    DATABASE_URL: Optional[str] = None

    # Seguridad
    API_KEY: str = ""  # clau genèrica (Ariadna)
    JORNADA_API_KEY: str = ""  # clau pròpia de la integració Jornada

    # Porter únic (Jornada/Jornals → Comanda): secret COMPARTIT per validar el
    # comanda_token (JWT) que emet la conxa. Ha de coincidir amb el secret_key
    # de Jornals/Jornada. Vegeu docs/PROPOSTA_PORTER_UNIC_JORNADA_COMANDA.md
    JORNADA_PORTER_SECRET: str = ""
    JORNADA_PORTER_ALGORITHM: str = "HS256"

    # Secret PROPI del porter (decisió Tomeu 18/09/2026): SEPARAT del secret_key
    # de sessió, perquè canviar un no trenqui l'altre. Si està omplert, mana
    # aquest; si no, es manté el comportament antic (JORNADA_PORTER_SECRET).
    COMANDA_PORTER_SECRET: str = ""
    COMANDA_PORTER_ALGORITHM: str = "HS256"

    @property
    def porter_secret_efectiu(self) -> str:
        """Secret que es fa servir per validar el porter (el nou mana si hi és)."""
        return self.COMANDA_PORTER_SECRET or self.JORNADA_PORTER_SECRET

    @property
    def porter_algorithm_efectiu(self) -> str:
        return self.COMANDA_PORTER_ALGORITHM or self.JORNADA_PORTER_ALGORITHM

    DEBUG: bool = False

    # Integració PMS (room charges cap a Estada o Mews/Cloudbeds...)
    PMS_PROVIDER: str = ""  # internal (Estada) | mews | ... (buit = desactivat)
    PMS_API_URL: str = ""
    PMS_API_KEY: str = ""

    # Integració Compta (assentaments del tancament Z cap al hub comptable)
    COMPTA_URL: str = "http://localhost:8010"  # servei de Compta
    COMPTA_KEY_COMANDA: str = ""  # clau per a l'intake /api/v1/intake/comanda

    # VeriFactu (cumplimiento fiscal)
    # Nombre del software declarado ante la AEAT
    VERIFACTU_SOFTWARE_NAME: str = "Comanda TPV"
    VERIFACTU_SOFTWARE_VERSION: str = "0.1.0"
    VERIFACTU_DEVELOPER_NIF: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
