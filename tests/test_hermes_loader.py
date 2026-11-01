"""Unit tests for src/hermes_loader.py."""

import pytest
from pathlib import Path
import tempfile
import sqlite3

from src.hermes_loader import (
    redact,
    discover_sqlite_schema,
    load_sqlite_documents,
    load_hermes_documents,
    scan_redacted_chunks,
    dry_run,
)
from src.ingest import load_file, Document, Chunk


def test_redact_api_key():
    # The pattern redacts the entire "key=value" including the key name
    assert redact("api_key=***") == "***REDACTED***"


def test_redact_bearer():
    assert redact("Authorization: Bearer abc.def.ghi") == "Authorization: Bearer ***REDACTED***"


def test_redact_email():
    assert redact("user@example.com") == "***REDACTED_EMAIL***"


def test_redact_secret_patterns():
    text = (
        "AIza" + "A" * 30 + " sk-secret1234 ghp_" + "A" * 30
        + " Bearer sampletoken password=hunter2 token='abc123' "
        + "GEMINI_API_KEY=private-key NEO4J_PASSWORD=private-password "
        + "user@example.com " + "a" * 32
    )
    redacted = redact(text)
    assert "AIza" not in redacted
    assert "sk-secret1234" not in redacted
    assert "ghp_" not in redacted
    assert "sampletoken" not in redacted
    assert "hunter2" not in redacted
    assert "abc123" not in redacted
    assert "private-key" not in redacted
    assert "private-password" not in redacted
    assert "user@example.com" not in redacted
    assert "a" * 32 not in redacted


def test_scan_redacted_chunks_counts_unredacted_patterns():
    results = scan_redacted_chunks(["email user@example.com and password=hunter2"])
    assert results["email addresses"]["count"] == 1
    assert results["credential assignments"]["count"] == 1
    context = results["email addresses"]["contexts"][0]
    assert len(context) <= 40
    assert "user@example.com" in context


def test_discover_sqlite_schema(tmp_path):
    p = tmp_path / "state_copy.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE users(id INTEGER, name TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice')")
    conn.execute("CREATE TABLE events(id TEXT, ts TEXT)")
    conn.commit()
    conn.close()
    schema = discover_sqlite_schema(p)
    assert set(schema.keys()) >= {"users", "events"}
    assert schema["users"] == ["id", "name"]
    assert schema["events"] == ["id", "ts"]


def test_load_sqlite_documents(tmp_path):
    p = tmp_path / "state_copy.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE sessions(id TEXT, role TEXT)")
    conn.execute("INSERT INTO sessions VALUES ('s1', 'main')")
    conn.commit()
    conn.close()
    docs = list(load_sqlite_documents(p))
    assert len(docs) == 1
    assert docs[0]["role"] == "db_row"


def test_load_hermes_with_fixture(tmp_path):
    memory = tmp_path / "MEMORY.md"
    memory.write_text("# Hello\nmy api key is xyz.\nuser@host.com\n", encoding="utf-8")
    docs = list(load_hermes_documents(tmp_path))
    assert len(docs) == 1
    d = docs[0]
    assert d["role"] == "memory"
    # Redaction happened in loader
    assert "xyz" not in d["text"] or "REDACTED" in d["text"]
    assert "user@host.com" not in d["text"]


def test_session_id_inferred():
    """Documents carry session_id."""
    doc = {
        "source": "/tmp/X.md",
        "session_id": "hermes",
        "timestamp": "",
        "role": "memory",
        "text": "x",
    }
    assert doc["session_id"] == "hermes"


def test_load_file_builds_chunks(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("a" * 200, encoding="utf-8")
    doc = load_file(p, session_id="test-sess")
    assert isinstance(doc, Document)
    assert len(doc.chunks) > 0
    first = doc.chunks[0]
    assert first.index == 0
    assert first.session_id == "test-sess"


def test_dry_run_scans_redacted_database_and_markdown_chunks(tmp_path):
    (tmp_path / "MEMORY.md").write_text("api_key=markdown-secret", encoding="utf-8")
    db_path = tmp_path / "state_copy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE secrets(value TEXT)")
    conn.execute("INSERT INTO secrets VALUES ('password=database-secret')")
    conn.commit()
    conn.close()

    result = dry_run(data_dir=tmp_path, db_path=db_path, scan_secrets=True)

    assert result["documents"] == 2
    assert result["chunks"] >= 2
    assert all(scan["count"] == 0 for scan in result["secret_scan"].values())
    sample_text = " ".join(sample["chunk_text_redacted"] for sample in result["redacted_samples"])
    assert "markdown-secret" not in sample_text
    assert "database-secret" not in sample_text
