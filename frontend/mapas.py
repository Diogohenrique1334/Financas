"""Ponte para o módulo de mapas dinâmicos da biblioteca Baltazar.

Importa o módulo via ``importlib`` para evitar conflito de nomes de path e
expõe as funções de mapa + um helper para descobrir os estados com gastos.
"""

import importlib.util
from pathlib import Path

import streamlit as st

from config import settings

_BALTAZAR_MAPAS = Path(settings.BALTAZAR_MAPAS_PATH)

_spec = importlib.util.spec_from_file_location("mapas_dinamicos", _BALTAZAR_MAPAS)
_mapas_dinamicos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mapas_dinamicos)

mapa_estado = _mapas_dinamicos.mapa_estado
mapa_brasil = _mapas_dinamicos.mapa_brasil
obter_mapping_municipios_estado = _mapas_dinamicos.obter_mapping_municipios_estado
obter_estados_unicos = _mapas_dinamicos.obter_estados_unicos


@st.cache_data
def extrair_estados_com_gastos(df):
    """Extrai os estados (UF, nome) únicos que têm gastos registrados no DataFrame."""
    mapa = obter_mapping_municipios_estado()
    cidades = df["cidade"].dropna().unique()
    estados = set()

    for cidade in cidades:
        if cidade in mapa:
            estados.add((mapa[cidade]["uf"], mapa[cidade]["estado"]))

    return sorted(list(estados), key=lambda x: x[1])
