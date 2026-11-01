"""L3 – Store entities, relations, and chunks in Neo4j."""

import logging

from src.db import get_session
from src.ingest import Chunk, Document
from src.extract import ExtractionResult

logger = logging.getLogger(__name__)


def store_document(doc: Document) -> None:
    """MERGE a Document node."""
    with get_session() as s:
        s.run(
            "MERGE (d:Document {id: $id}) "
            "SET d.source = $source, d.date = $date",
            id=doc.id,
            source=doc.source,
            date=doc.date,
        )
    logger.info("Stored Document %s", doc.id[:8])


def store_chunk(chunk: Chunk, embedding: list[float]) -> None:
    """MERGE a Chunk node with its embedding and link to Document."""
    with get_session() as s:
        s.run(
            "MERGE (c:Chunk {id: $id}) "
            "SET c.text = $text, c.embedding = $embedding, "
            "    c.session_id = $session_id, c.ts = $ts, "
            "    c.extraction_status = $status, c.extraction_error = $error, "
            "    c.doc_id = $doc_id, c.index = $idx "
            "WITH c "
            "MERGE (d:Document {id: $doc_id}) "
            "MERGE (c)-[:PART_OF]->(d)",
            id=chunk.id,
            text=chunk.text,
            embedding=embedding,
            session_id=chunk.session_id,
            ts=chunk.ts,
            status=chunk.extraction_status,
            error=chunk.extraction_error,
            doc_id=chunk.doc_id,
            idx=chunk.index,
        )
    logger.debug("Stored Chunk %s", chunk.id[:8])


def store_extraction(result: ExtractionResult) -> None:
    """MERGE extracted entities and relations; link via provenance; update chunk status."""
    with get_session() as s:
        # Update chunk status first
        s.run(
            "MATCH (c:Chunk {id: $cid}) "
            "SET c.extraction_status = $status, c.extraction_error = $error",
            cid=result.chunk_id,
            status=result.status,
            error=result.error_text,
        )
        # Entities
        for ent in result.entities:
            s.run(
                "MERGE (e:Entity {name: $name}) "
                "SET e.type = $type, e.aliases = $aliases, "
                "    e.description = $description",
                name=ent.name,
                type=ent.type,
                aliases=ent.aliases,
                description=ent.description,
            )
            s.run(
                "MATCH (c:Chunk {id: $cid}) "
                "MATCH (e:Entity {name: $name}) "
                "MERGE (c)-[:MENTIONS]->(e)",
                cid=result.chunk_id,
                name=ent.name,
            )
        # Relations
        for rel in result.relations:
            s.run(
                "MATCH (a:Entity {name: $src}) "
                "MATCH (b:Entity {name: $tgt}) "
                "MERGE (a)-[r:RELATION {type: $type}]->(b) "
                "SET r.evidence_chunk_id = $cid, r.ts = timestamp()",
                src=rel.source,
                tgt=rel.target,
                type=rel.type,
                cid=rel.evidence_chunk_id,
            )
    logger.info(
        "Stored extraction for chunk %s (%d ent, %d rel, status=%s)",
        result.chunk_id[:8],
        len(result.entities),
        len(result.relations),
        result.status,
    )
