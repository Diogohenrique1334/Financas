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

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modelo para configurar hiperparâmetros da LLM
class ModelConfig(BaseModel):
    """
    Configuração dos hiperparâmetros para o modelo de linguagem.
    
    Parâmetros:
    - model_name: Nome do modelo a ser usado (padrão: "llama3-8b-8192")
    - temperature: Controla a criatividade das respostas (0 = mais determinístico, 1 = mais criativo)
    - max_tokens: Número máximo de tokens na resposta gerada
    """
    model_name: str = "llama3-8b-8192"
    temperature: float = 0.1
    max_tokens: int = 4000

# Modelo para representar uma transação financeira
class Transaction(BaseModel):
    """
    Modelo Pydantic para validar e estruturar as transações extraídas.
    
    Campos:
    - date: Data da transação no formato DD/MM
    - descricao: Descrição/estabelecimento da transação
    - categoria: Categoria da despesa (alimentação, transporte, etc.)
    - amount: Valor da transação
    - currency: Moeda (padrão BRL)
    """
    date: str
    descricao: str
    categoria: str
    amount: float
    currency: str = "BRL"

class ProcessadorFaturas:
    """
    Classe principal para processamento de faturas de cartão de crédito.
    
    Funcionalidades:
    - Extrai texto de PDFs (com ou sem senha)
    - Identifica o período de referência da fatura
    - Envia o texto para um LLM para extração estruturada das transações
    - Converte as transações em um DataFrame pandas
    
    Uso:
    processor = ProcessadorFaturas()
    df = processor.processar_fatura("caminho/para/fatura.pdf")
    """
    
    def __init__(self, model_config: ModelConfig = ModelConfig(), groq_api_key: str = None):
        """
        Inicializa o processador de faturas.
        
        Parâmetros:
        - model_config: Configuração do modelo LLM
        - groq_api_key: Chave de API da Groq (se None, usa variável de ambiente GROQ_KEY)
        """
        self.model_config = model_config
        self.groq_api_key = groq_api_key or os.getenv("GROQ_KEY")
        self.llm = self._initialize_llm()
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month
        
    def _initialize_llm(self) -> ChatGroq:
        """Inicializa o cliente da API Groq com os parâmetros configurados"""
        return ChatGroq(
            model=self.model_config.model_name,
            temperature=self.model_config.temperature,
            max_tokens=self.model_config.max_tokens,
            api_key=self.groq_api_key
        )
    
    def extrair_texto_pdf(self, pdf_path: str, password: Optional[str] = None) -> str:
        """
        Extrai texto de um arquivo PDF, com suporte a PDFs protegidos por senha.
        
        Parâmetros:
        - pdf_path: Caminho para o arquivo PDF
        - password: Senha do PDF (opcional)
        
        Retorna:
        Texto extraído do PDF
        """
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                if reader.is_encrypted:
                    if password:
                        reader.decrypt(password)
                    else:
                        # Tentar senha vazia (alguns PDFs permitem)
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
        """
        Identifica o período de referência da fatura para determinar o ano das transações.
        
        Parâmetros:
        - text: Texto extraído da fatura
        
        Retorna:
        Tupla (ano, mês) do período da fatura
        """
        # Padrão para identificar "Maio / 2025" ou similar
        period_match = re.search(r'(\w+)\s*/\s*(\d{4})', text, re.IGNORECASE)
        if period_match:
            month_name, year = period_match.groups()
            try:
                # Converter nome do mês para número (1-12)
                month_num = list(calendar.month_name).index(month_name.capitalize())
                return int(year), month_num
            except ValueError:
                logger.warning(f"Nome do mês não reconhecido: {month_name}")
        
        # Fallback: usa ano e mês atual se não encontrar no texto
        return self.current_year, self.current_month
    
    def preprocess_text(self, text: str) -> str:
        """
        Limpa e normaliza o texto extraído do PDF.
        
        Parâmetros:
        - text: Texto bruto extraído do PDF
        
        Retorna:
        Texto limpo e normalizado
        """
        # Remove múltiplos espaços e quebras de linha consecutivas
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        return text.strip()
    
    def create_messages(self, texto_da_fatura: str) -> list:
        """
        Prepara as mensagens para enviar ao LLM com instruções de extração.
        
        Parâmetros:
        - texto_da_fatura: Texto pré-processado da fatura
        
        Retorna:
        Lista de mensagens no formato do LangChain
        """
        # Determina o período da fatura para contexto
        year, month = self.extrair_periodo_transacoes(texto_da_fatura)
        
        # Mensagem de sistema com instruções detalhadas
        system_message = SystemMessage(content=(
            "Você é um especialista em processamento de faturas de cartão de crédito. "
            "Sua tarefa é extrair transações financeiras de textos de faturas. "
            f"O período de referência desta fatura é {month}/{year}. "
            "Para cada transação, identifique: "
            "1. Data (no formato DD/MM) - O ano será adicionado posteriormente "
            "2. Descrição (nome do estabelecimento/comércio) "
            "3. Categoria (alimentação, transporte, lazer, saúde, educação, etc.) "
            "4. Valor (número decimal positivo) "
            "5.  Alguns gatos eu ja classifiquei, seguem as classificaçõe que eu usei:"
            "    HIROTA EXPRESS CLARO S ->	Alimentacao"
            "    AutoPostoPortalDa ->	transporte\n" 
            "    SUPERMERCADO FLAMENGO ->	alimentacao\n"
            "    AnaAlves ->	lazer\n"
            "    MorumbiCharm ->	alimentacao\n"
            "    Dka ->	alimentacao\n"
            "    KOBALL 01 ->	alimentacao\n"
            "    SEGURO SUPERPROTEGIDO ->	seguro\n"
            "    PAES E DOCES AGUIA D SAO PAULO ->	alimentacao\n"
            "    CASA DAS ALIANCAS ->	compra\n"
            "    LOJAS AMERICANAS 586 SAO PAULO ->	Alimentacao\n"
            "    ZP*PADARIA AGUIA DE OU ->	Alimentacao\n"
            "    PAES E DOCES AGUIA D ->	Alimentacao\n"
            "    HIROTA EXPRESS CLARO S SAO PAULO ->	Alimentacao\n"
            "    PRACA AROMA CAFE SAO PAULO ->	Alimentacao\n"
            "    SUPERMERCADO FLAMENGO SAO PAULO ->	Alimentacao\n"
            "   classifique essas e todas as outras transações."
            "   Retorne APENAS um JSON válido no formato: "
            '{"transactions": [{"date": "dd/mm", "descricao": "texto", "categoria": "texto", "amount": 123.45}, ...]}'
        ))
        
        # Mensagem humana com o conteúdo da fatura
        human_message = HumanMessage(content=(
            f"Extraia as transações do seguinte texto de fatura:\n\n"
            f"{texto_da_fatura}\n\n"
            "Instruções adicionais:\n"
            "- Ignore cabeçalhos e rodapés\n"
            "- Valores devem ser números\n"
            "- Se não encontrar transações, retorne {'transactions': []}\n"
            "- As datas estão apenas com dia e mês (ex: '12/05')"
        ))
        
        return [system_message, human_message]
    
    def parse_response(self, response: str) -> List[Transaction]:
        """
        Processa a resposta do LLM e converte em objetos Transaction.
        
        Parâmetros:
        - response: Resposta textual do LLM
        
        Retorna:
        Lista de objetos Transaction validados
        """
        try:
            # Extrai o JSON da resposta usando regex
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("Nenhum JSON encontrado na resposta do LLM")
                return []
                
            json_str = json_match.group()
            data = json.loads(json_str)
            transactions = data.get('transactions', [])
            
            # Valida e converte cada transação
            valid_transactions = []
            for t in transactions:
                try:
                    # Converte valores string para float
                    if isinstance(t['amount'], str):
                        # Remove símbolos monetários e formata
                        amount_str = re.sub(r'[^\d,\.]', '', t['amount'])
                        amount_str = amount_str.replace(',', '.')
                        
                        # Trata números com separadores de milhares
                        if '.' in amount_str and ',' in amount_str:
                            amount_str = amount_str.replace('.', '')
                            
                        t['amount'] = float(amount_str)
                    
                    # Valida a transação usando o modelo Pydantic
                    valid_transactions.append(Transaction(**t))
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(f"Transação inválida ignorada: {t} - Erro: {str(e)}")
            
            return valid_transactions
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Erro no parseamento: {str(e)}")
            return []
    
    def processar_fatura(self, pdf_path: str, pdf_password: Optional[str] = None) -> pd.DataFrame:
        """
        Processa um arquivo PDF de fatura e retorna um DataFrame com as transações.
        
        Parâmetros:
        - pdf_path: Caminho para o arquivo PDF
        - pdf_password: Senha do PDF (opcional)
        
        Retorna:
        DataFrame pandas com as transações extraídas
        """
        try:
            logger.info(f"Iniciando processamento: {pdf_path}")
            
            # Etapa 1: Extração de texto
            raw_text = self.extrair_texto_pdf(pdf_path, pdf_password)
            logger.info(f"Texto extraído - Tamanho: {len(raw_text)} caracteres")
            
            # Etapa 2: Identificação do período da fatura
            year, month = self.extrair_periodo_transacoes(raw_text)
            logger.info(f"Período detectado: {month}/{year}")
            
            # Etapa 3: Pré-processamento do texto
            clean_text = self.preprocess_text(raw_text)
            
            # Etapa 4: Preparação do prompt para o LLM
            messages = self.create_messages(clean_text)
            
            # Etapa 5: Chamada ao LLM com tratamento de rate limits
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
                        logger.error(f"Erro na chamada ao LLM: {str(e)}")
                        return pd.DataFrame()
            
            # Etapa 6: Processamento da resposta do LLM
            transactions = self.parse_response(response.content)
            logger.info(f"Transações válidas identificadas: {len(transactions)}")
            
            # Etapa 7: Criação do DataFrame
            if transactions:
                # Converte para DataFrame (compatível com Pydantic v1 e v2)
                try:
                    df = pd.DataFrame([t.model_dump() for t in transactions])
                except AttributeError:
                    df = pd.DataFrame([t.dict() for t in transactions])
                
                # Adiciona o ano às datas e converte para datetime
                if 'date' in df.columns:
                    df['full_date'] = df['date'].apply(lambda d: f"{d}/{year}")
                    df['date'] = pd.to_datetime(df['full_date'], format='%d/%m/%Y', errors='coerce')
                    df = df.dropna(subset=['date']).drop(columns=['full_date'])
                    df = df.sort_values('date')
                
                return df
            return pd.DataFrame()
        
        except Exception as e:
            logger.error(f"Erro no processamento: {str(e)}", exc_info=True)
            return pd.DataFrame()

# Função pública para uso em outros scripts
def processar_fatura_cartao(pdf_path: str, pdf_password: Optional[str] = None) -> pd.DataFrame:
    """
    Função principal para processar faturas de cartão de crédito.
    
    Parâmetros:
    pdf_path: Caminho para o arquivo PDF da fatura
    pdf_password: Senha do PDF (opcional)
    
    Retorna:
    DataFrame com as transações extraídas (date, descricao, categoria, amount)
    
    Exemplo de uso:
    from biblioteca import processar_fatura_cartao
    
    df = processar_fatura_cartao("fatura.pdf", "senha_se_houver")
    """
    processor = ProcessadorFaturas()
    return processor.processar_fatura(pdf_path, pdf_password)

# Exemplo de uso direto (para testes)
if __name__ == "__main__":
    # Testar com diferentes PDFs
    test_files = [
        ("fatura_sem_senha.pdf", None),
        ("fatura_com_senha.pdf", "43409647864")
    ]
    
    for file, password in test_files:
        if not os.path.exists(file):
            logger.warning(f"Arquivo não encontrado: {file}")
            continue
            
        print(f"\n{'='*50}")
        print(f"Processando: {file}")
        df = processar_fatura_cartao(file, password)
        
        if not df.empty:
            print(f"\nTransações encontradas ({len(df)}):")
            print(df[['date', 'descricao', 'categoria', 'amount']].head(10))
            csv_file = os.path.splitext(file)[0] + ".csv"
            df.to_csv(csv_file, index=False)
            print(f"Salvo em: {csv_file}")
        else:
            print("Nenhuma transação encontrada. Verifique os logs para detalhes.")