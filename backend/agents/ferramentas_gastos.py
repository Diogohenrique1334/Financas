"""Ferramentas (tool calling) que o Agente de Gastos pode invocar.

Camada fina de adaptação: cada ``@tool`` expõe ao LLM **apenas** os parâmetros
de negócio (mês, ano, categoria, …) e delega a aritmética para as funções puras
de ``services.consultas_gastos``. O LLM nunca recebe o DataFrame nem calcula
nada — ele só decide *qual* ferramenta chamar e com *quais* parâmetros.

O DataFrame dos gastos tratados é injetado via *closure* pela factory
``construir_ferramentas(df)``: a camada de serviço carrega os dados uma vez (de
``listar_gastos_tratados``) e constrói as ferramentas já ligadas a esse recorte.
Assim as tools permanecem finas e ``consultas_gastos`` continua pura/testável.

As descrições (docstrings) são o que o LLM lê para rotear — por isso são ricas e
em PT-BR. Cada tool devolve o dict completo da consulta (valor + ``recorte``),
que o executor expõe como passo intermediário para as "fontes" no frontend.
"""

from typing import Optional

import pandas as pd
from langchain_core.tools import tool

from services import consultas_gastos


def construir_ferramentas(df: pd.DataFrame) -> list:
    """Constrói a lista de ferramentas LangChain ligadas a um DataFrame de gastos.

    Args:
        df: gastos já tratados (saída de ``gastos_para_df`` sobre
            ``listar_gastos_tratados``). Capturado por closure pelas tools.

    Returns:
        Lista de ``@tool`` prontas para ``bind_tools``/``AgentExecutor``.
    """

    @tool
    def total_periodo(data_inicio: str, data_fim: str) -> dict:
        """Soma o total gasto entre duas datas (intervalo inclusivo).

        Use para perguntas com recorte de datas livres, ex.: "quanto gastei
        entre 10 de março e 5 de abril?". As datas devem estar no formato
        AAAA-MM-DD. Devolve o total, o nº de transações e o recorte usado.
        """
        return consultas_gastos.total_periodo(df, data_inicio, data_fim)

    @tool
    def gasto_por_categoria(mes: int, ano: int, categoria: Optional[str] = None) -> dict:
        """Total gasto por categoria num mês; ou de uma categoria específica.

        Use para "quanto gastei com restaurante em março?" (passe categoria) ou
        "como dividi meus gastos por categoria neste mês?" (sem categoria, devolve
        todas agrupadas e ordenadas). mes é 1-12 e ano tem 4 dígitos.
        """
        return consultas_gastos.gasto_por_categoria(df, mes, ano, categoria)

    @tool
    def gasto_por_cidade(mes: int, ano: int) -> dict:
        """Total gasto agrupado por cidade num mês.

        Use para "em quais cidades eu mais gastei em abril?". mes é 1-12 e ano
        tem 4 dígitos. Devolve o total por cidade, ordenado do maior para o menor.
        """
        return consultas_gastos.gasto_por_cidade(df, mes, ano)

    @tool
    def top_estabelecimentos(mes: int, ano: int, n: int = 5) -> dict:
        """Maiores gastos por estabelecimento (descrição) num mês.

        Use para "quais foram minhas maiores compras em março?" ou "onde mais
        gastei neste mês?". n controla quantos retornar (default 5). mes é 1-12.
        """
        return consultas_gastos.top_estabelecimentos(df, mes, ano, n)

    @tool
    def comparar_meses(mes_a: int, ano_a: int, mes_b: int, ano_b: int) -> dict:
        """Compara o total gasto entre dois meses e calcula a variação percentual.

        Use para "estou gastando mais que no mês passado?" ou "comparar fevereiro
        com março". O mês A é a referência (base da variação) e o mês B é o
        comparado. Devolve o total de cada mês, a variação absoluta e percentual.
        """
        return consultas_gastos.comparar_meses(df, mes_a, ano_a, mes_b, ano_b)

    @tool
    def buscar_transacoes(texto: str, mes: Optional[int] = None, ano: Optional[int] = None) -> dict:
        """Lista lançamentos cuja descrição contém um texto (case-insensitive).

        Use para "tenho alguma compra na Amazon?" ou "quanto gastei no iFood?".
        texto é o termo buscado na descrição; mes/ano são filtros opcionais.
        Devolve o total casado, o nº de transações e a lista de lançamentos.
        """
        return consultas_gastos.buscar_transacoes(df, texto, mes, ano)

    @tool
    def media_mensal(categoria: Optional[str] = None) -> dict:
        """Gasto médio por mês, opcionalmente filtrado por categoria.

        Use para "qual minha média de gasto mensal?" ou "quanto gasto por mês em
        média com transporte?". A média considera apenas os meses presentes nos
        dados. Devolve a média, o nº de meses e o total de cada mês.
        """
        return consultas_gastos.media_mensal(df, categoria)

    @tool
    def compromissos_parcelados() -> dict:
        """Parcelas futuras em aberto das compras parceladas.

        Use para "quanto ainda devo de parcelas?" ou "quais compras parceladas
        ainda estão em aberto?". Não recebe parâmetros. Devolve o valor total em
        aberto e a lista de compromissos (parcelas restantes por compra).
        """
        return consultas_gastos.compromissos_parcelados(df)

    return [
        total_periodo,
        gasto_por_categoria,
        gasto_por_cidade,
        top_estabelecimentos,
        comparar_meses,
        buscar_transacoes,
        media_mensal,
        compromissos_parcelados,
    ]
