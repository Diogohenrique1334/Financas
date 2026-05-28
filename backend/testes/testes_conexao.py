from sqlalchemy.ext.asyncio import create_async_engine
import asyncio

async def test_conecxao():
    engine = create_async_engine("postgresql+asyncpg://neondb_owner:npg_iIESJFf2W9Zn@ep-bitter-surf-a8cdmnbz.eastus2.azure.neon.tech/neondb?ssl=require")

    try:
        async with engine.connect() as conn:
            print("✅ Conectado!")
    finally:
        await engine.dispose() 

asyncio.run(test_conecxao())