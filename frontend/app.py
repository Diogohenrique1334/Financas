import streamlit as st

from api.client import get_gastos
from componentes.graficos import (
    barras_drilldown,
    barras_empilhadas_laterais,
    barras_laterais_sum_qtd,
    barras_simples,
    grafico_calendario,
    grafico_rosca,
)
from dados.preparo_graficos import (
    dados_grafico_barras,
    df_para_lista,
    df_para_lista_dict,
    dias_sem_gastos,
    get_delta,
    serie_dia_semana_complexo,
    serie_semana_mes_complexo,
    serie_simples,
    top_10_categorias,
    df_para_lista_percentual,
)
from mapas import (
    extrair_estados_com_gastos,
    mapa_brasil,
    mapa_estado,
    obter_mapping_municipios_estado,
)

# ---------------------------------- Dados -----------------------------------

df_limpo = get_gastos()

# --------------------------------- Layout -----------------------------------

st.set_page_config(layout="wide", page_title="Análise cartão de crédito bradesco")
st.success("Painel Financeiro de Diogo Oliveira")

st.sidebar.title("Painel de filtros")
st.sidebar.markdown("---")

# ------------------------------- Filtros ------------------------------------

month_filtros = st.sidebar.multiselect(
    "Selecione os meses de análise",
    df_limpo["date"].dt.strftime("%Y%m").sort_values().unique(),
)
categoria_filtro = st.sidebar.multiselect("Selecione as categorias do gasto", df_limpo.categoria.unique())
descricao_filtro = st.sidebar.multiselect("Selecione a descrição da fatura", df_limpo.descricao.unique())
cidade_filtro = st.sidebar.multiselect("Selecione a cidade do gasto", df_limpo.cidade.unique())

df_filtrado = df_limpo
if month_filtros:
    df_filtrado = df_filtrado[df_filtrado.date.dt.strftime("%Y%m").isin(month_filtros)]
if categoria_filtro:
    df_filtrado = df_filtrado[df_filtrado.categoria.isin(categoria_filtro)]
if descricao_filtro:
    df_filtrado = df_filtrado[df_filtrado.descricao.isin(descricao_filtro)]
if cidade_filtro:
    df_filtrado = df_filtrado[df_filtrado.cidade.isin(cidade_filtro)]

# --------------------------------- KPIs -------------------------------------

Dias_sem_gastos = dias_sem_gastos(df_filtrado)
previsto_kpi = df_filtrado.amount.sum()
avg_line = Dias_sem_gastos["sum"] / Dias_sem_gastos["count"]

col1, col2, col3, col4 = st.columns(4)

with col1:
    val = Dias_sem_gastos["sum"].sum() or 0
    delta = get_delta(Dias_sem_gastos.iloc[-1]["sum"], Dias_sem_gastos["sum"].mean()) if previsto_kpi is not None else None
    st.metric(
        "Total gasto",
        f"${val:,.0f}",
        delta=delta,
        border=True,
        delta_color="inverse",
        chart_data=Dias_sem_gastos["sum"].tolist(),
        chart_type="area",
    )

with col2:
    val = Dias_sem_gastos["count"].sum() or 0
    delta = get_delta(Dias_sem_gastos.iloc[-1]["count"], Dias_sem_gastos["count"].mean()) if previsto_kpi is not None else None
    st.metric(
        "Total de utilizações do cartão",
        f"{val:,}",
        delta=delta,
        delta_color="inverse",
        border=True,
        chart_data=Dias_sem_gastos["count"].tolist(),
        chart_type="bar",
    )

with col3:
    val = Dias_sem_gastos.dias_sem_gastar.mean() or 0
    delta = (
        get_delta(Dias_sem_gastos.iloc[-1]["dias_sem_gastar"], Dias_sem_gastos.dias_sem_gastar.mean())
        if previsto_kpi is not None
        else None
    )
    st.metric(
        "Media dias sem usar o cartão",
        f"{val:,.1f}",
        delta=delta,
        border=True,
        chart_data=Dias_sem_gastos.dias_sem_gastar.tolist(),
        chart_type="line",
    )

with col4:
    val = avg_line.mean() or 0
    delta = get_delta(avg_line.iloc[-1], val) if previsto_kpi is not None else None
    st.metric(
        "Avg. valor de Utilização",
        f"${val:,.0f}",
        delta=delta,
        border=True,
        delta_color="inverse",
        chart_data=avg_line.values.tolist(),
        chart_type="line",
    )

# ----------------------------- Gráficos (bloco 1) ---------------------------

with st.container(border=True, height=550):

    pcol1, pcol2 = st.columns([5, 5])

    with pcol1.container(border=True, height=520):
        st.subheader("Gastos por categoria", divider=True)
        grafico_rosca(df_para_lista_percentual(df_filtrado), tamanho="380px")

    with pcol2.container(border=True, height=520):
        st.subheader("Ranking de gastos e utilizações", divider=True)
        barras_laterais_sum_qtd(df_para_lista(df_filtrado), tamanho="380px")

    col1, col2 = st.columns([5, 5])

    with col1.container(border=True, height=520):
        st.subheader("Gastos por dia da semana", divider=True)
        barras_empilhadas_laterais(
            *serie_dia_semana_complexo(df_filtrado, "date", "amount", "categoria", "sum"), tamanho="400px"
        )

    with col2.container(border=True, height=520):
        st.subheader("Gastos por semana do mês", divider=True)
        barras_empilhadas_laterais(
            *serie_semana_mes_complexo(df_filtrado, "date", "amount", "categoria", "sum"), tamanho="400px"
        )

    with st.container(border=True, height=520):
        st.subheader("Top 10 gastos por categoria", divider=True)
        barras_drilldown(*top_10_categorias(df_limpo), tamanho="300px")

# ----------------------------- Mapas (bloco 2) ------------------------------

with st.container(border=True, height=500):

    with st.container(border=True, height=470):

        col_titulo, col_select = st.columns([3, 1])

        with col_titulo:
            st.subheader("Gastos por cidade", divider=True)

        with col_select:
            mapa_municipios = obter_mapping_municipios_estado()
            estados_com_gastos = extrair_estados_com_gastos(df_filtrado)

            opcoes = ["Brasil"] + [f"{uf} - {nome}" for uf, nome in estados_com_gastos]
            opcao_selecionada = st.selectbox(
                "Estado", opcoes, label_visibility="collapsed", key="select_estado_mapa"
            )

        if opcao_selecionada == "Brasil":
            dados_estados_gasto = []
            for uf, nome_estado in estados_com_gastos:
                cidades_uf = [c for c, info in mapa_municipios.items() if info["uf"] == uf]
                total = df_filtrado[df_filtrado["cidade"].isin(cidades_uf)]["amount"].sum()
                if total > 0:
                    dados_estados_gasto.append({"name": nome_estado, "value": int(total)})

            if dados_estados_gasto:
                mapa_brasil(dados_estados_gasto, tamanho="400px")
            else:
                st.info("Nenhum dado disponível para o Brasil com os filtros aplicados.")
        else:
            uf = opcao_selecionada.split(" - ")[0]
            cidades_do_estado = [c for c, info in mapa_municipios.items() if info["uf"] == uf]
            df_estado = df_filtrado[df_filtrado["cidade"].isin(cidades_do_estado)]

            if len(df_estado) > 0:
                dados_mapa = df_para_lista_dict(df_estado, "cidade")
                mapa_estado(dados_mapa, uf=uf, tamanho="400px")
            else:
                st.info(f"Nenhum dado disponível para {opcao_selecionada} com os filtros aplicados.")

    with st.container(border=True, height=430):
        st.subheader("Gastos por cidade", divider=True)
        barras_simples(*dados_grafico_barras(df_filtrado, "cidade", "amount"))

# ----------------------------- Calendário (bloco 3) -------------------------

with st.container(border=True, height=450):

    with st.container(border=True, height=400):
        st.subheader("Gastos por dia do ano", divider=True)
        grafico_calendario(serie_simples(df_filtrado, "date", "amount"), ano_2=2025, ano_3=2026)

    with st.container(border=True, height=430):
        st.subheader("Gastos por mês", divider=True)
        barras_simples(
            *dados_grafico_barras(df_filtrado, df_filtrado.date.dt.strftime("%Y%m"), "amount", ordenacao=False)
        )
