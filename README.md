# snip

[![PyPI version](https://img.shields.io/pypi/v/snip.svg)](https://pypi.org/project/snip/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**snip reduces context bloat in agentic coding workflows by classifying shell output, pruning verbose noise into compact digests, and preserving full raw logs for later retrieval.**

---

## Why snip Exists

AI coding agents like Claude Code run shell commands constantly — `ls`, `pip install`, `pytest`, `git log`. Many of these produce large, repetitive outputs that consume thousands of tokens per session without adding information.

The problem:
- A `ls -la` on a large project dumps hundreds of lines into context
- A `pip install` log scrolls through dependency resolution noise
- A full test run repeats stack traces you've already seen
- These outputs eat context window space that could be used for reasoning

The catch: you still need access to the full output later. Suppressing it entirely is wrong.

snip solves this by returning a compact digest to the agent while storing the full raw output locally. The agent gets signal. You keep access to the noise.

---

## How It Works

snip is an MCP server. When configured, Claude Code routes shell commands through snip instead of executing them directly.

```
Agent → snip_run(command) → Execute command
                             → Classify output (Durable / Volatile)
                             → If Durable: return full output
                             → If Volatile and large: prune to digest
                             → Store full raw output in SQLite
                             → Return digest + retrieval ID to agent
```

**Durable output** (errors, stack traces, compiler output, meaningful results) is returned as-is. Nothing is lost.

**Volatile output** (directory listings, install logs, progress bars, repetitive output) beyond the line threshold is summarized into a compact digest. The agent gets the shape of the result without the token cost.

**Full raw output** is always stored locally at `~/.snip/snip.db`. The agent can retrieve it by ID at any time using `get_raw_output`.

---

## Installation

> **Requirements:** Python 3.11+, Claude Code

**Step 1 — Install snip:**

```bash
pip install snip
```

**Step 2 — Register with Claude Code:**

```bash
snip init
```

**Step 3 — Restart Claude Code.**

That's it. You're done. snip is now active on every session automatically — no further setup required.

---

### What `snip init` does

`snip init` writes a single entry into `~/.claude.json` under `mcpServers`. Claude Code reads this file on startup and launches the snip server automatically each time. You never need to start it manually.

If you previously installed an older version under the name `brainfog` or `ctxsift`, `snip init` removes those entries automatically.

---

## MCP Tools

These tools are exposed to Claude Code through the MCP protocol. You do not call them directly — Claude uses them automatically.

| Tool | Description |
|---|---|
| `snip_run` | Execute a shell command. Returns full output if durable, a compact digest if volatile and large. Always stores raw output. |
| `get_raw_output` | Retrieve full raw output for a previous command by its log ID. Use when the digest is not enough. |
| `get_session_stats` | Return token savings and call statistics for the current session. |

### snip_run parameters

| Parameter | Type | Description |
|---|---|---|
| `command` | string | The shell command to execute |
| `cwd` | string (optional) | Working directory |
| `timeout` | int (optional) | Timeout in seconds |

---

## Why Use snip

- Reduces token consumption per session on large shell outputs
- Preserves full access to raw logs — nothing is lost, just summarized
- Works passively — no changes to your workflow once configured
- Useful for `ls`, `find`, `pip install`, `pytest`, `git log`, and similar noisy commands
- Lightweight local setup — SQLite only, no network dependencies
- Improves signal-to-noise ratio in long agentic sessions

---

## Benchmark

The benchmark runs snip against a corpus of real shell output samples and reports token savings per output type.

```bash
snip benchmark
```

To save results to a file:

```bash
snip benchmark --output results.md
```

Sample output (from included corpus):

| Command Type | Raw Tokens | Pruned Tokens | Savings |
|---|---|---|---|
| pip install | ~800 | ~80 | 90% |
| ls -la (large dir) | ~600 | ~40 | 93% |
| git log | ~1200 | ~100 | 92% |
| pytest (passing) | ~400 | ~60 | 85% |
| compiler error | ~150 | ~150 | 0% (durable) |

Durable outputs are never pruned. Volatile outputs are pruned only when they exceed the line threshold.

---

## Other Commands

```bash
snip status          # Show recent snip activity from the database
snip serve           # Start the MCP server manually (for debugging)
snip --version       # Check installed version
```

---

## Technologies

- **Python 3.11+** — runtime
- **MCP SDK** (`mcp`) — Model Context Protocol server implementation
- **SQLite + aiosqlite** — local storage for raw output logs
- **tiktoken** — token counting for context cost estimation
- **Click** — CLI framework
- **Rich** — terminal output formatting
- **Rule-based classifier** — heuristic patterns determine Durable vs Volatile output type

---

## Development

```bash
# Clone and install in editable mode with dev dependencies
git clone https://github.com/umairhaque03/snip
cd snip
pip install -e ".[dev]"

# Run tests
pytest --cov

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Run the MCP server locally
snip serve
```

### Running tests

Tests require no external services. SQLite databases are created in temp directories and cleaned up automatically.

```bash
pytest                                         # Run all tests
pytest tests/test_pruner.py                   # Run a specific module
pytest --cov --cov-report=term-missing        # With coverage detail
```

### Inspecting stored output

Raw output is stored in SQLite at `~/.snip/snip.db`.

```bash
sqlite3 ~/.snip/snip.db "SELECT id, command, created_at FROM raw_logs ORDER BY created_at DESC LIMIT 10;"
```

---

## Repository Structure

```
snip/
├── src/snip/
│   ├── classifier.py    # Rule-based Durable/Volatile classifier
│   ├── pruner.py        # Output pruning and digest generation
│   ├── server.py        # MCP server and tool handlers
│   ├── cli.py           # CLI entrypoint (snip command)
│   ├── config.py        # Claude Code MCP config registration
│   ├── db.py            # SQLite storage for raw output logs
│   ├── dashboard.py     # Live session stats display
│   ├── metrics.py       # Per-call token metrics
│   ├── tokenizer.py     # Token counting via tiktoken
│   ├── constants.py     # Thresholds, patterns, config paths
│   └── corpus/          # Sample shell outputs for benchmarking
├── tests/               # Pytest test suite
└── docs/
    └── architecture.md  # System design and data flow
```

---

## License

MIT
