"""Tests for Claude Code MCP config file manipulation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brainfog.config import (
    add_brainfog_server,
    is_brainfog_registered,
    read_config,
    write_config_atomic,
)


def test_read_config_returns_empty_dict_when_missing(tmp_path: Path):
    result = read_config(tmp_path / "nonexistent.json")
    assert result == {}


def test_read_config_parses_existing_file(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcpServers": {}}))
    result = read_config(config_file)
    assert result == {"mcpServers": {}}


def test_read_config_raises_on_invalid_json(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text("not valid json {{{")
    with pytest.raises(json.JSONDecodeError):
        read_config(config_file)


def test_add_brainfog_server_does_not_mutate_input():
    original = {"mcpServers": {"other-server": {"command": "other"}}}
    result = add_brainfog_server(original)
    assert "brainfog" not in original.get("mcpServers", {})
    assert "brainfog" in result["mcpServers"]


def test_add_brainfog_server_preserves_existing_servers():
    original = {"mcpServers": {"other-server": {"command": "other"}}}
    result = add_brainfog_server(original)
    assert "other-server" in result["mcpServers"]
    assert "brainfog" in result["mcpServers"]


def test_add_brainfog_server_creates_mcp_servers_key():
    result = add_brainfog_server({})
    assert "mcpServers" in result
    assert "brainfog" in result["mcpServers"]


def test_add_brainfog_server_entry_has_correct_structure():
    result = add_brainfog_server({})
    entry = result["mcpServers"]["brainfog"]
    assert entry["command"] == "brainfog"
    assert "serve" in entry["args"]


def test_write_config_atomic_creates_file(tmp_path: Path):
    config_file = tmp_path / "config.json"
    write_config_atomic({"mcpServers": {}}, config_file)
    assert config_file.exists()


def test_write_config_atomic_produces_valid_json(tmp_path: Path):
    config_file = tmp_path / "config.json"
    write_config_atomic({"mcpServers": {"brainfog": {"command": "brainfog"}}}, config_file)
    parsed = json.loads(config_file.read_text())
    assert parsed["mcpServers"]["brainfog"]["command"] == "brainfog"


def test_is_brainfog_registered_returns_false_when_missing(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcpServers": {}}))
    assert is_brainfog_registered(config_file) is False


def test_is_brainfog_registered_returns_true_when_present(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcpServers": {"brainfog": {"command": "brainfog"}}}))
    assert is_brainfog_registered(config_file) is True
