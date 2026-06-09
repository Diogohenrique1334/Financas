"""Teto de uso diário do agente (proteção de custo, sem dependência externa).

Contador em memória por processo: reseta a cada virada de dia (UTC) e estoura
quando o número de chamadas ultrapassa o limite configurado. Suficiente para um
deploy de portfólio em instância única (ex.: Render free). Para múltiplas
instâncias, trocar por um contador compartilhado (Redis) — ponto de extensão.
"""

from datetime import date, datetime, timezone


class LimiteDiario:
    """Contador de chamadas com reset diário e teto configurável."""

    def __init__(self, limite: int):
        self._limite = limite
        self._dia: date = datetime.now(timezone.utc).date()
        self._contador = 0

    def registrar(self) -> None:
        """Conta uma chamada; levanta ``LimiteExcedido`` se passar do teto."""
        hoje = datetime.now(timezone.utc).date()
        if hoje != self._dia:
            self._dia = hoje
            self._contador = 0
        if self._contador >= self._limite:
            raise LimiteExcedido(self._limite)
        self._contador += 1

    @property
    def usados_hoje(self) -> int:
        return self._contador


class LimiteExcedido(Exception):
    """Sinaliza que o teto diário de chamadas foi atingido."""

    def __init__(self, limite: int):
        self.limite = limite
        super().__init__(f"Limite diário de {limite} chamadas ao agente atingido.")
