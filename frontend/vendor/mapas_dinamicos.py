"""Mapas dinâmicos de estados e Brasil com dados via API do IBGE."""

import functools
import logging
import requests
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts, Map, JsCode

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _buscar_municipios_ibge():
    """Busca lista completa de municípios da API do IBGE."""
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Falha ao buscar municípios do IBGE: {e}")
        return []


@functools.lru_cache(maxsize=1)
def obter_mapping_municipios_estado():
    """
    Retorna dicionário mapeando nome oficial do município para UF e estado.

    Returns:
        dict: {nome_municipio: {"uf": "SP", "estado": "São Paulo"}}
    """
    municipios = _buscar_municipios_ibge()
    mapping = {}

    for m in municipios:
        nome_oficial = m["nome"]
        try:
            uf_dict = m.get("microrregiao", {}).get("mesorregiao", {}).get("UF", {})
            uf = uf_dict.get("sigla")
            estado_nome = uf_dict.get("nome")

            if uf and estado_nome:
                mapping[nome_oficial] = {"uf": uf, "estado": estado_nome}
        except (KeyError, AttributeError):
            continue

    return mapping


def obter_estados_unicos(mapa_municipios):
    """Retorna lista ordenada de (UF, nome_estado) únicos do mapping."""
    estados = {}
    for info in mapa_municipios.values():
        uf = info["uf"]
        if uf not in estados:
            estados[uf] = info["estado"]

    return sorted([(uf, nome) for uf, nome in estados.items()], key=lambda x: x[1])


def _obter_geojson_estado(uf):
    """Retorna URL do GeoJSON para um estado brasileiro."""
    codigo_estado = {
        "AC": "12", "AL": "27", "AP": "16", "AM": "13", "BA": "29", "CE": "23",
        "DF": "26", "ES": "32", "GO": "52", "MA": "11", "MT": "28", "MS": "50",
        "MG": "31", "PA": "15", "PB": "25", "PR": "41", "PE": "26", "PI": "22",
        "RJ": "33", "RN": "24", "RS": "43", "RO": "11", "RR": "14", "SC": "42",
        "SP": "35", "SE": "28", "TO": "27"
    }
    codigo = codigo_estado.get(uf, "35")
    return f"https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-{codigo}-mun.json"


def _formatter_tooltip_br():
    """Retorna formatter JavaScript para exibir valores em BRL."""
    return JsCode(
        """
        function (params) {
            if (params.data) {
                return params.name + '<br/>R$ ' +
                    params.value.toLocaleString('pt-BR', {minimumFractionDigits: 0, maximumFractionDigits: 0});
            }
            return params.name;
        }
    """
    ).js_code


def mapa_estado(dados=None, uf="SP", tamanho="800px"):
    """
    Renderiza mapa de um estado com gastos por município.

    Args:
        dados: list de dicts {"name": "Cidade", "value": 1000}
        uf: string código UF (ex: "SP", "RJ")
        tamanho: string altura do gráfico (ex: "400px")
    """
    if dados is None:
        dados = [
            {"name": "São Paulo", "value": 12000000},
            {"name": "Campinas", "value": 1200000},
        ]

    if not dados:
        st.info(f"Nenhum dado disponível para {uf}")
        return

    df_dados = pd.DataFrame(dados)
    _max = int(df_dados["value"].max()) if len(df_dados) > 0 else 1
    _min = int(df_dados["value"].min()) if len(df_dados) > 0 else 0

    # Carrega GeoJSON do estado
    url = _obter_geojson_estado(uf)
    try:
        geo_json = requests.get(url, timeout=10).json()
    except Exception as e:
        st.warning(f"Não foi possível carregar mapa para {uf}: {e}")
        return

    map_obj = Map(f"{uf}_Municipios", geo_json)

    options = {
        "tooltip": {
            "trigger": "item",
            "formatter": _formatter_tooltip_br(),
        },
        "visualMap": {
            "min": _min,
            "max": _max,
            "left": "left",
            "bottom": "10%",
            "text": ["Gasto alto", "Gasto baixo"],
            "calculable": True,
            "inRange": {
                "color": [
                    "#18990B",
                    "#65B581",
                    "#FF6E6B",
                    "#99251F",
                ]
            },
        },
        "series": [
            {
                "name": "Valor gasto",
                "type": "map",
                "map": f"{uf}_Municipios",
                "roam": True,
                "zoom": 1.2,
                "label": {
                    "show": False
                },
                "emphasis": {
                    "label": {
                        "show": True
                    }
                },
                "data": dados,
            }
        ],
    }

    st_echarts(options=options, map=map_obj, height=tamanho)


def mapa_brasil(dados=None, tamanho="700px"):
    """
    Renderiza mapa do Brasil com gastos por estado.

    Args:
        dados: list de dicts {"name": "São Paulo", "value": 1000}
        tamanho: string altura do gráfico
    """
    if dados is None:
        dados = [
            {"name": "São Paulo", "value": 46649132},
            {"name": "Minas Gerais", "value": 21411923},
        ]

    if not dados:
        st.info("Nenhum dado disponível para o Brasil")
        return

    df_dados = pd.DataFrame(dados)
    _max = int(df_dados["value"].max()) if len(df_dados) > 0 else 1
    _min = int(df_dados["value"].min()) if len(df_dados) > 0 else 0

    # GeoJSON do Brasil
    url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    try:
        geo_json = requests.get(url, timeout=10).json()
    except Exception as e:
        st.warning(f"Não foi possível carregar mapa do Brasil: {e}")
        return

    map_obj = Map("Brazil", geo_json)

    options = {
        "tooltip": {
            "trigger": "item",
            "formatter": _formatter_tooltip_br(),
        },
        "visualMap": {
            "min": _min,
            "max": _max,
            "left": "left",
            "top": "bottom",
            "text": ["Maior", "Menor"],
            "calculable": True,
            "inRange": {
                "color": [
                    "#18990B",
                    "#65B581",
                    "#FF6E6B",
                    "#99251F",
                ]
            },
        },
        "toolbox": {
            "show": True,
            "orient": "vertical",
            "left": "right",
            "top": "center",
            "feature": {
                "dataView": {"readOnly": False},
                "restore": {},
                "saveAsImage": {},
            },
        },
        "series": [
            {
                "name": "Valor gasto",
                "type": "map",
                "map": "Brazil",
                "roam": True,
                "emphasis": {
                    "label": {
                        "show": True
                    }
                },
                "data": dados,
            }
        ],
    }

    st_echarts(options=options, map=map_obj, height=tamanho)