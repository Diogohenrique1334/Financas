# Backend — API FastAPI do projeto Finanças
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instala dependências primeiro (melhor cache de camada)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia o código do backend (contexto = ./backend)
COPY . .

EXPOSE 8001

# Imports não-qualificados assumem o diretório do backend como raiz (cwd = /app).
# Forma shell para expandir $PORT (injetado pela nuvem, ex.: Render); local sem
# $PORT cai no default 8001 — idêntico ao docker-compose.
CMD uvicorn app.main_api:app --host 0.0.0.0 --port ${PORT:-8001}
