from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Base de Datos
    DATABASE_URL: Optional[str] = None

    # Seguridad
    API_KEY: str = ""  # clau genèrica (Ariadna)
    JORNADA_API_KEY: str = ""  # clau pròpia de la integració Jornada
    DEBUG: bool = False

    # Integració PMS (room charges cap a Estada o Mews/Cloudbeds...)
    PMS_PROVIDER: str = ""  # internal (Estada) | mews | ... (buit = desactivat)
    PMS_API_URL: str = ""
    PMS_API_KEY: str = ""

    # VeriFactu (cumplimiento fiscal)
    # Nombre del software declarado ante la AEAT
    VERIFACTU_SOFTWARE_NAME: str = "Comanda TPV"
    VERIFACTU_SOFTWARE_VERSION: str = "0.1.0"
    VERIFACTU_DEVELOPER_NIF: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
