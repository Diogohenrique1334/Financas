"""Testes das agregações puras do Agente de Gastos (determinísticos, sem LLM).

O ground truth é montado à mão sobre um DataFrame sintético pequeno, para que
cada total seja verificável por inspeção. Esta base precisa estar verde antes
do LLM entrar (passo 2 do roadmap em PROXIMOS_PASSOS_AGENTE_GASTOS.md).
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.consultas_gastos import (
    buscar_transacoes,
    comparar_meses,
    compromissos_parcelados,
    gasto_por_categoria,
    gasto_por_cidade,
    gastos_para_df,
    media_mensal,
    top_estabelecimentos,
    total_periodo,
)


@pytest.fixture
def df():
    """DataFrame sintético com valores escolhidos para conferência manual.

    Março/2025: Restaurante 100 (SP) + 50 (SP) = 150; Transporte 30 (Campinas).
    Abril/2025: Restaurante 200 (SP). Total março = 180, total abril = 200.
    Inclui uma compra parcelada (NETFLIX, 3 parcelas, 2 pagas).
    """
    registros = [
        {"date": "2025-03-05", "descricao": "IFOOD RESTAURANTE", "categoria": "Restaurante",
         "cidade": "Sao Paulo", "amount": 100.0, "parcelas": "00/00",
         "Parcelas_pagas": None, "total_parcelas": None},
        {"date": "2025-03-10", "descricao": "BAR DO ZE", "categoria": "Restaurante",
         "cidade": "Sao Paulo", "amount": 50.0, "parcelas": "00/00",
         "Parcelas_pagas": None, "total_parcelas": None},
        {"date": "2025-03-20", "descricao": "UBER TRIP", "categoria": "Transporte",
         "cidade": "Campinas", "amount": 30.0, "parcelas": "00/00",
         "Parcelas_pagas": None, "total_parcelas": None},
        {"date": "2025-04-08", "descricao": "IFOOD RESTAURANTE", "categoria": "Restaurante",
         "cidade": "Sao Paulo", "amount": 200.0, "parcelas": "00/00",
         "Parcelas_pagas": None, "total_parcelas": None},
        {"date": "2025-03-15", "descricao": "NETFLIX", "categoria": "Lazer",
         "cidade": "Sao Paulo", "amount": 25.0, "parcelas": "02/03",
         "Parcelas_pagas": 2, "total_parcelas": 3},
    ]
    return gastos_para_df(registros)


class TestGastosParaDf:
    def test_tipos_normalizados(self, df):
        assert pd.api.types.is_datetime64_any_dtype(df["date"])
        assert df["amount"].dtype == float

    def test_registros_vazios_devolve_df_vazio_com_colunas(self):
        vazio = gastos_para_df([])
        assert vazio.empty
        assert "amount" in vazio.columns


class TestTotalPeriodo:
    def test_total_marco(self, df):
        # 100 + 50 + 30 + 25 (netflix) = 205
        r = total_periodo(df, "2025-03-01", "2025-03-31")
        assert r["total"] == 205.0
        assert r["n_transacoes"] == 4

    def test_intervalo_inclusivo_nas_bordas(self, df):
        r = total_periodo(df, "2025-03-05", "2025-03-05")
        assert r["total"] == 100.0
        assert r["n_transacoes"] == 1

    def test_inicio_depois_do_fim_erro(self, df):
        with pytest.raises(ValueError):
            total_periodo(df, "2025-03-31", "2025-03-01")

    def test_data_invalida_erro(self, df):
        with pytest.raises(ValueError):
            total_periodo(df, "not-a-date", "2025-03-01")


class TestGastoPorCategoria:
    def test_agrupa_todas_ordenado_desc(self, df):
        r = gasto_por_categoria(df, mes=3, ano=2025)
        assert r["por_categoria"] == {"Restaurante": 150.0, "Transporte": 30.0, "Lazer": 25.0}
        assert list(r["por_categoria"])[0] == "Restaurante"  # ordem desc

    def test_categoria_especifica_case_insensitive(self, df):
        r = gasto_por_categoria(df, mes=3, ano=2025, categoria="restaurante")
        assert r["total"] == 150.0
        assert r["n_transacoes"] == 2

    def test_mes_invalido_erro(self, df):
        with pytest.raises(ValueError):
            gasto_por_categoria(df, mes=13, ano=2025)


class TestGastoPorCidade:
    def test_agrupa_por_cidade(self, df):
        r = gasto_por_cidade(df, mes=3, ano=2025)
        assert r["por_cidade"] == {"Sao Paulo": 175.0, "Campinas": 30.0}


class TestTopEstabelecimentos:
    def test_ordena_e_limita(self, df):
        r = top_estabelecimentos(df, mes=3, ano=2025, n=2)
        assert [t["descricao"] for t in r["top"]] == ["IFOOD RESTAURANTE", "BAR DO ZE"]
        assert r["top"][0]["total"] == 100.0

    def test_n_invalido_erro(self, df):
        with pytest.raises(ValueError):
            top_estabelecimentos(df, mes=3, ano=2025, n=0)


class TestCompararMeses:
    def test_variacao_percentual(self, df):
        # março = 205, abril = 200 -> variação (200-205)/205*100
        r = comparar_meses(df, mes_a=3, ano_a=2025, mes_b=4, ano_b=2025)
        assert r["mes_a"]["total"] == 205.0
        assert r["mes_b"]["total"] == 200.0
        assert r["variacao_abs"] == -5.0
        assert r["variacao_pct"] == round((-5.0 / 205.0) * 100, 2)

    def test_mes_base_zero_nao_divide(self, df):
        r = comparar_meses(df, mes_a=1, ano_a=2025, mes_b=3, ano_b=2025)
        assert r["mes_a"]["total"] == 0.0
        assert r["variacao_pct"] is None


class TestBuscarTransacoes:
    def test_busca_case_insensitive(self, df):
        r = buscar_transacoes(df, texto="ifood")
        assert r["n_transacoes"] == 2  # março 100 + abril 200
        assert r["total"] == 300.0

    def test_busca_com_filtro_mes(self, df):
        r = buscar_transacoes(df, texto="ifood", mes=3, ano=2025)
        assert r["total"] == 100.0

    def test_texto_vazio_erro(self, df):
        with pytest.raises(ValueError):
            buscar_transacoes(df, texto="   ")


class TestMediaMensal:
    def test_media_sobre_meses_presentes(self, df):
        # Restaurante: março 150, abril 200 -> média 175 sobre 2 meses
        r = media_mensal(df, categoria="Restaurante")
        assert r["n_meses"] == 2
        assert r["media"] == 175.0

    def test_categoria_inexistente_zera(self, df):
        r = media_mensal(df, categoria="Inexistente")
        assert r["media"] == 0.0
        assert r["n_meses"] == 0


class TestCompromissosParcelados:
    def test_estima_parcelas_em_aberto(self, df):
        # NETFLIX: 3 parcelas, 2 pagas -> 1 restante x 25 = 25 em aberto
        r = compromissos_parcelados(df)
        assert r["n_compromissos"] == 1
        assert r["valor_total_em_aberto"] == 25.0
        assert r["compromissos"][0]["parcelas_restantes"] == 1

    def test_sem_parceladas_zera(self):
        sem_parcelas = gastos_para_df([
            {"date": "2025-03-05", "descricao": "X", "categoria": "Y", "cidade": "Z",
             "amount": 10.0, "parcelas": "00/00", "Parcelas_pagas": None, "total_parcelas": None},
        ])
        r = compromissos_parcelados(sem_parcelas)
        assert r["n_compromissos"] == 0
