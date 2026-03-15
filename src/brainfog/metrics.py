"""
Data models for session metrics and per-call tracking.

All dataclasses are frozen (immutable). Callers must create new instances
rather than mutating existing ones.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCallMetric:
    """Metrics for a single tool call intercepted by BrainFog."""

    log_id: str           # UUID matching the raw_logs table
    tool_name: str        # e.g., "Bash", "Grep", "Read"
    command: str          # The command string or description
    category: str         # e.g., "directory_listing", "test_output"
    volatility: str       # "durable" or "volatile"
    tokens_raw: int       # Token count of the original output
    tokens_pruned: int    # Token count of the pruned output
    tokens_saved: int     # tokens_raw - tokens_pruned
    was_pruned: bool      # Whether pruning actually occurred
    timestamp: str        # ISO 8601 UTC timestamp


@dataclass(frozen=True)
class SessionStats:
    """Aggregated token savings for the current BrainFog session."""

    session_id: str
    total_tool_calls: int
    total_pruned: int            # Number of calls where was_pruned=True
    total_tokens_raw: int        # Sum of tokens_raw across all calls
    total_tokens_pruned: int     # Sum of tokens_pruned across all calls
    total_tokens_saved: int      # Sum of tokens_saved across all calls
    pct_reduction: float         # (tokens_saved / tokens_raw) * 100, or 0.0
    heaviest_prune_tokens: int   # Largest single tokens_saved value
    heaviest_prune_command: str  # Command that produced the heaviest prune
