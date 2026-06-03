# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the project

All commands inside `backend/` use unqualified imports (e.g. `from repository.gastos_repository import …`), so scripts must be run **from within the `backend/` directory**:

```bash
# Run the Streamlit dashboard
cd backend
streamlit run app.py

# Run the ingestion pipeline (process PDFs → DB)
cd backend
python main.py
```

The virtual environment is `myenv/` at the project root. Activate it before running anything:
```bash
myenv\Scripts\activate  # Windows
```

There is no test suite — `testes/` contains standalone exploration scripts, not pytest.

## Environment variables

Create a `.env` file inside `backend/` (it is gitignored). Required keys:
- `OPENAI_API_KEY` — used by `agents/modelo.py` to call the LLM
- `DATABASE_URL` — overrides the hardcoded default in `config.py` (use this to avoid the committed credential)

`config.py` loads `.env` via `pydantic-settings` `BaseSettings`.

## Architecture

The project has two independent entry points that share the database:

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

### 2. Streamlit dashboard (`backend/app.py`)
Reads all rows from the database, applies transformations, and renders interactive charts. Flow:

```
DB → get_gastos_bradesco() → raw DataFrame
  → pepi_gastos()         (drop duplicates, normalize cities via IBGE fuzzy match, cast types)
  → ajustes_data()        (shift future-dated transactions back one year)
  → pipe_parcelas()       (normalize instalment dates to purchase date)
  → sidebar filters (month, category, description, city)
  → chart functions       (in graficos.py, rendered via st.components)
```

The city normalization in `utils/De_para.py` calls the IBGE REST API at startup (`https://servicodados.ibge.gov.br/api/v1/localidades/municipios`) and then fuzzy-matches each city string against ~5,570 municipality names using `rapidfuzz`.

### Database
- Cloud PostgreSQL on Neon (`asyncpg` driver), configured in `config.py`
- SQLAlchemy async ORM; single table `faturas` defined in `models/gastos_fatura.py`
- Session factory in `database.py`; `create_tables()` is idempotent and called at pipeline startup
- There are no unique constraints on the `faturas` table — running the ingestion pipeline twice on the same file duplicates all rows

### Key data shape
`Transaction` (Pydantic, in `schemas/schemas_fatura.py`) and `fatura_bradesco` (SQLAlchemy, in `models/gastos_fatura.py`) both expect these columns: `date`, `descricao`, `parcelas`, `categoria`, `cidade`, `amount`. After DB load, `df_tratamento.py` enriches the DataFrame with computed columns (`Parcelas_pagas`, `total_parcelas`, `Cidade_sem_tratamento`).
