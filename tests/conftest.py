"""
Shared pytest fixtures for the snip test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from snip.classifier import ClassificationResult, VolatilityClass
from snip.db import LogRepository


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a temporary SQLite database file."""
    return tmp_path / "test_snip.db"


@pytest.fixture
async def repo(tmp_db: Path) -> LogRepository:
    """Return an initialized LogRepository backed by a temporary database."""
    r = LogRepository(tmp_db)
    await r.initialize()
    return r


@pytest.fixture
def sample_volatile_classification() -> ClassificationResult:
    return ClassificationResult(
        volatility=VolatilityClass.VOLATILE,
        category="directory_listing",
        confidence=0.95,
        reason="Command matches directory listing prefix",
    )


@pytest.fixture
def sample_durable_classification() -> ClassificationResult:
    return ClassificationResult(
        volatility=VolatilityClass.DURABLE,
        category="durable",
        confidence=1.0,
        reason="Known-Durable MCP tool",
    )


@pytest.fixture
def long_output() -> str:
    """Return a string with more than 50 lines."""
    return "\n".join(f"line {i}" for i in range(100))


@pytest.fixture
def short_output() -> str:
    """Return a string with fewer than 50 lines."""
    return "\n".join(f"line {i}" for i in range(10))


@pytest.fixture
def corpus_dir() -> Path:
    """Return the path to the benchmark corpus directory."""
    return Path(__file__).parent.parent / "corpus"
