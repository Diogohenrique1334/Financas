"""Camada de serviço: orquestra repositório + pipeline de tratamento.

Entrega registros de gastos já tratados (normalização de cidades, ajuste de
datas e parcelas) prontos para serialização JSON pela API.
"""

import numpy as np
import pandas as pd

from repository.gastos_repository import get_gastos_bradesco
from utils.df_tratamento import ajustes_data, pepi_gastos, pipe_parcelas


def _normalizar_valor(valor):
    """Normaliza um valor escalar para um tipo serializável em JSON."""
    if isinstance(valor, pd.Timestamp):
        return valor.date().isoformat()
    # NaN, NaT e <NA> viram None (pd.isna é seguro para os escalares desta tabela)
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(valor, np.integer):
        return int(valor)
    if isinstance(valor, np.floating):
        return float(valor)
    return valor


def _para_registros_json(df: pd.DataFrame) -> list[dict]:
    """Converte o DataFrame em registros serializáveis (NaN/NaT → None)."""
    df = df.copy()
    # colunas categóricas → object para não perder NaN na serialização
    for coluna in df.select_dtypes(include="category").columns:
        df[coluna] = df[coluna].astype(object)

    registros = df.to_dict(orient="records")
    return [
        {chave: _normalizar_valor(valor) for chave, valor in registro.items()}
        for registro in registros
    ]


async def listar_gastos_tratados() -> list[dict]:
    """Lê os gastos do banco, aplica o pipeline de tratamento e devolve registros."""
    df = await get_gastos_bradesco()

    if df.empty:
        return []

    df_tratado = (
        df
        .pipe(pepi_gastos)
        .pipe(ajustes_data)
        .pipe(pipe_parcelas)
    )

    return _para_registros_json(df_tratado)
