# Microproject Cookbook: Graph-Memory-Engine
## Advanced Code Intelligence, GraphRAG, Neo4j Knowledge Graphs, and Dual-Mode Querying for Autonomous Coding Agents

**Project Title:** Intelligent Codebase Knowledge Discovery and Agent Memory Integration Using GraphRAG and Dual-Mode Querying  
**Repository:** [https://github.com/s0ham2909/graph-memory-engine](https://github.com/s0ham2909/graph-memory-engine)  
**Authors:** s0ham2909 & Team  

---

### Project Objective
Design and implement an end-to-end GraphRAG application and code intelligence pipeline that ingests semi-structured and unstructured software source code, extracts code entities and syntactic/semantic relationships using structured-output LLMs, constructs a provenance-aware Property Knowledge Graph in Neo4j, and supports dual-mode querying (Natural Language grounded answering and direct Cypher relational analysis) while compiling live graph state into a compressed persistent memory layer (`MEMORY.md`) for autonomous coding agents.

This project demonstrates a production-ready system validated on complex, real-world open-source software (Home Assistant Core).

---

### Expected Learning & Engineering Outcomes
1. **Domain-Specific Schema Design:** Formulate a property graph schema capable of modeling hierarchical, relational, and functional dependencies in modern software codebases.
2. **LLM-Based Graph Transformation:** Apply structured LLM extraction (via NVIDIA NIM / Nemotron Ultra 550B & OpenAI-compatible APIs) to extract code entities, docstrings, method signatures, line boundaries, and dependency relationships.
3. **Graph Construction & Provenance:** Construct and query a property graph in Neo4j with deterministic SHA-256 entity resolution and exact source-code line provenance.
4. **Dual-Query Interface:** Implement dual-mode access: Natural-language-to-graph synthesis and read-only raw Cypher query execution.
5. **Hybrid Retrieval (Vector + Graph):** Develop a multi-stage retrieval engine linking vector embeddings (`all-MiniLM-L6-v2`) with 1- to 2-hop entity relationship expansion.
6. **Empirical Benchmarking:** Quantitatively evaluate the system against standard folder attachment and naive vector RAG across latency, token efficiency, and response fidelity.

---

## 1. System Architecture

```
┌────────────────────────────────────────────────────────┐
│           Source Codebase (Python / Multi-File)        │
│          Home Assistant Core (*.py, AST & Text)        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│      Document & AST Ingestion / Preprocessing          │
│   Chunking, Line Parsing, Deterministic SHA-256 Hash   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│        LLM-Based Graph Transformation Engine           │
│   NVIDIA NIM Nemotron / LLM Structured JSON Extraction  │
│   Extract: Files, Classes, Functions, Decorators, etc. │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               Neo4j Graph Database                     │
│  • Nodes: CodeEntity (64 nodes in pilot)               │
│  • Edges: CODE_REL (63 relations in pilot)             │
│  • Provenance: line_start, line_end, evidence_chunk    │
│  • Vector Index: chunk_embedding_index (384-dim)       │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
              ▼                            ▼
┌───────────────────────────┐┌───────────────────────────┐
│  Mode A: Natural Language ││   Mode B: Raw Cypher      │
│  Intent Translation       ││   Direct Relational       │
│  Entity Subgraph Retrieval││   Analysis & Analytics    │
└─────────────┬─────────────┘└─────────────┬─────────────┘
              │                            │
              └─────────────┬──────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│         Agent Memory Plugin (src/memory_plugin.py)     │
│   Compiles Subgraph into Compressed 1KB MEMORY.md      │
│   Auto-Loaded by AI Agents (Hermes, Cursor, etc.)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│      Grounded Response Generation / Evaluation         │
│   2.2x Lower Latency | >90% Token Reduction | 0 Halluc │
└────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Component | Technology | Version / Specification | Purpose |
|:---|:---|:---|:---|
| **Programming Language** | Python | 3.11 / 3.13 | Core pipeline and script execution |
| **Graph Database** | Neo4j Community / Docker | 5.x | Property graph storage, Cypher engine, Vector Index |
| **Extraction Model** | NVIDIA NIM / Nemotron | Ultra 550B / Open-compat | Zero-shot structured JSON extraction of code entities |
| **Embeddings** | Sentence Transformers | `all-MiniLM-L6-v2` (384-dim) | Semantic chunk vectorization for Hybrid RAG |
| **Database Driver** | Neo4j Python Driver | `neo4j>=5.0.0` | Transactional Cypher execution and MERGE operations |
| **Data Validation** | Pydantic | `>=2.0.0` | Strict schema parsing of LLM outputs |
| **CLI Wizard** | Custom Interactive Wizard | `scripts/setup.py` | REA-style 1-command environment & graph onboarding |
| **Agent Integration** | Hermes Memory Architecture | `MEMORY.md` | Persistent context injection without context window bloat |

---

## 3. Microproject Requirements & Compliance Matrix

| Requirement | Minimum Expectation | Our Implementation (`graph-memory-engine`) | Status |
|:---|:---|:---|:---:|
| **Code / Document Collection** | Real-world complex repository | Home Assistant Core (`homeassistant/homeassistant`) | **Exceeded** |
| **Entity Types** | At least 5 entity types | **11 Entity Types:** `File`, `Class`, `Function`, `Method`, `Import`, `Decorator`, `ConfigSchema`, `Service`, `Entity`, `Automation`, `Constant` | **Exceeded** |
| **Relationship Types** | At least 6 relationship types | **11 Relationship Types:** `CONTAINS`, `DEFINES`, `INHERITS`, `IMPORTS`, `CALLS`, `DECORATES`, `HAS_CONFIG`, `PROVIDES_SERVICE`, `REGISTERS_ENTITY`, `TRIGGERS_AUTOMATION`, `USES_CONSTANT` | **Exceeded** |
| **Provenance & Evidence** | Ground relations to source text | Every node/edge retains `file_path`, `line_start`, `line_end`, and code `signature` | **Full** |
| **Graph Persistence** | Persistent Neo4j database | Docker / local Neo4j (`bolt://localhost:7687`) with indexed property schema | **Full** |
| **Dual-Query Interface** | NL querying + Raw Cypher execution | **Mode A:** Natural Language query grounded via sub-graph synthesis.<br>**Mode B:** Read-only direct Cypher query executor. | **Full** |
| **Baseline Comparison** | Compare graph retrieval against baseline | Benchmarked against Full Folder Context Attachment & Vector RAG | **Full** |
| **Advanced Features** | Implement ≥2 advanced extensions | 1. Hybrid GraphRAG (Vector + Graph Hop)<br>2. Deterministic SHA-256 Entity Resolution<br>3. Agent Memory Compression (`MEMORY.md`) | **Exceeded** |
| **Reproducibility** | Clean GitHub repo + setup scripts | GitHub repository with REA-style `setup.py` onboarding wizard | **Full** |

---

## 4. Phase I — Codebase Corpus Selection & Preprocessing

### Target Corpus
- **Repository:** Home Assistant Core (`homeassistant/core`)
- **Nature of Corpus:** Highly asynchronous, event-driven, decorated Python architecture featuring components, services, config schemas, and platform lifecycle methods.
- **Competency Questions:**
  1. *What classes and functions exist in `backup_restore.py`, and how do they handle restore files?*
  2. *Which decorators are applied to specific methods across the bootstrap process?*
  3. *What external libraries and modules does a specific service import?*
  4. *What are the constants and file markers protecting against concurrent database restores?*

### Preprocessing Logic
Files are parsed programmatically, preserving relative file paths and line number indexing. Code snippets are bounded to avoid token overflow while maintaining complete syntactic blocks.

---

## 5. Phase II — Knowledge Graph Schema Design

The domain schema models software design patterns, inheritance, scoping, and decorators.

```
                              ┌───────────────────┐
                              │    File (Module)  │
                              └─────────┬─────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │ CONTAINS          │ IMPORTS           │ USES_CONSTANT
                    ▼                   ▼                   ▼
           ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
           │     Class       │ │     Import      │ │    Constant     │
           └────────┬────────┘ └─────────────────┘ └─────────────────┘
                    │
                    ├───────────────────┐
                    │ CONTAINS          │ DECORATES
                    ▼                   ▼
           ┌─────────────────┐ ┌─────────────────┐
           │ Function/Method │◀┤    Decorator    │
           └─────────────────┘ └─────────────────┘
```

### Schema Property Table

| Node Label | Key Properties | Description |
|:---|:---|:---|
| `CodeEntity` | `id`, `name`, `entity_type`, `file_path`, `line_start`, `line_end`, `signature`, `docstring` | Universal entity node representing all structural code units |
| `Chunk` | `id`, `text`, `token_count`, `embedding` | Semantic text chunk for vector similarity retrieval |
| `Document` | `source`, `total_chunks` | Source file metadata tracker |

---

## 6. Phase III — LLM-Based Entity & Relationship Extraction

### Extraction Engine (`scripts/analyze_codebase.py`)
Source code is submitted to the LLM with a strict JSON contract requiring entity classification, character/line boundaries, exact signatures, and pairwise relationships.

```python
CODE_EXTRACTION_PROMPT = """You are a precise code analysis engine for Home Assistant (Python).
Given the SOURCE CODE below, extract code entities and relationships.

Allowed entity types: File, Class, Function, Method, Import, Decorator, ConfigSchema, Service, Entity, Automation, Constant.
Allowed relation types: CONTAINS, DEFINES, INHERITS, IMPORTS, CALLS, DECORATES, HAS_CONFIG, PROVIDES_SERVICE, REGISTERS_ENTITY, TRIGGERS_AUTOMATION, USES_CONSTANT.

Rules:
- Only extract facts explicitly present in the code.
- Use canonical names (full module path for classes/functions).
- Include line_start, signature, and docstrings.
- Return ONLY valid JSON matching the schema.
"""
```

### Entity Resolution & Disambiguation
To prevent collisions and handle entities across multiple files with the same name (e.g., standard `setup()` or `__init__()` functions), every node generates a deterministic SHA-256 identifier:

$$\text{UID} = \text{SHA256}(\text{file\_path} : \text{name} : \text{type} : \text{line\_start})[0:16]$$

---

## 7. Phase IV — Neo4j Knowledge Graph Construction

Insertion is executed with transactional Cypher statements ensuring node idempotency and clean relation mapping.

```cypher
// Node Merging with Deterministic Unique Identifier
MERGE (e:CodeEntity {id: $id})
SET e.name = $name,
    e.entity_type = $entity_type,
    e.type = $entity_type,
    e.file_path = $file_path,
    e.line_start = $line_start,
    e.line_end = $line_end,
    e.signature = $signature,
    e.docstring = $docstring;

// Evidence-Aware Relationship Linking
MATCH (a:CodeEntity {id: $src_id})
MATCH (b:CodeEntity {id: $tgt_id})
MERGE (a)-[r:CODE_REL {type: $type}]->(b)
SET r.evidence_line = $line, 
    r.evidence_file = $file_path;
```

---

## 8. Phase V — Dual-Query Interface Implementation

### Mode A: Natural Language Grounded Querying
Natural language questions are resolved against the graph by identifying target files and entity clusters, querying the local sub-graph, and prompting the LLM with structured graph facts rather than raw code files.

```python
# test_real/test_our_tool_v3.py
entities = query_cypher("""
    MATCH (e:CodeEntity)
    WHERE e.file_path CONTAINS 'backup_restore'
    RETURN e.name, e.entity_type, e.signature, e.docstring, e.line_start
    ORDER BY e.line_start
""")
rels = query_cypher("""
    MATCH (a:CodeEntity)-[r:CODE_REL]->(b:CodeEntity)
    WHERE a.file_path CONTAINS 'backup_restore'
    RETURN a.name AS src, r.type AS rel, b.name AS tgt, b.entity_type AS tgt_type
""")
```

### Mode B: Raw Cypher Analytical Querying
Direct Cypher execution allows engineers to perform architectural audits:

```cypher
// Query 1: Find all classes and their applying decorators
MATCH (d:CodeEntity {entity_type: 'Decorator'})-[r:CODE_REL {type: 'DECORATES'}]->(c:CodeEntity {entity_type: 'Class'})
RETURN d.name AS Decorator, c.name AS DecoratedClass, r.evidence_line AS Line;

// Query 2: Inspect module dependencies and imported libraries
MATCH (f:CodeEntity {entity_type: 'File'})-[r:CODE_REL {type: 'IMPORTS'}]->(i:CodeEntity)
RETURN f.name AS Module, collect(i.name) AS Dependencies;
```

---

## 9. Phase VI — Advanced Extensions Implemented

1. **Hybrid GraphRAG (`src/retrieve.py`):**
   - Vector Search generates seed chunks using `sentence-transformers/all-MiniLM-L6-v2`.
   - Graph Traversal expands candidate seeds by 1–2 hops along `MENTIONS` and `CODE_REL` edges.
2. **Deterministic Entity Resolution:** Eliminates duplicate nodes across successive extractions using composite key hashing.
3. **Agent Memory Engine (`src/memory_plugin.py`):** Translates active Neo4j graph subgraphs into a unified, lightweight markdown specification (`MEMORY.md`) consumed automatically by autonomous agents at startup.
4. **Interactive Setup Wizard (`scripts/setup.py`):** Provides a 1-command REA-style CLI for instant team handoff and environment diagnostic checks.

---

## 10. Phase VII & VIII — Comprehensive Case Study: Home Assistant Core

### 10.1 Pilot Ingestion Statistics
- **Target Repository:** `homeassistant/homeassistant` (Core subset)
- **Files Processed:** `backup_restore.py`, `bootstrap.py`, `block_async_io.py`, `block_shared_serial.py`, `__init__.py`
- **Total CodeEntity Nodes Created:** **64**
- **Total CODE_REL Edges Created:** **63**
- **Total Semantic Chunk Nodes:** **218**

### 10.2 Detailed Inspection: `backup_restore.py`
The pipeline extracted 22 distinct entities and 22 relationships from `backup_restore.py`:

| Entity Name | Classified Type | Signature / Value | Provenance Line |
|:---|:---|:---|:---:|
| `backup_restore.py` | `File` | Module description | Line 1 |
| `RestoreBackupFileContent` | `Class` | `@dataclass\nclass RestoreBackupFileContent:` | Line 34 |
| `restore_backup_file_content` | `Function` | `def restore_backup_file_content(config_dir: Path)` | Line 40 |
| `RESTORE_BACKUP_FILE` | `Constant` | `".HA_RESTORE"` | Line 23 |
| `RESTORE_BACKUP_RESULT_FILE` | `Constant` | `".HA_RESTORE_RESULT"` | Line 24 |
| `KEEP_BACKUPS` | `Constant` | `("backups",)` | Line 25 |
| `KEEP_DATABASE` | `Constant` | `("home-assistant_v2.db", "home-assistant_v2.db-wal")` | Line 26 |
| `dataclasses.dataclass` | `Import` | `from dataclasses import dataclass` | Line 3 |
| `securetar` | `Import` | `import securetar` | Line 15 |
| `awesomeversion.AwesomeVersion` | `Import` | `from awesomeversion import AwesomeVersion` | Line 14 |

**Extracted Structural Edge:**
$$\text{dataclasses.dataclass} \xrightarrow{\text{DECORATES}} \text{RestoreBackupFileContent}$$

---

## 11. Phase IX — Empirical Evaluation & Benchmark Results

### 11.1 Controlled Head-to-Head Experiment
We benchmarked our Graph-Memory Engine directly against standard Brute-Force Context Attachment using the exact same prompt and LLM endpoint:
> *"Describe backup_restore.py from the Home Assistant codebase. List its main classes, functions, decorators, and key imports. Be concise but complete."*

| Metric | Baseline: Folder Attachment | Graph-Memory Engine (Our Tool) | Observed Advantage |
|:---|:---:|:---:|:---:|
| **Execution Latency** | **68.44 seconds** | **31.76 seconds** | **2.15× Faster response** |
| **Context Payload** | ~48,000 characters | **1,334 tokens** | **>90% Token Reduction** |
| **Output Token Count** | 744 tokens | 730 tokens | Equivalent output length |
| **Response Completeness** | Detailed | Detailed | Identical fidelity |
| **Hallucination Rate** | None (Source present) | None (Grounded by Graph) | Zero hallucination |

### 11.2 Key Insights
1. **Context Window Efficiency:** Passing relational graph facts instead of raw source code reduces input payload size by over 90%, preventing LLM context truncation.
2. **Speed:** Cutting context size allows faster time-to-first-token and reduces processing latency from over a minute down to ~31 seconds.
3. **Structured Accuracy:** The LLM cited exact decorators (`@dataclass`), constants (`RESTORE_BACKUP_FILE`), and function signatures directly from the graph facts without parsing messy file formatting.

---

## 12. Reproduction & Setup Guide

### Step 1: Clone Repository
```bash
git clone https://github.com/s0ham2909/graph-memory-engine.git
cd graph-memory-engine
```

### Step 2: Configure Environment
```bash
cp .env.example .env
# Set LLM_API_KEY, NEO4J_URI=bolt://localhost:7687, NEO4J_PASSWORD=changeme123
```

### Step 3: Launch Neo4j
```bash
docker compose up -d
```

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Run Setup Wizard & Verify
```bash
python scripts/setup.py
# Select Option 1 to reuse verified pilot graph, or Option 2 to extract new files.
```

### Step 6: Execute Benchmark
```bash
python test_real/test_folder_attach.py
python test_real/test_our_tool_v3.py
```
