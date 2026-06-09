"""Ponto de entrada da API FastAPI do projeto Finanças.

Executar a partir do diretório ``backend/``:

    uvicorn app.main_api:app --port 8001 --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import agente, gastos
from config import settings

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origem.strip() for origem in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gastos.router)
app.include_router(agente.router)


@app.get("/health", tags=["infra"])
def health() -> dict:
    """Healthcheck simples para orquestração/monitoramento."""
    return {"status": "ok"}
