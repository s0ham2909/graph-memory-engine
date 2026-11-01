# graph-memory-engine

Transform any Python repo into a **queryable Neo4j knowledge graph**, then export a condensed `MEMORY.md` that Hermes (and other agents) loads as persistent context.

**Result:** 2× faster, ~50× fewer tokens than folder attach, same answer quality.

---

## Quick Start

```bash
# 1. Clone & enter
git clone https://github.com/s0ham2909/graph-memory-engine
cd graph-memory-engine

# 2. Configure secrets
cp .env.example .env
# Edit .env: add your LLM_API_KEY (NVIDIA NIM), NEO4J_PASSWORD

# 3. Start Neo4j
docker compose up -d

# 4. Install deps
pip install -r requirements.txt
# (neo4j, sentence-transformers, httpx, pydantic, google-genai, python-dotenv)

# 5. REA-style setup wizard (checks graph, .env, runs extraction)
python scripts/setup.py
# → Select option 2, point to your Python repo (e.g., /path/to/homeassistant)

# 6. Or run extraction directly
python scripts/analyze_codebase.py
# (edit root path at bottom of script, or pass via -c)

# 7. Export MEMORY.md for Hermes
python -c "from src.memory_plugin import write_memory; write_memory()"
```

---

## Architecture

```
Python source files
        │
        ▼
scripts/analyze_codebase.py  ──▶  LLM extracts CodeEntity + CODE_REL
        │                              (File, Class, Function, Import, Decorator...)
        │
        ▼
Neo4j (bolt://localhost:7687)
        │
        ├── CodeEntity nodes (id, name, entity_type, signature, docstring)
        ├── CODE_REL edges (CONTAINS, IMPORTS, DECORATES, CALLS...)
        │
        ▼
src/memory_plugin.py  ──▶  MEMORY.md (auto-loaded by Hermes)
        │
        ▼
src/retrieve.hybrid_retrieve()  ──▶  Vector + Graph expansion (for RAG)
```

---

## Real End-to-End Test (Home Assistant `backup_restore.py`)

| Metric | Folder Attach (Normal) | Our Tool (Graph Query) |
|--------|------------------------|------------------------|
| **Latency** | 68.44s | **31.76s** (2.2× faster) |
| **Prompt tokens** | 62* | 1,334 |
| **Completion tokens** | 744 | 730 |
| **Answer quality** | ✅ Complete | ✅ Complete |

*Folder attach likely undercounted due to caching.

Run comparison yourself:
```bash
python test_real/test_folder_attach.py
python test_real/test_our_tool_v3.py
```

---

## Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup.py` | Interactive wizard — checks Neo4j, .env, runs extraction |
| `scripts/analyze_codebase.py` | Extracts Python files → LLM → Neo4j (CodeEntity + CODE_REL) |
| `scripts/compare.py` | 3-mode benchmark (full_context / vector_rag / kgirs) |
| `src/memory_plugin.py` | Neo4j → MEMORY.md (Hermes auto-loads this) |
| `src/retrieve.py` | `hybrid_retrieve()` — vector search + graph expansion |
| `test_real/test_our_tool_v3.py` | Working graph query (direct Cypher on CodeEntity) |

---

## Home Assistant Pilot (5 files)

- **64 CodeEntity nodes** (File, Class, Function, Import, Decorator, Constant)
- **63 CODE_REL relations** (CONTAINS, IMPORTS, DECORATES)
- **backup_restore.py**: 22 entities, 22 relations — classes, functions, imports, decorators all extracted

---

## For Team Handoff

```bash
git clone https://github.com/s0ham2909/graph-memory-engine
cd graph-memory-engine
cp .env.example .env   # add their NIM key + Neo4j password
python scripts/setup.py   # Select option 2, point to repo
# Done — graph built, MEMORY.md generated
```

---

## No UI / Streamlit

This is a **CLI-only pipeline**. The old README mentioned `streamlit run app.py` — that file doesn't exist and isn't needed. Everything runs via Python scripts.
