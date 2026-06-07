"""Avaliação da qualidade da extração de faturas.

Mede o quão completa e correta foi a extração de transações de uma fatura
*sem precisar re-chamar o LLM* — usando sinais determinísticos e reprodutíveis.
"""

from .avaliador_extracao import (
    linhas_candidatas,
    cobertura_linhas,
    reconciliacao_valor,
    valida_transacoes,
    relatorio_qualidade,
)

__all__ = [
    "linhas_candidatas",
    "cobertura_linhas",
    "reconciliacao_valor",
    "valida_transacoes",
    "relatorio_qualidade",
]