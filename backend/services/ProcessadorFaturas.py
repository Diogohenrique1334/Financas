from typing import List, Optional
import PyPDF2
import logging
import re
from langchain_core.messages import SystemMessage, HumanMessage
import json
from schemas.schemas_fatura import Transaction
import datetime


# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extrair_texto_pdf(pdf_path: str, password: Optional[str] = None) -> str:
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

def extrair_periodo_transacoes(text: str) -> int:
        
         # 1️⃣ tenta padrão com nome do mês (ex: Março / 2025)
        logger.info("Tentando extrair período pelo nome do mês...")
        match_nome = re.search(r'([A-Za-zÀ-ÿ]+)\s*/\s*(\d{4})', text, re.IGNORECASE)

        if match_nome:
            month_name, year_str = match_nome.groups()
            logger.info(f"Período encontrado por nome: {month_name} / {year_str}")
            return int(year_str)

        # 2️⃣ tenta padrão de data (ex: 10/12/2025)
        logger.info("Tentando extrair período por data numérica...")
        match_data = re.search(r'\d{2}/\d{2}/(\d{4})', text)

        if match_data:
            year_str = match_data.group(1)
            logger.info(f"Ano encontrado por data: {year_str}")
            return int(year_str)

        # 3️⃣ fallback
        current_year = datetime.now().year
        logger.warning(
            f"Não foi possível detectar o ano da fatura. Usando ano atual como fallback: {current_year}"
        )
        return current_year

def preprocess_text(text: str) -> str:
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

def create_messages(texto_fatura_limpo: str, ano_fatura: int) -> list:
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
        '{"transactions": [{"date": "dd/mm", "descricao": "nome do estabelecimento","parcelas": "parecelas da compra, caso de compras parceladas 01/03", "categoria": "categoria escolhida","cidade": "cidade da compra", "amount": 123.45}]}\n'
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

def parse_response(response: str) -> List[Transaction]:
    
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