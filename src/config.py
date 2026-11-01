"""Application configuration loaded from environment / .env file."""

import os
import logging
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from project root
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


@dataclass
class Settings:
    """Immutable application settings.

    All values are read from the environment at *instantiation* time so that
    test monkey-patching and runtime overrides are respected.
    """

    # Neo4j
    neo4j_uri: str = ""
    neo4j_user: str = ""
    neo4j_password: str = ""

    # Embeddings
    embedding_model: str = ""
    embedding_dims: int = 384

    # LLM
    llm_provider: str = "gemini"
    llm_model: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    gemini_api_key: str = ""
    llm_rpm: int = 8

    # Chunking
    chunk_size: int = 2800
    chunk_overlap: int = 200

    def __post_init__(self) -> None:
        """Populate fields from environment (called after __init__)."""
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "changeme123")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.embedding_dims = int(os.getenv("EMBEDDING_DIMS", "384"))
        self.llm_provider = os.getenv("LLM_PROVIDER", "gemini")
        self.llm_model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
        self.llm_base_url = os.getenv("LLM_BASE_URL", "")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.llm_rpm = int(os.getenv("LLM_RPM", "8"))
        self.llm_cache_dir = os.getenv("LLM_CACHE_DIR", ".llm_cache")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "2800"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))


def get_settings() -> Settings:
    """Return a singleton Settings instance."""
    return Settings()
