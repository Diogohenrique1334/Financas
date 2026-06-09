"""Rota do Agente de Gastos."""

from fastapi import APIRouter, HTTPException

from app.limite_uso import LimiteDiario, LimiteExcedido
from app.schemas_api import PerguntaIn, RespostaOut
from config import settings
from services.agente_service import responder

router = APIRouter(prefix="/agente", tags=["agente"])

# Teto diário de chamadas — protege a chave OpenAI caso o endpoint seja público.
_limite = LimiteDiario(settings.LIMITE_DIARIO_AGENTE)


@router.post("/perguntar", response_model=RespostaOut)
async def perguntar(payload: PerguntaIn) -> RespostaOut:
    """Responde uma pergunta em linguagem natural sobre os gastos.

    O agente decide qual ferramenta de consulta chamar (tool calling), executa a
    agregação determinística em pandas e redige a resposta em PT-BR. Devolve
    também as fontes (ferramentas + dados usados) e metadados de custo/latência.
    """
    try:
        _limite.registrar()
    except LimiteExcedido as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    try:
        return await responder(payload.pergunta)
    except Exception as exc:  # noqa: BLE001 — superfície única de erro p/ o cliente
        raise HTTPException(status_code=502, detail=f"Falha ao consultar o agente: {exc}") from exc
