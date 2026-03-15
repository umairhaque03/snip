"""
Tests for the SQLite repository layer.

Uses in-memory / temp-file databases for full isolation.
"""

from __future__ import annotations

from pathlib import Path

from brainfog.db import LogRepository, RawLogEntry

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

async def test_initialize_creates_database_file(tmp_db: Path):
    repo = LogRepository(tmp_db)
    await repo.initialize()
    assert tmp_db.exists()


async def test_initialize_is_idempotent(tmp_db: Path):
    repo = LogRepository(tmp_db)
    await repo.initialize()
    await repo.initialize()  # Should not raise


# ---------------------------------------------------------------------------
# Store and retrieve
# ---------------------------------------------------------------------------

async def test_store_and_retrieve_raw_output(tmp_db: Path):
    repo = LogRepository(tmp_db)
    await repo.initialize()

    entry = RawLogEntry(
        id=RawLogEntry.new_id(),
        session_id="sess-1",
        created_at=RawLogEntry.utcnow(),
        tool_name="Bash",
        command="ls -la",
        raw_output="file1\nfile2\nfile3",
        pruned_output="[BrainFog] 3 entries",
        volatility="volatile",
        category="directory_listing",
        line_count_raw=3,
        line_count_pruned=1,
        tokens_raw=10,
        tokens_pruned=5,
        tokens_saved=5,
        was_pruned=True,
    )
    await repo.store_log(entry)
    raw = await repo.get_raw_output(entry.id)
    assert raw == "file1\nfile2\nfile3"


async def test_get_raw_output_returns_none_for_missing_id(tmp_db: Path):
    repo = LogRepository(tmp_db)
    await repo.initialize()
    result = await repo.get_raw_output("nonexistent-id")
    assert result is None


async def test_get_log_entry_returns_full_entry(tmp_db: Path):
    repo = LogRepository(tmp_db)
    await repo.initialize()

    entry = RawLogEntry(
        id=RawLogEntry.new_id(),
        session_id="sess-1",
        created_at=RawLogEntry.utcnow(),
        tool_name="Bash",
        command="grep -r TODO src/",
        raw_output="\n".join(f"src/file.py:{i}: TODO" for i in range(5)),
        pruned_output="[BrainFog] 5 matches",
        volatility="volatile",
        category="grep_results",
        line_count_raw=5,
        line_count_pruned=1,
        tokens_raw=20,
        tokens_pruned=5,
        tokens_saved=15,
        was_pruned=True,
    )
    await repo.store_log(entry)
    fetched = await repo.get_log_entry(entry.id)
    assert fetched is not None
    assert fetched.command == "grep -r TODO src/"
    assert fetched.tokens_saved == 15


# ---------------------------------------------------------------------------
# Session stats
# ---------------------------------------------------------------------------

async def test_session_stats_totals_are_correct(tmp_db: Path):
    repo = LogRepository(tmp_db)
    await repo.initialize()

    for i in range(3):
        entry = RawLogEntry(
            id=RawLogEntry.new_id(),
            session_id="sess-stats",
            created_at=RawLogEntry.utcnow(),
            tool_name="Bash",
            command=f"ls {i}",
            raw_output="x\n" * 100,
            pruned_output="[BrainFog] summary",
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

    stats = await repo.get_session_stats("sess-stats")
    assert stats.total_tool_calls == 3
    assert stats.total_pruned == 3
    assert stats.total_tokens_saved == 270
    assert stats.pct_reduction > 0


async def test_session_stats_empty_session(tmp_db: Path):
    repo = LogRepository(tmp_db)
    await repo.initialize()
    stats = await repo.get_session_stats("nonexistent-session")
    assert stats.total_tool_calls == 0
    assert stats.total_tokens_saved == 0
    assert stats.pct_reduction == 0.0


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

async def test_cleanup_removes_old_logs(tmp_db: Path):
    repo = LogRepository(tmp_db)
    await repo.initialize()

    old_id = RawLogEntry.new_id()
    old_entry = RawLogEntry(
        id=old_id,
        session_id="sess-cleanup",
        created_at="2020-01-01 00:00:00",  # far in the past
        tool_name="Bash",
        command="ls",
        raw_output="old output",
        pruned_output="[BrainFog] old",
        volatility="volatile",
        category="directory_listing",
        line_count_raw=1,
        line_count_pruned=1,
        tokens_raw=5,
        tokens_pruned=3,
        tokens_saved=2,
        was_pruned=False,
    )
    await repo.store_log(old_entry)

    # Confirm it was stored
    assert await repo.get_raw_output(old_id) is not None

    # Cleanup anything older than 1 day
    deleted = await repo.cleanup_old_logs(days=1)
    assert deleted == 1
    assert await repo.get_raw_output(old_id) is None
