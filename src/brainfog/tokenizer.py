"""
Thin wrapper around tiktoken for approximate token counting.

Uses cl100k_base encoding, which is the closest publicly available
approximation to Claude's tokenizer. Token counts are suitable for
relative comparison and benchmarking — not for billing calculations.
"""

from __future__ import annotations

import tiktoken

from brainfog.constants import TIKTOKEN_ENCODING

# Module-level singleton — encoding initialization is expensive.
_encoding: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    """Return the shared encoding instance, initializing it on first call."""
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding(TIKTOKEN_ENCODING)
    return _encoding


def count_tokens(text: str) -> int:
    """
    Return the approximate token count for the given text.

    Args:
        text: The string to count tokens for.

    Returns:
        Number of tokens (always >= 0).
    """
    # TODO: Consider caching results for repeated identical inputs
    if not text:
        return 0
    return len(_get_encoding().encode(text))


def tokens_saved(raw: str, pruned: str) -> int:
    """
    Return how many tokens were saved by pruning.

    Args:
        raw: The original unmodified output.
        pruned: The pruned/digest output.

    Returns:
        Tokens saved (raw tokens - pruned tokens). May be 0 if pruning
        produced a longer output (shouldn't happen in practice).
    """
    return max(0, count_tokens(raw) - count_tokens(pruned))
