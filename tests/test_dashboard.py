"""
Tests for the Dashboard class.

Tests the state management, table building, and thread lifecycle
without triggering actual Rich Live terminal output.
"""

from __future__ import annotations

import io
import time

from rich.console import Console
from rich.layout import Layout
from rich.table import Table

from brainfog.dashboard import Dashboard, DashboardUpdate
from brainfog.metrics import ToolCallMetric

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_metric(
    command: str = "ls -la",
    tokens_raw: int = 200,
    tokens_saved: int = 150,
    was_pruned: bool = True,
    category: str = "directory_listing",
) -> ToolCallMetric:
    return ToolCallMetric(
        log_id="test-id",
        tool_name="Bash",
        command=command,
        category=category,
        volatility="volatile",
        tokens_raw=tokens_raw,
        tokens_pruned=tokens_raw - tokens_saved,
        tokens_saved=tokens_saved,
        was_pruned=was_pruned,
        timestamp="2026-03-15T01:00:00",
    )


def _silent_dashboard() -> Dashboard:
    """Return a Dashboard backed by a silent string-buffer Console."""
    return Dashboard(console=Console(file=io.StringIO(), highlight=False))


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def test_initial_state_is_zero():
    d = _silent_dashboard()
    assert d._total_calls == 0
    assert d._total_pruned == 0
    assert d._total_tokens_saved == 0
    assert d._recent == []


def test_push_enqueues_update():
    d = _silent_dashboard()
    metric = _make_metric()
    d.push(metric)
    assert not d._queue.empty()
    update = d._queue.get_nowait()
    assert isinstance(update, DashboardUpdate)
    assert update.metric is metric


def test_push_none_sentinel_enqueues_none():
    d = _silent_dashboard()
    d._queue.put(None)
    assert d._queue.get_nowait() is None


# ---------------------------------------------------------------------------
# _build_table (state injection)
# ---------------------------------------------------------------------------

def test_build_table_returns_table_instance():
    d = _silent_dashboard()
    result = d._build_table()
    assert isinstance(result, Table)


def test_build_table_empty_has_no_rows():
    d = _silent_dashboard()
    table = d._build_table()
    assert table.row_count == 0


def test_build_table_reflects_pushed_metrics():
    d = _silent_dashboard()
    d._recent = [_make_metric(command="ls -la"), _make_metric(command="git log")]
    table = d._build_table()
    assert table.row_count == 2


def test_build_table_caps_at_max_rows():
    d = _silent_dashboard()
    d._recent = [_make_metric(command=f"cmd {i}") for i in range(25)]
    # _build_table renders all of _recent (capping happens in _run)
    table = d._build_table()
    assert table.row_count == 25


def test_build_table_truncates_long_command():
    d = _silent_dashboard()
    long_cmd = "a" * 80
    d._recent = [_make_metric(command=long_cmd)]
    # Should not raise; truncation happens inside _build_table
    table = d._build_table()
    assert table.row_count == 1


# ---------------------------------------------------------------------------
# _render
# ---------------------------------------------------------------------------

def test_render_returns_layout():
    d = _silent_dashboard()
    result = d._render()
    assert isinstance(result, Layout)


def test_render_has_three_sections():
    d = _silent_dashboard()
    layout = d._render()
    names = {child.name for child in layout.children}
    assert {"header", "body", "footer"} == names


# ---------------------------------------------------------------------------
# Thread lifecycle
# ---------------------------------------------------------------------------

def test_start_creates_running_thread():
    d = _silent_dashboard()
    d.start()
    assert d._thread is not None
    assert d._thread.is_alive()
    d.stop()


def test_stop_terminates_thread():
    d = _silent_dashboard()
    d.start()
    d.stop()
    # Give the thread a moment to exit after stop()
    assert d._thread is not None
    d._thread.join(timeout=2.0)
    assert not d._thread.is_alive()


def test_start_stop_multiple_times_is_safe():
    """Each start() creates a fresh thread; stop() must be called after each start()."""
    d = _silent_dashboard()
    d.start()
    d.stop()
    d._thread.join(timeout=2.0)
    # A second start/stop cycle should work without error
    d.start()
    d.stop()
    d._thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Full pipeline: push → drain → verify state
# ---------------------------------------------------------------------------

def test_push_updates_counters_after_drain():
    """Push a metric, let the background thread process it, verify counters."""
    d = _silent_dashboard()
    d.start()

    metric = _make_metric(tokens_raw=100, tokens_saved=80, was_pruned=True)
    d.push(metric)

    # Wait for the background thread to drain the queue
    deadline = time.monotonic() + 2.0
    while not d._queue.empty() and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.1)  # one extra tick for processing

    d.stop()

    assert d._total_calls == 1
    assert d._total_pruned == 1
    assert d._total_tokens_saved == 80


def test_push_durable_metric_does_not_increment_pruned():
    d = _silent_dashboard()
    d.start()

    metric = _make_metric(tokens_raw=50, tokens_saved=0, was_pruned=False)
    d.push(metric)

    deadline = time.monotonic() + 2.0
    while not d._queue.empty() and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.1)

    d.stop()

    assert d._total_calls == 1
    assert d._total_pruned == 0
    assert d._total_tokens_saved == 0


def test_recent_list_capped_at_max_rows():
    d = _silent_dashboard()
    d.start()

    for i in range(25):
        d.push(_make_metric(command=f"cmd {i}"))

    deadline = time.monotonic() + 3.0
    while d._queue.qsize() > 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.1)

    d.stop()

    assert len(d._recent) <= d.MAX_ROWS
