# Projeto Desenvolvido na Data Science Academy
"""Configurações da aplicação via Pydantic BaseSettings."""

from pathlib import Path
from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Configurações da API carregadas de variáveis de ambiente."""

    APP_NAME: str = "Financas familia oliveira"
    DEBUG: bool = False
    DATABASE_URL: str
    BACKEND_URL: str = "http://backend:8001"
    ALLOWED_ORIGINS: str = "http://localhost:8501"
    # Teto diário de chamadas ao agente (protege a chave OpenAI se exposto).
    LIMITE_DIARIO_AGENTE: int = 200

    class Config:
        env_file = str(_ENV_FILE)
        extra = "allow"


settings = Settings()
