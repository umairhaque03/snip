"""
Volatility classifier.

Determines whether a tool's output is Durable (pass through unchanged)
or Volatile (candidate for pruning), and which pruning category applies.

Classification is a pure function — no I/O, no state.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum

from snip.constants import (
    CODE_INDICATOR_PATTERNS,
    DURABLE_COMMANDS,
    DURABLE_MCP_TOOLS,
    VOLATILE_COMMAND_PREFIXES,
    VOLATILE_CONTENT_PATTERNS,
    VOLATILE_MCP_TOOLS,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class VolatilityClass(Enum):
    DURABLE = "durable"
    VOLATILE = "volatile"


@dataclass(frozen=True)
class ClassificationResult:
    """Immutable result of classifying a single tool output."""

    volatility: VolatilityClass
    category: str        # e.g., "directory_listing", "test_output", "durable"
    confidence: float    # 0.0 to 1.0
    reason: str          # Human-readable explanation for the decision


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(
    tool_name: str,
    command: str,
    output: str,
) -> ClassificationResult:
    """
    Classify a tool output as Durable or Volatile.

    Checks in priority order:
      1. Exact MCP tool name match (Durable or Volatile)
      2. Command prefix match against known command lists
      3. Content-based heuristics as a fallback

    Args:
        tool_name: The MCP tool name (e.g., "Bash", "Read", "Grep").
        command:   The command string or arguments passed to the tool.
        output:    The raw output string from the tool.

    Returns:
        A ClassificationResult with volatility, category, confidence, reason.
    """
    # 1. Check known-Durable MCP tool names
    result = _classify_by_mcp_tool_name(tool_name)
    if result is not None:
        return result

    effective_cmd = _extract_effective_command(command)

    # 2. Check known-Durable command prefixes
    result = _classify_by_durable_command(effective_cmd)
    if result is not None:
        return result

    # 3. Check known-Volatile command prefixes
    result = _classify_by_volatile_command(effective_cmd)
    if result is not None:
        return result

    # 4. Check Volatile MCP tool names (e.g., Glob → directory_listing)
    result = _classify_by_volatile_mcp_tool(tool_name, effective_cmd)
    if result is not None:
        return result

    # 5. Content heuristics — only kick in for longer outputs
    result = _classify_by_content(output)
    if result is not None:
        return result

    # 6. Default: Durable (safety-first — never prune ambiguous short output)
    return ClassificationResult(
        volatility=VolatilityClass.DURABLE,
        category="durable",
        confidence=0.5,
        reason="No matching classification rule; defaulting to Durable (safety-first)",
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_SHELL_PREFIXES_TO_STRIP = re.compile(
    r"""
    ^\s*
    (?:
        cd\s+\S+\s*&&\s*        |  # cd /some/path &&
        pushd\s+\S+\s*&&\s*     |  # pushd /path &&
        export\s+\S+=\S*\s*&&\s*|  # export FOO=bar &&
        env\s+\S+=\S*\s+        |  # env VAR=val <cmd>
        sudo\s+                     # sudo <cmd>
    )
    """,
    re.VERBOSE,
)


def _extract_effective_command(command: str) -> str:
    """
    Strip shell wrappers (cd, sudo, env, pipes) to find the classifiable
    command. For compound commands joined with ``&&``, use the **last**
    segment since its output dominates stdout.
    """
    segments = re.split(r"\s*&&\s*", command)
    effective = segments[-1].strip() if segments else command.strip()

    effective = re.sub(r"\s*\d*>&\d+\s*", " ", effective)
    effective = re.sub(r"\s*2>/dev/null\s*", " ", effective)

    effective = _SHELL_PREFIXES_TO_STRIP.sub("", effective).strip()

    pipe_idx = effective.find("|")
    if pipe_idx != -1:
        effective = effective[:pipe_idx].strip()

    return effective


def _classify_by_mcp_tool_name(tool_name: str) -> ClassificationResult | None:
    """Return Durable if tool_name is a known-Durable MCP tool."""
    if tool_name in DURABLE_MCP_TOOLS:
        return ClassificationResult(
            volatility=VolatilityClass.DURABLE,
            category="durable",
            confidence=1.0,
            reason=f"Known-Durable MCP tool: {tool_name!r}",
        )
    return None


def _classify_by_durable_command(command: str) -> ClassificationResult | None:
    """Return Durable if the first token of the command is a known-Durable command."""
    normalized = command.strip().lower()
    if not normalized:
        return None
    first_token = normalized.split()[0]
    if first_token in DURABLE_COMMANDS:
        return ClassificationResult(
            volatility=VolatilityClass.DURABLE,
            category="durable",
            confidence=0.95,
            reason=f"Command starts with known-Durable prefix: {first_token!r}",
        )
    return None


def _classify_by_volatile_command(command: str) -> ClassificationResult | None:
    """
    Return the first matching Volatile category for the command string.

    Checks VOLATILE_COMMAND_PREFIXES in order; first match wins.
    Uses exact-or-followed-by-space matching to avoid false prefix matches
    (e.g. "ls" must not match "lsblk").
    """
    normalized = command.strip().lower()
    for prefix, category in VOLATILE_COMMAND_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + " ") or normalized.startswith(prefix + "\t"):
            return ClassificationResult(
                volatility=VolatilityClass.VOLATILE,
                category=category,
                confidence=0.95,
                reason=f"Command matches Volatile prefix {prefix!r} → {category!r}",
            )
    return None


def _classify_by_volatile_mcp_tool(
    tool_name: str, command: str
) -> ClassificationResult | None:
    """
    Return a Volatile classification if tool_name is a known-Volatile MCP tool.

    Bash is skipped — it's already handled by _classify_by_volatile_command.
    Non-Bash tools like Glob and Grep have a fixed category in VOLATILE_MCP_TOOLS.
    """
    if tool_name == "Bash":
        # Already handled upstream by _classify_by_volatile_command.
        return None
    category = VOLATILE_MCP_TOOLS.get(tool_name)
    if category is not None:
        return ClassificationResult(
            volatility=VolatilityClass.VOLATILE,
            category=category,
            confidence=0.9,
            reason=f"Known-Volatile MCP tool: {tool_name!r} → {category!r}",
        )
    return None


def _classify_by_content(output: str) -> ClassificationResult | None:
    """
    Content-based heuristic classification as a last resort.

    Scores the first 20 lines against code and volatile pattern sets.
    Only returns Volatile if volatile signals clearly dominate (> 30% of
    sampled lines and more than code signals). Returns None otherwise to
    let the caller apply the safe Durable default.
    """
    lines = output.splitlines()
    if not lines:
        return None

    sample = lines[:20]
    sample_size = len(sample)

    code_score = sum(
        1 for line in sample if _matches_any_pattern(line, CODE_INDICATOR_PATTERNS) > 0
    )
    volatile_score = sum(
        1 for line in sample if _matches_any_pattern(line, VOLATILE_CONTENT_PATTERNS) > 0
    )

    if volatile_score > code_score and volatile_score / sample_size > 0.3:
        confidence = min(0.85, volatile_score / sample_size)
        return ClassificationResult(
            volatility=VolatilityClass.VOLATILE,
            category="generic_volatile",
            confidence=confidence,
            reason=(
                f"Content heuristic: {volatile_score}/{sample_size} sample lines match "
                f"Volatile patterns (code_score={code_score})"
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _matches_any_pattern(text: str, patterns: list[str]) -> int:
    """Count how many of the given regex patterns match anywhere in text."""
    return sum(1 for p in patterns if re.search(p, text, re.MULTILINE))
