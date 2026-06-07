"""Testes do harness de avaliação da extração (determinísticos, sem LLM)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from avaliacao.avaliador_extracao import (
    linhas_candidatas,
    cobertura_linhas,
    reconciliacao_valor,
    valida_transacoes,
    relatorio_qualidade,
)

# Texto sintético: 3 linhas de transação + ruído que NÃO deve contar.
TEXTO_FATURA = """
FATURA DO CARTÃO - MARÇO / 2025
15/03 UBER TRIP SAO PAULO BR 15,99
16/03 IFOOD RESTAURANTE 47,50
20/03 POSTO SHELL CAMPINAS 120,00
Limite disponível: 5.000,00
Atendimento ao cliente 0800
"""


class TestLinhasCandidatas:
    def test_detecta_apenas_linhas_de_transacao(self):
        linhas = linhas_candidatas(TEXTO_FATURA)
        assert len(linhas) == 3
        assert all("/" in l for l in linhas)

    def test_normaliza_espacos_multiplos(self):
        texto = "15/03    UBER     TRIP     15,99"
        assert linhas_candidatas(texto) == ["15/03 UBER TRIP 15,99"]

    def test_ignora_linha_sem_valor(self):
        # Tem data mas não tem valor monetário -> não é transação
        assert linhas_candidatas("15/03 apenas uma anotação") == []


class TestCoberturaLinhas:
    def test_cobertura_total(self):
        r = cobertura_linhas(TEXTO_FATURA, n_extraidas=3)
        assert r["linhas_candidatas"] == 3
        assert r["cobertura"] == 1.0

    def test_cobertura_parcial(self):
        r = cobertura_linhas(TEXTO_FATURA, n_extraidas=2)
        assert r["cobertura"] == round(2 / 3, 4)

    def test_sem_candidatas_nao_divide_por_zero(self):
        r = cobertura_linhas("texto sem transações", n_extraidas=0)
        assert r["cobertura"] == 0.0


class TestReconciliacaoValor:
    def test_reconciliacao_perfeita(self):
        r = reconciliacao_valor(soma_extraida=100.0, total_fatura=100.0)
        assert r["reconciliacao"] == 1.0
        assert r["diferenca"] == 0.0

    def test_reconciliacao_com_diferenca(self):
        r = reconciliacao_valor(soma_extraida=95.0, total_fatura=100.0)
        assert r["reconciliacao"] == 0.95
        assert r["diferenca"] == -5.0

    def test_total_ausente_retorna_none(self):
        r = reconciliacao_valor(soma_extraida=100.0, total_fatura=None)
        assert r["reconciliacao"] is None


class TestValidaTransacoes:
    def _transacao_valida(self, **over):
        base = {
            "date": "15/03",
            "descricao": "UBER",
            "parcelas": "01/01",
            "categoria": "Transporte",
            "cidade": "Sao Paulo",
            "amount": 15.99,
        }
        base.update(over)
        return base

    def test_todas_validas(self):
        ts = [self._transacao_valida(), self._transacao_valida(amount=47.5)]
        r = valida_transacoes(ts)
        assert r["validade"] == 1.0

    def test_transacao_sem_campo_obrigatorio_reprova(self):
        invalida = self._transacao_valida()
        del invalida["amount"]
        r = valida_transacoes([self._transacao_valida(), invalida])
        assert r["total"] == 2
        assert r["validas"] == 1
        assert r["validade"] == 0.5


class TestRelatorioQualidade:
    def test_consolida_secoes(self):
        rel = relatorio_qualidade(TEXTO_FATURA, valores_extraidos=[15.99, 47.50, 120.00], total_fatura=183.49)
        assert rel["cobertura"]["cobertura"] == 1.0
        assert rel["reconciliacao"]["reconciliacao"] == 1.0