"""
BrainFog MCP server.

Registers three tools with the MCP SDK:
  - brainfog_intercept: Execute a command with output optimization
  - get_raw_output:     Retrieve full output for a pruned result by ID
  - get_session_stats:  Token savings summary for the current session

The server runs over stdio transport (standard for Claude Code MCP servers).
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from brainfog.classifier import classify
from brainfog.db import LogRepository, RawLogEntry
from brainfog.pruner import prune

# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

# Each invocation of `brainfog serve` gets a fresh session ID.
SESSION_ID: str = str(uuid.uuid4())

# Module-level repository — initialized in serve().
_repo: LogRepository | None = None

# Session start time for uptime reporting.
_session_start: datetime = datetime.now(timezone.utc)


def _get_repo() -> LogRepository:
    if _repo is None:
        raise RuntimeError("LogRepository not initialized. Call serve() first.")
    return _repo


# ---------------------------------------------------------------------------
# MCP server setup
# ---------------------------------------------------------------------------

server = Server("brainfog")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise available BrainFog tools to Claude."""
    return [
        Tool(
            name="brainfog_intercept",
            description=(
                "Execute a shell command with BrainFog output optimization. "
                "Volatile outputs over 50 lines are automatically pruned to a compact digest. "
                "The full raw output is stored locally and retrievable via get_raw_output."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Optional working directory for the command.",
                    },
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="get_raw_output",
            description=(
                "Retrieve the full unmodified output for a previously pruned result. "
                "Use the ID shown in the [Pruned from N lines. Use get_raw_output(id='...')] hint."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "log_id": {
                        "type": "string",
                        "description": "UUID of the log entry to retrieve.",
                    },
                },
                "required": ["log_id"],
            },
        ),
        Tool(
            name="get_session_stats",
            description=(
                "Get token savings statistics for the current BrainFog session. "
                "Returns total tokens saved, % context reduction, prune count, "
                "and the heaviest single prune."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch incoming tool calls to the appropriate handler."""
    try:
        if name == "brainfog_intercept":
            text = await _handle_intercept(
                command=arguments["command"],
                working_directory=arguments.get("working_directory"),
            )
        elif name == "get_raw_output":
            text = await _handle_get_raw_output(log_id=arguments["log_id"])
        elif name == "get_session_stats":
            text = await _handle_get_session_stats()
        else:
            text = f"Unknown tool: {name!r}"
    except Exception as exc:
        text = f"BrainFog error: {exc}"

    return [TextContent(type="text", text=text)]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_intercept(
    command: str,
    working_directory: str | None = None,
) -> str:
    """
    Execute a shell command with BrainFog output optimization.

    Pipeline:
      1. Run command via subprocess
      2. Classify output (Durable vs Volatile + category)
      3. If Volatile and > 50 lines, prune to digest
      4. Store raw log in SQLite
      5. Return pruned output (or original if not pruned)
    """
    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=working_directory,
    )

    # Combine stdout and stderr; prefer stdout, append stderr if present
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = stdout + stderr if stderr else stdout

    # Classify → prune → store
    classification = classify(tool_name="Bash", command=command, output=combined)
    log_id = RawLogEntry.new_id()
    result = prune(combined, log_id, classification)

    entry = RawLogEntry(
        id=log_id,
        session_id=SESSION_ID,
        created_at=RawLogEntry.utcnow(),
        tool_name="Bash",
        command=command,
        raw_output=result.raw_output,
        pruned_output=result.pruned_output,
        volatility=classification.volatility.value,
        category=classification.category,
        line_count_raw=result.line_count_raw,
        line_count_pruned=result.line_count_pruned,
        tokens_raw=result.tokens_raw,
        tokens_pruned=result.tokens_pruned,
        tokens_saved=result.tokens_saved,
        was_pruned=result.was_pruned,
    )
    await _get_repo().store_log(entry)

    return result.pruned_output


async def _handle_get_raw_output(log_id: str) -> str:
    """
    Retrieve the full unmodified output for a previously pruned result.

    Returns the raw output string, or an error message if not found.
    """
    raw = await _get_repo().get_raw_output(log_id)
    if raw is None:
        return f"No log found for id: {log_id}"
    return raw


async def _handle_get_session_stats() -> str:
    """Return token savings statistics for the current session as a formatted string."""
    stats = await _get_repo().get_session_stats(SESSION_ID)

    uptime = datetime.now(timezone.utc) - _session_start
    uptime_str = str(uptime).split(".")[0]  # strip microseconds

    lines = [
        "BrainFog Session Stats",
        f"  Session ID:      {stats.session_id}",
        f"  Uptime:          {uptime_str}",
        f"  Total calls:     {stats.total_tool_calls}",
        f"  Pruned calls:    {stats.total_pruned}",
        f"  Tokens raw:      {stats.total_tokens_raw:,}",
        f"  Tokens pruned:   {stats.total_tokens_pruned:,}",
        f"  Tokens saved:    {stats.total_tokens_saved:,}",
        f"  Context reduced: {stats.pct_reduction:.1f}%",
        f"  Heaviest prune:  {stats.heaviest_prune_tokens:,} tokens",
    ]
    if stats.heaviest_prune_command:
        cmd = stats.heaviest_prune_command
        if len(cmd) > 80:
            cmd = cmd[:77] + "..."
        lines.append(f"    Command:       {cmd}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def serve(db_path: Path | None = None) -> None:
    """
    Initialize the database and start the MCP server over stdio.

    Args:
        db_path: Override for the SQLite database path. Uses default if None.
    """
    global _repo, _session_start

    repo = LogRepository(db_path)
    await repo.initialize()
    await repo.cleanup_old_logs()
    _repo = repo
    _session_start = datetime.now(timezone.utc)

    from brainfog.dashboard import Dashboard

    dashboard = Dashboard()
    dashboard.start()

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        dashboard.stop()
