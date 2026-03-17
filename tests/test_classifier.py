"""
Tests for the volatility classifier.

Coverage targets:
  - Known-Durable MCP tool names
  - Known-Durable command prefixes
  - Known-Volatile command prefixes -> correct category
  - Volatile MCP tool names (Glob, Grep)
  - Content-based heuristic fallback
  - Default Durable for ambiguous short outputs
"""

from __future__ import annotations

import pytest

from snip.classifier import VolatilityClass, classify

# ---------------------------------------------------------------------------
# Durable classifications
# ---------------------------------------------------------------------------

def test_read_mcp_tool_is_durable():
    result = classify("Read", "", "def foo(): pass\n")
    assert result.volatility == VolatilityClass.DURABLE
    assert result.category == "durable"


def test_cat_command_is_durable():
    result = classify("Bash", "cat src/main.py", "def foo(): pass\n")
    assert result.volatility == VolatilityClass.DURABLE


def test_short_unknown_output_defaults_to_durable():
    result = classify("Bash", "some-unknown-command", "line 1\nline 2\n")
    assert result.volatility == VolatilityClass.DURABLE


# ---------------------------------------------------------------------------
# Volatile: directory listings
# ---------------------------------------------------------------------------

def test_ls_is_volatile_directory_listing():
    result = classify("Bash", "ls -la /tmp", "total 0\n" + "file.txt\n" * 60)
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "directory_listing"


def test_find_is_volatile_directory_listing():
    result = classify("Bash", "find . -name '*.py'", "\n".join(f"./src/file{i}.py" for i in range(60)))
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "directory_listing"


def test_glob_mcp_tool_is_volatile_directory_listing():
    result = classify("Glob", "**/*.py", "\n".join(f"src/file{i}.py" for i in range(60)))
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "directory_listing"


# ---------------------------------------------------------------------------
# Volatile: grep results
# ---------------------------------------------------------------------------

def test_grep_command_is_volatile_grep_results():
    result = classify("Bash", "grep -r 'TODO' src/", "\n".join(f"src/file.py:{i}: TODO fix this" for i in range(60)))
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "grep_results"


def test_rg_command_is_volatile_grep_results():
    result = classify("Bash", "rg 'classify' src/", "\n".join(f"src/file.py:{i}: classify" for i in range(60)))
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "grep_results"


def test_grep_mcp_tool_is_volatile():
    result = classify("Grep", "classify", "\n".join(f"file.py:{i}: classify" for i in range(60)))
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "grep_results"


# ---------------------------------------------------------------------------
# Volatile: test output
# ---------------------------------------------------------------------------

def test_pytest_command_is_volatile_test_output():
    result = classify("Bash", "pytest tests/", "collected 47 items\n" + "." * 47 + "\n47 passed")
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "test_output"


def test_npm_test_is_volatile_test_output():
    result = classify("Bash", "npm test", "PASS src/app.test.ts\n" * 60)
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "test_output"


# ---------------------------------------------------------------------------
# Volatile: build logs
# ---------------------------------------------------------------------------

def test_make_command_is_volatile_build_log():
    result = classify("Bash", "make build", "Compiling...\n" * 60)
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "build_log"


def test_npm_run_build_is_volatile_build_log():
    result = classify("Bash", "npm run build", "Building for production...\n" * 60)
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "build_log"


# ---------------------------------------------------------------------------
# Volatile: git output
# ---------------------------------------------------------------------------

def test_git_log_is_volatile_git_output():
    result = classify("Bash", "git log --oneline", "\n".join(f"abc{i} feat: commit {i}" for i in range(60)))
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "git_output"


# ---------------------------------------------------------------------------
# Volatile: install logs
# ---------------------------------------------------------------------------

def test_pip_install_is_volatile_install_log():
    result = classify("Bash", "pip install snip", "Collecting snip\n" * 60)
    assert result.volatility == VolatilityClass.VOLATILE
    assert result.category == "install_log"


# ---------------------------------------------------------------------------
# Classification result properties
# ---------------------------------------------------------------------------

def test_classification_result_is_immutable():
    result = classify("Read", "", "code")
    with pytest.raises((AttributeError, TypeError)):
        result.volatility = VolatilityClass.VOLATILE  # type: ignore[misc]


def test_classification_result_has_reason():
    result = classify("Read", "", "code")
    assert isinstance(result.reason, str)
    assert len(result.reason) > 0


def test_classification_confidence_in_range():
    result = classify("Bash", "ls -la", "total 0\n" * 60)
    assert 0.0 <= result.confidence <= 1.0
