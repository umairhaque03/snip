"""
Rich live CLI dashboard.

Shows a real-time table of recent tool calls and a running "Tokens Saved"
counter during an active brainfog serve session.

The dashboard runs in a background thread and is safe to update from the
async MCP event loop via thread-safe queue.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from brainfog.metrics import ToolCallMetric

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DashboardUpdate:
    """A single metric update to display in the dashboard."""
    metric: ToolCallMetric


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class Dashboard:
    """
    Thread-safe live dashboard backed by a Rich Live display.

    Usage:
        dashboard = Dashboard()
        dashboard.start()           # Start background thread
        dashboard.push(metric)      # Thread-safe update from any thread
        dashboard.stop()            # Graceful shutdown
    """

    # Maximum number of recent tool calls to show in the table.
    MAX_ROWS: int = 20

    def __init__(self, console: Console | None = None) -> None:
        self._queue: queue.Queue[DashboardUpdate | None] = queue.Queue()
        self._recent: list[ToolCallMetric] = []
        self._total_tokens_saved: int = 0
        self._total_calls: int = 0
        self._total_pruned: int = 0
        self._thread: threading.Thread | None = None
        self._start_time: datetime = datetime.now(timezone.utc)
        self._console = console or Console()

    def push(self, metric: ToolCallMetric) -> None:
        """
        Enqueue a metric update. Safe to call from any thread.

        Args:
            metric: The ToolCallMetric to display.
        """
        self._queue.put(DashboardUpdate(metric=metric))

    def start(self) -> None:
        """Start the dashboard background thread."""
        self._start_time = datetime.now(timezone.utc)
        self._thread = threading.Thread(target=self._run, daemon=True, name="brainfog-dashboard")
        self._thread.start()

    def stop(self) -> None:
        """Signal the dashboard to stop and wait for the thread to exit."""
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=3.0)

    def _run(self) -> None:
        """Main loop — runs in the background thread."""
        with Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,
            screen=False,
        ) as live:
            while True:
                try:
                    update = self._queue.get(timeout=0.25)
                except queue.Empty:
                    live.update(self._render())
                    continue

                # None sentinel signals shutdown
                if update is None:
                    break

                # Accumulate state
                self._recent.append(update.metric)
                if len(self._recent) > self.MAX_ROWS:
                    self._recent = self._recent[-self.MAX_ROWS :]
                self._total_tokens_saved += update.metric.tokens_saved
                self._total_calls += 1
                if update.metric.was_pruned:
                    self._total_pruned += 1

                live.update(self._render())

    def _render(self) -> Layout:
        """
        Build the current Rich renderable from internal state.

        Returns a Layout with:
          - Header: "BrainFog" title + session uptime
          - Body: Table of recent tool calls (last MAX_ROWS)
          - Footer: Running totals (tokens saved, calls, prunes)
        """
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        # Header
        uptime = datetime.now(timezone.utc) - self._start_time
        uptime_str = str(uptime).split(".")[0]  # strip microseconds
        header_text = Text.assemble(
            ("BrainFog", "bold green"),
            "  |  ",
            ("Uptime: ", "dim"),
            (uptime_str, "cyan"),
            "  |  ",
            ("Calls: ", "dim"),
            (str(self._total_calls), "white"),
        )
        layout["header"].update(Panel(header_text, border_style="green"))

        # Body — recent tool calls table
        layout["body"].update(self._build_table())

        # Footer — running totals
        pct = (
            (self._total_tokens_saved / max(1, self._total_tokens_saved + sum(
                m.tokens_pruned for m in self._recent
            ))) * 100
            if self._recent
            else 0.0
        )
        footer_text = Text.assemble(
            ("Tokens Saved: ", "dim"),
            (f"{self._total_tokens_saved:,}", "bold green"),
            "   ",
            ("Pruned: ", "dim"),
            (f"{self._total_pruned}", "yellow"),
            "/",
            (f"{self._total_calls}", "white"),
        )
        layout["footer"].update(Panel(footer_text, border_style="dim"))

        return layout

    def _build_table(self) -> Table:
        """Build the recent tool calls Rich Table."""
        table = Table(
            title="Recent Tool Calls",
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
            expand=True,
        )
        table.add_column("Time", style="dim", width=8, no_wrap=True)
        table.add_column("Tool", width=8, no_wrap=True)
        table.add_column("Command", no_wrap=True)
        table.add_column("Category", no_wrap=True)
        table.add_column("Raw Tokens", justify="right", width=11)
        table.add_column("Saved", justify="right", style="green", width=7)
        table.add_column("Pruned", justify="center", width=7)

        # Most recent first
        for metric in reversed(self._recent):
            # Truncate command for display
            cmd = metric.command or ""
            if len(cmd) > 40:
                cmd = cmd[:37] + "..."

            # Timestamp — strip to HH:MM:SS
            try:
                ts = metric.timestamp.split("T")[-1][:8]
            except Exception:
                ts = metric.timestamp[:8] if metric.timestamp else "—"

            if metric.was_pruned:
                row_style = "green"
                pruned_marker = "[green]✓[/green]"
            else:
                row_style = "dim"
                pruned_marker = " "

            table.add_row(
                ts,
                metric.tool_name,
                cmd,
                metric.category,
                f"{metric.tokens_raw:,}",
                f"{metric.tokens_saved:,}",
                pruned_marker,
                style=row_style,
            )

        return table
