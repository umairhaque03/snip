"""
Integration tests for the MCP server tool handlers.

Tests the classify → prune → store pipeline end-to-end using a real
temporary SQLite database.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import snip.server as server_module
from snip.db import LogRepository, RawLogEntry
from snip.server import (
    SESSION_ID,
    _handle_get_raw_output,
    _handle_get_session_stats,
    _handle_intercept,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a mock subprocess.CompletedProcess with the given output."""
    proc = MagicMock()
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


async def _init_repo(tmp_db: Path) -> LogRepository:
    repo = LogRepository(tmp_db)
    await repo.initialize()
    server_module._repo = repo
    return repo


# ---------------------------------------------------------------------------
# snip_run
# ---------------------------------------------------------------------------

async def test_intercept_returns_string(tmp_db: Path):
    await _init_repo(tmp_db)
    with patch("snip.server.subprocess.run", return_value=_make_proc("hello world\n")):
        result = await _handle_intercept("echo hello")
    assert isinstance(result, str)
    assert len(result) > 0


async def test_intercept_short_output_not_pruned(tmp_db: Path):
    await _init_repo(tmp_db)
    short_output = "\n".join(f"line {i}" for i in range(5))
    with patch("snip.server.subprocess.run", return_value=_make_proc(short_output)):
        result = await _handle_intercept("echo test")
    assert "[snip]" not in result
    assert result == short_output


async def test_intercept_long_volatile_output_is_pruned(tmp_db: Path):
    await _init_repo(tmp_db)
    ls_output = "\n".join(
        f"-rw-r--r-- 1 user staff 100 Mar 15 file{i}.py" for i in range(200)
    )
    with patch("snip.server.subprocess.run", return_value=_make_proc(ls_output)):
        result = await _handle_intercept("ls -la /tmp")
    assert "[snip]" in result


async def test_intercept_stores_log_in_database(tmp_db: Path):
    repo = await _init_repo(tmp_db)
    with patch("snip.server.subprocess.run", return_value=_make_proc("line\n" * 5)):
        await _handle_intercept("echo test")
    logs = await repo.get_session_logs(SESSION_ID)
    assert len(logs) >= 1


async def test_intercept_stores_correct_command(tmp_db: Path):
    repo = await _init_repo(tmp_db)
    with patch("snip.server.subprocess.run", return_value=_make_proc("output\n")):
        await _handle_intercept("git status")
    logs = await repo.get_session_logs(SESSION_ID)
    assert logs[0].command == "git status"


async def test_intercept_merges_stderr_into_output(tmp_db: Path):
    await _init_repo(tmp_db)
    with patch(
        "snip.server.subprocess.run",
        return_value=_make_proc(stdout="out\n", stderr="err\n"),
    ):
        result = await _handle_intercept("cmd")
    assert "out" in result
    assert "err" in result


async def test_intercept_raises_without_repo():
    server_module._repo = None
    with pytest.raises(RuntimeError, match="not initialized"):
        await _handle_intercept("ls")


# ---------------------------------------------------------------------------
# get_raw_output
# ---------------------------------------------------------------------------

async def test_get_raw_output_returns_full_output(tmp_db: Path):
    repo = await _init_repo(tmp_db)
    entry = RawLogEntry(
        id=RawLogEntry.new_id(),
        session_id=SESSION_ID,
        created_at=RawLogEntry.utcnow(),
        tool_name="Bash",
        command="ls -la",
        raw_output="full raw output content",
        pruned_output="[snip] pruned",
        volatility="volatile",
        category="directory_listing",
        line_count_raw=1,
        line_count_pruned=1,
        tokens_raw=10,
        tokens_pruned=5,
        tokens_saved=5,
        was_pruned=True,
    )
    await repo.store_log(entry)
    result = await _handle_get_raw_output(entry.id)
    assert result == "full raw output content"


async def test_get_raw_output_returns_error_for_missing_id(tmp_db: Path):
    await _init_repo(tmp_db)
    result = await _handle_get_raw_output("nonexistent-id")
    assert "No log found" in result
    assert "nonexistent-id" in result


# ---------------------------------------------------------------------------
# get_session_stats
# ---------------------------------------------------------------------------

async def test_get_session_stats_returns_string(tmp_db: Path):
    await _init_repo(tmp_db)
    result = await _handle_get_session_stats()
    assert isinstance(result, str)
    assert len(result) > 0


async def test_get_session_stats_contains_session_id(tmp_db: Path):
    await _init_repo(tmp_db)
    result = await _handle_get_session_stats()
    assert SESSION_ID in result


async def test_get_session_stats_reflects_stored_logs(tmp_db: Path):
    repo = await _init_repo(tmp_db)
    for i in range(2):
        entry = RawLogEntry(
            id=RawLogEntry.new_id(),
            session_id=SESSION_ID,
            created_at=RawLogEntry.utcnow(),
            tool_name="Bash",
            command=f"ls {i}",
            raw_output="x\n" * 100,
            pruned_output="[snip] summary",
            volatility="volatile",
            category="directory_listing",
            line_count_raw=100,
            line_count_pruned=5,
            tokens_raw=100,
            tokens_pruned=10,
            tokens_saved=90,
            was_pruned=True,
        )
        await repo.store_log(entry)
    result = await _handle_get_session_stats()
    # 2 entries × 90 tokens saved = 180
    assert "180" in result


async def test_get_session_stats_empty_session_shows_zeros(tmp_db: Path):
    await _init_repo(tmp_db)
    result = await _handle_get_session_stats()
    assert "0" in result
