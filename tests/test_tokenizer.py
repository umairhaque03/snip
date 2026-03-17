"""Tests for the tiktoken wrapper."""

from __future__ import annotations

from snip.tokenizer import count_tokens, tokens_saved


def test_empty_string_returns_zero():
    assert count_tokens("") == 0


def test_nonempty_string_returns_positive():
    assert count_tokens("hello world") > 0


def test_longer_text_has_more_tokens():
    short = "hello"
    long = "hello " * 100
    assert count_tokens(long) > count_tokens(short)


def test_tokens_saved_returns_nonnegative():
    raw = "hello world " * 100
    pruned = "hello"
    assert tokens_saved(raw, pruned) >= 0


def test_tokens_saved_is_zero_when_equal():
    text = "hello world"
    assert tokens_saved(text, text) == 0


def test_tokens_saved_is_positive_when_pruned_shorter():
    raw = "hello world " * 100
    pruned = "hello"
    assert tokens_saved(raw, pruned) > 0


def test_count_tokens_returns_int():
    result = count_tokens("some text")
    assert isinstance(result, int)
