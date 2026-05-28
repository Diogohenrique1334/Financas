import os
import pandas as pd
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from google.api_core.exceptions import ResourceExhausted, InvalidArgument
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import PyPDF2
import re
import logging
import time
from datetime import datetime

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

class ModelConfig(BaseModel):
    model_name: str = "gemini-1.5-flash-latest"
    temperature: float = 0.0 # Temperatura zero para maior precisão na extração
    max_tokens: int = 4096

class Transaction(BaseModel):
    date: str = Field(..., description="Data da transação no formato DD/MM")
    descricao: str = Field(..., description="Descrição/estabelecimento da transação")
    categoria: str = Field(..., description="Categoria da despesa (ex: Alimentação, Transporte)")
    amount: float = Field(..., description="Valor da transação")
    currency: str = "BRL"

class ProcessadorFaturas:
    def __init__(self, model_config: ModelConfig = ModelConfig(), google_api_key: str = None):
        self.model_config = model_config
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            raise ValueError("A chave da API do Google não foi encontrada. Defina a variável de ambiente GOOGLE_API_KEY.")
        self.llm = self._initialize_llm()
        self.current_year = datetime.now().year
    
    def _initialize_llm(self) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=self.model_config.model_name,
            temperature=self.model_config.temperature,
            max_output_tokens=self.model_config.max_tokens,
            google_api_key=self.google_api_key,
        )

    def extrair_texto_pdf(self, pdf_path: str, password: Optional[str] = None) -> str:
        # (Sem alterações)
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                if reader.is_encrypted:
                    if not password or not reader.decrypt(password):
                        raise ValueError(f"PDF protegido ou senha incorreta: {pdf_path}")
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text
        except Exception as e:
            logger.error(f"Erro na extração de texto do PDF '{pdf_path}': {str(e)}")
            raise

    def extrair_periodo_transacoes(self, text: str) -> int:
        # (Lógica simplificada para retornar apenas o ano)
        month_map_pt = {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12}
        period_match = re.search(r'([A-Za-z]+)\s*/\s*(\d{4})', text, re.IGNORECASE)
        if period_match:
            month_name, year_str = period_match.groups()
            return int(year_str)
        logger.warning("Não foi possível detectar o ano da fatura. Usando ano atual como fallback.")
        return self.current_year

    # --- MUDANÇA: Pré-processamento agressivo para otimizar para o plano gratuito ---
    def preprocess_text(self, text: str) -> str:
        """
        Limpa o texto da fatura, mantendo apenas as linhas que parecem ser transações.
        Isso reduz drasticamente o número de tokens enviados para a API.
        """
        linhas_relevantes = []
        # Padrão para identificar uma linha de transação: deve conter uma data (DD/MM) e um valor monetário.
        # Ex: "15/06 UBER TRIP HELP         SAO PAULO BR   15,99"
        padrao_transacao = re.compile(r'\d{2}/\d{2}.*\d+,\d{2}')
        
        for linha in text.split('\n'):
            # Remove espaços extras no início e fim da linha
            linha_limpa = linha.strip()
            # Se a linha corresponder ao padrão de transação, nós a mantemos
            if padrao_transacao.search(linha_limpa):
                # Remove múltiplos espaços dentro da linha
                linha_normalizada = re.sub(r'\s+', ' ', linha_limpa)
                linhas_relevantes.append(linha_normalizada)
        
        logger.info(f"Texto original com {len(text)} caracteres. Texto pré-processado com {len(' '.join(linhas_relevantes))} caracteres.")
        return "\n".join(linhas_relevantes)

    # --- MUDANÇA: Construção da mensagem corrigida e simplificada ---
    def create_messages(self, texto_fatura_limpo: str, ano_fatura: int) -> list:
        """Prepara as mensagens para enviar ao LLM."""
        if not texto_fatura_limpo:
            logger.error("O texto da fatura está vazio após o pré-processamento. Não é possível criar a mensagem.")
            return [] # Retorna lista vazia para evitar o erro

        system_prompt = (
            "Você é um assistente especialista em análise de faturas de cartão de crédito. "
            "Sua tarefa é extrair transações financeiras de uma lista de linhas de uma fatura. "
            f"O ano de referência para estas transações é {ano_fatura}. As datas estão no formato 'DD/MM'.\n"
            "Classifique cada despesa em uma das seguintes categorias: "
            "Alimentação, Transporte, Moradia, Saúde, Lazer, Compras, Serviços, Educação, Outros.\n"
            "Retorne a resposta exclusivamente no seguinte formato JSON, dentro de um único bloco de código:\n"
            '```json\n'
            '{"transactions": [{"date": "dd/mm", "descricao": "nome do estabelecimento", "categoria": "categoria escolhida", "amount": 123.45}]}\n'
            '```'
        )
        
        human_prompt = (
            "Extraia e categorize as transações da seguinte lista. Se a lista estiver vazia, retorne uma lista de transações vazia.\n\n"
            "--- TRANSAÇÕES ---\n"
            f"{texto_fatura_limpo}"
        )
        
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]

    def parse_response(self, response: str) -> List[Transaction]:
        # (Sem alterações)
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if not json_match: return []
            
            json_str = json_match.group(1).strip()
            data = json.loads(json_str)
            transactions_data = data.get('transactions', [])
            
            valid_transactions = []
            for t in transactions_data:
                try:
                    if isinstance(t.get('amount'), str):
                        amount_str = re.sub(r'[^\d,.]', '', t['amount']).replace('.', '', t['amount'].count('.') - 1).replace(',', '.')
                        t['amount'] = float(amount_str)
                    valid_transactions.append(Transaction(**t))
                except Exception as e:
                    logger.warning(f"Transação inválida ignorada: {t} - Erro: {e}")
            return valid_transactions
        except Exception as e:
            logger.error(f"Erro no parseamento da resposta: {e}")
            return []

    def processar_fatura(self, pdf_path: str, pdf_password: Optional[str] = None) -> pd.DataFrame:
        try:
            logger.info(f"Iniciando processamento do arquivo: {pdf_path}")
            raw_text = self.extrair_texto_pdf(pdf_path, pdf_password)

            # --- MUDANÇA: Aplicando o pré-processamento ---
            clean_text = self.preprocess_text(raw_text)
            if not clean_text:
                logger.warning("Nenhum texto relevante encontrado na fatura após a limpeza.")
                return pd.DataFrame()

            year = self.extrair_periodo_transacoes(raw_text)
            logger.info(f"Ano da fatura detectado: {year}")
            
            messages = self.create_messages(clean_text, year)
            if not messages:
                return pd.DataFrame() # Para se a criação da mensagem falhar

            response_content = None
            max_retries = 3
            base_wait_time = 20 # Aumentar a espera base para o plano gratuito

            for attempt in range(max_retries):
                try:
                    logger.info(f"Enviando requisição para o LLM (Tentativa {attempt + 1}/{max_retries})...")
                    response = self.llm.invoke(messages)
                    response_content = response.content
                    logger.info("Resposta recebida com sucesso do LLM.")
                    break
                # --- MUDANÇA: Capturando o novo erro InvalidArgument também ---
                except InvalidArgument as e:
                    logger.error(f"Erro de argumento inválido: {e}. Verifique o conteúdo enviado.")
                    return pd.DataFrame()
                except ResourceExhausted as e:
                    if attempt < max_retries - 1:
                        wait_time = base_wait_time * (2 ** attempt)
                        logger.warning(f"Limite de uso da API atingido. Aguardando {wait_time}s para tentar novamente...")
                        time.sleep(wait_time)
                    else:
                        logger.error("Limite de uso da API excedido. Tente novamente mais tarde.")
                        raise e
            
            if not response_content:
                logger.error("Não foi possível obter uma resposta do LLM.")
                return pd.DataFrame()

            transactions = self.parse_response(response_content)
            logger.info(f"Total de transações válidas extraídas: {len(transactions)}")
            
            if not transactions:
                return pd.DataFrame()

            df = pd.DataFrame([t.model_dump() for t in transactions])
            df['full_date'] = df['date'].apply(lambda d: f"{d}/{year}")
            df['date'] = pd.to_datetime(df['full_date'], format='%d/%m/%Y', errors='coerce')
            df = df.dropna(subset=['date']).drop(columns=['full_date'])
            df = df.sort_values('date').reset_index(drop=True)
            return df
        
        except Exception as e:
            logger.error(f"Ocorreu um erro fatal no processamento: {e}", exc_info=False)
            return pd.DataFrame()

# (Restante do script sem alterações)
def processar_fatura_cartao(pdf_path: str, pdf_password: Optional[str] = None) -> pd.DataFrame:
    try:
        processor = ProcessadorFaturas()
        return processor.processar_fatura(pdf_path, pdf_password)
    except Exception as e:
        logger.error(e)
        return pd.DataFrame()

if __name__ == "__main__":
    caminho_do_pdf = "fatura_sem_senha.pdf" 
    senha_do_pdf = None # Use None se não tiver senha

    if not os.path.exists(caminho_do_pdf):
        logger.error(f"Arquivo de teste não encontrado: '{caminho_do_pdf}'. Verifique o caminho.")
    else:
        print(f"\n{'='*50}")
        print(f"Processando arquivo: {caminho_do_pdf}")
        df_transacoes = processar_fatura_cartao(caminho_do_pdf, senha_do_pdf)
        if not df_transacoes.empty:
            print(f"\n✅ Transações extraídas com sucesso ({len(df_transacoes)}):")
            print(df_transacoes[['date', 'descricao', 'categoria', 'amount']].to_string())
            csv_file = os.path.splitext(caminho_do_pdf)[0] + ".csv"
            df_transacoes.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f"\nResultados salvos em: {csv_file}")
        else:
            print("\n❌ Nenhuma transação foi extraída. Verifique os logs para mais detalhes.")
        print(f"{'='*50}\n")