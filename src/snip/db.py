"""
SQLite storage layer for raw logs and session metrics.

Uses the repository pattern — all database access goes through LogRepository.
The schema is created on first use via initialize().

Database location: ~/.snip/snip.db
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from snip.constants import DB_RELATIVE_PATH, LOG_RETENTION_DAYS
from snip.metrics import SessionStats

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_logs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    tool_name TEXT NOT NULL,
    command TEXT,
    raw_output TEXT NOT NULL,
    pruned_output TEXT NOT NULL,
    volatility TEXT NOT NULL,
    category TEXT NOT NULL,
    line_count_raw INTEGER NOT NULL,
    line_count_pruned INTEGER NOT NULL,
    tokens_raw INTEGER NOT NULL,
    tokens_pruned INTEGER NOT NULL,
    tokens_saved INTEGER NOT NULL,
    was_pruned INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_INDEX_SESSION_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_raw_logs_session ON raw_logs(session_id)"
)
_CREATE_INDEX_ID_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_raw_logs_id ON raw_logs(id)"
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawLogEntry:
    """A single stored log entry. Mirrors the raw_logs table columns."""

    id: str
    session_id: str
    created_at: str
    tool_name: str
    command: str
    raw_output: str
    pruned_output: str
    volatility: str
    category: str
    line_count_raw: int
    line_count_pruned: int
    tokens_raw: int
    tokens_pruned: int
    tokens_saved: int
    was_pruned: bool

    @staticmethod
    def new_id() -> str:
        """Generate a new unique log ID."""
        return str(uuid.uuid4())

    @staticmethod
    def utcnow() -> str:
        """Return current UTC time in SQLite-compatible format (YYYY-MM-DD HH:MM:SS)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class LogRepository:
    """
    Async repository for raw log storage and session stats queries.

    Usage:
        repo = LogRepository()
        await repo.initialize()
        await repo.store_log(entry)
        raw = await repo.get_raw_output("some-uuid")
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / DB_RELATIVE_PATH
        self._db_path = db_path

    @property
    def db_path(self) -> Path:
        return self._db_path

    async def initialize(self) -> None:
        """Create the database directory and tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(_CREATE_TABLE_SQL)
            await conn.execute(_CREATE_INDEX_SESSION_SQL)
            await conn.execute(_CREATE_INDEX_ID_SQL)
            await conn.commit()

    async def store_log(self, entry: RawLogEntry) -> None:
        """
        Insert a new log entry into the database.

        Args:
            entry: The fully-populated RawLogEntry to persist.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO raw_logs (
                    id, session_id, created_at, tool_name, command,
                    raw_output, pruned_output, volatility, category,
                    line_count_raw, line_count_pruned,
                    tokens_raw, tokens_pruned, tokens_saved, was_pruned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.session_id,
                    entry.created_at,
                    entry.tool_name,
                    entry.command,
                    entry.raw_output,
                    entry.pruned_output,
                    entry.volatility,
                    entry.category,
                    entry.line_count_raw,
                    entry.line_count_pruned,
                    entry.tokens_raw,
                    entry.tokens_pruned,
                    entry.tokens_saved,
                    1 if entry.was_pruned else 0,
                ),
            )
            await conn.commit()

    async def get_raw_output(self, log_id: str) -> str | None:
        """
        Retrieve the full raw output for a log entry by ID.

        Args:
            log_id: UUID of the log entry.

        Returns:
            The raw_output string, or None if not found.
        """
        async with aiosqlite.connect(self._db_path) as conn, conn.execute(
            "SELECT raw_output FROM raw_logs WHERE id = ?", (log_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_log_entry(self, log_id: str) -> RawLogEntry | None:
        """
        Retrieve a full log entry by ID.

        Args:
            log_id: UUID of the log entry.

        Returns:
            The RawLogEntry, or None if not found.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            async with conn.execute(
                "SELECT * FROM raw_logs WHERE id = ?", (log_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return _row_to_entry(row) if row else None

    async def get_session_logs(self, session_id: str) -> list[RawLogEntry]:
        """
        Retrieve all log entries for a session, ordered by created_at.

        Args:
            session_id: The session identifier.

        Returns:
            List of RawLogEntry, oldest first.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            async with conn.execute(
                "SELECT * FROM raw_logs WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_entry(row) for row in rows]

    async def get_session_stats(self, session_id: str) -> SessionStats:
        """
        Compute aggregated token savings statistics for a session.

        Args:
            session_id: The session identifier.

        Returns:
            A SessionStats dataclass with all aggregate values.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            # Aggregate totals in a single query
            async with conn.execute(
                """
                SELECT
                    COUNT(*)                        AS total_calls,
                    COALESCE(SUM(was_pruned), 0)   AS total_pruned,
                    COALESCE(SUM(tokens_raw), 0)   AS total_tokens_raw,
                    COALESCE(SUM(tokens_pruned), 0) AS total_tokens_pruned,
                    COALESCE(SUM(tokens_saved), 0) AS total_tokens_saved,
                    COALESCE(MAX(tokens_saved), 0) AS heaviest_tokens
                FROM raw_logs
                WHERE session_id = ?
                """,
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                total_calls      = row[0]
                total_pruned     = row[1]
                total_tokens_raw = row[2]
                total_tokens_pruned = row[3]
                total_tokens_saved  = row[4]
                heaviest_tokens     = row[5]

            # Find the command that saved the most tokens
            heaviest_command = ""
            async with conn.execute(
                """
                SELECT command FROM raw_logs
                WHERE session_id = ?
                ORDER BY tokens_saved DESC
                LIMIT 1
                """,
                (session_id,),
            ) as cursor:
                cmd_row = await cursor.fetchone()
                if cmd_row and cmd_row[0]:
                    heaviest_command = cmd_row[0]

        pct_reduction = (
            (total_tokens_saved / total_tokens_raw) * 100
            if total_tokens_raw > 0
            else 0.0
        )

        return SessionStats(
            session_id=session_id,
            total_tool_calls=total_calls,
            total_pruned=total_pruned,
            total_tokens_raw=total_tokens_raw,
            total_tokens_pruned=total_tokens_pruned,
            total_tokens_saved=total_tokens_saved,
            pct_reduction=pct_reduction,
            heaviest_prune_tokens=heaviest_tokens,
            heaviest_prune_command=heaviest_command,
        )

    async def cleanup_old_logs(self, days: int = LOG_RETENTION_DAYS) -> int:
        """
        Delete log entries older than `days` days.

        Args:
            days: Retention period. Defaults to LOG_RETENTION_DAYS.

        Returns:
            Number of rows deleted.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            async with conn.execute(
                "DELETE FROM raw_logs WHERE created_at < datetime('now', ?)",
                (f"-{days} days",),
            ) as cursor:
                deleted = cursor.rowcount
            await conn.commit()
            return deleted


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _row_to_entry(row: sqlite3.Row) -> RawLogEntry:
    """Convert a sqlite3.Row (accessed by column name) to a RawLogEntry."""
    return RawLogEntry(
        id=row["id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        tool_name=row["tool_name"],
        command=row["command"] or "",
        raw_output=row["raw_output"],
        pruned_output=row["pruned_output"],
        volatility=row["volatility"],
        category=row["category"],
        line_count_raw=row["line_count_raw"],
        line_count_pruned=row["line_count_pruned"],
        tokens_raw=row["tokens_raw"],
        tokens_pruned=row["tokens_pruned"],
        tokens_saved=row["tokens_saved"],
        was_pruned=bool(row["was_pruned"]),
    )
