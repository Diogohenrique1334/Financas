# Frontend — dashboard Streamlit do projeto Finanças
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Instala dependências primeiro (melhor cache de camada)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia o código do frontend (contexto = ./frontend)
COPY . .

EXPOSE 8501

# /app na raiz do sys.path → `from api.client import ...` resolve
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
