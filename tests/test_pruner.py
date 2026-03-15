"""
Tests for the rule-based pruning engine.

Coverage targets:
  - Durable outputs always pass through unchanged
  - Short Volatile outputs (< threshold) pass through unchanged
  - Each category-specific strategy produces correct digest format
  - Token counts are always positive
  - tokens_saved >= 0
  - PrunedResult is immutable
  - Retrieval hint is always present in pruned output
"""

from __future__ import annotations

import pytest

from brainfog.classifier import ClassificationResult, VolatilityClass
from brainfog.constants import PRUNE_LINE_THRESHOLD
from brainfog.pruner import prune

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def volatile(category: str) -> ClassificationResult:
    return ClassificationResult(VolatilityClass.VOLATILE, category, 0.95, "test")


def durable() -> ClassificationResult:
    return ClassificationResult(VolatilityClass.DURABLE, "durable", 1.0, "test")


def make_output(n_lines: int, prefix: str = "line") -> str:
    return "\n".join(f"{prefix} {i}" for i in range(n_lines))


# ---------------------------------------------------------------------------
# Pass-through conditions
# ---------------------------------------------------------------------------

def test_durable_short_passes_through():
    output = make_output(10)
    result = prune(output, "test-id", durable())
    assert result.was_pruned is False
    assert result.pruned_output == output


def test_durable_long_passes_through():
    output = make_output(200)
    result = prune(output, "test-id", durable())
    assert result.was_pruned is False
    assert result.pruned_output == output


def test_volatile_short_passes_through():
    output = make_output(PRUNE_LINE_THRESHOLD - 1)
    result = prune(output, "test-id", volatile("directory_listing"))
    assert result.was_pruned is False


def test_volatile_at_threshold_passes_through():
    output = make_output(PRUNE_LINE_THRESHOLD)
    result = prune(output, "test-id", volatile("directory_listing"))
    assert result.was_pruned is False


# ---------------------------------------------------------------------------
# Pruning is triggered
# ---------------------------------------------------------------------------

def test_volatile_over_threshold_is_pruned():
    output = make_output(PRUNE_LINE_THRESHOLD + 1)
    result = prune(output, "test-id", volatile("directory_listing"))
    assert result.was_pruned is True


def test_pruned_output_is_shorter_than_raw():
    output = make_output(200)
    result = prune(output, "test-id", volatile("directory_listing"))
    assert result.line_count_pruned < result.line_count_raw


def test_tokens_saved_is_positive_after_pruning():
    output = make_output(200)
    result = prune(output, "test-id", volatile("directory_listing"))
    assert result.tokens_saved > 0


def test_tokens_saved_never_negative():
    output = make_output(200)
    result = prune(output, "test-id", volatile("generic_volatile"))
    assert result.tokens_saved >= 0


# ---------------------------------------------------------------------------
# Retrieval hint
# ---------------------------------------------------------------------------

def test_pruned_output_contains_retrieval_hint():
    output = make_output(200)
    result = prune(output, "my-log-id", volatile("directory_listing"))
    assert "my-log-id" in result.pruned_output


def test_pruned_output_contains_raw_line_count():
    output = make_output(200)
    result = prune(output, "test-id", volatile("directory_listing"))
    assert "200" in result.pruned_output


# ---------------------------------------------------------------------------
# Category-specific digest content
# ---------------------------------------------------------------------------

def test_directory_listing_digest_mentions_extensions():
    lines = [f"-rw-r--r-- 1 user staff 100 Mar 15 file{i}.py" for i in range(100)]
    output = "\n".join(lines)
    result = prune(output, "test-id", volatile("directory_listing"))
    assert ".py" in result.pruned_output


def test_grep_results_digest_shows_file_counts():
    lines = [f"src/auth.py:{i}: login" for i in range(60)] + [f"src/utils.py:{i}: login" for i in range(30)]
    output = "\n".join(lines)
    result = prune(output, "test-id", volatile("grep_results"))
    assert "auth.py" in result.pruned_output


def test_test_output_digest_shows_failure_names():
    lines = [
        "collected 50 items",
        *["." for _ in range(47)],
        "FAILED tests/test_auth.py::test_login - AssertionError",
        "FAILED tests/test_db.py::test_connect - ConnectionError",
        "FAILED tests/test_cache.py::test_ttl - TimeoutError",
        "3 failed, 47 passed in 2.1s",
    ]
    output = "\n".join(lines)
    result = prune(output, "test-id", volatile("test_output"))
    assert "test_login" in result.pruned_output or "test_auth" in result.pruned_output


def test_build_log_digest_shows_errors():
    lines = [
        "Compiling...",
        *[f"Building module {i}..." for i in range(40)],
        "src/main.ts(12,3): error TS2304: Cannot find name 'Foo'",
        "src/util.ts(45,8): error TS2345: Type mismatch",
        "Found 2 errors.",
    ]
    output = "\n".join(lines)
    result = prune(output, "test-id", volatile("build_log"))
    assert "error" in result.pruned_output.lower()


def test_git_output_digest_shows_commit_count():
    lines = []
    for i in range(20):
        lines += [
            f"commit abc{i:03d}",
            "Author: Dev <dev@example.com>",
            f"Date: Sat Mar 15 0{i % 10}:00:00 2026",
            "",
            f"    feat: commit {i}",
            "",
        ]
    output = "\n".join(lines)
    result = prune(output, "test-id", volatile("git_output"))
    assert "commit" in result.pruned_output.lower()


def test_install_log_digest_shows_packages():
    lines = [
        "Collecting brainfog",
        *[f"Collecting dep{i}" for i in range(20)],
        "Installing collected packages: " + ", ".join(f"dep{i}" for i in range(20)) + ", brainfog",
        "Successfully installed brainfog-0.1.0 " + " ".join(f"dep{i}-1.0.{i}" for i in range(20)),
    ]
    output = "\n".join(lines)
    result = prune(output, "test-id", volatile("install_log"))
    assert "brainfog" in result.pruned_output


def test_generic_digest_shows_head_and_tail():
    lines = [f"line {i}" for i in range(200)]
    output = "\n".join(lines)
    result = prune(output, "test-id", volatile("generic_volatile"))
    assert "line 0" in result.pruned_output
    assert "line 199" in result.pruned_output


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

def test_pruned_result_is_immutable():
    output = make_output(10)
    result = prune(output, "test-id", durable())
    with pytest.raises((AttributeError, TypeError)):
        result.was_pruned = True  # type: ignore[misc]
