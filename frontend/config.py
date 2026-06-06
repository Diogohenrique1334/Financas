"""Configurações do frontend (Streamlit) via Pydantic BaseSettings."""

from pathlib import Path

from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Configurações carregadas de variáveis de ambiente / .env."""

    # URL do serviço backend (FastAPI). Default p/ execução local.
    BACKEND_URL: str = "http://localhost:8001"
    # Tempo de cache (segundos) dos dados buscados na API.
    CACHE_TTL: int = 300
    # Caminho do módulo de mapas dinâmicos da biblioteca Baltazar.
    # Default p/ execução local no Windows; no Docker é injetado via env.
    BALTAZAR_MAPAS_PATH: str = (
        r"c:\Users\User\OneDrive - Claro SA\Área de Trabalho\notebook Dell"
        r"\Diogo Coisas pessoais\Projetos\baltazar\graficos\graficos_streamlit"
        r"\mapas_dinamicos.py"
    )

    class Config:
        env_file = str(_ENV_FILE)
        extra = "allow"


settings = Settings()
