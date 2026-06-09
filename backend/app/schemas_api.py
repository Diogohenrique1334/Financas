"""Schemas de resposta da API."""

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class GastoOut(BaseModel):
    """Um lançamento de fatura já tratado, pronto para o frontend."""

    date: date
    descricao: str
    parcelas: Optional[str] = None
    categoria: Optional[str] = None
    cidade: Optional[str] = None
    amount: float
    Parcelas_pagas: Optional[int] = None
    total_parcelas: Optional[int] = None
    Cidade_sem_tratamento: Optional[str] = None


class PerguntaIn(BaseModel):
    """Pergunta do usuário em linguagem natural para o Agente de Gastos."""

    pergunta: str = Field(min_length=1, max_length=500)


class TokensUso(BaseModel):
    """Uso de tokens de uma chamada ao agente (observabilidade/custo)."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class FerramentaUsada(BaseModel):
    """Uma ferramenta que o agente escolheu chamar e com quais parâmetros."""

    ferramenta: str
    parametros: dict[str, Any]


class FonteDados(BaseModel):
    """Retorno cru de uma ferramenta (valor + recorte) para transparência."""

    ferramenta: str
    resultado: Any


class RespostaOut(BaseModel):
    """Resposta do agente com metadados de roteamento, fontes e custo."""

    resposta: str
    ferramentas_usadas: list[FerramentaUsada]
    dados_brutos: list[FonteDados]
    tokens: TokensUso
    latencia_ms: int
