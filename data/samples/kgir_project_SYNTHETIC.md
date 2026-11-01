# KGIRS Micro Project — Agent Memory

## Goal
Prove that storing agent memory as a Neo4j knowledge graph and retrieving it with
hybrid search (vector + graph traversal) gives better answers with fewer tokens
than pasting full history or vector-only RAG.

## Stack
- Python 3.11, virtualenv, requirements.txt
- Neo4j 5.x via Docker Compose (native vector index)
- Embeddings: sentence-transformers, model configurable via env (default all-MiniLM-L6-v2, 384 dims)
- LLM: provider-agnostic wrapper in src/llm.py, provider and model chosen by env vars, with on-disk response caching
- UI: Streamlit + pyvis (single app.py)
- Tests: pytest

## Architecture (layers)
L1 ingest → L2 extract → L3 store → L4 retrieve → L5 answer → L6 UI/eval.

## Graph data model
Nodes:
- Document(id, source, date)
- Chunk(id, text, embedding, session_id, ts)
- Entity(name, type, aliases, description). Entity types: Project, Decision, Concept, Tool, Person, Task.

Relationships:
- (Chunk)-[:PART_OF]->(Document)
- (Chunk)-[:MENTIONS]->(Entity)
- (Entity)-[:RELATION {type, evidence_chunk_id, ts}]->(Entity)
Relation types: DEPENDS_ON, DECIDED_OVER, CAUSED_BY, PART_OF, USES, SUPERSEDES.

RULES:
- every entity and relation must carry provenance (evidence chunk id)
- all writes use MERGE so they are idempotent.

## Source documents
This is the primary source document for the KGIRS micro project. It describes
the architecture, data model, and pipeline layers used to store and retrieve
agent memories in a Neo4j knowledge graph.

## Decisions made
1. Use Neo4j 5.x native vector index for similarity search.
2. Store all entities and relations with explicit provenance (evidence_chunk_id).
3. Hybrid retrieval: vector search → entity link → 1-2 hop graph expansion.
4. Answer generation with chunk citations using [chunk:<id>] notation.

## Tools
- sentence-transformers for embeddings (all-MiniLM-L6-v2, 384 dimensions)
- Neo4j for graph storage and hybrid search
- Gemini LLM for extraction and answer generation
- Streamlit for UI, pyvis for graph visualization

## Memory context
The agent's current session is focused on building a full-stack user analytics
application (Node/Express + MongoDB backend, React+Vite dashboard, vanilla JS
tracker, demo storefront). Deploying to Render with MongoDB Atlas. Key
constraints: flat design (2px radii, hairline borders, Inter/JetBrains Mono),
dummy data swappable, Playwright verification for multi-viewport checks.
