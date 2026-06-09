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

## 🤖 Agente de Gastos — pergunte em linguagem natural

Além do dashboard, o projeto expõe um **agente conversacional** que responde
perguntas sobre os gastos em português — *"quanto gastei com transporte em março?"*,
*"estou gastando mais que no mês passado?"*, *"quanto ainda devo de parcelas?"* — com
base nos **dados reais** do banco.

```
POST /agente/perguntar  {"pergunta": "quanto gastei com transporte em março de 2025?"}
  → o LLM escolhe a ferramenta e os parâmetros:  gasto_por_categoria(mes=3, ano=2025, categoria="Transporte")
  → a consulta roda em pandas determinístico sobre os MESMOS dados tratados do dashboard
  → o número volta ao LLM, que redige a resposta em PT-BR citando o valor e o filtro
  → RespostaOut { resposta, ferramentas_usadas, dados_brutos, tokens, latencia_ms }
```

### Por que **tool calling** e não text-to-SQL nem RAG?

- **Não é RAG.** Os dados são estruturados e as perguntas exigem **agregação exata**
  (SUM, GROUP BY, filtro de data), não recuperação semântica. Recuperar transações
  por similaridade daria somas **numericamente erradas**.
- **Não é text-to-SQL.** O LLM **não escreve SQL e não calcula nada** — só decide
  *qual ferramenta* chamar e *com quais parâmetros*. A aritmética é código Python
  determinístico. Resultado: **zero superfície de SQL injection** e **alucinação
  numérica praticamente eliminada** (o número vem da ferramenta, não do modelo).
- **Mesma fonte de verdade do dashboard.** As ferramentas agregam sobre
  `listar_gastos_tratados()` — as respostas do agente **batem** com os gráficos.

As 8 ferramentas (`total_periodo`, `gasto_por_categoria`, `gasto_por_cidade`,
`top_estabelecimentos`, `comparar_meses`, `buscar_transacoes`, `media_mensal`,
`compromissos_parcelados`) são **funções puras** em
[`services/consultas_gastos.py`](backend/services/consultas_gastos.py) — 100%
testáveis sem LLM e sem banco. Cada resposta devolve também as **fontes**
(ferramentas chamadas + dados usados), exibidas no chat para o usuário conferir
que o número é real.

### Avaliação (golden set)

O que diferencia *"fiz um agente"* de *"sei avaliar um agente"*. Um
[golden set de 20 perguntas](backend/avaliacao/avaliador_agente.py) tem, para cada
uma, a ferramenta esperada e o **valor numérico esperado** (ground truth calculado
direto em pandas, **fora** do agente). Rodando contra o agente real:

| Métrica | Resultado |
|---|---|
| **Acerto de roteamento** (ferramenta certa) | **100%** (20/20) |
| **Acerto de parâmetros** | **100%** |
| **Acerto numérico** (valor bate com o ground truth) | **100%** |
| **Taxa de alucinação** (número que não veio de ferramenta) | **0%** |
| **Custo médio / pergunta** | **R$ 0,015** |
| **Latência média** | **~9,4 s** |

A lógica de pontuação (parsing de valores, detecção de alucinação) é coberta por
testes determinísticos. Reproduza com:

```bash
cd backend
python -m avaliacao.avaliador_agente          # golden set contra o agente real (gasta tokens)
python -m pytest testes/test_consultas_gastos.py testes/test_avaliador_agente.py
```

> Amostra pequena (20 perguntas curadas), reportada como ordem de grandeza — o
> valor está em ter o pipeline **auditável e reprodutível**, não em garantia
> estatística.

---

## 🚀 Stack

| Camada | Tecnologias |
|---|---|
| **Backend / API** | FastAPI, Uvicorn, SQLAlchemy (async), asyncpg, Pydantic |
| **Frontend** | Streamlit, streamlit-echarts (Apache ECharts), httpx |
| **Dados / ML** | pandas, RapidFuzz (fuzzy match IBGE), LangChain + OpenAI (extração) |
| **Agente** | LangChain *tool calling* (`create_tool_calling_agent`) + OpenAI, agregação em pandas |
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
| `OPENAI_API_KEY` | ingestão + agente | Chave da OpenAI usada pelo LLM de extração e pelo Agente de Gastos |
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

## ✅ Qualidade da extração

Como a extração é feita por um LLM (não-determinístico e pago), a qualidade é
medida **sem re-chamar o modelo**, comparando o resultado com sinais obtidos
direto do texto da fatura. O harness vive em [`backend/avaliacao/`](backend/avaliacao)
e é coberto por testes determinísticos (`backend/testes/test_avaliador_extracao.py`).

Duas métricas:

- **Cobertura de linhas (recall):** das linhas que *parecem* transação (heurística
  de regex `data + valor`), quantas viraram transação estruturada.
- **Reconciliação de valor:** a soma das transações extraídas bate com o total
  da fatura (verificado manualmente)?

Avaliando uma fatura real de teste (Santander):

| Métrica | Resultado |
|---|---|
| Cobertura de linhas | **98,4%** (61 de 62 linhas) |
| Reconciliação de valor | **99,5%** (R$ 2.763,71 extraídos vs. R$ 2.777,08 da fatura) |

Reproduza com:

```bash
cd backend
python -m avaliacao.avaliar_faturas \
  --pdf ../testes/fatura_sem_senha.pdf \
  --csv ../testes/fatura_sem_senha.csv \
  --total 2777.08
```

> É uma amostra pequena (faturas de teste), reportada como ordem de grandeza —
> não como garantia estatística. O objetivo é tornar o pipeline **auditável**: a
> mesma função pode rodar sobre qualquer par (PDF, transações extraídas).

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
    main_api.py            # app FastAPI (CORS, rotas, /health)
    schemas_api.py         # GastoOut + PerguntaIn/RespostaOut (response models)
    routers/gastos.py      # GET /gastos
    routers/agente.py      # POST /agente/perguntar
  services/
    gastos_service.py      # repo + pipeline de tratamento → registros JSON
    consultas_gastos.py    # agregações PURAS do agente (pandas, sem LLM)
    agente_service.py      # orquestra pergunta → agente → resposta + metadados
    ProcessadorFaturas.py
  repository/              # acesso ao banco (SQLAlchemy async)
  models/                 # ORM (tabela faturas)
  schemas/                # schemas Pydantic da ingestão
  agents/
    modelo.py              # wrapper do LLM (LangChain ChatOpenAI)
    ferramentas_gastos.py  # @tool: wrappers finos sobre consultas_gastos
    agente_gastos.py       # monta o agente (tool calling) + system prompt
  avaliacao/              # métricas: qualidade da extração + golden set do agente
  utils/                  # df_tratamento, De_para (IBGE), leitura de faturas
  main.py                 # entrada da ingestão
  config.py               # settings (pydantic-settings)
frontend/
  app.py                  # layout/orquestração Streamlit
  config.py               # settings (BACKEND_URL, cache)
  api/client.py           # cliente HTTP (httpx) → DataFrame / agente
  dados/                  # view-model (pandas → estruturas ECharts)
  componentes/            # componentes de gráfico (ECharts)
  chat/agente_chat.py     # componente de chat do agente (com fontes)
  pages/                  # páginas Streamlit (2_Agente_de_Gastos.py)
  mapas.py                # ponte p/ mapas dinâmicos do Baltazar
data/                  # faturas (PDF) e backups
```

---

## 📚 Biblioteca Baltazar

Os mapas dinâmicos vêm de um módulo reutilizável da biblioteca pessoal
**Baltazar** (`graficos/graficos_streamlit/mapas_dinamicos.py`), que integra
GeoJSON + API do IBGE para colorir estados/municípios por valor. O frontend o
carrega via `importlib` em `frontend/mapas.py`.
