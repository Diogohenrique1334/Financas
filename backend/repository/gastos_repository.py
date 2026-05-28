from database import async_session
from models.gastos_fatura import fatura_bradesco
import pandas as pd
from sqlalchemy import select


async def salvar_gastos(df):
    async with async_session() as session:
        objetos = []

        for _, row in df.iterrows():
            gasto = fatura_bradesco(
                date=row["date"],
                descricao=row["descricao"],
                parcelas=row["parcelas"],
                categoria = row["categoria"],
                cidade = row["cidade"],
                amount = row["amount"]
            )
            objetos.append(gasto)

        session.add_all(objetos)
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

