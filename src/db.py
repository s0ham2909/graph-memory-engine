"""Neo4j driver management."""

import logging
from contextlib import contextmanager
from typing import Generator, Any

from neo4j import GraphDatabase, Driver, Session

from src.config import get_settings

logger = logging.getLogger(__name__)

_driver: Driver | None = None


def get_driver() -> Driver:
    """Return a singleton Neo4j driver."""
    global _driver
    if _driver is None:
        cfg = get_settings()
        logger.info("Connecting to Neo4j at %s", cfg.neo4j_uri)
        _driver = GraphDatabase.driver(
            cfg.neo4j_uri,
            auth=(cfg.neo4j_user, cfg.neo4j_password),
        )
    return _driver


@contextmanager
def get_session(**kwargs: Any) -> Generator[Session, None, None]:
    """Yield a Neo4j session from the singleton driver."""
    driver = get_driver()
    with driver.session(**kwargs) as session:
        yield session


def close() -> None:
    """Close the singleton driver."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed.")
