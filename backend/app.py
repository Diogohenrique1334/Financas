import streamlit as st
import pandas as pd
import asyncio
from repository.gastos_repository import get_gastos_bradesco
from utils.df_tratamento import ajustes_data, pepi_gastos, pipe_parcelas
from graficos import barras_laterais_sum_qtd, grafico_rosca,mapa_sp, grefico_calendario,barras_drilldown,barras_empilhadas_laterais,grafico_cachoeira, mapa_palavras,barras_simples


# entrada dos dados
@st.cache_data
def carregar_dados():
    return asyncio.run(get_gastos_bradesco())

df = carregar_dados()

@st.cache_data
def preparar_df():
    df = carregar_dados()
    df_filtrado = (
        df
        .pipe(pepi_gastos)
        .pipe(ajustes_data)
        .pipe(pipe_parcelas)
    )
    return df_filtrado

df_limpo = preparar_df()

def df_para_lista_dict(df_filtrado,categoria = 'categoria', somatorio = 'amount', controle = "name"):

    dados = df_filtrado.groupby(categoria)[somatorio].sum().sort_values(ascending = False).reset_index()

    return [{"value": y, controle: x} for x,y in dados.values ]

def df_para_lista(df_filtrado, categoria = 'categoria', somatorio = 'amount'):

    dados = df_filtrado.groupby(categoria)[somatorio].agg(['sum','count']).reset_index().rename(columns = {categoria:'product','sum':'amount','count':'score'})[['score','amount','product']]

    mylist = dados.values.tolist()

    mylist.sort(key=lambda x: x[1])

    mylist.reverse()

    mylist.append(list(dados))

    mylist.reverse()

    return mylist

def Serie_simples(df_filtrado, col_data, col_values):

    serie_gastos = df_filtrado.pivot_table(index=col_data,
                        values = col_values,
                        aggfunc = 'sum')
    
    return serie_gastos.reset_index().rename(columns = {"date":'Data', 'amount':'value'})

def serei_dia_semana(df,col_data,valores,colunas,agg):

    serie_gastos = df.pivot_table(index=colunas,
                        values = valores,
                        columns = df[col_data].dt.dayofweek,
                        aggfunc = agg)
    
    eixo = [ x for x in serie_gastos.columns.map({0:'Domingo',1:'Segunda',2:'Terça',3:'Quarta',4:'Quinta',5:'Sexta',6:'Sábado',7:'Domingo'})]

    categorias = [ x for x in serie_gastos.index]

    valores_series = serie_gastos.values.tolist()
    
    return valores_series, categorias, eixo

def serei_dia_semana_complexo(df,col_data,valores,colunas,agg):

    def config_data(lista_valores,categorias):

        add_dic = list()
        for x in range(len(lista_valores)):
            
            add_dic.append( {
            "name": categorias[x],
            "type": "bar",
            "stack": "total",
            "label": {"show": True},
            "emphasis": {"focus": "series"},
            "data": [ int(l) for l in lista_valores[x] ],
            })

        return add_dic

    serie_gastos = df.pivot_table(index=colunas,
                        values = valores,
                        columns = df[col_data].dt.dayofweek,
                        aggfunc = agg)
    
    eixo = [ x for x in serie_gastos.columns.map({6:'Domingo',0:'Segunda',1:'Terça',2:'Quarta',3:'Quinta',4:'Sexta',5:'Sábado'})]
    #eixo = [ x for x in serie_gastos.columns]

    categorias = [ x for x in serie_gastos.index]

    valores_series = serie_gastos.values.tolist()

    return config_data(valores_series,categorias), categorias, eixo

def serei_semana_mes_complexo_2(df, col_data, valores, colunas, agg):

    def config_data(lista_valores, categorias):
        add_dic = []
        for x in range(len(lista_valores)):
            add_dic.append({
                "name": categorias[x],
                "type": "bar",
                "stack": "total",
                "label": {"show": True},
                "emphasis": {"focus": "series"},
                "data": [int(l) for l in lista_valores[x]],
            })
        return add_dic

    # Calcula a semana do mês (1ª semana, 2ª semana, etc.)
    semanas_mes = ((df[col_data].dt.day - 1) // 7) + 1

    serie_gastos = df.pivot_table(
        index=colunas,
        values=valores,
        columns=semanas_mes,
        aggfunc=agg
    )

    # Nomeando os eixos como "Semana 1", "Semana 2", etc.
    eixo = [f"Semana {x}" for x in serie_gastos.columns]

    categorias = [x for x in serie_gastos.index]
    valores_series = serie_gastos.values.tolist()

    return config_data(valores_series, categorias), categorias, eixo

def dias_sem_gastos(df_filtrado):

    dias_mês =  pd.DataFrame({"mês":df_filtrado.date.dt.strftime('%Y%m'),"Dias do mês":df_filtrado.date.dt.daysinmonth}).drop_duplicates().set_index('mês').to_dict()['Dias do mês']

    dias_com_gastos = df_filtrado.pivot_table(index = df_filtrado.date.dt.strftime('%Y%m'),
                        values = 'date',
                        aggfunc = lambda x: len(x.unique())).rename(columns = {"date":"dias com gastos"}).reset_index()
    
    dias_com_gastos['Dias do mês'] = dias_com_gastos.date.map(dias_mês)

    dias_com_gastos['dias_sem_gastar'] = dias_com_gastos['Dias do mês'] - dias_com_gastos['dias com gastos']

    gastos_utilizacoes = df_filtrado.groupby(df_filtrado.date.dt.strftime('%Y%m'))['amount'].agg(['sum','count'])

    return dias_com_gastos.merge(gastos_utilizacoes, left_on = 'date', right_index = True, how = 'left')

def top_10_categorias(df_filtrado):

    categorias = [ x for x in df_filtrado.groupby('categoria')['amount'].sum().sort_values(ascending = False).reset_index().categoria ] 

    op = dict()

    for a in categorias:

        t = df_filtrado[df_filtrado.categoria == a].pivot_table(index = 'descricao',
                                                                values = 'amount',
                                                                aggfunc = 'sum').sort_values(by = 'amount', ascending = False).head(15).reset_index()
        
        t = t.values.tolist()

        op.update({a:t})

    return op,categorias,df_para_lista_dict(df_filtrado,controle='groupId')

def get_delta(curr, prev, is_pct=False):
    if prev is None or prev == 0:
        return None
    if is_pct:
        return f"{curr - prev:+.1f}%"
    return f"{(curr - prev) / prev * 100:+.1f}%"

def dados_grafico_cachoeira(df_filtrado):

    gastos_mes = df_filtrado.groupby(df_filtrado["date"].dt.strftime('%Y%m'))['amount'].sum()

    aumento = [ '-' if x < 0 else int(x) for x in gastos_mes.diff().fillna(gastos_mes[0]) ]

    queda = [ '-' if x < 0 else int(x) for x in (gastos_mes.diff() * -1).fillna(-1) ]

    valores = [int(x) for x in gastos_mes.values ]

    categorias = [ x for x in gastos_mes.index ]

    return categorias, valores, aumento, queda

def dados_grafico_barras(df, agregardor,valores, _agg = 'sum', ordenacao = True):

    t = df.pivot_table(index = agregardor,
                        values = valores,
                         aggfunc = _agg )
    
    if ordenacao:
    
        t = t.sort_values(by = valores, ascending = False)
    
    categorias = [ x for x in t.index ]

    _valores = [ x for x in t[valores] ]

    return categorias,_valores

#Inicio do app
st.set_page_config(layout="wide", page_title='Análise cartão de crédito bradesco')

st.success("Painel Financeiro de Diogo Oliveira")

st.sidebar.title('Painel de filtros')

st.sidebar.markdown("---")

#----------------------------------Filtros do app------------------------------------------------

month_filtros = st.sidebar.multiselect('Selecione os meses de análise', df_limpo["date"].dt.strftime('%Y%m').sort_values().unique())
categoria_filtro = st.sidebar.multiselect('Selecione as categorias do gasto', df_limpo.categoria.unique())
descricao_filtro = st.sidebar.multiselect('Selecione a descrição da fatura', df_limpo.descricao.unique())
cidade_filtro = st.sidebar.multiselect('Selecione a cidade do gasto', df_limpo.cidade.unique())

if month_filtros != []:
    df_filtrado = df_limpo[df_limpo.date.dt.strftime('%Y%m').isin(month_filtros)]
else:
    df_filtrado = df_limpo

if categoria_filtro != []:
    df_filtrado = df_filtrado[df_filtrado.categoria.isin(categoria_filtro)]

if descricao_filtro != []:
    df_filtrado = df_filtrado[df_filtrado.descricao.isin(descricao_filtro)]

if cidade_filtro != []:
    df_filtrado = df_filtrado[df_filtrado.cidade.isin(cidade_filtro)]

#----------------Inicio do relatório--------------------------

Dias_sem_gastos = dias_sem_gastos(df_filtrado)

previsto_kpi = df_filtrado.amount.sum()

avg_line = Dias_sem_gastos['sum']/Dias_sem_gastos['count']

col1,col2, col3, col4 = st.columns(4)

with col1:
    val = Dias_sem_gastos['sum'].sum() or 0

    delta = (
        get_delta(Dias_sem_gastos.iloc[-1]['sum'], Dias_sem_gastos['sum'].mean()) if previsto_kpi is not None else None
    )
    st.metric(
        "Total gasto",
        f"${val:,.0f}",
        delta=delta,
        border=True,
        delta_color="inverse",
        chart_data=Dias_sem_gastos['sum'].tolist(),
        chart_type="area",
    )

with col2:
    val = Dias_sem_gastos['count'].sum() or 0
    delta = (
        get_delta(Dias_sem_gastos.iloc[-1]['count'], Dias_sem_gastos['count'].mean()) if previsto_kpi is not None else None
    )
    st.metric(
        "Total de utilizações do cartão",
        f"{val:,}",
        delta=delta,
        delta_color="inverse",
        border=True,
        chart_data=Dias_sem_gastos['count'].tolist(),
        chart_type="bar",
    )

with col3:
    val = Dias_sem_gastos.dias_sem_gastar.mean() or 0
    delta = (
        get_delta(Dias_sem_gastos.iloc[-1]['dias_sem_gastar'], Dias_sem_gastos.dias_sem_gastar.mean())
        if previsto_kpi is not None
        else None
    )
    st.metric(
        "Media dias sem usar o cartão",
        f"{val:,f}",
        delta=delta,
        border=True,
        chart_data=Dias_sem_gastos.dias_sem_gastar.tolist(),
        chart_type="line",
    )

with col4:
    val = avg_line.mean() or 0
    delta = (
        get_delta(val, avg_line[len(avg_line)-1])
        if previsto_kpi is not None
        else None
    )
    st.metric(
        "Avg. valor de Utilização",
        f"${val:,.0f}",
        delta=delta,
        border=True,
        delta_color="inverse",
        chart_data=avg_line.values.tolist(),
        chart_type="line",
    )

with st.container(border=True, height = 550):

    pcol1, pcol2 = st.columns([5,5])

    with pcol1.container(border=True,height=520):

        st.subheader("Gastos por categoria", divider=True)

        grafico_rosca(df_para_lista_dict(df_filtrado),tamanho = "380px")

    with pcol2.container(border=True,height=520):
        
        st.subheader("Ranking de gastos e utilizações", divider=True)

        barras_laterais_sum_qtd(df_para_lista(df_filtrado),tamanho="380px")

    with st.container(border=True,height=520):

        st.subheader("Gastos por dia da semana", divider=True)

        barras_empilhadas_laterais(*serei_dia_semana_complexo(df_filtrado, 'date', 'amount', 'categoria', 'sum'),tamanho = "300px")

    with st.container(border=True,height=520):

        st.subheader("Gastos por semana do mês", divider=True)

        barras_empilhadas_laterais(*serei_semana_mes_complexo_2(df_filtrado, 'date', 'amount', 'categoria', 'sum'),tamanho = "300px")

    with st.container(border=True,height=520):

        st.subheader("Top 10 gastos por categoria", divider=True)

        barras_drilldown(*top_10_categorias(df_limpo), tamanho = "300px" )

with st.container(border=True, height = 500):

    with st.container(border=True, height=470):

        st.subheader("Gastos por cidade de são paulo", divider=True)

        mapa_sp(df_para_lista_dict(df_filtrado,'cidade'),tamanho="400px")

    with st.container(border=True, height=430):

        st.subheader("Gastos por cidade", divider=True)

        barras_simples(*dados_grafico_barras(df_filtrado, "cidade", "amount"))

with st.container(border=True, height = 450):

    with st.container(border=True, height=400):

        st.subheader("Gastos por dia do ano", divider=True)

        grefico_calendario(Serie_simples(df_filtrado, 'date', 'amount'),ano_2=2025,ano_3=2026)

    with st.container(border=True, height=430):

        st.subheader("Gastos por mês", divider=True)

        barras_simples(*dados_grafico_barras(df_filtrado, df_filtrado.date.dt.strftime('%Y%m'), "amount", ordenacao=False))

