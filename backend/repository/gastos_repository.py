from database import async_session
from models.gastos_fatura import fatura_bradesco
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert


async def salvar_gastos(df):
    async with async_session() as session:
        registros = [
            {
                "date": row["date"],
                "descricao": row["descricao"],
                "parcelas": row["parcelas"],
                "categoria": row["categoria"],
                "cidade": row["cidade"],
                "amount": row["amount"],
            }
            for _, row in df.iterrows()
        ]

        stmt = insert(fatura_bradesco).values(registros).on_conflict_do_nothing(
            index_elements=["date", "descricao", "amount"]
        )
        await session.execute(stmt)
        await session.commit()

async def get_gastos_bradesco():
    async with async_session() as session:
        result = await session.execute(select(fatura_bradesco))
        gastos = result.scalars().all()

        # transforma em lista de dicionários
        dados = [
            {
                "date": g.date,
                "descricao": g.descricao,
                "parcelas": g.parcelas,
                "categoria": g.categoria,
                "cidade": g.cidade,
                "amount": g.amount,
            }
            for g in gastos
        ]

        return pd.DataFrame(dados)

