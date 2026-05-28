
from services.ProcessadorFaturas import extrair_texto_pdf, extrair_periodo_transacoes, preprocess_text, parse_response, create_messages
from agents.modelo import llm
import pandas as pd
import logging
from typing import Optional
from google.api_core.exceptions import ResourceExhausted, InvalidArgument
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def processar_fatura(pdf_path: str, pdf_password: Optional[str] = None) -> pd.DataFrame:
        try:
            logger.info(f"Iniciando processamento do arquivo: {pdf_path}")
            raw_text = extrair_texto_pdf(pdf_path, pdf_password)

            # --- MUDANÇA: Aplicando o pré-processamento ---
            clean_text = preprocess_text(raw_text)
            if not clean_text:
                logger.warning("Nenhum texto relevante encontrado na fatura após a limpeza.")
                return pd.DataFrame()

            year = extrair_periodo_transacoes(raw_text)
            logger.info(f"Ano da fatura detectado: {year}")
            
            messages = create_messages(clean_text, year)
            if not messages:
                return pd.DataFrame() # Para se a criação da mensagem falhar

            response_content = None
            max_retries = 3
            base_wait_time = 20 # Aumentar a espera base para o plano gratuito

            for attempt in range(max_retries):
                try:
                    logger.info(f"Enviando requisição para o LLM (Tentativa {attempt + 1}/{max_retries})...")
                    response = llm()._initialize_llm().invoke(messages)
                    response_content = response.content
                    logger.info("Resposta recebida com sucesso do LLM.")
                    break
                
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

            transactions = parse_response(response_content)
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