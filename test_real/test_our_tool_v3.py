#!/usr/bin/env python3
"""Test our tool v3: queries CodeEntity graph with full detail."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import call_llm_structured
from src.memory_plugin import write_memory, query_cypher

PROMPT = (
    "Describe backup_restore.py from the Home Assistant codebase. "
    "List its main classes, functions, decorators, and key imports. "
    "Be concise but complete."
)

def main():
    project_root = Path(__file__).resolve().parent.parent
    write_memory(output_path=str(project_root / "MEMORY.md"))
    
    memory_path = project_root / "MEMORY.md"
    memory_text = memory_path.read_text(encoding="utf-8")
    print(f"MEMORY.md: {len(memory_text)} chars")
    
    # Query CodeEntity graph with full detail
    entities = query_cypher("""
        MATCH (e:CodeEntity)
        WHERE e.file_path CONTAINS 'backup_restore'
        RETURN e.name AS name, e.entity_type AS type, 
               e.signature AS sig, e.docstring AS doc, e.line_start AS line
        ORDER BY e.line_start, e.name
    """)
    
    rels = query_cypher("""
        MATCH (a:CodeEntity)-[r:CODE_REL]->(b:CodeEntity)
        WHERE a.file_path CONTAINS 'backup_restore' 
           OR b.file_path CONTAINS 'backup_restore'
        RETURN a.name AS src, r.type AS rel, b.name AS tgt, b.entity_type AS tgt_type
        LIMIT 30
    """)
    
    # Build detailed entity text
    entity_lines = []
    for e in entities:
        sig = e.get('sig') or ''
        doc = e.get('doc') or ''
        line = e.get('line') or ''
        entity_lines.append(f"  {e['type']}: {e['name']} (line {line})")
        if sig:
            entity_lines.append(f"    Signature: {sig}")
        if doc:
            entity_lines.append(f"    Doc: {doc}")
    
    rel_lines = [f"  {r['src']} → {r['rel']} → {r['tgt']} ({r['tgt_type']})" for r in rels]
    
    print(f"Found {len(entities)} entities, {len(rels)} relations")
    
    combined_context = (
        f"PROJECT MEMORY:\n{memory_text}\n\n"
        f"BACKUP_RESTORE.PY ENTITIES (from Neo4j graph):\n" + "\n".join(entity_lines) + "\n\n"
        f"RELATIONS:\n" + "\n".join(rel_lines)
    )
    
    full_prompt = f"CONTEXT:\n{combined_context}\n\n{PROMPT}"
    
    start = time.perf_counter()
    result = call_llm_structured(
        prompt=full_prompt,
        system="You are a precise code analyst. Answer based only on provided context.",
        use_cache=False,
        max_tokens=2000,
    )
    elapsed = time.perf_counter() - start
    
    prompt_tokens = getattr(result, 'prompt_tokens', 'N/A')
    completion_tokens = getattr(result, 'completion_tokens', 'N/A')
    
    print(f"\n=== OUR TOOL V3 RESULT (Full Graph Detail) ===")
    print(f"Latency: {elapsed:.2f}s")
    print(f"Prompt tokens: {prompt_tokens}")
    print(f"Completion tokens: {completion_tokens}")
    print(f"Answer:\n{result.text}")

if __name__ == "__main__":
    main()