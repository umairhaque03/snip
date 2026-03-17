"""
Claude Code MCP config file manipulation.

Manages reading, merging, and atomically writing to:
  ~/.claude.json        (Claude Code — user-level MCP servers)

All operations are immutable: read the existing config, create a new merged
dict, write to a temp file, then rename into place. The original is never
modified in-memory or on disk until the rename succeeds.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

_CONFIG_RELATIVE_PATH = ".claude.json"

# Legacy server names to remove on registration
_LEGACY_SERVER_NAMES: frozenset[str] = frozenset(["brainfog", "ctxsift"])

_SNIP_SERVER_ENTRY: dict[str, Any] = {
    "command": "snip",
    "args": ["serve"],
    "env": {},
}


def get_config_path() -> Path:
    """Return the absolute path to the Claude Code MCP config file."""
    return Path.home() / _CONFIG_RELATIVE_PATH


def read_config(config_path: Path | None = None) -> dict[str, Any]:
    """
    Read and parse the Claude Code MCP config file.

    Returns an empty dict if the file does not exist.

    Args:
        config_path: Path to the config file. Defaults to the standard location.

    Returns:
        Parsed JSON as a plain dict.

    Raises:
        json.JSONDecodeError: If the file exists but contains invalid JSON.
        ValueError: If the file contains valid JSON but not a dict.
    """
    path = config_path or get_config_path()
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(f"Expected a JSON object in {path}, got {type(result).__name__}")
    return result


def add_snip_server(
    config: dict[str, Any],
    server_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Return a new config dict with the snip MCP server entry merged in.

    Does NOT mutate the input config. Creates a new dict.
    Removes any legacy "brainfog" or "ctxsift" entries automatically.

    Args:
        config:       The existing parsed config dict.
        server_entry: Override for the server entry. Defaults to the standard entry.

    Returns:
        A new dict with snip added under config["mcpServers"]["snip"].
    """
    entry = server_entry or _SNIP_SERVER_ENTRY
    new_config: dict[str, Any] = copy.deepcopy(config)
    if "mcpServers" not in new_config or not isinstance(new_config["mcpServers"], dict):
        new_config["mcpServers"] = {}
    for legacy_name in _LEGACY_SERVER_NAMES:
        new_config["mcpServers"].pop(legacy_name, None)
    new_config["mcpServers"]["snip"] = copy.deepcopy(entry)
    return new_config


def write_config_atomic(config: dict[str, Any], config_path: Path | None = None) -> None:
    """
    Write a config dict to disk atomically.

    Writes to a temp file in the same directory, then renames into place.
    This ensures the config file is never in a partially-written state.

    Args:
        config:      The config dict to serialize and write.
        config_path: Destination path. Defaults to the standard location.

    Raises:
        OSError: If the write or rename fails.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(config, indent=2)

    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(serialized)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Clean up the temp file if something goes wrong before the rename
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def is_snip_registered(config_path: Path | None = None) -> bool:
    """
    Return True if snip is already registered in the MCP config.

    Returns False if only legacy names ("brainfog", "ctxsift") are present,
    indicating re-registration is needed to migrate to the new name.

    Args:
        config_path: Path to the config file. Defaults to the standard location.

    Returns:
        True if "snip" exists under config["mcpServers"].
    """
    config = read_config(config_path)
    mcp_servers = config.get("mcpServers", {})
    return isinstance(mcp_servers, dict) and "snip" in mcp_servers


def has_legacy_server(config_path: Path | None = None) -> bool:
    """Return True if any legacy MCP entry ("brainfog", "ctxsift") still exists."""
    config = read_config(config_path)
    mcp_servers = config.get("mcpServers", {})
    return isinstance(mcp_servers, dict) and bool(
        _LEGACY_SERVER_NAMES & set(mcp_servers.keys())
    )
