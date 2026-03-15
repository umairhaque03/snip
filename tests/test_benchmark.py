"""Tests for the brainfog benchmark command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from brainfog.cli import benchmark


def test_benchmark_runs_without_error(corpus_dir: Path, tmp_path: Path):
    runner = CliRunner()
    output_file = tmp_path / "results.md"
    result = runner.invoke(benchmark, ["--corpus", str(corpus_dir), "--output", str(output_file)])
    assert result.exit_code == 0, result.output


def test_benchmark_produces_output_file(corpus_dir: Path, tmp_path: Path):
    runner = CliRunner()
    output_file = tmp_path / "results.md"
    runner.invoke(benchmark, ["--corpus", str(corpus_dir), "--output", str(output_file)])
    assert output_file.exists()


def test_benchmark_report_contains_markdown_table(corpus_dir: Path, tmp_path: Path):
    runner = CliRunner()
    output_file = tmp_path / "results.md"
    runner.invoke(benchmark, ["--corpus", str(corpus_dir), "--output", str(output_file)])
    content = output_file.read_text()
    # Markdown table must have a header row and separator
    assert "|" in content
    assert "---" in content


def test_benchmark_report_mentions_tokens_saved(corpus_dir: Path, tmp_path: Path):
    runner = CliRunner()
    output_file = tmp_path / "results.md"
    runner.invoke(benchmark, ["--corpus", str(corpus_dir), "--output", str(output_file)])
    content = output_file.read_text()
    assert "token" in content.lower() or "Token" in content
