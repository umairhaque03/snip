"""Tests for Claude Code MCP config file manipulation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from snip.config import (
    add_snip_server,
    has_legacy_server,
    is_snip_registered,
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


def test_add_snip_server_does_not_mutate_input():
    original = {"mcpServers": {"other-server": {"command": "other"}}}
    result = add_snip_server(original)
    assert "snip" not in original.get("mcpServers", {})
    assert "snip" in result["mcpServers"]


def test_add_snip_server_preserves_existing_servers():
    original = {"mcpServers": {"other-server": {"command": "other"}}}
    result = add_snip_server(original)
    assert "other-server" in result["mcpServers"]
    assert "snip" in result["mcpServers"]


def test_add_snip_server_creates_mcp_servers_key():
    result = add_snip_server({})
    assert "mcpServers" in result
    assert "snip" in result["mcpServers"]


def test_add_snip_server_entry_has_correct_structure():
    result = add_snip_server({})
    entry = result["mcpServers"]["snip"]
    assert entry["command"] == "snip"
    assert "serve" in entry["args"]


def test_write_config_atomic_creates_file(tmp_path: Path):
    config_file = tmp_path / "config.json"
    write_config_atomic({"mcpServers": {}}, config_file)
    assert config_file.exists()


def test_write_config_atomic_produces_valid_json(tmp_path: Path):
    config_file = tmp_path / "config.json"
    write_config_atomic({"mcpServers": {"snip": {"command": "snip"}}}, config_file)
    parsed = json.loads(config_file.read_text())
    assert parsed["mcpServers"]["snip"]["command"] == "snip"


def test_is_snip_registered_returns_false_when_missing(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcpServers": {}}))
    assert is_snip_registered(config_file) is False


def test_is_snip_registered_returns_true_when_present(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcpServers": {"snip": {"command": "snip"}}}))
    assert is_snip_registered(config_file) is True


def test_add_snip_server_removes_legacy_brainfog_entry():
    original = {"mcpServers": {"brainfog": {"command": "brainfog", "args": ["serve"]}}}
    result = add_snip_server(original)
    assert "brainfog" not in result["mcpServers"]
    assert "snip" in result["mcpServers"]


def test_add_snip_server_removes_legacy_ctxsift_entry():
    original = {"mcpServers": {"ctxsift": {"command": "ctxsift", "args": ["serve"]}}}
    result = add_snip_server(original)
    assert "ctxsift" not in result["mcpServers"]
    assert "snip" in result["mcpServers"]


def test_has_legacy_server_returns_true_when_brainfog_present(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcpServers": {"brainfog": {"command": "brainfog"}}}))
    assert has_legacy_server(config_file) is True


def test_has_legacy_server_returns_true_when_ctxsift_present(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcpServers": {"ctxsift": {"command": "ctxsift"}}}))
    assert has_legacy_server(config_file) is True


def test_has_legacy_server_returns_false_when_absent(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"mcpServers": {"snip": {"command": "snip"}}}))
    assert has_legacy_server(config_file) is False
