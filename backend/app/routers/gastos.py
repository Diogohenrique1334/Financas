"""Rotas de gastos."""

from fastapi import APIRouter

from app.schemas_api import GastoOut
from services.gastos_service import listar_gastos_tratados

router = APIRouter(prefix="/gastos", tags=["gastos"])


@router.get("", response_model=list[GastoOut])
async def get_gastos() -> list[GastoOut]:
    """Retorna todos os gastos já tratados (normalizados e com parcelas resolvidas)."""
    return await listar_gastos_tratados()
