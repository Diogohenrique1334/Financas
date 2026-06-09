"""Testes das métricas puras do avaliador do agente (sem rede, sem LLM)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from avaliacao.avaliador_agente import (
    avaliar_caso,
    custo_brl,
    numeros_de_estrutura,
    parse_numeros_br,
)


class TestParseNumerosBr:
    def test_extrai_valores_monetarios(self):
        nums = parse_numeros_br("Você gastou R$ 1.234,56 e também R$ 175,00 no total.")
        assert 1234.56 in nums
        assert 175.0 in nums

    def test_ignora_inteiros_sem_decimais(self):
        # "11 parcelas" e "66" não devem virar valores citados
        nums = parse_numeros_br("São 11 parcelas em 66 compromissos, total R$ 28.768,68.")
        assert nums == [28768.68]

    def test_captura_percentual(self):
        assert parse_numeros_br("variação de 2,44% no período") == [2.44]


class TestNumerosDeEstrutura:
    def test_coleta_recursiva(self):
        obj = {"total": 150.0, "itens": [{"amount": 100.0}, {"amount": 50.0}], "n": 2}
        nums = numeros_de_estrutura(obj)
        assert {150.0, 100.0, 50.0, 2.0} <= nums

    def test_ignora_booleanos(self):
        assert numeros_de_estrutura({"ok": True, "v": 10.0}) == {10.0}


class TestAvaliarCaso:
    def _caso(self):
        return {"pergunta": "x", "ferramenta": "gasto_por_categoria",
                "params": {"mes": 3, "ano": 2025, "categoria": "Transporte"}}

    def _resultado(self, resposta, tool="gasto_por_categoria", params=None, total=987.65):
        return {
            "resposta": resposta,
            "ferramentas_usadas": [{"ferramenta": tool, "parametros": params or {"mes": 3, "ano": 2025, "categoria": "Transporte"}}],
            "dados_brutos": [{"ferramenta": tool, "resultado": {"total": total, "recorte": []}}],
        }

    def test_caso_perfeito(self):
        flags = avaliar_caso(self._caso(), self._resultado("Você gastou R$ 987,65 com transporte."), [987.65])
        assert flags == {"roteamento_ok": True, "parametros_ok": True, "numerico_ok": True, "alucinou": False}

    def test_ferramenta_errada(self):
        r = self._resultado("R$ 987,65", tool="gasto_por_cidade")
        flags = avaliar_caso(self._caso(), r, [987.65])
        assert flags["roteamento_ok"] is False
        assert flags["parametros_ok"] is False

    def test_parametro_errado(self):
        r = self._resultado("R$ 987,65", params={"mes": 4, "ano": 2025, "categoria": "Transporte"})
        flags = avaliar_caso(self._caso(), r, [987.65])
        assert flags["roteamento_ok"] is True
        assert flags["parametros_ok"] is False

    def test_numero_errado(self):
        flags = avaliar_caso(self._caso(), self._resultado("Você gastou R$ 100,00."), [987.65])
        assert flags["numerico_ok"] is False

    def test_detecta_alucinacao(self):
        # resposta cita R$ 500,00 que NÃO veio da ferramenta (tool deu 987,65)
        flags = avaliar_caso(self._caso(), self._resultado("Foram R$ 987,65, e estimo R$ 500,00 a mais."), [987.65])
        assert flags["alucinou"] is True

    def test_tolerancia_arredondamento(self):
        # tool 987.654 -> resposta arredonda para 987,65; deve casar
        r = self._resultado("R$ 987,65", total=987.654)
        flags = avaliar_caso(self._caso(), r, [987.654])
        assert flags["numerico_ok"] is True
        assert flags["alucinou"] is False

    def test_variacao_negativa_relatada_como_magnitude_nao_e_alucinacao(self):
        # comparar_meses guarda variação com sinal (-39.38); o agente diz
        # "redução de 39,38%". Magnitude positiva deve casar com |-39.38|.
        caso = {"pergunta": "x", "ferramenta": "comparar_meses", "params": {}}
        resultado = {
            "resposta": "Março R$ 3.275,66, Abril R$ 1.985,80, redução de R$ 1.289,86 (39,38%).",
            "ferramentas_usadas": [{"ferramenta": "comparar_meses", "parametros": {}}],
            "dados_brutos": [{"ferramenta": "comparar_meses", "resultado": {
                "mes_a": {"total": 3275.66}, "mes_b": {"total": 1985.80},
                "variacao_abs": -1289.86, "variacao_pct": -39.38,
            }}],
        }
        flags = avaliar_caso(caso, resultado, [3275.66, 1985.80])
        assert flags["alucinou"] is False


class TestCustoBrl:
    def test_calculo(self):
        # 1M input + 1M output com premissas padrão (0.25 + 2.00) USD * 5.40
        c = custo_brl({"input_tokens": 1_000_000, "output_tokens": 1_000_000})
        assert c == round((0.25 + 2.00) * 5.40, 4)
