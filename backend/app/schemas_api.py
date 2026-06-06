"""Schemas de resposta da API."""

from datetime import date
from typing import Optional

from pydantic import BaseModel


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
