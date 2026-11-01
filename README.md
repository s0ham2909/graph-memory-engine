# KGIRS – Knowledge Graph Information Retrieval System

A micro-project proving that storing agent memory as a **Neo4j knowledge graph**
and retrieving it with **hybrid search** (vector + graph traversal) gives better
answers with fewer tokens than pasting full history or vector-only RAG.

## Quick start

```bash
# 1. Clone & enter
git clone <repo> && cd kgirs-micro

# 2. Copy env and edit secrets
cp .env.example .env

# 3. Start Neo4j
docker compose up -d

# 4. Create virtualenv & install
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt

# 5. Initialise schema
python scripts/init_schema.py

# 6. Verify connection
python scripts/check_connection.py

# 7. Run UI
streamlit run app.py
```

## Architecture

```
L1 ingest → L2 extract → L3 store → L4 retrieve → L5 answer → L6 UI/eval
```

## Local Hermes data check

Set `HERMES_DATA_DIR=data/raw/hermes` in `.env`, then run the local dry-run:

```powershell
.\.venv\Scripts\python -m src.hermes_loader --dry-run
.\.venv\Scripts\python -m src.hermes_loader --dry-run --scan-secrets
```

The dry-run reads local Markdown and SQLite data only; it does not call Neo4j or
an embedding/LLM service. The secret scan checks every generated redacted chunk
and prints hit counts with short context for any matches. Keep `data/raw/`
private; it is excluded by `.gitignore`.

See the project spec for full details.
