"""KGIRS pipeline: ingest (no LLM) and extract (LLM) stages."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings
from src.ingest import load_directory, Document, Chunk
from src.extract import extract_from_chunk, ExtractionResult
from src.graph import store_document, store_chunk, store_extraction
from src.embeddings import embed_batch
from src.retrieve import hybrid_retrieve
from src.answer import generate_answer
from src.db import get_driver, close, get_session
from src.hermes_loader import load_hermes_documents, load_session_documents

logger = logging.getLogger(__name__)

PROGRESS_FILE = Path("results/progress.json")


def _load_progress() -> set[str]:
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text()).get("chunk_ids", []))
    return set()


def _save_progress(chunk_ids: set[str], max_calls: int | None, completed: int, message: str) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps({
            "chunk_ids": list(chunk_ids),
            "max_calls": max_calls,
            "completed_calls": completed,
            "message": message,
        }),
        encoding="utf-8",
    )


def _docs_from_hermes(data_dir: Path | None = None, session_ids: list[str] | None = None) -> list[Document]:
    """Load documents via Hermes loader (session-aware), convert to Document+Chunk objects."""
    if data_dir is None:
        data_dir = Path("data/raw/hermes")
    db_path = data_dir / "state_copy.db"
    docs = []
    if session_ids and db_path.exists():
        from collections import defaultdict
        session_chunks = defaultdict(list)
        for d in load_session_documents(db_path, session_ids):
            session_chunks[d["session_id"]].append(d)
        from src.ingest import load_text
        for sid, chunks in session_chunks.items():
            full_text = "\n\n".join(ch["text"] for ch in chunks)
            doc = load_text(full_text, source=f"session:{sid}", session_id=sid)
            docs.append(doc)
    else:
        for d in load_hermes_documents(data_dir):
            from src.ingest import load_text
            doc = load_text(d["text"], source=d["source"], session_id=d.get("session_id", "hermes"))
            docs.append(doc)
    return docs


def run_ingest(
    data_dir: Path | None = None,
    session_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Ingest stage: load, redact, chunk, embed, store Document/Chunk (NO LLM)."""
    cfg = get_settings()
    logger.info("Starting INGEST stage: neo4j_uri=%s", cfg.neo4j_uri)

    if data_dir:
        logger.info("Loading documents from %s (legacy mode)", data_dir)
        docs: list[Document] = load_directory(data_dir)
    else:
        logger.info("Loading documents via Hermes loader")
        docs: list[Document] = _docs_from_hermes(data_dir=data_dir, session_ids=session_ids)

    if not docs:
        logger.error("No documents found - aborting")
        return {"error": "no_documents"}

    total_chunks = sum(len(d.chunks) for d in docs)
    avg_len = sum(len(c.text) for d in docs for c in d.chunks) / total_chunks if total_chunks else 0
    logger.info("Loaded %d documents -> %d total chunks (avg %.0f chars)", len(docs), total_chunks, avg_len)

    logger.info("Generating embeddings for %d chunks...", total_chunks)
    all_texts = [c.text for d in docs for c in d.chunks]
    embeddings = embed_batch(all_texts)
    logger.info("Generated %d embeddings (dim=%d)", len(embeddings), cfg.embedding_dims)

    logger.info("Storing in Neo4j (Document + Chunk only)...")
    driver = get_driver()
    try:
        stored_docs = 0
        stored_chunks = 0
        for i, doc in enumerate(docs):
            store_document(doc)
            stored_docs += 1
            for j, chunk in enumerate(doc.chunks):
                emb = embeddings[i * len(doc.chunks) + j]
                store_chunk(chunk, emb)  # extraction_status="pending" by default
                stored_chunks += 1
        logger.info("Ingest complete: %d docs, %d chunks (status=pending)", stored_docs, stored_chunks)
    except Exception as exc:
        logger.error("Failed to store in Neo4j: %s", exc)
        raise
    finally:
        close()

    return {"docs": len(docs), "chunks": total_chunks, "stored_docs": stored_docs, "stored_chunks": stored_chunks}


def get_pending_chunks(limit: int | None = None) -> list[Chunk]:
    """Fetch chunks with extraction_status in ('pending', 'failed') from Neo4j."""
    query = """
    MATCH (c:Chunk)
    WHERE c.extraction_status IN ['pending', 'failed']
    RETURN c.id AS id, c.text AS text, c.session_id AS session_id, c.ts AS ts,
           c.doc_id AS doc_id, c.index AS index, c.extraction_status AS status,
           c.extraction_error AS error
    """
    if limit:
        query += f" LIMIT {limit}"
    with get_session() as s:
        results = s.run(query)
        chunks = []
        for r in results:
            chunks.append(Chunk(
                id=r["id"],
                text=r["text"],
                source=r["session_id"],
                doc_id=r["doc_id"],
                index=r["index"],
                session_id=r["session_id"],
                ts=r["ts"],
                extraction_status=r["status"],
                extraction_error=r["error"],
            ))
        return chunks


def run_extract(
    max_calls: int | None = None,
    skip_llm: bool = False,
) -> dict[str, Any]:
    """Extract stage: read pending/failed chunks from Neo4j, run LLM extraction, store results."""
    cfg = get_settings()
    logger.info("Starting EXTRACT stage: neo4j_uri=%s", cfg.neo4j_uri)

    chunks = get_pending_chunks(limit=max_calls)
    total = len(chunks)
    if total == 0:
        logger.info("No pending/failed chunks to process")
        return {"processed": 0, "entities": 0, "relations": 0}

    logger.info("Processing %d chunks (max_calls=%s)", total, max_calls)

    extractions: list[ExtractionResult] = []
    for i, chunk in enumerate(chunks):
        if max_calls is not None and i >= max_calls:
            logger.warning("Max calls reached, stopping")
            break
        try:
            result = extract_from_chunk(chunk.id, chunk.text)
            extractions.append(result)
            if result.status == "failed":
                logger.error("Chunk %s FAILED: %s", chunk.id[:8], result.error_text)
        except Exception as exc:
            logger.error("Extraction exception for chunk %s: %s", chunk.id[:8], exc)
            result = ExtractionResult(chunk_id=chunk.id, status="failed", error_text=str(exc))
            extractions.append(result)

    # Store extractions (updates chunk status)
    driver = get_driver()
    try:
        total_entities = 0
        total_relations = 0
        for result in extractions:
            store_extraction(result)  # updates chunk extraction_status
            total_entities += len(result.entities)
            total_relations += len(result.relations)
        logger.info("Extract complete: %d entities, %d relations across %d chunks",
                    total_entities, total_relations, len(extractions))
    except Exception as exc:
        logger.error("Failed to store extractions: %s", exc)
        raise
    finally:
        close()

    return {"processed": len(extractions), "entities": total_entities, "relations": total_relations}


def run_rechunk(
    document_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Delete and rebuild chunks for a document. Dry-run by default."""
    cfg = get_settings()
    logger.info("RECHUNK: document_id=%s dry_run=%s", document_id, dry_run)

    with get_session() as s:
        # Find chunks to delete
        chunks = s.run(
            "MATCH (c:Chunk)-[:PART_OF]->(d:Document {id: $did}) "
            "RETURN c.id AS id, c.text AS text",
            did=document_id
        ).data()
        logger.info("Would delete %d chunks for document %s", len(chunks), document_id)
        if dry_run:
            return {"document": document_id, "chunks_to_delete": len(chunks), "dry_run": True}

        if len(chunks) == 0:
            return {"document": document_id, "message": "No chunks found", "dry_run": False}

        # Delete chunks and their relations
        s.run(
            "MATCH (c:Chunk)-[:PART_OF]->(d:Document {id: $did}) "
            "DETACH DELETE c",
            did=document_id
        )

        # Reload document text and rechunk
        # Note: This assumes original document text is not stored.
        # In practice, you'd need to re-ingest from source.
        logger.warning("Rechunk requires re-ingesting from source; not fully automated yet")
        return {"document": document_id, "deleted": len(chunks), "dry_run": False, "note": "Re-ingest needed"}


def main() -> None:
    parser = argparse.ArgumentParser(description="KGIRS pipeline - separate ingest/extract")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    p_ingest = subparsers.add_parser("ingest", help="Load, chunk, embed, store (no LLM)")
    p_ingest.add_argument("--data-dir", type=Path, help="Legacy data directory")
    p_ingest.add_argument("--sessions", type=str, default="20261012_194239_70c37b,20261026_210619_35bda0", help="Session IDs")

    # Extract command
    p_extract = subparsers.add_parser("extract", help="Run LLM extraction on pending/failed chunks")
    p_extract.add_argument("--max-calls", type=int, default=None, help="Max LLM calls")
    p_extract.add_argument("--skip-llm", action="store_true", help="Skip LLM (mark all done)")

    # Rechunk command
    p_rechunk = subparsers.add_parser("rechunk", help="Delete and rebuild chunks for a document")
    p_rechunk.add_argument("document_id", type=str, help="Document ID")
    p_rechunk.add_argument("--yes", action="store_true", help="Actually perform deletion (default dry-run)")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.command == "ingest":
        result = run_ingest(
            data_dir=args.data_dir,
            session_ids=args.sessions.split(",") if args.sessions else None,
        )
    elif args.command == "extract":
        result = run_extract(
            max_calls=args.max_calls,
            skip_llm=args.skip_llm,
        )
    elif args.command == "rechunk":
        result = run_rechunk(
            document_id=args.document_id,
            dry_run=not args.yes,
        )
    else:
        parser.error("Unknown command")

    if result.get("error"):
        sys.exit(1)
    print("\n=== Command Complete ===")
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
