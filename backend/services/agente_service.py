"""Orquestração do Agente de Gastos: pergunta → agente → resposta + metadados.

Camada de mais alto nível que cola tudo: carrega os gastos tratados (mesma
fonte de verdade do dashboard), monta o agente sobre esse recorte, executa a
pergunta medindo tokens e latência, e extrai as "fontes" (ferramentas chamadas +
dados que alimentaram cada resposta) para a transparência anti-alucinação no
frontend.

É a única função desta frente que toca banco e LLM ao mesmo tempo — por isso a
aritmética (``consultas_gastos``) e a montagem do agente (``agente_gastos``)
ficam isoladas e testáveis sem ela.
"""

import json
import logging
import time

from langchain_core.callbacks import get_usage_metadata_callback

from agents.agente_gastos import construir_agente
from agents.modelo import estimar_custo_brl
from services.consultas_gastos import gastos_para_df
from services.gastos_service import listar_gastos_tratados

logger = logging.getLogger(__name__)


def _extrair_fontes(intermediate_steps: list) -> tuple[list[dict], list[dict]]:
    """Separa os passos do agente em ferramentas chamadas e dados retornados.

    Args:
        intermediate_steps: lista de ``(AgentAction, observation)`` do executor.

    Returns:
        ``(ferramentas_usadas, dados_brutos)`` — a primeira lista com
        ``{ferramenta, parametros}`` (o roteamento do LLM), a segunda com o
        retorno cru de cada ferramenta (valor + recorte) para exibir as fontes.
    """
    ferramentas_usadas = []
    dados_brutos = []
    for acao, observacao in intermediate_steps:
        ferramentas_usadas.append({"ferramenta": acao.tool, "parametros": acao.tool_input})
        dados_brutos.append({"ferramenta": acao.tool, "resultado": observacao})
    return ferramentas_usadas, dados_brutos


def _agregar_tokens(usage_metadata: dict) -> dict:
    """Soma o uso de tokens reportado por modelo num total único.

    Args:
        usage_metadata: dict ``{modelo: {input_tokens, output_tokens, ...}}``
            preenchido pelo ``get_usage_metadata_callback``.

    Returns:
        dict com ``input_tokens``, ``output_tokens`` e ``total_tokens``.
    """
    entrada = sum(uso.get("input_tokens", 0) for uso in usage_metadata.values())
    saida = sum(uso.get("output_tokens", 0) for uso in usage_metadata.values())
    return {
        "input_tokens": entrada,
        "output_tokens": saida,
        "total_tokens": entrada + saida,
    }


async def responder(pergunta: str) -> dict:
    """Responde uma pergunta sobre os gastos, com metadados de observabilidade.

    Args:
        pergunta: pergunta do usuário em linguagem natural.

    Returns:
        dict com ``resposta`` (texto PT-BR), ``ferramentas_usadas`` (roteamento),
        ``dados_brutos`` (fontes para transparência), ``tokens`` e
        ``latencia_ms``.
    """
    registros = await listar_gastos_tratados()
    df = gastos_para_df(registros)
    executor = construir_agente(df)

    inicio = time.perf_counter()
    with get_usage_metadata_callback() as callback:
        resultado = await executor.ainvoke({"pergunta": pergunta})
    latencia_ms = round((time.perf_counter() - inicio) * 1000)

    ferramentas_usadas, dados_brutos = _extrair_fontes(resultado.get("intermediate_steps", []))
    tokens = _agregar_tokens(callback.usage_metadata)

    # Observabilidade: uma linha estruturada por consulta (sem os dados brutos,
    # que podem ser grandes/sensíveis) para análise de custo e roteamento.
    logger.info(
        "agente_consulta %s",
        json.dumps(
            {
                "pergunta": pergunta,
                "ferramentas": [f["ferramenta"] for f in ferramentas_usadas],
                "tokens": tokens,
                "latencia_ms": latencia_ms,
                "custo_brl": estimar_custo_brl(tokens),
            },
            ensure_ascii=False,
        ),
    )

    return {
        "resposta": resultado["output"],
        "ferramentas_usadas": ferramentas_usadas,
        "dados_brutos": dados_brutos,
        "tokens": tokens,
        "latencia_ms": latencia_ms,
    }
