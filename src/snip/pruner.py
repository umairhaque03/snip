"""
Rule-based pruning engine.

Each category maps to a dedicated pruning strategy. Strategies are pure
functions: (raw_output: str, log_id: str) -> str (the digest).

Pruning only activates when:
  - volatility == VOLATILE
  - line_count > PRUNE_LINE_THRESHOLD

If those conditions aren't met, the output is returned unchanged with
was_pruned=False.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from snip.classifier import ClassificationResult, VolatilityClass
from snip.constants import (
    BRAINFOG_TAG,
    DIGEST_HEAD_LINES,
    DIGEST_TAIL_LINES,
    GIT_DIGEST_MAX_ENTRIES,
    GREP_DIGEST_HEAD,
    GREP_DIGEST_TAIL,
    INSTALL_DIGEST_MAX_PACKAGES,
    MAX_BUILD_WARNINGS_SHOWN,
    MAX_FAILING_TESTS_SHOWN,
    PRUNE_LINE_THRESHOLD,
    RETRIEVAL_HINT_TEMPLATE,
)
from snip.tokenizer import count_tokens

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PrunedResult:
    """Result of the pruning step for a single tool output."""

    log_id: str             # UUID for retrieval
    pruned_output: str      # The digest/summary to return to Claude
    raw_output: str         # The original full output (stored in DB)
    line_count_raw: int
    line_count_pruned: int
    tokens_raw: int
    tokens_pruned: int
    tokens_saved: int
    was_pruned: bool
    category: str


# A pruning strategy is a callable that takes (raw, log_id) and returns a digest string.
_PruningStrategy = Callable[[str, str], str]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def prune(
    raw_output: str,
    log_id: str,
    classification: ClassificationResult,
) -> PrunedResult:
    """
    Apply the appropriate pruning strategy for the given classification.

    If the output is Durable or does not exceed PRUNE_LINE_THRESHOLD,
    returns it unchanged with was_pruned=False.

    Args:
        raw_output:      The full output string from the tool.
        log_id:          UUID assigned to this log entry.
        classification:  Result from classifier.classify().

    Returns:
        A PrunedResult with the (possibly pruned) output and token metrics.
    """
    lines = raw_output.splitlines()
    tokens_raw = count_tokens(raw_output)

    should_prune = (
        classification.volatility == VolatilityClass.VOLATILE
        and len(lines) > PRUNE_LINE_THRESHOLD
    )

    if not should_prune:
        return PrunedResult(
            log_id=log_id,
            pruned_output=raw_output,
            raw_output=raw_output,
            line_count_raw=len(lines),
            line_count_pruned=len(lines),
            tokens_raw=tokens_raw,
            tokens_pruned=tokens_raw,
            tokens_saved=0,
            was_pruned=False,
            category=classification.category,
        )

    strategy = _get_strategy(classification.category)
    digest = strategy(raw_output, log_id)
    tokens_pruned = count_tokens(digest)

    return PrunedResult(
        log_id=log_id,
        pruned_output=digest,
        raw_output=raw_output,
        line_count_raw=len(lines),
        line_count_pruned=len(digest.splitlines()),
        tokens_raw=tokens_raw,
        tokens_pruned=tokens_pruned,
        tokens_saved=max(0, tokens_raw - tokens_pruned),
        was_pruned=True,
        category=classification.category,
    )


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

def _get_strategy(category: str) -> _PruningStrategy:
    """Return the pruning strategy for the given category."""
    registry: dict[str, _PruningStrategy] = {
        "directory_listing": _prune_directory_listing,
        "grep_results": _prune_grep_results,
        "test_output": _prune_test_output,
        "build_log": _prune_build_log,
        "git_output": _prune_git_output,
        "install_log": _prune_install_log,
        "generic_volatile": _prune_generic,
    }
    return registry.get(category, _prune_generic)


# ---------------------------------------------------------------------------
# Pruning strategies
# ---------------------------------------------------------------------------

def _prune_directory_listing(raw: str, log_id: str) -> str:
    """
    Digest for ls/find/tree/Glob output.

    Shows: total entry count, file extension breakdown, top directories.
    """
    lines = raw.splitlines()

    # Skip blank lines and ls header ("total 1234")
    entry_lines = [
        line for line in lines
        if line.strip() and not re.match(r"^total \d+", line)
    ]

    ext_counts: dict[str, int] = {}
    dir_names: list[str] = []

    for line in entry_lines:
        tokens = line.rstrip().split()
        if not tokens:
            continue
        last = tokens[-1]

        # Skip . and .. entries
        if last in (".", ".."):
            continue

        # Detect directories: ls -la (leading 'd') or trailing '/'
        if re.match(r"^d", line) or last.endswith("/"):
            dir_names.append(last.rstrip("/"))

        # Extract extension from the last token (the filename)
        m = re.search(r"(\.\w+)$", last)
        if m:
            ext = m.group(1).lower()
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

    top_exts = sorted(ext_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]

    parts = [f"{BRAINFOG_TAG} Directory listing: {len(entry_lines)} entries"]

    if top_exts:
        ext_str = ", ".join(f"{ext} ({count})" for ext, count in top_exts)
        parts.append(f"File types: {ext_str}")

    if dir_names:
        shown = dir_names[:8]
        dir_str = ", ".join(f"{d}/" for d in shown)
        remaining = len(dir_names) - len(shown)
        if remaining > 0:
            dir_str += f", ... ({remaining} more)"
        parts.append(f"Directories: {dir_str}")

    parts.append(_retrieval_hint(len(lines), log_id))
    return "\n".join(parts)


def _prune_grep_results(raw: str, log_id: str) -> str:
    """
    Digest for grep/rg/Grep output.

    Shows: total match count, matches per file, first N + last N lines verbatim.
    """
    lines = raw.splitlines()

    # Count matches per file using file:line: pattern
    file_counts: dict[str, int] = {}
    for line in lines:
        m = re.match(r"^([^:]+):\d+:", line)
        if m:
            filename = m.group(1)
            file_counts[filename] = file_counts.get(filename, 0) + 1

    total_matches = sum(file_counts.values()) if file_counts else len(lines)
    top_files = sorted(file_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

    parts = [
        f"{BRAINFOG_TAG} Search results: {total_matches} matches"
        f" across {len(file_counts)} files"
    ]

    if top_files:
        files_str = ", ".join(f"{f} ({c})" for f, c in top_files)
        parts.append(f"Top files: {files_str}")

    # Verbatim head + tail
    if len(lines) > GREP_DIGEST_HEAD + GREP_DIGEST_TAIL:
        parts.append(f"--- First {GREP_DIGEST_HEAD} matches ---")
        parts.extend(lines[:GREP_DIGEST_HEAD])
        parts.append(f"--- Last {GREP_DIGEST_TAIL} matches ---")
        parts.extend(lines[-GREP_DIGEST_TAIL:])
    else:
        parts.extend(lines)

    parts.append(_retrieval_hint(len(lines), log_id))
    return "\n".join(parts)


def _prune_test_output(raw: str, log_id: str) -> str:
    """
    Digest for pytest/jest/cargo test output.

    Shows: pass/fail/skip counts, failing test names + first N traceback lines.
    """
    lines = raw.splitlines()

    # Extract summary counts from the full text
    passed = _extract_int(raw, r"(\d+) passed")
    failed = _extract_int(raw, r"(\d+) failed")
    skipped = _extract_int(raw, r"(\d+) skipped")
    errors = _extract_int(raw, r"(\d+) error")

    count_parts = []
    if passed:
        count_parts.append(f"{passed} passed")
    if failed:
        count_parts.append(f"{failed} failed")
    if skipped:
        count_parts.append(f"{skipped} skipped")
    if errors:
        count_parts.append(f"{errors} error(s)")
    summary = ", ".join(count_parts) if count_parts else "unknown results"

    parts = [f"{BRAINFOG_TAG} Test results: {summary}"]

    # Collect failing test lines (pytest FAILED/ERROR, jest ●)
    failing: list[str] = []
    for line in lines:
        if (
            re.match(r"^FAILED ", line)
            or re.match(r"^ERROR ", line)
            or re.match(r"^● ", line)
        ):
            failing.append(line)

    if failing:
        shown = failing[:MAX_FAILING_TESTS_SHOWN]
        parts.append(f"Failed tests ({len(shown)} of {len(failing)}):")
        for test_line in shown:
            parts.append(f"  {test_line}")

    parts.append(_retrieval_hint(len(lines), log_id))
    return "\n".join(parts)


def _prune_build_log(raw: str, log_id: str) -> str:
    """
    Digest for make/npm run build/cargo build/tsc output.

    Shows: success/failure status, all error lines, first N warning lines.
    """
    lines = raw.splitlines()

    error_lines = [l for l in lines if re.search(r"\b(error|Error|ERROR)\b", l)]
    warning_lines = [l for l in lines if re.search(r"\b(warning|Warning|WARN)\b", l)]

    # Determine build status
    explicitly_failed = bool(
        re.search(r"\b(BUILD FAILED|build failed)\b", raw)
        or re.search(r"\bFound \d+ error", raw)
    )
    status = "FAILED" if (error_lines or explicitly_failed) else "SUCCESS"

    parts = [
        f"{BRAINFOG_TAG} Build: {status}"
        f" ({len(error_lines)} errors, {len(warning_lines)} warnings)"
    ]

    if error_lines:
        parts.append("Errors:")
        for line in error_lines:
            parts.append(f"  {line}")

    if warning_lines:
        shown = warning_lines[:MAX_BUILD_WARNINGS_SHOWN]
        remaining = len(warning_lines) - len(shown)
        parts.append(f"Warnings (showing {len(shown)} of {len(warning_lines)}):")
        for line in shown:
            parts.append(f"  {line}")
        if remaining > 0:
            parts.append(f"  ... and {remaining} more warnings")

    parts.append(_retrieval_hint(len(lines), log_id))
    return "\n".join(parts)


def _prune_git_output(raw: str, log_id: str) -> str:
    """
    Digest for git log/status/diff --stat output.

    Shows: total entry count, first N entries verbatim, remainder as count.
    """
    lines = raw.splitlines()

    # Detect git log format by looking for "commit <hash>" lines near the top
    is_log_format = any(
        re.match(r"^commit \S+", line) for line in lines[:10]
    )

    if is_log_format:
        # Split output into individual commit blocks
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if re.match(r"^commit \S+", line) and current:
                blocks.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(current)

        shown_blocks = blocks[:GIT_DIGEST_MAX_ENTRIES]
        remaining = len(blocks) - len(shown_blocks)

        parts = [
            f"{BRAINFOG_TAG} Git log: {len(blocks)} commits",
            f"--- Most recent {len(shown_blocks)} commits ---",
        ]
        for block in shown_blocks:
            parts.extend(block)
        if remaining > 0:
            parts.append(f"... and {remaining} more commits")

    else:
        # git status / diff --stat: show first N lines
        shown = lines[:GIT_DIGEST_MAX_ENTRIES]
        remaining = len(lines) - len(shown)

        parts = [
            f"{BRAINFOG_TAG} Git output: {len(lines)} lines",
            f"--- First {len(shown)} lines ---",
        ]
        parts.extend(shown)
        if remaining > 0:
            parts.append(f"... and {remaining} more lines")

    parts.append(_retrieval_hint(len(lines), log_id))
    return "\n".join(parts)


def _prune_install_log(raw: str, log_id: str) -> str:
    """
    Digest for pip install/npm install output.

    Shows: success/failure, package names and versions installed.
    """
    lines = raw.splitlines()

    # Detect success
    success = bool(
        re.search(r"Successfully installed", raw)
        or re.search(r"added \d+ packages", raw)
        or re.search(r"successfully installed", raw, re.IGNORECASE)
    )
    status = "SUCCESS" if success else "UNKNOWN"

    # Extract packages: pip "Successfully installed pkg-ver pkg-ver ..."
    packages: list[str] = []
    m = re.search(r"Successfully installed (.+)", raw)
    if m:
        packages = m.group(1).split()
    else:
        # npm style: lines starting with "+"
        for line in lines:
            nm = re.match(r"^\+ (.+)", line)
            if nm:
                packages.append(nm.group(1))

    parts = [f"{BRAINFOG_TAG} Install: {status} — {len(packages)} packages"]

    if packages:
        shown = packages[:INSTALL_DIGEST_MAX_PACKAGES]
        remaining = len(packages) - len(shown)
        pkg_str = ", ".join(shown)
        if remaining > 0:
            pkg_str += f", ... ({remaining} more)"
        parts.append(f"Key packages: {pkg_str}")

    parts.append(_retrieval_hint(len(lines), log_id))
    return "\n".join(parts)


def _prune_generic(raw: str, log_id: str) -> str:
    """
    Fallback digest for unknown Volatile outputs.

    Shows first N and last N lines verbatim, with total line count.
    """
    lines = raw.splitlines()
    total = len(lines)

    # If the output is small enough to show entirely without overlap, just show it
    if total <= DIGEST_HEAD_LINES + DIGEST_TAIL_LINES:
        parts = [f"{BRAINFOG_TAG} Output ({total} lines):"]
        parts.extend(lines)
        parts.append(_retrieval_hint(total, log_id))
        return "\n".join(parts)

    head = lines[:DIGEST_HEAD_LINES]
    tail = lines[-DIGEST_TAIL_LINES:]
    omitted = total - DIGEST_HEAD_LINES - DIGEST_TAIL_LINES

    parts = [f"{BRAINFOG_TAG} Output truncated ({total} lines)"]
    parts.append(f"--- First {DIGEST_HEAD_LINES} lines ---")
    parts.extend(head)
    parts.append(f"--- [{omitted} lines omitted] ---")
    parts.append(f"--- Last {DIGEST_TAIL_LINES} lines ---")
    parts.extend(tail)
    parts.append(_retrieval_hint(total, log_id))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _retrieval_hint(line_count: int, log_id: str) -> str:
    return RETRIEVAL_HINT_TEMPLATE.format(line_count=line_count, log_id=log_id)


def _extract_int(text: str, pattern: str) -> int:
    """Extract the first captured integer from a regex pattern, or 0 if not found."""
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0
