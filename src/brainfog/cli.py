"""
BrainFog CLI entry point.

Commands:
  brainfog init        Register BrainFog as an MCP server in Claude Code config
  brainfog serve       Start the BrainFog MCP server (stdio transport)
  brainfog benchmark   Run BrainFog against the test corpus and produce a report
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
@click.version_option(package_name="brainfog")
def main() -> None:
    """BrainFog — Reduce token bloat in agentic AI workflows."""


# ---------------------------------------------------------------------------
# brainfog init
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    default=None,
    help="Override path to Claude Code MCP config file.",
)
@click.option("--force", is_flag=True, help="Re-register even if already registered.")
def init(config: Path | None, force: bool) -> None:
    """Register BrainFog as an MCP server in Claude Code config."""
    from brainfog.config import (
        add_brainfog_server,
        get_config_path,
        is_brainfog_registered,
        read_config,
        write_config_atomic,
    )

    config_path = config or get_config_path()

    if not force and is_brainfog_registered(config_path):
        console.print(
            Panel(
                f"[green]BrainFog is already registered.[/green]\n"
                f"Config: {config_path}\n"
                f"Use [bold]--force[/bold] to re-register.",
                title="BrainFog Init",
            )
        )
        return

    existing_config = read_config(config_path)
    new_config = add_brainfog_server(existing_config)
    write_config_atomic(new_config, config_path)

    entry = new_config["mcpServers"]["brainfog"]
    console.print(
        Panel(
            f"[green]BrainFog registered successfully.[/green]\n\n"
            f"Config path: [bold]{config_path}[/bold]\n"
            f"Server entry:\n"
            f"  command: {entry['command']}\n"
            f"  args:    {entry['args']}",
            title="BrainFog Init",
        )
    )


# ---------------------------------------------------------------------------
# brainfog serve
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=None,
    help="Override path to the SQLite database file.",
)
def serve(db: Path | None) -> None:
    """Start the BrainFog MCP server (stdio transport, for use by Claude Code)."""
    from brainfog.server import serve as _serve

    asyncio.run(_serve(db_path=db))


# ---------------------------------------------------------------------------
# brainfog benchmark
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("benchmark_results.md"),
    show_default=True,
    help="Output path for the benchmark markdown report.",
)
@click.option(
    "--corpus",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Override path to the corpus directory.",
)
def benchmark(output: Path, corpus: Path | None) -> None:
    """
    Run BrainFog against the test corpus and produce a markdown report.

    Loads all .txt files from the corpus/ directory, classifies and prunes
    each one, counts tokens before and after, and writes a summary report.
    """
    from brainfog.classifier import classify
    from brainfog.db import RawLogEntry
    from brainfog.pruner import prune

    corpus_dir = corpus or (Path(__file__).parent.parent.parent / "corpus")

    corpus_files = sorted(corpus_dir.glob("*.txt"))
    if not corpus_files:
        console.print(f"[yellow]No .txt files found in {corpus_dir}[/yellow]")
        return

    rows: list[dict] = []
    for txt_file in corpus_files:
        content = txt_file.read_text(encoding="utf-8", errors="replace")

        # Derive tool_name and command from filename (e.g. ls_large.txt → "ls -la")
        tool_name, command = _corpus_filename_to_tool(txt_file.stem)

        classification = classify(tool_name=tool_name, command=command, output=content)
        log_id = RawLogEntry.new_id()
        result = prune(content, log_id, classification)

        pct = (
            (result.tokens_saved / result.tokens_raw * 100)
            if result.tokens_raw > 0
            else 0.0
        )
        rows.append(
            {
                "filename": txt_file.name,
                "category": classification.category,
                "tokens_raw": result.tokens_raw,
                "tokens_pruned": result.tokens_pruned,
                "tokens_saved": result.tokens_saved,
                "pct_reduction": pct,
                "was_pruned": result.was_pruned,
            }
        )

    rows.sort(key=lambda r: r["tokens_saved"], reverse=True)

    _write_benchmark_report(rows, output)
    _print_benchmark_table(rows)
    console.print(f"\n[bold green]Report written to:[/bold green] {output}")


# ---------------------------------------------------------------------------
# Benchmark report helpers
# ---------------------------------------------------------------------------

def _corpus_filename_to_tool(stem: str) -> tuple[str, str]:
    """
    Map a corpus filename stem to a (tool_name, command) pair for classification.

    Examples:
        ls_large        → ("Bash", "ls -la /tmp")
        grep_results    → ("Bash", "grep -r TODO src/")
        test_fail       → ("Bash", "pytest")
        test_pass       → ("Bash", "pytest")
        build_log_fail  → ("Bash", "make build")
        build_log_success → ("Bash", "make build")
        git_log         → ("Bash", "git log")
        pip_install     → ("Bash", "pip install")
        file_read_python → ("Read", "")
    """
    mapping: dict[str, tuple[str, str]] = {
        "ls_large": ("Bash", "ls -la /tmp"),
        "grep_results": ("Bash", "grep -r TODO src/"),
        "test_fail": ("Bash", "pytest"),
        "test_pass": ("Bash", "pytest"),
        "build_log_fail": ("Bash", "make build"),
        "build_log_success": ("Bash", "make build"),
        "git_log": ("Bash", "git log"),
        "pip_install": ("Bash", "pip install requests"),
        "file_read_python": ("Read", ""),
    }
    return mapping.get(stem, ("Bash", stem.replace("_", " ")))


def _write_benchmark_report(rows: list[dict], output: Path) -> None:
    """
    Write a markdown benchmark report to disk.

    Args:
        rows:   List of dicts with keys: filename, category, tokens_raw,
                tokens_pruned, tokens_saved, pct_reduction.
        output: Output file path.
    """
    total_raw = sum(r["tokens_raw"] for r in rows)
    total_pruned = sum(r["tokens_pruned"] for r in rows)
    total_saved = sum(r["tokens_saved"] for r in rows)
    overall_pct = (total_saved / total_raw * 100) if total_raw > 0 else 0.0

    lines = [
        "# BrainFog Benchmark Results",
        "",
        "Rule-based token pruning benchmarked against a fixed corpus of representative tool outputs.",
        "",
        f"**Overall token reduction: {overall_pct:.1f}%** "
        f"({total_saved:,} tokens saved out of {total_raw:,} raw tokens)",
        "",
        "## Results by File",
        "",
        "| File | Category | Raw Tokens | Pruned Tokens | Tokens Saved | % Reduction |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]

    for row in rows:
        pruned_flag = " ✓" if row["was_pruned"] else ""
        lines.append(
            f"| {row['filename']}{pruned_flag} | {row['category']} "
            f"| {row['tokens_raw']:,} | {row['tokens_pruned']:,} "
            f"| {row['tokens_saved']:,} | {row['pct_reduction']:.1f}% |"
        )

    # Totals row
    lines.append(
        f"| **TOTAL** | — "
        f"| **{total_raw:,}** | **{total_pruned:,}** "
        f"| **{total_saved:,}** | **{overall_pct:.1f}%** |"
    )

    lines += [
        "",
        "## Summary",
        "",
        f"- Files processed: {len(rows)}",
        f"- Files pruned: {sum(1 for r in rows if r['was_pruned'])}",
        f"- Total raw tokens: {total_raw:,}",
        f"- Total pruned tokens: {total_pruned:,}",
        f"- Total tokens saved: {total_saved:,}",
        f"- Overall context reduction: {overall_pct:.1f}%",
        "",
        "_Reproduced with: `brainfog benchmark`_",
    ]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_benchmark_table(rows: list[dict]) -> None:
    """Print a rich table of benchmark results to the terminal."""
    table = Table(
        title="BrainFog Benchmark Results",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("File", style="dim")
    table.add_column("Category")
    table.add_column("Raw Tokens", justify="right")
    table.add_column("Pruned Tokens", justify="right")
    table.add_column("Saved", justify="right", style="green")
    table.add_column("% Reduction", justify="right", style="bold green")

    for row in rows:
        pruned_marker = "✓" if row["was_pruned"] else " "
        table.add_row(
            f"{pruned_marker} {row['filename']}",
            row["category"],
            f"{row['tokens_raw']:,}",
            f"{row['tokens_pruned']:,}",
            f"{row['tokens_saved']:,}",
            f"{row['pct_reduction']:.1f}%",
        )

    # Totals row
    total_raw = sum(r["tokens_raw"] for r in rows)
    total_pruned = sum(r["tokens_pruned"] for r in rows)
    total_saved = sum(r["tokens_saved"] for r in rows)
    overall_pct = (total_saved / total_raw * 100) if total_raw > 0 else 0.0

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        "—",
        f"[bold]{total_raw:,}[/bold]",
        f"[bold]{total_pruned:,}[/bold]",
        f"[bold]{total_saved:,}[/bold]",
        f"[bold]{overall_pct:.1f}%[/bold]",
    )

    console.print(table)
