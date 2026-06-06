# 💳 Finanças — Análise de Faturas de Cartão de Crédito

Pipeline de dados + dashboard que transforma **faturas de cartão em PDF** em
análises financeiras interativas. As faturas são lidas por um LLM, normalizadas
(datas, parcelas e cidades via API do IBGE), persistidas em PostgreSQL e
exploradas em um painel Streamlit.

A aplicação é dividida em **dois serviços independentes** que compartilham o banco:

```
┌─ backend/ — FastAPI (:8001) ──────────┐      ┌─ frontend/ — Streamlit (:8501) ─────┐
│ GET /gastos → dados já tratados (JSON) │◄─────┤ api/client.py   (httpx → DataFrame) │
│ GET /health                            │ HTTP │ dados/          (view-model p/ ECharts)
│ ORM · banco · normalização IBGE        │      │ componentes/    (gráficos ECharts)  │
│ services/gastos_service (pipeline)     │      │ mapas.py        (mapas dinâmicos)   │
│ main.py (ingestão de PDFs, offline)    │      │ app.py          (só orquestração)   │
└─────────────────────────────────────────┘      └───────────────────────────────────┘
```

> **Por que o split?** O tratamento dos dados (normalização de cidades, ajuste de
> datas e parcelas) fica no backend. A API entrega os dados prontos — o frontend
> não conhece banco, ORM nem regras de domínio, só apresentação.

---

## 🚀 Stack

| Camada | Tecnologias |
|---|---|
| **Backend / API** | FastAPI, Uvicorn, SQLAlchemy (async), asyncpg, Pydantic |
| **Frontend** | Streamlit, streamlit-echarts (Apache ECharts), httpx |
| **Dados / ML** | pandas, RapidFuzz (fuzzy match IBGE), LangChain + OpenAI (extração) |
| **Banco** | PostgreSQL na nuvem (Neon) |
| **Mapas** | Módulo reutilizável da biblioteca [Baltazar](#-biblioteca-baltazar) (GeoJSON + IBGE) |

---

## 🐳 Rodando com Docker (recomendado)

Pré-requisitos: Docker + Docker Compose e um `.env` na raiz (veja
[Variáveis de ambiente](#-variáveis-de-ambiente)).

```bash
docker compose up --build
```

- **Backend (API):** http://localhost:8001 — docs em `/docs`
- **Frontend (dashboard):** http://localhost:8502 *(host 8502 → container 8501, para evitar conflito com outros stacks que usem 8501)*

O `frontend` só sobe depois que o `backend` fica *healthy* (`/health`). O módulo
de mapas da biblioteca **Baltazar** (que vive fora do projeto) é montado como
volume read-only — veja o `volumes:` em [`docker-compose.yml`](docker-compose.yml).
Se a sua cópia do Baltazar estiver em outro caminho, ajuste esse volume.

> O banco é o PostgreSQL na nuvem (Neon), então **não há container de banco** —
> apenas a `DATABASE_URL` do `.env`. A ingestão de PDFs (`backend/main.py`) é um
> job offline e não faz parte do compose.

---

## 📦 Como rodar (sem Docker)

Pré-requisitos: Python 3.9+, o virtualenv `myenv/` e um arquivo `.env` na raiz
(veja [Variáveis de ambiente](#-variáveis-de-ambiente)).

```bash
# Ativar o ambiente (Windows)
myenv\Scripts\activate

# Instalar dependências de cada serviço
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

### 1. Subir o backend (API)
```bash
cd backend
uvicorn app.main_api:app --port 8001 --reload
```
Documentação interativa em `http://localhost:8001/docs`.

### 2. Subir o frontend (dashboard)
A partir da **raiz do projeto** (para que `frontend/` entre no `sys.path`):
```bash
streamlit run frontend/app.py
```
O painel abre em `http://localhost:8501` e consome a API.

### 3. Ingestão de faturas (offline)
Processa os PDFs em `data/Faturas_bradesco/` e popula o banco:
```bash
cd backend
python main.py
```

---

## 🔑 Variáveis de ambiente

Crie um `.env` na **raiz** do projeto (gitignored):

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | ✅ | String de conexão PostgreSQL (Neon) |
| `OPENAI_API_KEY` | ingestão | Chave da OpenAI usada pelo LLM de extração |
| `GOOGLE_API_KEY` | ingestão | Usada no tratamento de rate-limit durante a ingestão |
| `BACKEND_URL` | — | Endereço da API p/ o frontend (default `http://localhost:8001`) |
| `ALLOWED_ORIGINS` | — | Origens CORS da API (default `http://localhost:8501`) |

---

## 🔄 Fluxo de ingestão (PDF → banco)

```
data/Faturas_bradesco/*.pdf
  → extração de texto (PyPDF2)
  → filtro de linhas de transação
  → extração estruturada via LLM (OpenAI / LangChain)
  → parse JSON → Transaction[] (Pydantic)
  → insert no banco (ON CONFLICT DO NOTHING)
  → move o PDF para data/Faturas_bradesco/bkp/
```

---

## 📊 O que o dashboard mostra

- **KPIs**: total gasto, nº de utilizações, dias sem usar o cartão, ticket médio
- Gastos por **categoria** (rosca) e ranking de gastos × utilizações
- Gastos por **dia da semana** e por **semana do mês** (barras empilhadas)
- **Top 10** gastos por categoria com *drilldown*
- **Mapas dinâmicos**: gastos por estado (Brasil) e por município (estado), com
  colorização por valor e tooltip em BRL
- **Calendário** de gastos por dia do ano e evolução mensal

---

## 🧱 Estrutura do projeto

```
backend/
  app/
    main_api.py        # app FastAPI (CORS, rotas, /health)
    schemas_api.py     # GastoOut (response model)
    routers/gastos.py  # GET /gastos
  services/
    gastos_service.py  # repo + pipeline de tratamento → registros JSON
    ProcessadorFaturas.py
  repository/          # acesso ao banco (SQLAlchemy async)
  models/              # ORM (tabela faturas)
  schemas/             # schemas Pydantic da ingestão
  agents/              # wrapper do LLM (LangChain)
  utils/               # df_tratamento, De_para (IBGE), leitura de faturas
  main.py              # entrada da ingestão
  config.py            # settings (pydantic-settings)
frontend/
  app.py               # layout/orquestração Streamlit
  config.py            # settings (BACKEND_URL, cache)
  api/client.py        # cliente HTTP (httpx) → DataFrame
  dados/               # view-model (pandas → estruturas ECharts)
  componentes/         # componentes de gráfico (ECharts)
  mapas.py             # ponte p/ mapas dinâmicos do Baltazar
data/                  # faturas (PDF) e backups
```

---

## 📚 Biblioteca Baltazar

Os mapas dinâmicos vêm de um módulo reutilizável da biblioteca pessoal
**Baltazar** (`graficos/graficos_streamlit/mapas_dinamicos.py`), que integra
GeoJSON + API do IBGE para colorir estados/municípios por valor. O frontend o
carrega via `importlib` em `frontend/mapas.py`.
