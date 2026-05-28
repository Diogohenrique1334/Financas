from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from datetime import datetime
import os

from dotenv import load_dotenv
load_dotenv()


class ModelConfig(BaseModel):
    model_name: str = "gpt-5-mini"
    temperature: float = 0.0 # Temperatura zero para maior precisão na extração
    max_tokens: int = 4096


class llm:
    def __init__(self, model_config: ModelConfig = ModelConfig(), openai_api_key: str = None):
        self.model_config = model_config
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("A chave da API do Google não foi encontrada. Defina a variável de ambiente openai_api_key.")
        self.llm = self._initialize_llm()
        self.current_year = datetime.now().year
    
    def _initialize_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.model_config.model_name,
            temperature=self.model_config.temperature,
            #max_output_tokens=self.model_config.max_tokens,
            openai_api_key=self.openai_api_key,
        )