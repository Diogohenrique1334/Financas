import datetime as dt
import matplotlib.pyplot as plt
from streamlit_echarts import st_echarts
import plotly.express as px
import pandas as pd
import numpy as np
from streamlit_echarts import st_echarts,Map, JsCode
import json
import requests
import streamlit as st


def liquid_fill(valor):
    liquidfill_option = {
        "title": {
            "text": "Aderência total",
            "left": "center",
            "textStyle": {
                "fontSize": 20,
                "fontWeight": "bold",
                "color": "#ffffff"
            }
        },
        "series": [{
            "type": 'liquidFill',
            "data": [valor],
            "center": ['50%', '50%'],
            "radius": '50%',
            "waveAnimation": True,
            "outline": {
                "show": True,
                "borderDistance": 8,
                "itemStyle": {
                    "borderWidth": 4,
                    "borderColor": "#ffffff"
                }
            },
            "backgroundStyle": {
                "color": "#ffffff"
            },
            "label": {
                "normal": {
                    
                    "textStyle": {
                        "fontSize": 20,
                        "color": '#18990b'
                    }
                }
            },
            "color":['#18990b']
        }]
    }

    return liquidfill_option

def barras_laterais_sum_qtd(data, tamanho = "500px"):

    options1 = {
                "dataset": {
                    "source": data
                },
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
    return st_echarts(options=options1, height=tamanho)

def grafico_rosca(data, tamanho = "500px"):

    options = {
        "tooltip": {"trigger": "item"},
        "legend": {"top": "5%", "left": "center"},
        "series": [
            {
                "name": "Access From",
                "type": "pie",
                "radius": ["40%", "70%"],
                "avoidLabelOverlap": False,
                "padAngle": 5,
                "itemStyle": {"borderRadius": 10},
                "label": {"show": False, "position": "center"},
                "emphasis": {
                    "label": {"show": True, "fontSize": 40, "fontWeight": "bold"}
                },
                "labelLine": {"show": False},
                "data": data
                ,
            }
        ],
    }
    st_echarts(options=options, height=tamanho)

def meia_rosca(data,tamanho = "500px"):

    options = {
        "tooltip": {"trigger": "item"},
        "legend": {"top": "5%", "left": "center"},
        "series": [
            {
                "name": "Access From",
                "type": "pie",
                "radius": ["40%", "70%"],
                "center": ["50%", "70%"],
                "startAngle": 180,
                "endAngle": 360,
                "data": data,
            }
        ],
    }
    return st_echarts(options=options, height=tamanho)

def grefico_calendario(df,
#                        ano_1, 
                        ano_2,
                        ano_3):

    # Tipos corretos
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    df['value'] = pd.to_numeric(df['value'], errors='coerce')

    # Remove linhas inválidas e agrega por dia
    datas = (
        df.dropna(subset=['Data'])  # mantém linhas com Data válida (valor pode ser NaN e virar None)
        .pivot_table(index='Data', values='value', aggfunc='sum')
        .sort_index()
    )

    # --- 2) Helpers para converter para tipos nativos/serializáveis ---
    def _to_date_str(idx):
        # ECharts (calendário) gosta de "YYYY-MM-DD"
        return idx.strftime("%Y-%m-%d")

    def _to_native_val(x):
        # None para NaN/<NA>; int nativo para numéricos
        if pd.isna(x):
            return None  # ou 0, se preferir preencher vazio
        return int(x)

    def _build_year(y: int):
        out = []
        if datas.empty:
            return out
        # Evita iterrows; usamos index + values e filtramos pelo ano
        for idx, val in zip(datas.index, datas['value'].values):
            if isinstance(idx, pd.Timestamp) and not pd.isna(idx) and idx.year == y:
                out.append([_to_date_str(idx), _to_native_val(val)])
        return out

    #data_1 = _build_year(ano_1)
    data_2 = _build_year(ano_2)
    data_3 = _build_year(ano_3)

    # Max para o visualMap (float nativo; fallback quando NaN)
    if datas.empty:
        vmax_native = 1.0
    else:
        vmax = pd.to_numeric(datas['value'], errors='coerce').max()
        vmax_native = float(vmax) if pd.notna(vmax) else 1.0

    # --- 3) Opções do ECharts ---
    option1 = {
        "tooltip": {"position": "top"},
        "visualMap": {
            "min": 0,
            "max": vmax_native,
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            # Use o esquema de cores padrão do ECharts via inRange
            "inRange": {"color": ["#cac2c2", "#99251F"]},  # claro -> escuro
        },
        "calendar": [
            #{  # Calendário ano_1
            #    "range": str(ano_1),
            #    "cellSize": ["auto", 14],
            #    "top": "7%",
            #    "splitLine": {"lineStyle": {"color": "#000000"}},
            #    "itemStyle": {"color": "#ffffff"},
            #    "dayLabel": {"color": "#ffffff"},
            #    "monthLabel": {"color": "#ffffff"},
            #    "yearLabel": {"color": "#cac2c2"},
            #},
            {  # Calendário ano_2
                "range": str(ano_2),
                "cellSize": ["auto", 14],
                "top": "7%",
                "splitLine": {"lineStyle": {"color": "#000000"}},
                "itemStyle": {"color": "#ffffff"},
                "dayLabel": {"color": "#ffffff"},
                "monthLabel": {"color": "#ffffff"},
                "yearLabel": {"color": "#cac2c2"},
            },
            {  # Calendário ano_3
                "range": str(ano_3),
                "cellSize": ["auto", 14],
                "top": "50%",
                "splitLine": {"lineStyle": {"color": "#000000"}},
                "itemStyle": {"color": "#ffffff"},
                "dayLabel": {"color": "#ffffff"},
                "monthLabel": {"color": "#ffffff"},
                "yearLabel": {"color": "#cac2c2"},
            },
        ],
        "series": [
        #    {
        #        "type": "heatmap",
        #        "coordinateSystem": "calendar",
        #        "calendarIndex": 0,
        #        "data": data_1,
        #    },
            {
                "type": "heatmap",
                "coordinateSystem": "calendar",
                "calendarIndex": 0,
                "data": data_2,
            },
            {
                "type": "heatmap",
                "coordinateSystem": "calendar",
                "calendarIndex": 1,
                "data": data_3,
            },
        ],
    }

    # --- 4) Blindagem final contra tipos NumPy/Pandas no dicionário ---
    def to_native(obj):
        from datetime import date, datetime
        if isinstance(obj, (np.integer,)):  # np.int64 -> int
            return int(obj)
        if isinstance(obj, (np.floating,)):  # np.float64 -> float
            return float(obj)
        if isinstance(obj, (np.bool_,)):  # np.bool_ -> bool
            return bool(obj)
        if isinstance(obj, (pd.Timestamp, datetime)):  # datas -> string ISO
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

    return st_echarts(options=to_native(option1))

def mapa_brasil(dados_estados = None):


    if dados_estados is None:
        dados_estados = [
            {"name": "São Paulo", "value": 46649132},
            {"name": "Minas Gerais", "value": 21411923},
            {"name": "Rio de Janeiro", "value": 17366189},
            {"name": "Bahia", "value": 14985284},
            {"name": "Paraná", "value": 11835379},
            {"name": "Rio Grande do Sul", "value": 11466630},
            {"name": "Pernambuco", "value": 9674793},
            {"name": "Ceará", "value": 9240580},
            {"name": "Pará", "value": 8777124},
            {"name": "Santa Catarina", "value": 7610361},
            {"name": "Goiás", "value": 7206589},
            {"name": "Maranhão", "value": 6775805},
            {"name": "Amazonas", "value": 4269995},
            {"name": "Espírito Santo", "value": 4108508},
            {"name": "Paraíba", "value": 4059905},
            {"name": "Rio Grande do Norte", "value": 3560903},
            {"name": "Mato Grosso", "value": 3658813},
            {"name": "Alagoas", "value": 3365351},
            {"name": "Piauí", "value": 3281480},
            {"name": "Distrito Federal", "value": 3094325},
            {"name": "Mato Grosso do Sul", "value": 2839188},
            {"name": "Sergipe", "value": 2338474},
            {"name": "Rondônia", "value": 1815278},
            {"name": "Tocantins", "value": 1607363},
            {"name": "Acre", "value": 906876},
            {"name": "Amapá", "value": 877613},
            {"name": "Roraima", "value": 652713},
        ]

    formatter = JsCode(
        """
        function (params) {
            return params.seriesName + '<br/>' +
                params.name + ': ' +
                params.value.toLocaleString('pt-BR');
        }
    """
    ).js_code

    # GeoJSON do Brasil
    url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    geo_json = requests.get(url).json()

    # Cria o mapa
    map = Map(
        "Brazil",
        geo_json,
    )

    options = {
        "title": {
            "text": "População dos Estados Brasileiros",
            "subtext": "Dados exemplo",
            "left": "right",
        },
        "tooltip": {
            "trigger": "item",
            "formatter": formatter,
        },
        "visualMap": {
            "min": 500000,
            "max": 50000000,
            "left": "left",
            "top": "bottom",
            "text": ["Maior", "Menor"],
            "calculable": True,
            "inRange": {
                "color": [
                    "#E0F3F8",
                    "#ABD9E9",
                    "#74ADD1",
                    "#4575B4",
                    "#313695",
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
                "name": "População",
                "type": "map",
                "map": "Brazil",
                "roam": True,
                "emphasis": {
                    "label": {
                        "show": True
                    }
                },
                "data": dados_estados,
            }
        ],
    }

    st_echarts(options=options, map=map, height="700px")


def barras_empilhadas(raw_data = None, series_names = None, eixo_x = None, tamanho = "500px"):


    if raw_data is None:
        raw_data = [
            [100, 302, 301, 334, 390, 330, 320],
            [320, 132, 101, 134, 90, 230, 210],
            [220, 182, 191, 234, 290, 330, 310],
            [150, 212, 201, 154, 190, 330, 410],
            [820, 832, 901, 934, 1290, 1330, 1320],
        ]

    if series_names is None:
        series_names = ["Direct", "Mail Ad", "Affiliate Ad", "Video Ad", "Search Engine"]

    if eixo_x is None:
        
        eixo_x = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    total_data = []
    for i in range(len(raw_data[0])):
        sum_val = 0
        for j in range(len(raw_data)):
            sum_val += raw_data[j][i]
        total_data.append(sum_val)

    
    series = []
    for sid, name in enumerate(series_names):
        series.append(
            {
                "name": name,
                "type": "bar",
                "stack": "total",
                "barWidth": "60%",
                "label": {
                    "show": True,
                    "formatter": JsCode(
                        "function(params) { return Math.round(params.value * 1000) / 10 + '%'; }"
                    ).js_code,
                },
                "data": [
                    (0 if total_data[did] <= 0 else d / total_data[did])
                    for did, d in enumerate(raw_data[sid])
                ],
            }
        )

    options = {
        "legend": {"selectedMode": False},
        "yAxis": {"type": "value"},
        "xAxis": {
            "type": "category",
            "data": eixo_x,
        },
        "series": series,
    }

    return st_echarts(options=options, height=tamanho)

def barras_empilhadas_laterais(raw_data = None, series_names = None, eixo = None, tamanho = "500px"):

    options = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {
            "data": series_names
        },
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "value"},
        "yAxis": {
            "type": "category",
            "data": eixo,
        },
        "series": raw_data,
    }

    return st_echarts(options=options, height=tamanho)

def barras_drilldown(drilldown_data,categorias,dados_principais,tamanho ="500px" ):

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
            "axisLabel": {
                "interval": 0,       # mostra todos os labels
                "rotate": 30,        # rotaciona para não sobrepor
                "overflow": "break", # quebra linha se for muito longo
                },
            "yAxis": {},
            "tooltip": {
                "trigger": "axis",   # mostra tooltip ao passar no eixo
                "axisPointer": {"type": "shadow"},
                },
            "animationDurationUpdate": 500,
            "series": {
                "type": "bar",
                "id": "sales",
                "dataGroupId": group,
                "data": [item[1] for item in sub_data],
                #"data": [{"value": item[1], "groupId": item[0]} for item in sub_data],
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
#        replace_merge="series",
        key="render_bar_drilldown",
    )

    if result and result in drilldown_data and st.session_state.bar_drilldown_group != result:
        st.session_state.bar_drilldown_group = result
        st.rerun()

def grafico_cachoeira(categorias, valores, aumento, queda, tamanho ="500px"):

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
        "xAxis": {
            "type": "category",
            "data": categorias,
        },
        "yAxis": {"type": "value"},
        "series": [
            {
                "name": "Placeholder",
                "type": "bar",
                "stack": "Total",
                "silent": True,
                "itemStyle": {
                    "borderColor": "transparent",
                    "color": "transparent",
                },
                "emphasis": {
                    "itemStyle": {
                        "borderColor": "transparent",
                        "color": "transparent",
                    }
                },
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

    wordcloud_option = {"series": [{"type": "wordCloud", "data": data}]}
    
    return st_echarts(wordcloud_option)

def barras_simples(categorias,valores, tamanho = "300px"):

    options = {
        "title": {"text": "Análise de Gastos"},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        #"legend": {"data": ["Gastos"]},
        "toolbox": {"feature": {"saveAsImage": {}, "restore": {}, "dataView": {}}},
        "xAxis": {"type": "category", "data": categorias},
        "yAxis": {"type": "value"},
        "series": [{
            "name": "Gastos",
            "data": valores,
            "type": "bar",
            #"label": {"show": True, "position": "top"},
            "markLine": {"data": [{"type": "average", "name": "Média"}]}
        }],
    }
    return st_echarts(options=options, height=tamanho)
