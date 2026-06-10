"""Componentes de visualização (ECharts via streamlit-echarts).

Cada função recebe dados já no formato esperado (ver `dados.preparo_graficos`)
e renderiza um gráfico no Streamlit.
"""

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_echarts import JsCode, st_echarts


def barras_laterais_sum_qtd(data, tamanho="500px"):
    """Barras horizontais com visualMap por quantidade de utilizações."""
    options = {
        "dataset": {"source": data},
        "grid": {"containLabel": True},
        "xAxis": {"name": "amount"},
        "yAxis": {"type": "category"},
        "visualMap": {
            "orient": "horizontal",
            "left": "center",
            "min": 10,
            "max": 100,
            "text": ["Muitas utilizações", "Poucas utilizações"],
            "dimension": 0,
            "inRange": {"color": ["#65B581", "#FFCE34", "#FD665F"]},
        },
        "series": [{"type": "bar", "encode": {"x": "amount", "y": "product"}}],
    }
    return st_echarts(options=options, height=tamanho)

def grafico_rosca(data, tamanho="500px"):
    """Gráfico de rosca (donut)."""
    options = {
        "tooltip": {"trigger": "item"},
        "legend": {
    #        "data": series_names,
            "textStyle": {
                "color": "#ffffff",  # cor da fonte da legenda
                "fontSize": 11,      # opcional: tamanho da fonte
    #                "fontWeight": "bold" # opcional: negrito
            }},
        "series": [
            {
                "name": "Access From",
                "type": "pie",
                "radius": ["40%", "70%"],
                "avoidLabelOverlap": False,
                "padAngle": 5,
                "itemStyle": {"borderRadius": 10},
                "label": {"show": False, "position": "center"},
                "emphasis": {"label": {"show": True, "fontSize": 40, "fontWeight": "bold"}},
                "labelLine": {"show": False},
                "data": data,
            }
        ],
    }
    st_echarts(options=options, height=tamanho)

def grafico_calendario(df, ano_2, ano_3):
    """Heatmap de calendário para dois anos (gastos por dia)."""
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    datas = (
        df.dropna(subset=["Data"])
        .pivot_table(index="Data", values="value", aggfunc="sum")
        .sort_index()
    )

    def _to_date_str(idx):
        return idx.strftime("%Y-%m-%d")

    def _to_native_val(x):
        if pd.isna(x):
            return None
        return int(x)

    def _build_year(y: int):
        out = []
        if datas.empty:
            return out
        for idx, val in zip(datas.index, datas["value"].values):
            if isinstance(idx, pd.Timestamp) and not pd.isna(idx) and idx.year == y:
                out.append([_to_date_str(idx), _to_native_val(val)])
        return out

    data_2 = _build_year(ano_2)
    data_3 = _build_year(ano_3)

    if datas.empty:
        vmax_native = 1.0
    else:
        vmax = pd.to_numeric(datas["value"], errors="coerce").max()
        vmax_native = float(vmax) if pd.notna(vmax) else 1.0

    def _calendario(range_ano, top):
        return {
            "range": str(range_ano),
            "cellSize": ["auto", 14],
            "top": top,
            "splitLine": {"lineStyle": {"color": "#000000"}},
            "itemStyle": {"color": "#ffffff"},
            "dayLabel": {"color": "#ffffff"},
            "monthLabel": {"color": "#ffffff"},
            "yearLabel": {"color": "#cac2c2"},
        }

    option = {
        "tooltip": {"position": "top"},
        "visualMap": {
            "min": 0,
            "max": vmax_native,
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "inRange": {"color": ["#cac2c2", "#99251F"]},
        },
        "calendar": [_calendario(ano_2, "7%"), _calendario(ano_3, "50%")],
        "series": [
            {"type": "heatmap", "coordinateSystem": "calendar", "calendarIndex": 0, "data": data_2},
            {"type": "heatmap", "coordinateSystem": "calendar", "calendarIndex": 1, "data": data_3},
        ],
    }

    def to_native(obj):
        from datetime import datetime

        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if obj is pd.NaT:
            return None
        if isinstance(obj, np.ndarray):
            return [to_native(x) for x in obj.tolist()]
        if isinstance(obj, (list, tuple, set)):
            return [to_native(x) for x in obj]
        if isinstance(obj, dict):
            return {str(k): to_native(v) for k, v in obj.items()}
        return obj

    return st_echarts(options=to_native(option))

def barras_empilhadas_laterais(raw_data=None, series_names=None, eixo=None, tamanho="500px"):
    """Barras horizontais empilhadas (séries já no formato ECharts)."""
    options = {
        "tooltip": {
            "trigger": "axis", 
            "axisPointer": {"type": "shadow"}
            },
        "legend": {
            "data": series_names,
            "textStyle": {
                "color": "#ffffff",  # cor da fonte da legenda
                "fontSize": 11,      # opcional: tamanho da fonte
    #                "fontWeight": "bold" # opcional: negrito
            }},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "category", "data": eixo},
        "series": raw_data,
    }
    return st_echarts(options=options, height=tamanho)

def barras_drilldown(drilldown_data, categorias, dados_principais, tamanho="500px"):
    """Barras com drilldown por clique (usa session_state p/ navegação)."""
    if "bar_drilldown_group" not in st.session_state:
        st.session_state.bar_drilldown_group = None

    group = st.session_state.bar_drilldown_group

    if group is None:
        options = {
            "xAxis": {"data": categorias},
            "yAxis": {},
            "animationDurationUpdate": 500,
            "series": {
                "type": "bar",
                "id": "sales",
                "data": dados_principais,
                "universalTransition": {"enabled": True, "divideShape": "clone"},
            },
        }
    else:
        sub_data = drilldown_data[group]
        options = {
            "xAxis": {"data": [item[0] for item in sub_data]},
            "axisLabel": {"interval": 0, "rotate": 30, "overflow": "break"},
            "yAxis": {},
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "animationDurationUpdate": 500,
            "series": {
                "type": "bar",
                "id": "sales",
                "dataGroupId": group,
                "data": [item[1] for item in sub_data],
                "universalTransition": {"enabled": True, "divideShape": "clone"},
            },
        }

    events = {
        "click": "function(params) { return params.data && params.data.groupId ? params.data.groupId : null }",
    }

    if group is not None:
        if st.button("Back", key="bar_drilldown_back"):
            st.session_state.bar_drilldown_group = None
            st.rerun()

    result = st_echarts(
        options=options,
        events=events,
        height=tamanho,
        key="render_bar_drilldown",
    )

    if result and result in drilldown_data and st.session_state.bar_drilldown_group != result:
        st.session_state.bar_drilldown_group = result
        st.rerun()

def grafico_cachoeira(categorias, valores, aumento, queda, tamanho="500px"):
    """Gráfico cachoeira (waterfall) de gastos acumulados por mês."""
    options = {
        "title": {"text": "Gastos acumulados por mês"},
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "formatter": JsCode(
                """
                function (params) {
                let tar;
                if (params[1] && params[1].value !== '-') {
                    tar = params[1];
                } else {
                    tar = params[2];
                }
                return tar && tar.name + '<br/>' + tar.seriesName + ' : ' + tar.value;
                }
                """
            ).js_code,
        },
        "legend": {"data": ["queda", "Aumento"]},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "category", "data": categorias},
        "yAxis": {"type": "value"},
        "series": [
            {
                "name": "Placeholder",
                "type": "bar",
                "stack": "Total",
                "silent": True,
                "itemStyle": {"borderColor": "transparent", "color": "transparent"},
                "emphasis": {"itemStyle": {"borderColor": "transparent", "color": "transparent"}},
                "data": valores,
            },
            {
                "name": "Aumento",
                "type": "bar",
                "stack": "Total",
                "label": {"show": True, "position": "top"},
                "data": aumento,
            },
            {
                "name": "queda",
                "type": "bar",
                "stack": "Total",
                "label": {"show": True, "position": "bottom"},
                "data": queda,
            },
        ],
    }
    return st_echarts(options=options, height=tamanho)

def mapa_palavras(data):
    """Nuvem de palavras (wordCloud)."""
    wordcloud_option = {"series": [{"type": "wordCloud", "data": data}]}
    return st_echarts(wordcloud_option)

def barras_simples(categorias, valores, tamanho="300px"):
    """Barras verticais simples com linha de média."""
    options = {
        "title": {"text": "Análise de Gastos"},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "toolbox": {"feature": {"saveAsImage": {}, "restore": {}, "dataView": {}}},
        "xAxis": {"type": "category", "data": categorias},
        "yAxis": {"type": "value"},
        "series": [
            {
                "name": "Gastos",
                "data": valores,
                "type": "bar",
                "markLine": {"data": [{"type": "average", "name": "Média"}]},
            }
        ],
    }
    return st_echarts(options=options, height=tamanho)
