"""Hermes Memory Plugin: exports Neo4j code graph + docs into MEMORY.md format for agent context."""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any
from neo4j import GraphDatabase


@dataclass
class Settings:
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "changeme123")
    output_path: str = os.getenv("MEMORY_OUTPUT", "MEMORY.md")


def get_driver():
    return GraphDatabase.driver(Settings.neo4j_uri, auth=(Settings.neo4j_user, Settings.neo4j_password))


def query_cypher(cypher: str, **params) -> list[dict]:
    driver = get_driver()
    try:
        with driver.session() as s:
            r = s.run(cypher, **params)
            return [dict(rec) for rec in r]
    finally:
        driver.close()


def build_memory_md() -> str:
    lines = [
        "# Project Memory: Home Assistant Core",
        "",
        "Auto-generated from Neo4j knowledge graph. Updated on import.",
        "",
    ]

    # --- MODULES (Files) ---
    files = query_cypher("""
        MATCH (e:CodeEntity {type: 'File'})
        RETURN e.name AS name, e.file_path AS path, e.docstring AS doc
        ORDER BY e.name
    """)
    if files:
        lines.append("## Modules")
        lines.append("")
        for f in files[:100]:  # cap for readability
            doc = (f.get("doc") or "").strip()
            if len(doc) > 160:
                doc = doc[:157] + "..."
            lines.append(f"- **{f['name']}** — {doc or 'No docstring'}")
        lines.append("")

    # --- KEY CLASSES ---
    classes = query_cypher("""
        MATCH (e:CodeEntity {type: 'Class'})
        RETURN e.name AS name, e.file_path AS path, e.signature AS sig, e.docstring AS doc
        ORDER BY e.name
    """)
    if classes:
        lines.append("## Key Classes")
        lines.append("")
        for c in classes[:80]:
            sig = (c.get("sig") or "").strip()
            doc = (c.get("doc") or "").strip()
            if len(doc) > 120:
                doc = doc[:117] + "..."
            lines.append(f"- **{c['name']}** (`{c['path']}`){': ' + sig if sig else ''} — {doc or 'No docstring'}")
        lines.append("")

    # --- SERVICES ---
    services = query_cypher("""
        MATCH (e:CodeEntity {type: 'Service'})
        RETURN e.name AS name, e.file_path AS path, e.signature AS sig, e.docstring AS doc
        ORDER BY e.name
    """)
    if services:
        lines.append("## Services")
        lines.append("")
        for s in services[:50]:
            doc = (s.get("doc") or "").strip()
            if len(doc) > 120:
                doc = doc[:117] + "..."
            lines.append(f"- **{s['name']}** — {doc or 'No docstring'}")
        lines.append("")

    # --- ENTITIES ---
    entities = query_cypher("""
        MATCH (e:CodeEntity {type: 'Entity'})
        RETURN e.name AS name, e.file_path AS path, e.signature AS sig, e.docstring AS doc
        ORDER BY e.name
    """)
    if entities:
        lines.append("## Entities")
        lines.append("")
        for e in entities[:50]:
            doc = (e.get("doc") or "").strip()
            if len(doc) > 120:
                doc = doc[:117] + "..."
            lines.append(f"- **{e['name']}** — {doc or 'No docstring'}")
        lines.append("")

    # --- AUTOMATIONS ---
    autos = query_cypher("""
        MATCH (e:CodeEntity {type: 'Automation'})
        RETURN e.name AS name, e.file_path AS path, e.signature AS sig, e.docstring AS doc
        ORDER BY e.name
    """)
    if autos:
        lines.append("## Automations")
        lines.append("")
        for a in autos[:30]:
            doc = (a.get("doc") or "").strip()
            if len(doc) > 120:
                doc = doc[:117] + "..."
            lines.append(f"- **{a['name']}** — {doc or 'No docstring'}")
        lines.append("")

    # --- DECORATORS / CONFIG PATTERNS ---
    decorators = query_cypher("""
        MATCH (e:CodeEntity {type: 'Decorator'})
        RETURN e.name AS name, e.file_path AS path, e.signature AS sig, e.docstring AS doc
        ORDER BY e.name
    """)
    configs = query_cypher("""
        MATCH (e:CodeEntity {type: 'ConfigSchema'})
        RETURN e.name AS name, e.file_path AS path, e.signature AS sig, e.docstring AS doc
        ORDER BY e.name
    """)
    if decorators or configs:
        lines.append("## Decorators & Config Schemas")
        lines.append("")
        for d in decorators[:30]:
            doc = (d.get("doc") or "").strip()
            if len(doc) > 120:
                doc = doc[:117] + "..."
            lines.append(f"- **@{d['name']}** — {doc or 'No docstring'}")
        for c in configs[:20]:
            doc = (c.get("doc") or "").strip()
            if len(doc) > 120:
                doc = doc[:117] + "..."
            lines.append(f"- **CONFIG_SCHEMA: {c['name']}** — {doc or 'No docstring'}")
        lines.append("")

    # --- RELATIONSHIP SUMMARY ---
    rels = query_cypher("""
        MATCH (a:CodeEntity)-[r:CODE_REL]->(b:CodeEntity)
        RETURN r.type AS type, count(*) AS cnt
        ORDER BY cnt DESC
    """)
    if rels:
        lines.append("## Relationship Summary")
        lines.append("")
        for r in rels:
            lines.append(f"- **{r['type']}**: {r['cnt']}")
        lines.append("")

    # --- DOCUMENT CHUNKS (Hermes ingest) ---
    chunks = query_cypher("""
        MATCH (d:Document)<-[:PART_OF]-(c:Chunk)
        RETURN d.source AS source, count(c) AS chunks, sum(c.token_count) AS tokens
        ORDER BY tokens DESC
    """)
    if chunks:
        lines.append("## Ingested Documents (Vector RAG)")
        lines.append("")
        for c in chunks:
            lines.append(f"- **{c['source']}**: {c['chunks']} chunks, ~{c['tokens']} tokens")
        lines.append("")

    lines.append("---")
    lines.append("*End of memory export*")
    return "\n".join(lines)


def write_memory(output_path: str | None = None) -> str:
    out = Path(output_path or Settings().output_path)
    md = build_memory_md()
    out.write_text(md, encoding="utf-8")
    print(f"✓ Wrote memory to {out} ({len(md)} chars)")
    return md


if __name__ == "__main__":
    write_memory()