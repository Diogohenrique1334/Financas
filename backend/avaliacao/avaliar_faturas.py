"""CLI para avaliar a qualidade da extração de uma fatura.

Compara um PDF de fatura com o CSV de transações já extraídas e imprime as
métricas de cobertura e reconciliação. Não chama o LLM.

Uso:
    python -m avaliacao.avaliar_faturas \
        --pdf testes/fatura_sem_senha.pdf \
        --csv testes/fatura_sem_senha.csv \
        --total 2777.08

Executar a partir da pasta ``backend/`` (para os imports de ``services`` e
``schemas`` funcionarem).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Garante que a raiz do backend está no path quando rodado como script solto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.ProcessadorFaturas import extrair_texto_pdf  # noqa: E402
from avaliacao.avaliador_extracao import relatorio_qualidade  # noqa: E402


def ler_valores_csv(csv_path: str, coluna_valor: str = "amount") -> list[float]:
    """Lê a coluna de valores de um CSV de transações extraídas."""
    with open(csv_path, encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f)
        return [float(linha[coluna_valor]) for linha in leitor if linha.get(coluna_valor)]


def avaliar(pdf_path: str, csv_path: str, total: float | None = None, senha: str | None = None) -> dict:
    """Avalia um par (PDF, CSV extraído) e devolve o relatório de qualidade."""
    texto = extrair_texto_pdf(pdf_path, password=senha)
    valores = ler_valores_csv(csv_path)
    return relatorio_qualidade(texto, valores, total_fatura=total)


def _formata(relatorio: dict) -> str:
    cob = relatorio["cobertura"]
    rec = relatorio["reconciliacao"]
    linhas = [
        "Cobertura de linhas:",
        f"  linhas candidatas (regex): {cob['linhas_candidatas']}",
        f"  transações extraídas:      {cob['transacoes_extraidas']}",
        f"  cobertura:                 {cob['cobertura']:.1%}",
        "",
        "Reconciliação de valor:",
    ]
    if rec["reconciliacao"] is None:
        linhas.append("  (total da fatura não informado — passe --total)")
    else:
        linhas += [
            f"  total da fatura:  R$ {rec['total_fatura']:.2f}",
            f"  soma extraída:    R$ {rec['soma_extraida']:.2f}",
            f"  diferença:        R$ {rec['diferenca']:.2f}",
            f"  reconciliação:    {rec['reconciliacao']:.1%}",
        ]
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia a qualidade da extração de uma fatura.")
    parser.add_argument("--pdf", required=True, help="Caminho do PDF da fatura")
    parser.add_argument("--csv", required=True, help="CSV com as transações já extraídas")
    parser.add_argument("--total", type=float, default=None, help="Total conhecido da fatura (para reconciliação)")
    parser.add_argument("--senha", default=None, help="Senha do PDF, se protegido")
    args = parser.parse_args()

    relatorio = avaliar(args.pdf, args.csv, total=args.total, senha=args.senha)
    print(_formata(relatorio))


if __name__ == "__main__":
    main()