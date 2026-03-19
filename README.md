# snip

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**snip reduces context bloat in agentic coding workflows by classifying shell output, pruning verbose noise into compact digests, and preserving full raw logs for later retrieval.**

---

## 80.6% fewer tokens. Nothing lost.

snip benchmarks at **80.6% overall token reduction** across real shell output types — directory listings, installs, test runs, build logs, and more. The full raw output is always stored locally and retrievable by ID.

| Output Type | Raw Tokens | After snip | Savings |
|---|---:|---:|---:|
| pytest (passing) | 1,836 | 52 | **97.2%** |
| pip install | 2,030 | 110 | **94.6%** |
| ls -la (large dir) | 2,277 | 124 | **94.6%** |
| webpack build (success) | 761 | 60 | **92.1%** |
| webpack build (failure) | 1,056 | 295 | **72.1%** |
| pytest (with failures) | 1,073 | 229 | **78.7%** |
| grep results | 1,062 | 313 | **70.5%** |
| git log | 1,442 | 874 | **39.4%** |
| file read (source code) | 223 | 223 | **0% — preserved** |

Durable outputs like source code reads are never pruned. Only noisy, repetitive outputs get compressed.

> Run `snip benchmark` yourself — results are generated fresh from the included corpus.

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

**Durable output** (source code, errors, stack traces, compiler output, meaningful results) is returned as-is. Nothing is lost.

**Volatile output** (directory listings, install logs, progress bars, repetitive output) beyond the line threshold is summarized into a compact digest. The agent gets the shape of the result without the token cost.

**Full raw output** is always stored locally at `~/.snip/snip.db`. The agent can retrieve it by ID at any time using `get_raw_output`.

### What a digest looks like

Before (pip install — 2,030 tokens):
```
Collecting mcp>=1.0.0
  Downloading mcp-1.4.1-py3-none-any.whl (75 kB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 75.2/75.2 kB 2.1 MB/s eta 0:00:00
Collecting click>=8.1.0
  Downloading click-8.1.7-py3-none-any.whl (97 kB)
... [60+ more lines of download progress]
Successfully installed aiosqlite-0.20.0 anyio-4.3.0 certifi-2024.2.2 ...
```

After (110 tokens):
```
[snip] Install: SUCCESS — 29 packages
Key packages: aiosqlite-0.20.0, anyio-4.3.0, snip-0.1.0, certifi-2024.2.2, ... (24 more)
[Pruned from 75 lines. Use get_raw_output(id='...') for full output]
```

---

## Installation

> **Requirements:** Python 3.11+, Claude Code

**Step 1 — Install snip:**

```bash
pip install git+https://github.com/umairhaque03/snip.git
```

**Step 2 — Register with Claude Code:**

```bash
snip init
```

**Step 3 — Restart Claude Code.**

That's it. You're done. snip is now active on every session automatically — no further setup required.

<details>
<summary>What <code>snip init</code> does under the hood</summary>

`snip init` writes a single entry into `~/.claude.json` under `mcpServers`. Claude Code reads this file on startup and launches the snip server automatically each time. You never need to start it manually.

If you previously installed an older version under the name `brainfog` or `ctxsift`, `snip init` removes those entries automatically.
</details>

---

## Other Commands

```bash
snip status          # Show recent snip activity from the database
snip serve           # Start the MCP server manually (for debugging)
snip --version       # Check installed version
```

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

## Benchmark

Run snip against the included corpus of representative shell outputs:

```bash
snip benchmark
```

Save results to a file:

```bash
snip benchmark --output results.md
```

See [`benchmark_results.md`](benchmark_results.md) for the full report.

---

## Why Use snip

- Reduces token consumption per session on large shell outputs
- Preserves full access to raw logs — nothing is lost, just summarized
- Works passively — no changes to your workflow once configured
- Useful for `ls`, `find`, `pip install`, `pytest`, `git log`, and similar noisy commands
- Lightweight local setup — SQLite only, no network dependencies
- Improves signal-to-noise ratio in long agentic sessions

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and repository structure.

## Privacy

When you run `snip init`, an anonymous install event is logged. The only data sent is Python version and OS platform — no personally identifiable information is collected.

## License

MIT
