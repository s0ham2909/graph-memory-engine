"""L5 – Generate answers with chunk citations from retrieval context."""

import logging
from typing import Any

from src.llm import call_llm
from src.retrieve import RetrievalResult

logger = logging.getLogger(__name__)

ANSWER_SYSTEM = """You are a knowledge-graph-augmented assistant.
Answer the user question using ONLY the context provided.
Cite sources using [chunk:<id>] notation.
If the context is insufficient, say so."""


def _build_context(result: RetrievalResult) -> str:
    """Format retrieval results into a text context block."""
    parts: list[str] = []

    parts.append("== Seed Chunks (vector search) ==")
    for ch in result.seed_chunks:
        parts.append(f"[chunk:{ch['id'][:8]}] (score={ch.get('score', '?'):.3f})")
        parts.append(ch["text"])
        parts.append("")

    if result.entities:
        parts.append("== Entities ==")
        for e in result.entities:
            parts.append(f"- {e['name']} ({e['type']}): {e.get('description', '')}")
        parts.append("")

    if result.subgraph_triples:
        parts.append("== Relationships ==")
        for t in result.subgraph_triples:
            parts.append(f"- {t['source']} --[{t['rel_type']}]--> {t['target']}")
        parts.append("")

    if result.related_chunks:
        parts.append("== Related Chunks (graph expansion) ==")
        for ch in result.related_chunks:
            parts.append(
                f"[chunk:{ch['id'][:8]}] (via {ch.get('via_entity', '?')})"
            )
            parts.append(ch["text"])
            parts.append("")

    return "\n".join(parts)


def generate_answer(question: str, retrieval: RetrievalResult) -> str:
    """Generate a cited answer from retrieval results."""
    context = _build_context(retrieval)
    prompt = f"Context:\n{context}\n\nQuestion: {question}"
    answer = call_llm(prompt, system=ANSWER_SYSTEM)
    logger.info("Generated answer (%d chars) for: %s", len(answer), question[:60])
    return answer
