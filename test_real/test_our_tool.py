#!/usr/bin/env python3
"""Test our tool: uses hybrid_retrieve() from Neo4j + MEMORY.md, measures tokens/latency."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import call_llm_structured
from src.memory_plugin import write_memory
from src.retrieve import hybrid_retrieve
from src.embeddings import embed_text

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
    
    # Run hybrid retrieval for backup_restore
    print("Running hybrid_retrieve for 'backup_restore'...")
    query_emb = embed_text("backup_restore")
    retrieved = hybrid_retrieve(query_emb, top_k=5)
    seed_chunks = retrieved.seed_chunks
    entities = retrieved.entities
    related_chunks = retrieved.related_chunks
    
    retrieved_text = "\n\n".join([f"[Chunk {c['id'][:8]}] {c['text'][:500]}" for c in seed_chunks + related_chunks])
    entity_text = "\n".join([f"  {e['name']} ({e['type']})" for e in entities])
    print(f"Retrieved {len(seed_chunks)} seed chunks, {len(entities)} entities, {len(related_chunks)} related chunks")
    
    # Combine memory + retrieved chunks
    combined_context = f"PROJECT MEMORY:\n{memory_text}\n\nRETRIEVED CHUNKS:\n{retrieved_text}\n\nENTITIES:\n{entity_text}"
    
    messages = [
        {"role": "system", "content": "You are a precise code analyst. Answer based only on provided context."},
        {"role": "user", "content": f"CONTEXT:\n{combined_context}\n\n{PROMPT}"}
    ]
    
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
    
    print(f"\n=== OUR TOOL RESULT ===")
    print(f"Latency: {elapsed:.2f}s")
    print(f"Prompt tokens: {prompt_tokens}")
    print(f"Completion tokens: {completion_tokens}")
    print(f"Answer:\n{result.text}")

if __name__ == "__main__":
    main()