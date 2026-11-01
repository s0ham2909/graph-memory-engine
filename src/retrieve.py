"""L4 – Hybrid retrieval: vector seeds → entity link → 1-2 hop expansion."""

import logging
from dataclasses import dataclass, field
from typing import Any

from src.db import get_session

logger = logging.getLogger(__name__)

VECTOR_INDEX_NAME = "chunk_embedding_index"


@dataclass
class RetrievalResult:
    """Container for hybrid retrieval output."""

    seed_chunks: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    related_chunks: list[dict[str, Any]] = field(default_factory=list)
    subgraph_triples: list[dict[str, Any]] = field(default_factory=list)


def vector_search(query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    """Find top-k chunks by cosine similarity using Neo4j vector index."""
    with get_session() as s:
        result = s.run(
            "CALL db.index.vector.queryNodes($idx, $k, $emb) "
            "YIELD node, score "
            "RETURN node.id AS id, node.text AS text, score "
            "ORDER BY score DESC",
            idx=VECTOR_INDEX_NAME,
            k=top_k,
            emb=query_embedding,
        )
        return [dict(r) for r in result]


def expand_entities(chunk_ids: list[str], hops: int = 2) -> dict[str, Any]:
    """From seed chunk IDs, find mentioned entities and expand 1-2 hops."""
    with get_session() as s:
        # Get directly mentioned entities
        ent_result = s.run(
            "UNWIND $cids AS cid "
            "MATCH (c:Chunk {id: cid})-[:MENTIONS]->(e:Entity) "
            "RETURN DISTINCT e.name AS name, e.type AS type, "
            "       e.description AS description",
            cids=chunk_ids,
        )
        entities = [dict(r) for r in ent_result]
        entity_names = [e["name"] for e in entities]

        # Expand via RELATION edges
        triples: list[dict[str, Any]] = []
        if entity_names and hops >= 1:
            hop_result = s.run(
                "UNWIND $names AS n "
                "MATCH (a:Entity {name: n})-[r:RELATION]-(b:Entity) "
                "RETURN a.name AS source, r.type AS rel_type, "
                "       b.name AS target, b.type AS target_type, "
                "       r.evidence_chunk_id AS evidence",
                names=entity_names,
            )
            triples = [dict(r) for r in hop_result]

        # Gather related chunks (chunks mentioning expanded entities)
        expanded_names = list({t["target"] for t in triples} | set(entity_names))
        related_result = s.run(
            "UNWIND $names AS n "
            "MATCH (c:Chunk)-[:MENTIONS]->(e:Entity {name: n}) "
            "WHERE NOT c.id IN $exclude "
            "RETURN DISTINCT c.id AS id, c.text AS text, e.name AS via_entity "
            "LIMIT 10",
            names=expanded_names,
            exclude=chunk_ids,
        )
        related = [dict(r) for r in related_result]

    return {"entities": entities, "triples": triples, "related_chunks": related}


def hybrid_retrieve(
    query_embedding: list[float], top_k: int = 5, hops: int = 2
) -> RetrievalResult:
    """Full hybrid retrieval pipeline."""
    seeds = vector_search(query_embedding, top_k)
    chunk_ids = [s["id"] for s in seeds]
    expansion = expand_entities(chunk_ids, hops)
    return RetrievalResult(
        seed_chunks=seeds,
        entities=expansion["entities"],
        related_chunks=expansion["related_chunks"],
        subgraph_triples=expansion["triples"],
    )
