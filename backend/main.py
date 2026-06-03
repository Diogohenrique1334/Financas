from utils.func_leitor_faturas import processar_fatura
from repository.gastos_repository import salvar_gastos
from utils.mover_arquivos import mover_arquivo
from database import create_tables, engine

import os
import asyncio
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


async def alimentar_banco():

    await create_tables()

    caminho = BASE_DIR / "data" / "Faturas_bradesco"
    caminho_bkp = caminho / "bkp"

    pdfs = [x for x in os.listdir(caminho) if x.endswith(".pdf")]

    for pdf in pdfs:
        try:
            logger.info(f"Processando fatura: {pdf}")

            caminho_pdf = caminho / pdf

            # 1️⃣ processa
            df = processar_fatura(str(caminho_pdf))

            if df.empty:
                logger.warning(f"Fatura {pdf} não gerou dados. Pulando...")
                continue

            # 2️⃣ salva no banco
            await salvar_gastos(df)
            logger.info(f"Fatura {pdf} salva no banco com sucesso ✅")

            # 3️⃣ move para backup
            mover_arquivo(
                caminho_origem=str(caminho_pdf),
                caminho_destino=str(caminho_bkp / pdf)
            )

            logger.info(f"Fatura {pdf} movida para bkp 📦")

        except Exception as e:
            logger.error(f"Erro ao processar {pdf}: {e}", exc_info=True)
            # não para o processo — continua nas próximas
            continue

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(alimentar_banco())