"""Smoke tests for config loading."""

import os
import pytest


def test_settings_loads():
    """Settings dataclass can be instantiated."""
    from src.config import get_settings

    s = get_settings()
    assert s.neo4j_uri.startswith("bolt://") or s.neo4j_uri.startswith("neo4j://")
    assert s.embedding_dims == 384


def test_settings_env_override(monkeypatch):
    """Environment variables override defaults."""
    monkeypatch.setenv("NEO4J_URI", "bolt://custom:7687")
    # Force re-evaluation by creating a new instance
    from src.config import Settings

    s = Settings()
    assert s.neo4j_uri == "bolt://custom:7687"
