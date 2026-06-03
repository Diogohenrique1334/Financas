from sqlalchemy import Column, String, Integer, Float, Date, UniqueConstraint
from database import Base

# --- Tabelas ---
class fatura_bradesco(Base):

    __tablename__ = "faturas"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    descricao = Column(String, nullable=False)
    parcelas = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    cidade = Column(String, nullable=False)
    amount = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint('date', 'descricao', 'amount', name='uq_transacao'),
    )