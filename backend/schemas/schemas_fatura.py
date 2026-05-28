from pydantic import BaseModel, Field 

class Transaction(BaseModel):
    
    date: str = Field(..., description="Data da transação no formato DD/MM") 
    descricao: str = Field(..., description="Descrição/estabelecimento da transação") 
    parcelas: str = Field(..., description="Parcelas da compra que estão no formato 01/03") 
    categoria: str = Field(..., description="Categoria da despesa (ex: Alimentação, Transporte)") 
    cidade: str = Field(..., description="Cidade da compra") 
    amount: float = Field(..., description="Valor da transação")