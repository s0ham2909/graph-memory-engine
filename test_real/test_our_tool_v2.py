#!/usr/bin/env python3
"""Test our tool v2: queries CodeEntity graph directly (no hybrid_retrieve)."""
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
    # Ensure MEMORY.md is fresh
    print("Regenerating MEMORY.md from Neo4j...")
    project_root = Path(__file__).resolve().parent.parent
    write_memory(output_path=str(project_root / "MEMORY.md"))
    
    # Read MEMORY.md
    memory_path = project_root / "MEMORY.md"
    memory_text = memory_path.read_text(encoding="utf-8")
    print(f"MEMORY.md: {len(memory_text)} chars")
    
    # Query CodeEntity graph directly for backup_restore.py
    print("Querying CodeEntity graph for backup_restore.py...")
    entities = query_cypher("""
        MATCH (e:CodeEntity)
        WHERE e.file_path CONTAINS 'backup_restore'
           OR e.name CONTAINS 'backup_restore'
        RETURN e.id AS id, e.name AS name, e.entity_type AS type, 
               e.file_path AS path, e.signature AS sig, e.docstring AS doc
        ORDER BY e.name
    """)
    
    rels = query_cypher("""
        MATCH (a:CodeEntity)-[r:CODE_REL]->(b:CodeEntity)
        WHERE a.file_path CONTAINS 'backup_restore' 
           OR b.file_path CONTAINS 'backup_restore'
        RETURN a.name AS src, r.type AS rel, b.name AS tgt, b.entity_type AS tgt_type
        LIMIT 30
    """)
    
    entity_text = "\n".join([
        f"  {e['name']} ({e['type']})" + (f": {e['sig']}" if e.get('sig') else "")
        for e in entities
    ])
    rel_text = "\n".join([
        f"  {r['src']} → {r['rel']} → {r['tgt']} ({r['tgt_type']})"
        for r in rels
    ])
    
    print(f"Found {len(entities)} entities, {len(rels)} relations")
    
    # Combine memory + direct graph query
    combined_context = f"PROJECT MEMORY:\n{memory_text}\n\nBACKUP_RESTORE ENTITIES:\n{entity_text}\n\nRELATIONS:\n{rel_text}"
    
    start = time.perf_counter()
    result = call_llm_structured(
        prompt=PROMPT,
        system="You are a precise code analyst. Answer based only on provided context.",
        use_cache=False,
        max_tokens=2000,
    )
    elapsed = time.perf_counter() - start
    
    prompt_tokens = getattr(result, 'prompt_tokens', 'N/A')
    completion_tokens = getattr(result, 'completion_tokens', 'N/A')
    
    print(f"\n=== OUR TOOL V2 RESULT (Direct Graph Query) ===")
    print(f"Latency: {elapsed:.2f}s")
    print(f"Prompt tokens: {prompt_tokens}")
    print(f"Completion tokens: {completion_tokens}")
    print(f"Answer:\n{result.text}")

if __name__ == "__main__":
    main()