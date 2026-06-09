"""Smoke test manual do Agente de Gastos contra LLM + Neon reais.

NÃO é pytest — roda o agente de verdade (gasta tokens). Executar de backend/:
    ../myenv/Scripts/python.exe testes/smoke_agente.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.agente_service import responder

PERGUNTAS = [
    "Qual é a minha média de gasto mensal?",
    "Quanto eu ainda devo de parcelas em aberto?",
]


async def main():
    for pergunta in PERGUNTAS:
        print("\n" + "=" * 70)
        print("PERGUNTA:", pergunta)
        r = await responder(pergunta)
        print("RESPOSTA:", r["resposta"])
        print("FERRAMENTAS:", [f["ferramenta"] for f in r["ferramentas_usadas"]])
        print("TOKENS:", r["tokens"], "| LATENCIA_MS:", r["latencia_ms"])
        print("PARAMS:", json.dumps([f["parametros"] for f in r["ferramentas_usadas"]], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
