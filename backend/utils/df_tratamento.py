import pandas as pd
import datetime as dt
from utils.De_para import normalizar_cidades

def ajustes_data(df1,columns = 'date'):

    """ajusta o ano da data das faturas, caso o formato a data seja maior que a data atual ou em caso de faturas de dezembro"""

    #mask = df1[columns].dt.month == 12

    #df1.loc[mask,columns] = pd.to_datetime({
    #'year': df1.loc[mask, 'date'].dt.year - 1,
    #'month': df1.loc[mask, 'date'].dt.month,
    #'day': df1.loc[mask, 'date'].dt.day
    #})
    
    mask_1 = df1[columns] > pd.to_datetime(dt.datetime.now().date())

    df1.loc[mask_1,columns] = pd.to_datetime({
    'year': df1.loc[mask_1, columns].dt.year - 1,
    'month': df1.loc[mask_1, columns].dt.month,
    'day': df1.loc[mask_1, columns].dt.day
    })

    return df1.drop_duplicates().reset_index(drop = "index")

def pepi_gastos(df):

    df_filtrado = df.drop_duplicates()

    cidades_trtadas = normalizar_cidades(df_filtrado.cidade)

    df_filtrado.date = pd.to_datetime(df_filtrado.date)

    df_filtrado = df_filtrado[~df_filtrado.descricao.isin([ x for x in df_filtrado.descricao.unique() if 'PAGTO' in x ])]

    df_filtrado['Cidade_sem_tratamento'] = df_filtrado.cidade

    df_filtrado.cidade = df_filtrado.cidade.map(cidades_trtadas)

    df_filtrado = df_filtrado.astype({'categoria':'category', 'cidade':'category'})

    df_filtrado.descricao = df_filtrado.descricao.str.upper()

    return df_filtrado

def pipe_parcelas(df_filtrado):
    # Inicializa colunas
    df_filtrado['Parcelas_pagas'] = None
    df_filtrado['total_parcelas'] = None

    # Máscara para compras parceladas
    mask = df_filtrado.parcelas.str.len() == 5

    # Cria chave única
    df_filtrado['Chave'] = (
        df_filtrado['date'].astype(str).str[5:] + " & " + df_filtrado['descricao'].astype(str)
    )

    # Calcula parcelas primeiro
    df_filtrado.loc[mask, 'Parcelas_pagas'] = (
        df_filtrado.loc[mask, 'parcelas']
        .str.replace(r'\D', '', regex=True)
        .str[0:2]
        .astype(int)
    )

    df_filtrado.loc[mask, 'total_parcelas'] = (
        df_filtrado.loc[mask, 'parcelas']
        .str.replace(r'\D', '', regex=True)
        .str[2:4]
        .astype(int)
    )

    # Agora pode agrupar
    compras_parceladas = df_filtrado[mask]
    Datas_compras_parceladas = (
        compras_parceladas.loc[compras_parceladas.groupby('Chave')['Parcelas_pagas'].idxmin()][['Chave','date']]
        .set_index('Chave')
        .to_dict()
        .get('date')
    )

    # Atualiza datas com base na chave
    df_filtrado.loc[mask, 'date'] = df_filtrado.loc[mask, 'Chave'].map(Datas_compras_parceladas)

    return df_filtrado.drop(columns='Chave')