"""L1 – Load, clean, and chunk source documents."""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A text chunk with metadata."""

    id: str
    text: str
    source: str
    doc_id: str
    index: int
    session_id: str = ""
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extraction_status: str = "pending"   # pending | done | failed
    extraction_error: str = ""


@dataclass
class Document:
    """A loaded source document."""

    id: str
    source: str
    date: str
    raw_text: str
    chunks: list[Chunk] = field(default_factory=list)


def _clean(text: str) -> str:
    """Normalize whitespace and strip control chars."""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[^\S\n]+", " ", text)  # collapse horizontal whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excessive newlines
    return text.strip()


def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping windows by character count."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def load_file(path: Path, session_id: str = "") -> Document:
    """Load a single file and split into chunks."""
    cfg = get_settings()
    raw = path.read_text(encoding="utf-8", errors="replace")
    cleaned = _clean(raw)
    doc_id = uuid.uuid5(uuid.NAMESPACE_URL, str(path)).hex
    doc = Document(
        id=doc_id,
        source=str(path),
        date=datetime.now(timezone.utc).isoformat(),
        raw_text=cleaned,
    )
    parts = _chunk_text(cleaned, cfg.chunk_size, cfg.chunk_overlap)
    for i, part in enumerate(parts):
        chunk_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{i}").hex
        doc.chunks.append(
            Chunk(
                id=chunk_id,
                text=part,
                source=str(path),
                doc_id=doc_id,
                index=i,
                session_id=session_id,
            )
        )
    logger.info("Loaded %s → %d chunks", path.name, len(doc.chunks))
    return doc


def load_directory(directory: Path, session_id: str = "") -> list[Document]:
    """Load all .md and .txt files from a directory."""
    docs: list[Document] = []
    for p in sorted(directory.glob("*")):
        if p.suffix.lower() in {".md", ".txt"}:
            docs.append(load_file(p, session_id=session_id))
    logger.info("Loaded %d documents from %s", len(docs), directory)
    return docs


def load_text(text: str, source: str, session_id: str = "") -> Document:
    """Split in-memory text into chunks using the configured chunk settings."""
    cfg = get_settings()
    cleaned = _clean(text)
    doc_id = uuid.uuid5(uuid.NAMESPACE_URL, source).hex
    doc = Document(
        id=doc_id,
        source=source,
        date=datetime.now(timezone.utc).isoformat(),
        raw_text=cleaned,
    )
    parts = _chunk_text(cleaned, cfg.chunk_size, cfg.chunk_overlap)
    for i, part in enumerate(parts):
        chunk_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{i}").hex
        doc.chunks.append(
            Chunk(
                id=chunk_id,
                text=part,
                source=source,
                doc_id=doc_id,
                index=i,
                session_id=session_id,
            )
        )
    logger.info("Loaded %s -> %d chunks", Path(source).name, len(doc.chunks))
    return doc
