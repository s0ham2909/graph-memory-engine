"""L2 – LLM-based entity and relation extraction from chunks."""

import json
import logging
from dataclasses import dataclass, field

from src.llm import call_llm

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a precise information-extraction engine.
Given the TEXT below, extract entities and relationships.

Allowed entity types: Project, Decision, Concept, Tool, Person, Task.
Allowed relation types: DEPENDS_ON, DECIDED_OVER, CAUSED_BY, PART_OF, USES, SUPERSEDES.
Only include facts stated explicitly in the text. Use one canonical name per entity.
Include a short evidence quote (<20 words) for each relation.
Return ONLY JSON matching this schema (no markdown, no explanation):
{
  "entities": [{"name":"...","type":"...","aliases":[],"description":"..."}],
  "relations": [{"source":"...","target":"...","type":"...","evidence_quote":"..."}]
}

TEXT:
{text}
"""


@dataclass
class ExtractedEntity:
    name: str
    type: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ExtractedRelation:
    source: str
    target: str
    type: str
    evidence_chunk_id: str = ""
    evidence_quote: str = ""


@dataclass
class ExtractionResult:
    chunk_id: str
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    status: str = "pending"   # pending | done | failed
    error_text: str = ""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0] if "```" in text else text
    return text.strip()


def extract_from_chunk(chunk_id: str, text: str) -> ExtractionResult:
    """Run LLM extraction on a single chunk with structured output + retry."""
    result = ExtractionResult(chunk_id=chunk_id, status="pending")
    prompt = EXTRACTION_PROMPT.format(text=text)
    try:
        raw = call_llm(prompt, system="You must return valid JSON only.")
        cleaned = _strip_fences(raw)
        data = json.loads(cleaned)
        if not isinstance(data, dict) or "entities" not in data or "relations" not in data:
            raise ValueError("Missing entities/relations keys")
        for e in data.get("entities", []):
            result.entities.append(ExtractedEntity(
                name=e.get("name", ""),
                type=e.get("type", ""),
                aliases=e.get("aliases", []),
                description=e.get("description", ""),
            ))
        for r in data.get("relations", []):
            result.relations.append(ExtractedRelation(
                source=r.get("source", ""),
                target=r.get("target", ""),
                type=r.get("type", ""),
                evidence_chunk_id=chunk_id,
                evidence_quote=r.get("evidence_quote", "")[:20],
            ))
        result.status = "done"
        return result
    except Exception as exc:
        error_msg = f"Attempt 1 failed: {exc}"
        logger.warning("Chunk %s %s", chunk_id[:8], error_msg)
        try:
            retry_prompt = (
                f"Your previous JSON was invalid: {exc}.\n"
                f"Correct it and return ONLY valid JSON (no markdown):\n{cleaned[:500]}"
            )
            raw2 = call_llm(retry_prompt, system="Return valid JSON only.")
            cleaned2 = _strip_fences(raw2)
            data = json.loads(cleaned2)
            if not isinstance(data, dict) or "entities" not in data:
                raise ValueError("Still invalid after retry")
            for e in data.get("entities", []):
                result.entities.append(ExtractedEntity(
                    name=e.get("name", ""),
                    type=e.get("type", ""),
                    aliases=e.get("aliases", []),
                    description=e.get("description", ""),
                ))
            for r in data.get("relations", []):
                result.relations.append(ExtractedRelation(
                    source=r.get("source", ""),
                    target=r.get("target", ""),
                    type=r.get("type", ""),
                    evidence_chunk_id=chunk_id,
                    evidence_quote=r.get("evidence_quote", "")[:20],
                ))
            result.status = "done"
            return result
        except Exception as exc2:
            result.status = "failed"
            result.error_text = f"Attempt 2 failed: {exc2}; attempt 1: {exc}"
            logger.error("Chunk %s FAILED: %s", chunk_id[:8], result.error_text)
            return result
