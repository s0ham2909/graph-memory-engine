"""L6 – Evaluation utilities: compare retrieval strategies."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.llm import call_llm

logger = logging.getLogger(__name__)


@dataclass
class EvalCase:
    """A single evaluation question."""

    id: str
    question: str
    expected_entity_types: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of one evaluation run."""

    case_id: str
    strategy: str
    answer: str
    context_tokens: int
    entity_coverage: float = 0.0  # fraction of expected types found


def load_gold_questions(path: Path | str = "data/gold_questions.json") -> list[EvalCase]:
    """Load evaluation questions from JSON."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [EvalCase(**item) for item in data]


def count_tokens(text: str) -> int:
    """Rough token count (whitespace split). Replace with tiktoken if needed."""
    return len(text.split())


def evaluate_entity_coverage(
    answer: str,
    expected_types: list[str],
    entities_found: list[dict[str, Any]],
) -> float:
    """Fraction of expected entity types that appear in the retrieved entities."""
    if not expected_types:
        return 1.0
    found_types = {e.get("type", "") for e in entities_found}
    matched = sum(1 for t in expected_types if t in found_types)
    return matched / len(expected_types)
