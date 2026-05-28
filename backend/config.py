# Projeto Desenvolvido na Data Science Academy
"""Configurações da aplicação via Pydantic BaseSettings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da API carregadas de variáveis de ambiente."""

    APP_NAME: str = "Financas familia oliveira"
    DEBUG: bool = False
    DATABASE_URL: str = 'postgresql+asyncpg://neondb_owner:npg_iIESJFf2W9Zn@ep-bitter-surf-a8cdmnbz.eastus2.azure.neon.tech/neondb?ssl=require'
    BACKEND_URL: str = "http://backend:8001"
    ALLOWED_ORIGINS: str = "http://localhost:8501"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
