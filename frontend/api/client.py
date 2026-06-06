"""Client HTTP para o serviço backend (FastAPI)."""

import httpx
import pandas as pd
import streamlit as st

from config import settings


@st.cache_data(ttl=settings.CACHE_TTL)
def get_gastos() -> pd.DataFrame:
    """Busca os gastos já tratados na API e devolve um DataFrame pronto p/ análise.

    O tratamento (normalização de cidades, ajuste de datas e parcelas) é feito
    no backend; aqui apenas restauramos os tipos convenientes para os gráficos.
    """
    resposta = httpx.get(f"{settings.BACKEND_URL}/gastos", timeout=60)
    resposta.raise_for_status()

    df = pd.DataFrame(resposta.json())
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    for coluna in ("categoria", "cidade"):
        df[coluna] = df[coluna].astype("category")

    return df
