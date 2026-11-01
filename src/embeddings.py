"""Embedding generation via sentence-transformers."""

import logging
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)

_model: Any = None


def get_model() -> Any:
    """Return a singleton SentenceTransformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        cfg = get_settings()
        logger.info("Loading embedding model: %s", cfg.embedding_model)
        _model = SentenceTransformer(cfg.embedding_model)
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single string and return a list of floats."""
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings efficiently."""
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    return [e.tolist() for e in embeddings]