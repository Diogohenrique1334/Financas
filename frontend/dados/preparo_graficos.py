"""Camada view-model: transforma o DataFrame de gastos nas estruturas
(listas/dicionários) que os componentes ECharts consomem.

Funções puras de pandas - sem dependência de Streamlit nem da API.
"""

import pandas as pd


def df_para_lista_dict(df_filtrado, categoria="categoria", somatorio="amount", controle="name"):
    """Agrega por `categoria` e devolve [{controle: nome, "value": soma}, ...]."""
    dados = (
        df_filtrado.groupby(categoria)[somatorio]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    return [{"value": y, controle: x} for x, y in dados.values]

def df_para_lista_percentual(df_filtrado, categoria="categoria", somatorio="amount", controle="name"):
    """Agrega por `categoria` e devolve [{controle: nome, "percent": percentual}, ...]."""
    dados = (
        df_filtrado.groupby(categoria)[somatorio]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    total = dados[somatorio].sum()
    return [{"value": round((y / total)*100, 2) , controle: x}for x, y in dados.values]

def df_para_lista(df_filtrado, categoria="categoria", somatorio="amount"):
    """Devolve lista [score, amount, product] com cabeçalho, ordenada por valor."""
    dados = (
        df_filtrado.groupby(categoria)[somatorio]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={categoria: "product", "sum": "amount", "count": "score"})
    )[["score", "amount", "product"]]

    mylist = dados.values.tolist()
    mylist.sort(key=lambda x: x[1])
    mylist.reverse()
    mylist.append(list(dados))
    mylist.reverse()
    return mylist


def serie_simples(df_filtrado, col_data, col_values):
    """Série temporal simples (Data, value) somando `col_values` por data."""
    serie_gastos = df_filtrado.pivot_table(
        index=col_data, values=col_values, aggfunc="sum"
    )
    return serie_gastos.reset_index().rename(columns={"date": "Data", "amount": "value"})


def serie_dia_semana(df, col_data, valores, colunas, agg):
    """Matriz de valores por categoria x dia da semana (versão simples)."""
    serie_gastos = df.pivot_table(
        index=colunas, values=valores, columns=df[col_data].dt.dayofweek, aggfunc=agg
    )
    eixo = [
        x
        for x in serie_gastos.columns.map(
            {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}
        )
    ]
    categorias = [x for x in serie_gastos.index]
    valores_series = serie_gastos.values.tolist()
    return valores_series, categorias, eixo


def serie_dia_semana_complexo(df, col_data, valores, colunas, agg):
    """Séries empilhadas (ECharts) por categoria x dia da semana."""

    def config_data(lista_valores, categorias):
        add_dic = []
        for x in range(len(lista_valores)):
            add_dic.append(
                {
                    "name": categorias[x],
                    "type": "bar",
                    "stack": "total",
                    "label": {"show": False},
                    "emphasis": {"focus": "series"},
                    "data": [int(l) for l in lista_valores[x]],
                }
            )
        return add_dic

    serie_gastos = df.pivot_table(
        index=colunas, values=valores, columns=df[col_data].dt.dayofweek, aggfunc=agg
    )
    eixo = [
        x
        for x in serie_gastos.columns.map(
            {6: "Domingo", 0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado"}
        )
    ]
    categorias = [x for x in serie_gastos.index]
    valores_series = serie_gastos.values.tolist()
    return config_data(valores_series, categorias), categorias, eixo


def serie_semana_mes_complexo(df, col_data, valores, colunas, agg):
    """Séries empilhadas (ECharts) por categoria x semana do mês."""

    def config_data(lista_valores, categorias):
        add_dic = []
        for x in range(len(lista_valores)):
            add_dic.append(
                {
                    "name": categorias[x],
                    "type": "bar",
                    "stack": "total",
                    "label": {"show": False},
                    "emphasis": {"focus": "series"},
                    "data": [int(l) for l in lista_valores[x]],
                }
            )
        return add_dic

    semanas_mes = ((df[col_data].dt.day - 1) // 7) + 1
    serie_gastos = df.pivot_table(
        index=colunas, values=valores, columns=semanas_mes, aggfunc=agg
    )
    eixo = [f"Semana {x}" for x in serie_gastos.columns]
    categorias = [x for x in serie_gastos.index]
    valores_series = serie_gastos.values.tolist()
    return config_data(valores_series, categorias), categorias, eixo


def dias_sem_gastos(df_filtrado):
    """Resumo mensal: dias do mês, dias com/sem gastos, soma e contagem."""
    dias_mes = (
        pd.DataFrame(
            {
                "mês": df_filtrado.date.dt.strftime("%Y%m"),
                "Dias do mês": df_filtrado.date.dt.daysinmonth,
            }
        )
        .drop_duplicates()
        .set_index("mês")
        .to_dict()["Dias do mês"]
    )

    dias_com_gastos = (
        df_filtrado.pivot_table(
            index=df_filtrado.date.dt.strftime("%Y%m"),
            values="date",
            aggfunc=lambda x: len(x.unique()),
        )
        .rename(columns={"date": "dias com gastos"})
        .reset_index()
    )

    dias_com_gastos["Dias do mês"] = dias_com_gastos.date.map(dias_mes)
    dias_com_gastos["dias_sem_gastar"] = (
        dias_com_gastos["Dias do mês"] - dias_com_gastos["dias com gastos"]
    )

    gastos_utilizacoes = df_filtrado.groupby(df_filtrado.date.dt.strftime("%Y%m"))[
        "amount"
    ].agg(["sum", "count"])

    return dias_com_gastos.merge(
        gastos_utilizacoes, left_on="date", right_index=True, how="left"
    )


def top_10_categorias(df_filtrado):
    """Estrutura de drilldown: top 15 descrições por categoria + dados principais."""
    categorias = [
        x
        for x in df_filtrado.groupby("categoria")["amount"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .categoria
    ]

    op = {}
    for a in categorias:
        t = (
            df_filtrado[df_filtrado.categoria == a]
            .pivot_table(index="descricao", values="amount", aggfunc="sum")
            .sort_values(by="amount", ascending=False)
            .head(15)
            .reset_index()
        )
        op[a] = t.values.tolist()

    return op, categorias, df_para_lista_dict(df_filtrado, controle="groupId")


def get_delta(curr, prev, is_pct=False):
    """Variação percentual formatada (com sinal) entre dois valores."""
    if prev is None or prev == 0:
        return None
    if is_pct:
        return f"{curr - prev:+.1f}%"
    return f"{(curr - prev) / prev * 100:+.1f}%"


def dados_grafico_cachoeira(df_filtrado):
    """Dados para gráfico cachoeira: gastos acumulados mês a mês."""
    gastos_mes = df_filtrado.groupby(df_filtrado["date"].dt.strftime("%Y%m"))["amount"].sum()
    aumento = ["-" if x < 0 else int(x) for x in gastos_mes.diff().fillna(gastos_mes[0])]
    queda = ["-" if x < 0 else int(x) for x in (gastos_mes.diff() * -1).fillna(-1)]
    valores = [int(x) for x in gastos_mes.values]
    categorias = [x for x in gastos_mes.index]
    return categorias, valores, aumento, queda


def dados_grafico_barras(df, agregador, valores, _agg="sum", ordenacao=True):
    """Categorias e valores agregados para gráfico de barras simples."""
    t = df.pivot_table(index=agregador, values=valores, aggfunc=_agg)
    if ordenacao:
        t = t.sort_values(by=valores, ascending=False)
    categorias = [x for x in t.index]
    _valores = [x for x in t[valores]]
    return categorias, _valores
