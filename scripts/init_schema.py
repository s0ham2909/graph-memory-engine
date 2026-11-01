"""Initialise Neo4j constraints, indexes, and the vector index."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings
from src.db import get_session, close

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Schema statements
SCHEMA_STATEMENTS: list[str] = [
    # Uniqueness constraints
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk)    REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity)   REQUIRE e.name IS UNIQUE",
    # Text index on Chunk.text for keyword fallback
    "CREATE TEXT INDEX chunk_text_index IF NOT EXISTS FOR (c:Chunk) ON (c.text)",
]


def main() -> None:
    cfg = get_settings()

    # 1. Constraints and indexes
    with get_session() as s:
        for stmt in SCHEMA_STATEMENTS:
            logger.info("Running: %s", stmt[:80])
            s.run(stmt)

    # 2. Vector index (requires Neo4j 5.11+)
    vector_stmt = (
        "CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS "
        "FOR (c:Chunk) ON (c.embedding) "
        "OPTIONS {indexConfig: {"
        "  `vector.dimensions`: $dims, "
        "  `vector.similarity_function`: 'cosine'"
        "}}"
    )
    with get_session() as s:
        logger.info("Creating vector index (dims=%d)...", cfg.embedding_dims)
        s.run(vector_stmt, dims=cfg.embedding_dims)

    logger.info("Schema initialisation complete.")
    close()


if __name__ == "__main__":
    main()
