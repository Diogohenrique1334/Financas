"""Métricas determinísticas de qualidade da extração de faturas.

A extração de transações é feita por um LLM (não-determinístico e pago). Para
avaliar a qualidade *sem* re-executar o modelo, este módulo compara o resultado
da extração com sinais que podem ser obtidos diretamente do texto da fatura:

1. **Cobertura de linhas** (recall): das linhas que *parecem* transação (mesma
   heurística de regex do pré-processamento), quantas viraram transação
   estruturada. É a métrica principal — robusta e independente do banco.
2. **Reconciliação de valor**: a soma das transações extraídas bate com o total
   da fatura? Recebe o total como argumento explícito (verificado/conhecido),
   para não depender de uma detecção frágil de "total" no texto.
3. **Validade de schema**: percentual de transações que satisfazem o schema
   ``Transaction`` (data, valor, campos obrigatórios). Útil sobre a saída crua
   do LLM, dentro da pipeline.

Nenhuma função aqui faz chamada de rede.
"""

from __future__ import annotations

import re
from typing import Iterable

# Mesma heurística usada em services.ProcessadorFaturas.preprocess_text:
# uma linha de transação tem uma data (DD/MM) e um valor monetário (0,00).
_PADRAO_TRANSACAO = re.compile(r"\d{2}/\d{2}.*\d+,\d{2}")


def linhas_candidatas(texto: str) -> list[str]:
    """Retorna as linhas do texto que têm forma de transação.

    Args:
        texto: texto bruto extraído do PDF da fatura.

    Returns:
        Lista de linhas normalizadas (espaços colapsados) que casam com o
        padrão data + valor. É o "universo" de transações esperadas.
    """
    candidatas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if _PADRAO_TRANSACAO.search(linha):
            candidatas.append(re.sub(r"\s+", " ", linha))
    return candidatas


def cobertura_linhas(texto: str, n_extraidas: int) -> dict:
    """Compara o nº de transações extraídas com o nº de linhas candidatas.

    Args:
        texto: texto bruto do PDF da fatura.
        n_extraidas: quantas transações o pipeline efetivamente estruturou.

    Returns:
        dict com ``linhas_candidatas``, ``transacoes_extraidas`` e
        ``cobertura`` (razão entre os dois, arredondada). Valores próximos de
        1.0 indicam que o LLM capturou quase todas as linhas de transação.
    """
    n_cand = len(linhas_candidatas(texto))
    cobertura = (n_extraidas / n_cand) if n_cand else 0.0
    return {
        "linhas_candidatas": n_cand,
        "transacoes_extraidas": n_extraidas,
        "cobertura": round(cobertura, 4),
    }


def reconciliacao_valor(soma_extraida: float, total_fatura: float | None) -> dict:
    """Reconcilia a soma das transações extraídas com o total da fatura.

    Args:
        soma_extraida: soma dos valores das transações extraídas.
        total_fatura: total conhecido/verificado da fatura. Se ``None``, a
            reconciliação não é calculada.

    Returns:
        dict com ``total_fatura``, ``soma_extraida``, ``diferenca`` e
        ``reconciliacao`` (1 - erro relativo). ``reconciliacao`` perto de 1.0
        indica que nenhum valor relevante foi perdido nem inventado.
    """
    if not total_fatura:
        return {
            "total_fatura": None,
            "soma_extraida": round(soma_extraida, 2),
            "diferenca": None,
            "reconciliacao": None,
        }
    diferenca = soma_extraida - total_fatura
    erro_relativo = abs(diferenca) / total_fatura
    return {
        "total_fatura": round(total_fatura, 2),
        "soma_extraida": round(soma_extraida, 2),
        "diferenca": round(diferenca, 2),
        "reconciliacao": round(1 - erro_relativo, 4),
    }


def valida_transacoes(transacoes: Iterable[dict]) -> dict:
    """Valida cada transação contra o schema ``Transaction``.

    Importa o schema preguiçosamente para que o módulo não dependa de pydantic
    a menos que esta função seja usada.

    Args:
        transacoes: iterável de dicts (tipicamente a saída crua do LLM).

    Returns:
        dict com ``total``, ``validas`` e ``validade`` (proporção de
        transações que satisfazem o schema).
    """
    from schemas.schemas_fatura import Transaction

    transacoes = list(transacoes)
    validas = 0
    for t in transacoes:
        try:
            Transaction(**t)
            validas += 1
        except Exception:
            pass
    total = len(transacoes)
    return {
        "total": total,
        "validas": validas,
        "validade": round(validas / total, 4) if total else 0.0,
    }


def relatorio_qualidade(
    texto: str,
    valores_extraidos: list[float],
    total_fatura: float | None = None,
) -> dict:
    """Consolida as métricas de qualidade de uma fatura em um único relatório.

    Args:
        texto: texto bruto do PDF da fatura.
        valores_extraidos: lista dos valores (``amount``) das transações
            extraídas. O comprimento é usado como nº de transações.
        total_fatura: total conhecido da fatura (opcional, para reconciliação).

    Returns:
        dict com as seções ``cobertura`` e ``reconciliacao``.
    """
    cobertura = cobertura_linhas(texto, len(valores_extraidos))
    reconciliacao = reconciliacao_valor(sum(valores_extraidos), total_fatura)
    return {"cobertura": cobertura, "reconciliacao": reconciliacao}