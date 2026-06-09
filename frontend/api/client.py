"""Client HTTP para o serviço backend (FastAPI)."""

import httpx
import pandas as pd
import streamlit as st

from config import settings


def _base_url() -> str:
    """URL do backend garantindo o esquema http(s).

    O Render injeta o endereço interno como ``host:port`` (sem esquema); aqui
    normalizamos para uma URL válida sem quebrar o default local já completo.
    """
    url = settings.BACKEND_URL
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url.rstrip("/")


@st.cache_data(ttl=settings.CACHE_TTL)
def get_gastos() -> pd.DataFrame:
    """Busca os gastos já tratados na API e devolve um DataFrame pronto p/ análise.

    O tratamento (normalização de cidades, ajuste de datas e parcelas) é feito
    no backend; aqui apenas restauramos os tipos convenientes para os gráficos.
    """
    resposta = httpx.get(f"{_base_url()}/gastos", timeout=60)
    resposta.raise_for_status()

    df = pd.DataFrame(resposta.json())
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    for coluna in ("categoria", "cidade"):
        df[coluna] = df[coluna].astype("category")

    return df


def perguntar_agente(pergunta: str) -> dict:
    """Envia uma pergunta ao Agente de Gastos e devolve a resposta + fontes.

    Não é cacheado: cada pergunta é única e a resposta carrega metadados
    (ferramentas usadas, dados brutos, tokens, latência) para transparência.

    Args:
        pergunta: pergunta do usuário em linguagem natural.

    Returns:
        dict no formato ``RespostaOut`` da API (``resposta``,
        ``ferramentas_usadas``, ``dados_brutos``, ``tokens``, ``latencia_ms``).
    """
    resposta = httpx.post(
        f"{_base_url()}/agente/perguntar",
        json={"pergunta": pergunta},
        timeout=120,
    )
    resposta.raise_for_status()
    return resposta.json()
