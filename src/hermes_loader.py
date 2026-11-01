"""Hermes data loader: MEMORY.md, USER.md, read-only SQLite + redaction."""

import argparse
import sqlite3
import logging
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterator, Any

logger = logging.getLogger(__name__)

REDACT_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[^\s\n]+"), r"\1***REDACTED***"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), "***REDACTED_GOOGLE_KEY***"),
    (re.compile(r"\bsk-[0-9A-Za-z_-]{8,}"), "***REDACTED_API_KEY***"),
    (re.compile(r"\bghp_[0-9A-Za-z]{20,}"), "***REDACTED_GITHUB_TOKEN***"),
    (re.compile(r"[\w.+-]+@[\w.-]+\.\w+"), "***REDACTED_EMAIL***"),
    (re.compile(r"(?i)((?:api[_-]?key|secret|token|password)\s*[:=]\s*)"), r"\1***REDACTED***"),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "***REDACTED_HEX***"),
    (re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"), "***REDACTED_BASE64***"),
]

def redact(text: str) -> str:
    """Redact secrets in a single pass, longest patterns first to avoid overlap."""
    # Sort patterns by expected match length (longer first) to avoid partial overlaps
    # Specific token patterns first
    patterns = [
        (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), "***REDACTED_GOOGLE_KEY***"),
        (re.compile(r"\bsk-[0-9A-Za-z_-]{8,}"), "***REDACTED_API_KEY***"),
        (re.compile(r"\bghp_[0-9A-Za-z]{20,}"), "***REDACTED_GITHUB_TOKEN***"),
        (re.compile(r"[\w.+-]+@[\w.-]+\.\w+"), "***REDACTED_EMAIL***"),
        # Credential assignments - match the whole "key=value" pattern
        (re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*[^\s,;]+"), "***REDACTED***"),
        (re.compile(r"(?i)(bearer\s+)[^\s\n]+"), r"\1***REDACTED***"),
        # Generic long strings (hex, base64) - apply last
        (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "***REDACTED_HEX***"),
        (re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"), "***REDACTED_BASE64***"),
    ]
    for pat, repl in patterns:
        text = pat.sub(repl, text)
    return text

def load_sqlite_documents(db_path: Path, session_id: str = "hermes") -> Iterator[dict[str, Any]]:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        for t in tables:
            cursor.execute(f"SELECT * FROM {t} LIMIT 100")
            rows = cursor.fetchall()
            lines = [f"Table: {t}", f"Rows: {len(rows)}"]
            for row in rows:
                lines.append(" | ".join(str(c) for c in row if c is not None))
            yield {
                "source": str(db_path),
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": "db_row",
                "text": "\n".join(lines),
            }
    finally:
        conn.close()

def load_session_documents(
    db_path: Path, session_ids: list[str], *, roles=("user","assistant"),
    max_message_chars=4000, chunk_char=2800, overlap_char=200,
) -> Iterator[dict[str, Any]]:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.cursor()
        for sid in session_ids:
            cursor.execute(
                "SELECT content, role, timestamp FROM messages WHERE session_id=? ORDER BY timestamp ASC",
                (sid,))
            rows = cursor.fetchall()
            filtered = [(c, r, ts) for c, r, ts in rows if r in roles]
            truncated = []
            for c, r, ts in filtered:
                if c is None: continue
                text = c
                if len(text) > max_message_chars:
                    text = text[:max_message_chars] + "[truncated]"
                truncated.append((text, r, ts))
            # Merge messages but do NOT chunk here; load_text handles chunking
            merged_text = "\n".join(text for text, _, _ in truncated)
            yield {
                "source": sid,
                "session_id": sid,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": "merged",
                "text": merged_text,
            }
    finally:
        conn.close()

if __name__ == "__main__":
    print("hermes_loader.py rebuilt with load_session_documents")

def load_hermes_documents(data_dir: Path | None = None) -> Iterator[dict[str, Any]]:
    if data_dir is None:
        data_dir = Path(os.getenv("HERMES_DATA_DIR", "data/raw/hermes"))
    data_dir = Path(data_dir)
    for fname in ("MEMORY.md", "USER.md"):
        p = data_dir / fname
        if p.exists():
            raw = p.read_text(encoding="utf-8", errors="replace")
            redacted = redact(raw)
            yield {
                "source": str(p),
                "session_id": "hermes",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": "memory" if fname == "MEMORY.md" else "user",
                "text": redacted,
            }
            logger.info("Loaded %s -> %d chars (redacted)", fname, len(redacted))

def discover_sqlite_schema(db_path: Path) -> dict[str, list[str]]:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        schema: dict[str, list[str]] = {}
        for t in tables:
            cursor.execute(f"PRAGMA table_info({t})")
            cols = [row[1] for row in cursor.fetchall() if row[1]]
            schema[t] = cols
    finally:
        conn.close()
    return schema

SECRET_SCAN_PATTERNS = [
    ("Google API keys", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}")),
    ("sk- keys", re.compile(r"\bsk-[0-9A-Za-z_-]{8,}")),
    ("GitHub tokens", re.compile(r"\bghp_[0-9A-Za-z]{20,}")),
    ("Bearer credentials", re.compile(r"(?i)\bBearer\s+[^\s,;]+")),
    ("credential assignments", re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*(?!.*REDACTED)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)")),
    ("email addresses", re.compile(r"[\w.+-]+@[\w.-]+\.\w+")),
    ("long hex strings", re.compile(r"\b[0-9a-fA-F]{32,}\b")),
]

def scan_redacted_chunks(chunks: list[str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, pattern in SECRET_SCAN_PATTERNS:
        contexts = []
        for text in chunks:
            for match in pattern.finditer(text):
                s = max(0, match.start() - 20)
                e = min(len(text), s + 40)
                s = max(0, e - 40)
                contexts.append(text[s:e].replace("\n", " "))
        results[name] = {"count": len(contexts), "contexts": contexts}
    return results

def dry_run(data_dir: Path | None = None, db_path: Path | None = None, scan_secrets: bool = False) -> dict:
    if data_dir is None:
        data_dir = Path(os.getenv("HERMES_DATA_DIR", "data/raw/hermes"))
    docs = list(load_hermes_documents(data_dir))
    if db_path is None:
        db_path = data_dir / "state_copy.db"
    schema = {}
    if db_path.exists():
        schema = discover_sqlite_schema(db_path)
        docs += list(load_sqlite_documents(db_path))
    chunks = 0
    samples = []
    all_chunk_texts = []
    for d in docs:
        redacted_text = redact(d["text"])
        from src.ingest import Document
        doc_obj = Document(id=d["source"], source=d["source"], date=d["timestamp"], raw_text=redacted_text)
        doc_obj.chunks = []
        start = 0
        while start < len(redacted_text):
            end = min(start + 512, len(redacted_text))
            doc_obj.chunks.append(
                type("Chunk", (), {
                    "id": f"{start}",
                    "text": redacted_text[start:end],
                    "source": str(d.get("source", "")),
                    "doc_id": d["source"],
                    "index": len(doc_obj.chunks),
                    "session_id": d.get("session_id", ""),
                    "ts": d.get("timestamp", ""),
                })()
            )
            start += 448
        chunks += len(doc_obj.chunks)
        all_chunk_texts.extend(c.text for c in doc_obj.chunks)
        for c in doc_obj.chunks[:1]:
            if len(samples) < 3:
                samples.append({"source": d["source"], "chunk_text_redacted": c.text[:300], "chunk_id": c.id[:8]})
    result = {
        "data_dir": str(data_dir),
        "db_path": str(db_path) if db_path.exists() else "NOT FOUND",
        "sqlite_schema": schema,
        "documents": len(docs),
        "chunks": chunks,
        "redacted_samples": samples,
    }
    if scan_secrets:
        result["secret_scan"] = scan_redacted_chunks(all_chunk_texts)
    return result
