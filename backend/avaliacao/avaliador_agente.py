"""Avaliação do Agente de Gastos: golden set + métricas de qualidade.

Mede o que diferencia "fiz um agente" de "sei avaliar um agente". Para cada
pergunta do golden set conhecemos a **ferramenta esperada** e o **valor numérico
esperado** (ground truth calculado direto pelas funções puras de
``consultas_gastos``, FORA do agente). Rodamos o agente e comparamos.

Métricas reportadas (seção 5 de PROXIMOS_PASSOS_AGENTE_GASTOS.md):
1. **Acerto de roteamento** — escolheu a ferramenta certa? (%)
2. **Acerto de parâmetros** — chamou com os parâmetros certos, dado o roteamento? (%)
3. **Acerto numérico** — o valor citado bate com o ground truth, dentro de tolerância? (%)
4. **Taxa de alucinação** — citou número que não veio de ferramenta? (deve ser ~0)
5. **Custo médio** (tokens → R$) e **latência média**.

As funções de métrica (parsing/comparação) são puras e sem rede — testáveis. Só
o runner ``avaliar`` chama o agente (LLM) e o banco.
"""

import asyncio
import os
import re
import sys

import httpx
import openai

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.modelo import estimar_custo_brl as custo_brl
from services import consultas_gastos
from services.agente_service import responder
from services.consultas_gastos import gastos_para_df
from services.gastos_service import listar_gastos_tratados

# Tolerância da comparação numérica.
TOL_REL = 0.01
TOL_ABS = 0.02


# --------------------------------------------------------------------------- #
# Golden set — ground truth via funções puras (computado em runtime sobre o df).
# Cada caso: pergunta, ferramenta esperada, params esperados e uma função que
# devolve a lista de valores que DEVEM aparecer na resposta do agente.
# --------------------------------------------------------------------------- #
def _maior(d: dict) -> float:
    return max(d.values()) if d else 0.0


GOLDEN_SET = [
    {
        "pergunta": "Quanto eu gastei no total entre 1 e 31 de março de 2025?",
        "ferramenta": "total_periodo",
        "params": {"data_inicio": "2025-03-01", "data_fim": "2025-03-31"},
        "esperado": lambda df: [consultas_gastos.total_periodo(df, "2025-03-01", "2025-03-31")["total"]],
    },
    {
        "pergunta": "Qual foi meu gasto total em todo o ano de 2025?",
        "ferramenta": "total_periodo",
        "params": {"data_inicio": "2025-01-01", "data_fim": "2025-12-31"},
        "esperado": lambda df: [consultas_gastos.total_periodo(df, "2025-01-01", "2025-12-31")["total"]],
    },
    {
        "pergunta": "Quanto gastei com transporte em março de 2025?",
        "ferramenta": "gasto_por_categoria",
        "params": {"mes": 3, "ano": 2025, "categoria": "Transporte"},
        "esperado": lambda df: [consultas_gastos.gasto_por_categoria(df, 3, 2025, "Transporte")["total"]],
    },
    {
        "pergunta": "Quanto gastei com alimentação em janeiro de 2025?",
        "ferramenta": "gasto_por_categoria",
        "params": {"mes": 1, "ano": 2025, "categoria": "Alimentação"},
        "esperado": lambda df: [consultas_gastos.gasto_por_categoria(df, 1, 2025, "Alimentação")["total"]],
    },
    {
        "pergunta": "Quanto gastei com lazer em maio de 2025?",
        "ferramenta": "gasto_por_categoria",
        "params": {"mes": 5, "ano": 2025, "categoria": "Lazer"},
        "esperado": lambda df: [consultas_gastos.gasto_por_categoria(df, 5, 2025, "Lazer")["total"]],
    },
    {
        "pergunta": "Como se dividiram meus gastos por categoria em abril de 2025?",
        "ferramenta": "gasto_por_categoria",
        "params": {"mes": 4, "ano": 2025},
        "esperado": lambda df: [_maior(consultas_gastos.gasto_por_categoria(df, 4, 2025)["por_categoria"])],
    },
    {
        "pergunta": "Em quais cidades eu mais gastei em maio de 2025?",
        "ferramenta": "gasto_por_cidade",
        "params": {"mes": 5, "ano": 2025},
        "esperado": lambda df: [_maior(consultas_gastos.gasto_por_cidade(df, 5, 2025)["por_cidade"])],
    },
    {
        "pergunta": "Em quais cidades eu mais gastei em fevereiro de 2025?",
        "ferramenta": "gasto_por_cidade",
        "params": {"mes": 2, "ano": 2025},
        "esperado": lambda df: [_maior(consultas_gastos.gasto_por_cidade(df, 2, 2025)["por_cidade"])],
    },
    {
        "pergunta": "Quais foram minhas 5 maiores compras em março de 2025?",
        "ferramenta": "top_estabelecimentos",
        "params": {"mes": 3, "ano": 2025},
        "esperado": lambda df: [consultas_gastos.top_estabelecimentos(df, 3, 2025, 5)["top"][0]["total"]],
    },
    {
        "pergunta": "Quais foram meus 3 maiores estabelecimentos em fevereiro de 2025?",
        "ferramenta": "top_estabelecimentos",
        "params": {"mes": 2, "ano": 2025, "n": 3},
        "esperado": lambda df: [consultas_gastos.top_estabelecimentos(df, 2, 2025, 3)["top"][0]["total"]],
    },
    {
        "pergunta": "Eu gastei mais em março ou em fevereiro de 2025?",
        "ferramenta": "comparar_meses",
        "params": {"mes_a": 2, "ano_a": 2025, "mes_b": 3, "ano_b": 2025},
        "esperado": lambda df: [
            consultas_gastos.comparar_meses(df, 2, 2025, 3, 2025)["mes_a"]["total"],
            consultas_gastos.comparar_meses(df, 2, 2025, 3, 2025)["mes_b"]["total"],
        ],
    },
    {
        "pergunta": "Como meu gasto de abril de 2025 se compara com o de março de 2025?",
        "ferramenta": "comparar_meses",
        "params": {"mes_a": 3, "ano_a": 2025, "mes_b": 4, "ano_b": 2025},
        "esperado": lambda df: [
            consultas_gastos.comparar_meses(df, 3, 2025, 4, 2025)["mes_a"]["total"],
            consultas_gastos.comparar_meses(df, 3, 2025, 4, 2025)["mes_b"]["total"],
        ],
    },
    {
        "pergunta": "Tenho gastos com o PayPal? Quanto no total?",
        "ferramenta": "buscar_transacoes",
        "params": {"texto": "PAYPAL"},
        "esperado": lambda df: [consultas_gastos.buscar_transacoes(df, "PAYPAL")["total"]],
    },
    {
        "pergunta": "Quanto gastei em postos de combustível no total?",
        "ferramenta": "buscar_transacoes",
        "params": {"texto": "POSTO"},
        "esperado": lambda df: [consultas_gastos.buscar_transacoes(df, "POSTO")["total"]],
    },
    {
        "pergunta": "Quanto gastei em supermercado em março de 2025?",
        "ferramenta": "buscar_transacoes",
        "params": {"texto": "SUPERMERCADO", "mes": 3, "ano": 2025},
        "esperado": lambda df: [consultas_gastos.buscar_transacoes(df, "SUPERMERCADO", 3, 2025)["total"]],
    },
    {
        "pergunta": "Qual é a minha média de gasto mensal?",
        "ferramenta": "media_mensal",
        "params": {},
        "esperado": lambda df: [consultas_gastos.media_mensal(df)["media"]],
    },
    {
        "pergunta": "Qual a minha média mensal de gastos com transporte?",
        "ferramenta": "media_mensal",
        "params": {"categoria": "Transporte"},
        "esperado": lambda df: [consultas_gastos.media_mensal(df, "Transporte")["media"]],
    },
    {
        "pergunta": "Qual a minha média mensal de gastos com alimentação?",
        "ferramenta": "media_mensal",
        "params": {"categoria": "Alimentação"},
        "esperado": lambda df: [consultas_gastos.media_mensal(df, "Alimentação")["media"]],
    },
    {
        "pergunta": "Quanto eu ainda devo de parcelas em aberto?",
        "ferramenta": "compromissos_parcelados",
        "params": {},
        "esperado": lambda df: [consultas_gastos.compromissos_parcelados(df)["valor_total_em_aberto"]],
    },
    {
        "pergunta": "Quanto gastei com compras em dezembro de 2025?",
        "ferramenta": "gasto_por_categoria",
        "params": {"mes": 12, "ano": 2025, "categoria": "Compras"},
        "esperado": lambda df: [consultas_gastos.gasto_por_categoria(df, 12, 2025, "Compras")["total"]],
    },
]


# --------------------------------------------------------------------------- #
# Métricas puras (sem rede)
# --------------------------------------------------------------------------- #
_PADRAO_NUM_BR = re.compile(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\b")


def parse_numeros_br(texto: str) -> list[float]:
    """Extrai valores monetários/percentuais em formato brasileiro do texto.

    Capta padrões como ``R$ 1.234,56``, ``175,00`` ou ``2,44%`` e devolve floats.
    Inteiros sem casas decimais (ex.: "11 parcelas") são ignorados de propósito —
    só nos interessam os valores numéricos "citados", não contagens.
    """
    numeros = []
    for inteiro, decimais in _PADRAO_NUM_BR.findall(texto):
        numeros.append(float(inteiro.replace(".", "") + "." + decimais))
    return numeros


def numeros_de_estrutura(obj) -> set[float]:
    """Coleta recursivamente todos os números (não-bool) de dicts/listas.

    Usado para montar o universo de valores que vieram de ferramentas — a base
    para detectar alucinação numérica.
    """
    encontrados: set[float] = set()

    def _walk(o):
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            encontrados.add(round(float(o), 2))
        elif isinstance(o, dict):
            for v in o.values():
                _walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                _walk(v)

    _walk(obj)
    return encontrados


def _proximo(valor: float, universo) -> bool:
    """True se ``valor`` casa com algum do ``universo`` dentro da tolerância."""
    return any(
        abs(valor - ref) <= max(TOL_ABS, TOL_REL * abs(ref)) for ref in universo
    )


def avaliar_caso(caso: dict, resultado: dict, esperado: list[float]) -> dict:
    """Calcula os acertos de um caso comparando o resultado do agente ao ground truth.

    Args:
        caso: entrada do golden set (pergunta, ferramenta, params).
        resultado: retorno de ``agente_service.responder``.
        esperado: valores que devem aparecer na resposta (ground truth).

    Returns:
        dict com flags ``roteamento_ok``, ``parametros_ok``, ``numerico_ok`` e
        ``alucinou`` (booleanos) para agregação.
    """
    ferramentas = [f["ferramenta"] for f in resultado["ferramentas_usadas"]]
    roteamento_ok = caso["ferramenta"] in ferramentas

    parametros_ok = roteamento_ok and _parametros_batem(
        caso["params"],
        next((f["parametros"] for f in resultado["ferramentas_usadas"] if f["ferramenta"] == caso["ferramenta"]), {}),
    )

    nums_resposta = parse_numeros_br(resultado["resposta"])
    numerico_ok = all(_proximo(v, nums_resposta) for v in esperado) if esperado else True

    universo_ferramentas = set()
    for fonte in resultado["dados_brutos"]:
        universo_ferramentas |= numeros_de_estrutura(fonte["resultado"])
    # As ferramentas guardam variações com sinal (ex.: variacao_pct = -39.38),
    # mas o agente as redige como magnitude positiva ("redução de 39,38%"). Para
    # não marcar isso como alucinação, o número da resposta é rastreável se ele
    # OU seu valor absoluto casa com algum valor (ou |valor|) das ferramentas.
    universo_ferramentas |= {abs(x) for x in universo_ferramentas}
    alucinou = any(
        not (_proximo(v, universo_ferramentas) or _proximo(abs(v), universo_ferramentas))
        for v in nums_resposta
    )

    return {
        "roteamento_ok": roteamento_ok,
        "parametros_ok": parametros_ok,
        "numerico_ok": numerico_ok,
        "alucinou": alucinou,
    }


def _parametros_batem(esperados: dict, obtidos: dict) -> bool:
    """Compara os parâmetros esperados com os usados (string case-insensitive)."""
    for chave, valor in esperados.items():
        if chave not in obtidos:
            return False
        a, b = obtidos[chave], valor
        if isinstance(b, str) and isinstance(a, str):
            if a.casefold() != b.casefold():
                return False
        elif a != b:
            return False
    return True


# --------------------------------------------------------------------------- #
# Runner (chama o agente — faz rede)
# --------------------------------------------------------------------------- #
MAX_TENTATIVAS = 3
BACKOFF_S = 5


async def _responder_com_retry(pergunta: str) -> dict:
    """Chama ``responder`` com retry/backoff para erros transitórios de rede.

    Erros de conexão (DNS/timeout ao falar com a OpenAI) são transitórios e não
    devem derrubar a avaliação inteira. Tentamos ``MAX_TENTATIVAS`` vezes; só
    relançamos se todas falharem.
    """
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            return await responder(pergunta)
        except (httpx.HTTPError, openai.APIConnectionError, openai.APITimeoutError) as exc:
            if tentativa == MAX_TENTATIVAS:
                raise
            print(f"  ⚠️ tentativa {tentativa} falhou ({type(exc).__name__}); retry em {BACKOFF_S}s…")
            await asyncio.sleep(BACKOFF_S)


async def avaliar(casos: list[dict] = GOLDEN_SET) -> dict:
    """Roda o golden set contra o agente real e agrega as métricas.

    Resiliente a falhas: cada pergunta é isolada em try/except (com retry para
    erros de rede), de modo que uma falha pontual não derruba a rodada nem
    impede o relatório. As métricas de acerto são calculadas só sobre os casos
    concluídos; falhas são reportadas à parte.

    Args:
        casos: lista de casos (default: ``GOLDEN_SET``).

    Returns:
        dict com as métricas consolidadas, os resultados por caso e as falhas.
    """
    df = gastos_para_df(await listar_gastos_tratados())

    por_caso = []
    falhas = []
    for i, caso in enumerate(casos, 1):
        print(f"[{i}/{len(casos)}] {caso['pergunta']}")
        try:
            esperado = caso["esperado"](df)
            resultado = await _responder_com_retry(caso["pergunta"])
        except Exception as exc:  # noqa: BLE001 — registra e segue
            print(f"  ✗ falhou definitivamente: {type(exc).__name__}: {exc}")
            falhas.append({"pergunta": caso["pergunta"], "erro": f"{type(exc).__name__}: {exc}"})
            continue

        flags = avaliar_caso(caso, resultado, esperado)
        por_caso.append(
            {
                "pergunta": caso["pergunta"],
                "esperado": esperado,
                "resposta": resultado["resposta"],
                "tokens": resultado["tokens"],
                "latencia_ms": resultado["latencia_ms"],
                "custo_brl": custo_brl(resultado["tokens"]),
                **flags,
            }
        )

    n = len(por_caso)
    metricas = {
        "n_casos": len(casos),
        "n_concluidos": n,
        "n_falhas": len(falhas),
        "acerto_roteamento": round(sum(c["roteamento_ok"] for c in por_caso) / n, 4) if n else None,
        "acerto_parametros": round(sum(c["parametros_ok"] for c in por_caso) / n, 4) if n else None,
        "acerto_numerico": round(sum(c["numerico_ok"] for c in por_caso) / n, 4) if n else None,
        "taxa_alucinacao": round(sum(c["alucinou"] for c in por_caso) / n, 4) if n else None,
        "custo_medio_brl": round(sum(c["custo_brl"] for c in por_caso) / n, 4) if n else None,
        "latencia_media_ms": round(sum(c["latencia_ms"] for c in por_caso) / n) if n else None,
        "tokens_medio": round(sum(c["tokens"]["total_tokens"] for c in por_caso) / n) if n else None,
    }
    return {"metricas": metricas, "por_caso": por_caso, "falhas": falhas}


def _imprimir_relatorio(relatorio: dict) -> None:
    """Imprime a tabela de métricas e os casos que falharam."""
    m = relatorio["metricas"]
    print("\n" + "=" * 60)
    print(f"AVALIAÇÃO DO AGENTE DE GASTOS — {m['n_concluidos']}/{m['n_casos']} perguntas concluídas")
    if m["n_falhas"]:
        print(f"(⚠️ {m['n_falhas']} falha(s) de execução — ver lista abaixo)")
    print("=" * 60)
    if not m["n_concluidos"]:
        print("Nenhuma pergunta concluída — sem métricas.")
        for f in relatorio["falhas"]:
            print(f"  ✗ {f['erro']} | {f['pergunta']}")
        print("=" * 60)
        return
    print(f"Acerto de roteamento : {m['acerto_roteamento']:.0%}")
    print(f"Acerto de parâmetros : {m['acerto_parametros']:.0%}")
    print(f"Acerto numérico      : {m['acerto_numerico']:.0%}")
    print(f"Taxa de alucinação   : {m['taxa_alucinacao']:.0%}")
    print(f"Custo médio/pergunta : R$ {m['custo_medio_brl']:.4f}")
    print(f"Latência média       : {m['latencia_media_ms']} ms")
    print(f"Tokens médio         : {m['tokens_medio']}")
    print("-" * 60)
    for c in relatorio["por_caso"]:
        falhas = []
        if not c["roteamento_ok"]:
            falhas.append("ROTEAMENTO")
        if not c["parametros_ok"]:
            falhas.append("PARAMS")
        if not c["numerico_ok"]:
            falhas.append("NUMERICO")
        if c["alucinou"]:
            falhas.append("ALUCINOU")
        if falhas:
            print(f"✗ {', '.join(falhas):<28} | {c['pergunta']}")
            print(f"    esperado={c['esperado']}  resposta={c['resposta'][:90]!r}")
    for f in relatorio["falhas"]:
        print(f"✗ {'EXECUÇÃO':<28} | {f['pergunta']}  ({f['erro']})")
    print("=" * 60)


def _salvar_json(relatorio: dict, caminho: str) -> None:
    """Persiste o relatório completo em JSON (artefato p/ README e inspeção)."""
    import json

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(relatorio, arquivo, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    # Console do Windows é cp1252; garante UTF-8 para os caracteres do relatório.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    relatorio = asyncio.run(avaliar())
    caminho_json = os.path.join(os.path.dirname(__file__), "resultado_avaliacao.json")
    _salvar_json(relatorio, caminho_json)
    _imprimir_relatorio(relatorio)
    print(f"\nRelatório completo salvo em: {caminho_json}")
