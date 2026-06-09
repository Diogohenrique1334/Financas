"""Agregações puras sobre os gastos tratados (sem LLM, sem banco).

Este é o coração determinístico do Agente de Gastos. Cada função recebe um
``DataFrame`` no formato de ``services.gastos_service.listar_gastos_tratados``
(mesma fonte de verdade do dashboard) e devolve **um número/estrutura + o
recorte de dados usado**. Por serem puras, são 100% testáveis sem rede — a
aritmética é validada separadamente da camada de linguagem (ver
``testes/test_consultas_gastos.py``).

O LLM nunca calcula nada: ele apenas decide *qual* destas funções chamar e com
*quais* parâmetros (via os wrappers ``@tool`` em ``agents/ferramentas_gastos``).
A consulta é executada aqui, em pandas determinístico, eliminando alucinação
numérica.

Colunas esperadas no DataFrame: ``date`` (datetime), ``descricao``, ``categoria``,
``cidade``, ``amount`` (float), ``Parcelas_pagas`` e ``total_parcelas`` (parcelas).
"""

from __future__ import annotations

import pandas as pd

# Colunas expostas no "recorte" devolvido para transparência no frontend.
_COLUNAS_RECORTE = ["date", "descricao", "categoria", "cidade", "amount"]


# --------------------------------------------------------------------------- #
# Adaptador e helpers internos
# --------------------------------------------------------------------------- #
def gastos_para_df(registros: list[dict]) -> pd.DataFrame:
    """Converte os registros tratados (JSON) num DataFrame tipado para consulta.

    Ponte entre a camada de serviço (``listar_gastos_tratados`` devolve dicts
    com ``date`` como string ISO) e as agregações deste módulo, que assumem
    ``date`` datetime e ``amount`` float.

    Args:
        registros: lista de dicts no formato de ``listar_gastos_tratados``.

    Returns:
        DataFrame com dtypes normalizados. Vazio (com as colunas esperadas) se
        ``registros`` for vazio.
    """
    if not registros:
        return pd.DataFrame(columns=_COLUNAS_RECORTE + ["Parcelas_pagas", "total_parcelas"])

    df = pd.DataFrame(registros)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    for coluna in ("Parcelas_pagas", "total_parcelas"):
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    return df


def _validar_mes(mes: int) -> None:
    """Garante que ``mes`` é um inteiro de 1 a 12; senão, erro amigável."""
    if not isinstance(mes, int) or isinstance(mes, bool) or not 1 <= mes <= 12:
        raise ValueError(f"Mês inválido: {mes!r}. Informe um inteiro de 1 a 12.")


def _validar_ano(ano: int) -> None:
    """Garante que ``ano`` é um inteiro plausível de 4 dígitos."""
    if not isinstance(ano, int) or isinstance(ano, bool) or not 1900 <= ano <= 2100:
        raise ValueError(f"Ano inválido: {ano!r}. Informe um ano com 4 dígitos.")


def _para_data(valor, nome: str) -> pd.Timestamp:
    """Converte ``valor`` para Timestamp normalizado (00:00); erro amigável."""
    try:
        return pd.to_datetime(valor).normalize()
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Data inválida em '{nome}': {valor!r}. Use o formato AAAA-MM-DD."
        ) from exc


def _filtrar_mes_ano(df: pd.DataFrame, mes: int, ano: int) -> pd.DataFrame:
    """Recorta o DataFrame para um mês/ano específico."""
    return df[(df["date"].dt.month == mes) & (df["date"].dt.year == ano)]


def _recorte(df: pd.DataFrame, limite: int | None = None) -> list[dict]:
    """Serializa as linhas usadas numa agregação (transparência anti-alucinação).

    Devolve apenas as colunas relevantes, com ``date`` em ISO e ordenado do
    maior gasto para o menor. ``limite`` corta a lista (None = sem corte).
    """
    if df.empty:
        return []
    colunas = [c for c in _COLUNAS_RECORTE if c in df.columns]
    recorte = df[colunas].sort_values("amount", ascending=False)
    if limite is not None:
        recorte = recorte.head(limite)
    recorte = recorte.copy()
    recorte["date"] = recorte["date"].dt.date.astype(str)
    return recorte.to_dict(orient="records")


# --------------------------------------------------------------------------- #
# Ferramentas de consulta (funções puras)
# --------------------------------------------------------------------------- #
def total_periodo(df: pd.DataFrame, data_inicio, data_fim) -> dict:
    """Soma total dos gastos num intervalo de datas (inclusivo).

    Args:
        df: gastos tratados.
        data_inicio: início do intervalo (string ISO, date ou Timestamp).
        data_fim: fim do intervalo (inclusivo).

    Returns:
        dict com ``total``, ``n_transacoes``, ``periodo`` e ``recorte``.
    """
    inicio = _para_data(data_inicio, "data_inicio")
    fim = _para_data(data_fim, "data_fim")
    if inicio > fim:
        raise ValueError("data_inicio não pode ser posterior a data_fim.")

    recorte = df[(df["date"].dt.normalize() >= inicio) & (df["date"].dt.normalize() <= fim)]
    return {
        "total": round(float(recorte["amount"].sum()), 2),
        "n_transacoes": int(len(recorte)),
        "periodo": {"data_inicio": inicio.date().isoformat(), "data_fim": fim.date().isoformat()},
        "recorte": _recorte(recorte),
    }


def gasto_por_categoria(df: pd.DataFrame, mes: int, ano: int, categoria: str | None = None) -> dict:
    """Gasto total por categoria num mês; ou de uma categoria específica.

    Args:
        df: gastos tratados.
        mes: mês (1-12).
        ano: ano (4 dígitos).
        categoria: se informada, devolve só o total dessa categoria
            (casamento case-insensitive). Se None, agrupa todas.

    Returns:
        Sem ``categoria``: dict com ``por_categoria`` (dict ordenado desc).
        Com ``categoria``: dict com ``total`` daquela categoria.
        Em ambos, ``mes``, ``ano``, ``n_transacoes`` e ``recorte``.
    """
    _validar_mes(mes)
    _validar_ano(ano)
    recorte = _filtrar_mes_ano(df, mes, ano)

    if categoria is not None:
        recorte = recorte[recorte["categoria"].str.casefold() == categoria.casefold()]
        return {
            "mes": mes,
            "ano": ano,
            "categoria": categoria,
            "total": round(float(recorte["amount"].sum()), 2),
            "n_transacoes": int(len(recorte)),
            "recorte": _recorte(recorte),
        }

    por_categoria = (
        recorte.groupby("categoria", observed=True)["amount"].sum().sort_values(ascending=False)
    )
    return {
        "mes": mes,
        "ano": ano,
        "por_categoria": {k: round(float(v), 2) for k, v in por_categoria.items()},
        "n_transacoes": int(len(recorte)),
        "recorte": _recorte(recorte),
    }


def gasto_por_cidade(df: pd.DataFrame, mes: int, ano: int) -> dict:
    """Gasto total agrupado por cidade num mês.

    Args:
        df: gastos tratados.
        mes: mês (1-12).
        ano: ano (4 dígitos).

    Returns:
        dict com ``por_cidade`` (dict ordenado desc), ``mes``, ``ano``,
        ``n_transacoes`` e ``recorte``.
    """
    _validar_mes(mes)
    _validar_ano(ano)
    recorte = _filtrar_mes_ano(df, mes, ano)
    por_cidade = (
        recorte.groupby("cidade", observed=True)["amount"].sum().sort_values(ascending=False)
    )
    return {
        "mes": mes,
        "ano": ano,
        "por_cidade": {k: round(float(v), 2) for k, v in por_cidade.items()},
        "n_transacoes": int(len(recorte)),
        "recorte": _recorte(recorte),
    }


def top_estabelecimentos(df: pd.DataFrame, mes: int, ano: int, n: int = 5) -> dict:
    """Maiores gastos por estabelecimento (descrição) num mês.

    Args:
        df: gastos tratados.
        mes: mês (1-12).
        ano: ano (4 dígitos).
        n: quantos estabelecimentos retornar (default 5).

    Returns:
        dict com ``top`` (lista de ``{descricao, total}`` ordenada desc),
        ``mes``, ``ano`` e ``recorte``.
    """
    _validar_mes(mes)
    _validar_ano(ano)
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError(f"n inválido: {n!r}. Informe um inteiro >= 1.")

    recorte = _filtrar_mes_ano(df, mes, ano)
    top = (
        recorte.groupby("descricao", observed=True)["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(n)
    )
    return {
        "mes": mes,
        "ano": ano,
        "top": [{"descricao": k, "total": round(float(v), 2)} for k, v in top.items()],
        "recorte": _recorte(recorte, limite=n),
    }


def comparar_meses(df: pd.DataFrame, mes_a: int, ano_a: int, mes_b: int, ano_b: int) -> dict:
    """Compara o total gasto entre dois meses e calcula a variação percentual.

    Args:
        df: gastos tratados.
        mes_a, ano_a: primeiro mês de referência.
        mes_b, ano_b: segundo mês (o "atual", base da variação relativa a A).

    Returns:
        dict com ``total_a``, ``total_b``, ``variacao_abs`` e ``variacao_pct``
        (None se o mês A foi zero — evita divisão por zero).
    """
    _validar_mes(mes_a)
    _validar_ano(ano_a)
    _validar_mes(mes_b)
    _validar_ano(ano_b)

    total_a = round(float(_filtrar_mes_ano(df, mes_a, ano_a)["amount"].sum()), 2)
    total_b = round(float(_filtrar_mes_ano(df, mes_b, ano_b)["amount"].sum()), 2)
    variacao_abs = round(total_b - total_a, 2)
    variacao_pct = round((variacao_abs / total_a) * 100, 2) if total_a else None
    return {
        "mes_a": {"mes": mes_a, "ano": ano_a, "total": total_a},
        "mes_b": {"mes": mes_b, "ano": ano_b, "total": total_b},
        "variacao_abs": variacao_abs,
        "variacao_pct": variacao_pct,
    }


def buscar_transacoes(df: pd.DataFrame, texto: str, mes: int | None = None, ano: int | None = None) -> dict:
    """Lista lançamentos cuja descrição contém ``texto`` (case-insensitive).

    Args:
        df: gastos tratados.
        texto: termo buscado na descrição.
        mes: filtro opcional de mês (1-12).
        ano: filtro opcional de ano.

    Returns:
        dict com ``total`` (soma dos casados), ``n_transacoes`` e ``recorte``.
    """
    if not texto or not str(texto).strip():
        raise ValueError("Informe um texto para buscar nas descrições.")

    recorte = df
    if mes is not None:
        _validar_mes(mes)
        recorte = recorte[recorte["date"].dt.month == mes]
    if ano is not None:
        _validar_ano(ano)
        recorte = recorte[recorte["date"].dt.year == ano]

    recorte = recorte[recorte["descricao"].str.contains(texto, case=False, na=False, regex=False)]
    return {
        "texto": texto,
        "mes": mes,
        "ano": ano,
        "total": round(float(recorte["amount"].sum()), 2),
        "n_transacoes": int(len(recorte)),
        "recorte": _recorte(recorte),
    }


def media_mensal(df: pd.DataFrame, categoria: str | None = None) -> dict:
    """Gasto médio por mês (opcionalmente filtrado por categoria).

    A média é sobre os meses **presentes** nos dados (mês sem gasto não entra
    como zero), refletindo o ritmo de gasto observado.

    Args:
        df: gastos tratados.
        categoria: se informada, calcula a média só dessa categoria.

    Returns:
        dict com ``media``, ``n_meses``, ``categoria`` e ``por_mes``
        (dict {AAAA-MM: total}).
    """
    recorte = df
    if categoria is not None:
        recorte = recorte[recorte["categoria"].str.casefold() == categoria.casefold()]

    if recorte.empty:
        return {"categoria": categoria, "media": 0.0, "n_meses": 0, "por_mes": {}}

    por_mes = recorte.groupby(recorte["date"].dt.to_period("M"))["amount"].sum()
    return {
        "categoria": categoria,
        "media": round(float(por_mes.mean()), 2),
        "n_meses": int(len(por_mes)),
        "por_mes": {str(k): round(float(v), 2) for k, v in por_mes.items()},
    }


def compromissos_parcelados(df: pd.DataFrame) -> dict:
    """Parcelas futuras em aberto das compras parceladas.

    Identifica cada compra parcelada por ``descricao`` + ``amount`` +
    ``total_parcelas`` e, com base na maior parcela já vista
    (``Parcelas_pagas``), estima as parcelas restantes e o valor em aberto
    (assume parcelas iguais ao ``amount`` da linha).

    Args:
        df: gastos tratados (precisa das colunas de parcelas).

    Returns:
        dict com ``valor_total_em_aberto``, ``n_compromissos`` e ``compromissos``
        (lista de ``{descricao, amount_parcela, total_parcelas, parcelas_pagas,
        parcelas_restantes, valor_em_aberto}``).
    """
    if "total_parcelas" not in df.columns or df.empty:
        return {"valor_total_em_aberto": 0.0, "n_compromissos": 0, "compromissos": []}

    parceladas = df[df["total_parcelas"].notna() & df["Parcelas_pagas"].notna()].copy()
    if parceladas.empty:
        return {"valor_total_em_aberto": 0.0, "n_compromissos": 0, "compromissos": []}

    agrupado = (
        parceladas.groupby(["descricao", "amount", "total_parcelas"], observed=True)["Parcelas_pagas"]
        .max()
        .reset_index()
    )

    compromissos = []
    valor_total = 0.0
    for _, linha in agrupado.iterrows():
        restantes = int(linha["total_parcelas"]) - int(linha["Parcelas_pagas"])
        if restantes <= 0:
            continue
        valor_em_aberto = round(float(linha["amount"]) * restantes, 2)
        valor_total += valor_em_aberto
        compromissos.append(
            {
                "descricao": linha["descricao"],
                "amount_parcela": round(float(linha["amount"]), 2),
                "total_parcelas": int(linha["total_parcelas"]),
                "parcelas_pagas": int(linha["Parcelas_pagas"]),
                "parcelas_restantes": restantes,
                "valor_em_aberto": valor_em_aberto,
            }
        )

    compromissos.sort(key=lambda c: c["valor_em_aberto"], reverse=True)
    return {
        "valor_total_em_aberto": round(valor_total, 2),
        "n_compromissos": len(compromissos),
        "compromissos": compromissos,
    }
