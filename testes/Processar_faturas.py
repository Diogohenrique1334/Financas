import os
import pandas as pd
import json
from typing import List, Optional
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
import PyPDF2
import re
import logging
import time
import calendar
from datetime import datetime

#Minha chave da groq, llm que estou usando neste projeto
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GROQ_KEY")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#travando os hiperparametros da minha llm com pydantic 
class ModelConfig(BaseModel):
    model_name: str = "llama3-8b-8192"
    temperature: float = 0.1
    max_tokens: int = 4000


#colunas das bases encontradas no meu data frame
class Transaction(BaseModel):
    date: str
    descricao: str
    categoria: str
    amount: float
    currency: str = "BRL"

class processar_transacoes:
    def __init__(self, model_config: ModelConfig = ModelConfig(), groq_api_key: str = None):
        self.model_config = model_config
        self.groq_api_key = groq_api_key or os.getenv("GROQ_KEY")
        self.llm = self._initialize_llm()
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month
        
    def _initialize_llm(self):
        return ChatGroq(
            model=self.model_config.model_name,
            temperature=self.model_config.temperature,
            max_tokens=self.model_config.max_tokens,
            api_key=self.groq_api_key
        )
    
    def extrair_texto_pdf(self, pdf_path: str, password: Optional[str] = None) -> str:
        """Extrai texto de PDFs com ou sem senha"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                if reader.is_encrypted:
                    if password:
                        reader.decrypt(password)
                    else:
                        # Tentar senha vazia
                        try:
                            reader.decrypt('')
                        except:
                            raise ValueError("PDF protegido por senha. Forneça a senha.")
                
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
                return text
        except Exception as e:
            logger.error(f"Erro na extração de texto: {str(e)}")
            raise
    
    def extrair_periodo_transacoes(self, text: str) -> tuple:
        """Extrai o período de referência da fatura para determinar o ano das transações"""
        # Procura padrões como "Maio / 2025"
        period_match = re.search(r'(\w+)\s*/\s*(\d{4})', text, re.IGNORECASE)
        if period_match:
            month_name, year = period_match.groups()
            try:
                month_num = list(calendar.month_name).index(month_name.capitalize())
                return int(year), month_num
            except:
                pass
        
        # Se não encontrar, usa o ano e mês atual
        return self.current_year, self.current_month
    
    def preprocess_text(self, text: str) -> str:
        """Limpa e formata o texto"""
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        return text.strip()
    
    def create_messages(self, texto_da_fatura: str) -> list:
        """Cria mensagens para o LLM com instruções mais claras"""
        # Encontrar o período da fatura para determinar o ano das transações
        year, month = self.extrair_periodo_transacoes(texto_da_fatura)
        
        system_message = SystemMessage(content=(
            "Você é um especialista em processamento de faturas de cartão de crédito. "
            "Sua tarefa é extrair transações financeiras de textos de faturas. "
            f"O período de referência desta fatura é {month}/{year}. "
            "Para cada transação, identifique: "
            "1. Data (no formato DD/MM) - O ano será adicionado posteriormente "
            "2. Descrição (nome do estabelecimento/comércio) "
            "3. Categoria (alimentação, transporte, lazer, saúde, educação, etc.) "
            "4. Valor (número decimal positivo) "
            "Retorne APENAS um JSON válido no formato: "
            '{"transactions": [{"date": "dd/mm", "descricao": "texto", "categoria": "texto", "amount": 123.45}, ...]}'
        ))
        
        human_message = HumanMessage(content=(
            f"Extraia as transações do seguinte texto de fatura:\n\n"
            f"{texto_da_fatura}\n\n"
            "Instruções adicionais:\n"
            "- Ignore cabeçalhos e rodapés\n"
            "- Valores devem ser números positivos\n"
            "- Se não encontrar transações, retorne {'transactions': []}\n"
            "- As datas estão apenas com dia e mês (ex: '12/05')"
        ))
        
        return [system_message, human_message]
    
    def parse_response(self, response: str) -> List[Transaction]:
        """Parseia a resposta do LLM de forma robusta"""
        try:
            # Tenta encontrar JSON na resposta
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("Nenhum JSON encontrado na resposta")
                logger.debug(f"Resposta completa: {response}")
                return []
                
            json_str = json_match.group()
            data = json.loads(json_str)
            transactions = data.get('transactions', [])
            
            # Validar e converter transações
            valid_transactions = []
            for t in transactions:
                try:
                    # Garantir que amount é número
                    if isinstance(t['amount'], str):
                        # Remover R$ e outros símbolos
                        amount_str = re.sub(r'[^\d,\.]', '', t['amount'])
                        # Substituir vírgula por ponto para float
                        amount_str = amount_str.replace(',', '.')
                        # Remover pontos de milhar
                        if '.' in amount_str and ',' in amount_str:
                            amount_str = amount_str.replace('.', '')
                        t['amount'] = float(amount_str)
                    valid_transactions.append(Transaction(**t))
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(f"Transação inválida ignorada: {t} - Erro: {str(e)}")
            
            return valid_transactions
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {str(e)}")
            logger.debug(f"String JSON: {json_str}")
            return []
        except Exception as e:
            logger.error(f"Erro no parseamento: {str(e)}")
            logger.debug(f"Resposta original: {response}")
            return []
    
    def processar_fatura(self, pdf_path: str, pdf_password: Optional[str] = None) -> pd.DataFrame:
        """Processa o PDF e retorna um DataFrame"""
        try:
            logger.info(f"Processando: {pdf_path}")
            
            # Extrair texto
            raw_text = self.extrair_texto_pdf(pdf_path, pdf_password)
            logger.info(f"Texto extraído com {len(raw_text)} caracteres")
            
            # Extrair período de referência
            year, month = self.extrair_periodo_transacoes(raw_text)
            logger.info(f"Período da fatura detectado: Mês {month}, Ano {year}")
            
            # Pré-processar
            clean_text = self.preprocess_text(raw_text)
            
            # Preparar e enviar para o LLM
            messages = self.create_messages(clean_text)
            
            # Lidar com rate limits
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.llm.invoke(messages)
                    break
                except Exception as e:
                    if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                        wait_time = 10 * (attempt + 1)
                        logger.warning(f"Rate limit atingido. Aguardando {wait_time} segundos...")
                        time.sleep(wait_time)
                    else:
                        raise
            
            # Parsear resposta
            transactions = self.parse_response(response.content)
            logger.info(f"Encontradas {len(transactions)} transações válidas")
            
            # Criar DataFrame
            if transactions:
                # Usar model_dump() para Pydantic v2
                try:
                    df = pd.DataFrame([t.model_dump() for t in transactions])
                except AttributeError:
                    df = pd.DataFrame([t.dict() for t in transactions])
                
                # Adicionar ano às datas
                if 'date' in df.columns:
                    # Converter para data completa (DD/MM/AAAA)
                    df['full_date'] = df['date'].apply(lambda d: f"{d}/{year}")
                    
                    # Converter para datetime
                    df['date'] = pd.to_datetime(df['full_date'], format='%d/%m/%Y', errors='coerce')
                    
                    # Remover datas inválidas (fora do período da fatura)
                    df = df.dropna(subset=['date'])
                    
                    # Ordenar por data
                    df = df.sort_values('date')
                    df = df.drop(columns=['full_date'])
                return df
            return pd.DataFrame()
        
        except Exception as e:
            logger.error(f"Erro no processamento: {str(e)}", exc_info=True)
            return pd.DataFrame()

# Função para testar com diferentes PDFs
def test_processor():
    processor = processar_transacoes(
        groq_api_key=api_key
    )
    
    test_files = [
        ("fatura_sem_senha.pdf", None),
        ("fatura_com_senha.pdf", "43409647864")  # Substituir pela senha real
    ]
    
    for file, password in test_files:
        if not os.path.exists(file):
            logger.warning(f"Arquivo não encontrado: {file}")
            continue
            
        print(f"\n{'='*50}")
        print(f"Processando: {file}")
        df = processor.processar_fatura(file, password)
        
        if not df.empty:
            print(f"\nTransações encontradas ({len(df)}):")
            print(df[['date', 'descricao', 'categoria', 'amount']].head(10))
            # Salvar em CSV
            csv_file = os.path.splitext(file)[0] + ".csv"
            df.to_csv(csv_file, index=False)
            print(f"Salvo em: {csv_file}")
        else:
            print("Nenhuma transação encontrada. Verifique os logs para detalhes.")

if __name__ == "__main__":
    test_processor()