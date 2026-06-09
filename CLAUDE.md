# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⭐ Próximo grande incremento — Agente de Gastos

O Diogo quer construir um **agente conversacional (tool calling) que responde perguntas
sobre os gastos em linguagem natural**, sobre os dados reais. A especificação completa
(arquitetura, catálogo de ferramentas, avaliação, roadmap ordenado) está em
**[`PROXIMOS_PASSOS_AGENTE_GASTOS.md`](PROXIMOS_PASSOS_AGENTE_GASTOS.md)**. Leia-o antes de
mexer nessa frente. Pontos inegociáveis: **não é RAG** (dado estruturado → tool calling),
as ferramentas **agregam em pandas sobre `listar_gastos_tratados()`** (consistência com o
dashboard, zero SQL injection), e a etapa de **avaliação com golden set** não é opcional.

## Running the project

The project is split into **two independent processes** plus an offline ingestion job. The backend and the ingestion job run **from within `backend/`** (their modules use unqualified imports, e.g. `from repository.gastos_repository import …`); the frontend runs **from the project root**.

### With Docker (recommended)

```bash
docker compose up --build   # backend :8001, frontend host :8502 → container :8501
```

`frontend` waits for `backend` to be healthy (`/health`). The Baltazar maps module (outside the project) is bind-mounted read-only via `docker-compose.yml`; adjust the `volumes:` path if your Baltazar copy lives elsewhere. The database is cloud Neon (no DB container) — only `DATABASE_URL` from `.env` is needed. Ingestion (`main.py`) is offline and not part of compose.

### Manually (no Docker)

```bash
# 1. Backend API (FastAPI) — serves treated data at http://localhost:8001
cd backend
uvicorn app.main_api:app --port 8001 --reload

# 2. Frontend dashboard (Streamlit) — http://localhost:8501
#    Run from the PROJECT ROOT so `frontend/` is on sys.path.
streamlit run frontend/app.py

# 3. Ingestion pipeline (process PDFs → DB), one-off
cd backend
python main.py
```

The frontend talks to the backend over HTTP (`httpx`), so the backend must be running first. `frontend/config.py` reads `BACKEND_URL` (default `http://localhost:8001`).

The virtual environment is `myenv/` at the project root. Activate it before running anything:
```bash
myenv\Scripts\activate  # Windows
```

Dependencies are split per service: `backend/requirements.txt` and `frontend/requirements.txt`.

There is no test suite — `testes/` contains standalone exploration scripts, not pytest.

## Environment variables

Create a `.env` file at the **project root** (it is gitignored). `backend/config.py` and `frontend/config.py` both load it via `pydantic-settings` `BaseSettings` (`_ENV_FILE = <root>/.env`). Keys:
- `DATABASE_URL` — Neon PostgreSQL connection string (required; no hardcoded default)
- `OPENAI_API_KEY` — used by `agents/modelo.py` to call the LLM (ingestion only)
- `GOOGLE_API_KEY` — used during ingestion (`func_leitor_faturas` handles Google API rate-limit exceptions)
- `BACKEND_URL` — optional; frontend's address for the backend API (default `http://localhost:8001`)
- `ALLOWED_ORIGINS` — optional; comma-separated CORS origins for the API (default `http://localhost:8501`)

## Architecture

The project is a **two-process app** (FastAPI backend + Streamlit frontend) plus an offline ingestion job, all sharing the same Neon database.

```
┌─ backend/ (FastAPI :8001) ────────────┐      ┌─ frontend/ (Streamlit :8501) ───────┐
│ GET /gastos  → treated records (JSON) │◄─────┤ api/client.py  (httpx → DataFrame)  │
│ GET /health                           │ HTTP │ dados/preparo_graficos.py (view-mdl)│
│ DB · ORM · IBGE city normalization    │      │ componentes/graficos.py (ECharts)   │
│ services/gastos_service.py (pipeline) │      │ mapas.py (Baltazar dynamic maps)    │
└────────────────────────────────────────┘      │ app.py (layout/orchestration only)  │
                                                 └───────────────────────────────────┘
```

The treatment pipeline (`pepi_gastos → ajustes_data → pipe_parcelas`, incl. IBGE normalization) lives in the **backend**: the API returns data already treated, so the frontend has no ORM/DB/`df_tratamento` dependency. The frontend layers are: `api/` (HTTP adapter) → `dados/` (pandas → ECharts structures) → `componentes/` (chart widgets) → `app.py` (Streamlit layout).

### Backend entry points

### 1. Ingestion pipeline (`backend/main.py`)
Processes PDF credit card invoices into the database. Flow:

```
data/Faturas_bradesco/*.pdf
  → PyPDF2 text extraction        (ProcessadorFaturas.extrair_texto_pdf)
  → Line filter for transactions  (ProcessadorFaturas.preprocess_text)
  → LLM extraction (OpenAI)       (func_leitor_faturas.processar_fatura)
  → JSON parse → Transaction[]    (ProcessadorFaturas.parse_response)
  → Pydantic validation           (schemas/schemas_fatura.Transaction)
  → DB insert                     (repository/gastos_repository.salvar_gastos)
  → Move PDF to data/Faturas_bradesco/bkp/
```

The LLM is initialized in `agents/modelo.py` as a LangChain `ChatOpenAI` wrapper. `func_leitor_faturas.processar_fatura` is the top-level function that orchestrates the full PDF→DataFrame flow, including retry logic for API rate limits.

### 2. Backend API (`backend/app/main_api.py`)
FastAPI service that exposes the treated data. Flow:

```
GET /gastos
  → services.gastos_service.listar_gastos_tratados()
      → get_gastos_bradesco()  (raw DataFrame from DB)
      → pepi_gastos()          (drop dups, normalize cities via IBGE fuzzy match, cast types)
      → ajustes_data()         (shift future-dated transactions back one year)
      → pipe_parcelas()        (normalize instalment dates to purchase date)
      → records (NaN/NaT → None, Timestamp → ISO date)
  → List[GastoOut]  (app/schemas_api.py)
GET /health → {"status": "ok"}
```

The city normalization in `utils/De_para.py` calls the IBGE REST API (`https://servicodados.ibge.gov.br/api/v1/localidades/municipios`) and then fuzzy-matches each city string against ~5,570 municipality names using `rapidfuzz`.

### 3. Frontend dashboard (`frontend/app.py`)
Streamlit app. Fetches treated data from the API, filters/aggregates client-side, renders charts. Flow:

```
api/client.get_gastos()            (httpx GET /gastos → DataFrame, @st.cache_data)
  → sidebar filters (month, category, description, city)
  → dados/preparo_graficos.*       (pandas → ECharts-ready lists/dicts)
  → componentes/graficos.*         (ECharts widgets)
  → mapas.*                        (dynamic maps from the Baltazar library)
```

### Database
- Cloud PostgreSQL on Neon (`asyncpg` driver), configured in `config.py`
- SQLAlchemy async ORM; single table `faturas` defined in `models/gastos_fatura.py`
- Session factory in `database.py`; `create_tables()` is idempotent and called at pipeline startup
- `fatura_bradesco` has a `UniqueConstraint(date, descricao, amount)`; `salvar_gastos` inserts with `ON CONFLICT DO NOTHING`, so re-running ingestion on the same file no longer duplicates rows

### Key data shape
`Transaction` (Pydantic, in `schemas/schemas_fatura.py`) and `fatura_bradesco` (SQLAlchemy, in `models/gastos_fatura.py`) both expect these columns: `date`, `descricao`, `parcelas`, `categoria`, `cidade`, `amount`. After DB load, `df_tratamento.py` enriches the DataFrame with computed columns (`Parcelas_pagas`, `total_parcelas`, `Cidade_sem_tratamento`).
