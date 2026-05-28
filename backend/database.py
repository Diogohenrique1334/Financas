from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


from config import settings

_engine_kwargs = {"echo": settings.DEBUG}
# Configuração de pool só se aplica a backends com pool de conexões (não ao SQLite)
if "sqlite" not in settings.DATABASE_URL:
    _engine_kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base declarativa para todos os modelos."""

    pass


async def get_db():
    """Dependency que fornece uma sessão de banco de dados."""
    async with async_session() as session:
        yield session


async def create_tables():
    """Cria todas as tabelas no banco de dados (idempotente)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
