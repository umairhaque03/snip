# snip Architecture

## Overview

snip is a Python MCP server that reduces token bloat in agentic AI workflows
by intercepting tool outputs, classifying them, and pruning noisy Volatile outputs
before they reach Claude's context window.

## Data Flow

```
Claude Code
    │
    │  calls snip_run(command)
    ▼
snip MCP Server (server.py)
    │
    ├─► classifier.classify(tool_name, command, output)
    │       └─► returns ClassificationResult (Durable | Volatile + category)
    │
    ├─► pruner.prune(raw_output, log_id, classification)
    │       └─► if Volatile AND > 50 lines:
    │               apply category strategy → PrunedResult
    │           else:
    │               pass through unchanged
    │
    ├─► db.store_log(RawLogEntry)
    │       └─► SQLite: ~/.snip/snip.db
    │
    └─► return pruned_output to Claude
```

## Classification Priority

1. Known-Durable MCP tool name (`Read`) → always Durable
2. Known-Durable command prefix (`cat`, `head`) → always Durable
3. Known-Volatile command prefix (`ls`, `grep`, `pytest`, ...) → Volatile + category
4. Known-Volatile MCP tool name (`Glob`, `Grep`) → Volatile + category
5. Content heuristics (regex scoring) → Volatile only if strong signals
6. Default → **Durable** (safety-first: never prune ambiguous output)

## Pruning Strategies

| Category | Key Signals | Digest Shows |
|---|---|---|
| `directory_listing` | `ls`, `find`, `tree`, `Glob` | Entry count, extension breakdown, top dirs |
| `grep_results` | `grep`, `rg`, `Grep` | Match count/file, first 5 + last 5 lines |
| `test_output` | `pytest`, `jest`, `cargo test` | Pass/fail counts, failing test names + tracebacks |
| `build_log` | `make`, `tsc`, `cargo build` | All error lines, first 5 warnings, status |
| `git_output` | `git log`, `git status` | First 10 entries, remainder as count |
| `install_log` | `pip install`, `npm install` | Success/failure, key package versions |
| `generic_volatile` | Unknown, ≥50 lines | First 10 + last 10 lines |

All digests end with: `[Pruned from N lines. Use get_raw_output(id='...') for full output]`

## Database Schema

Single table `raw_logs` in `~/.snip/snip.db`:

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | UUID for retrieval |
| `session_id` | TEXT | Groups logs by session |
| `created_at` | TEXT | ISO 8601 UTC |
| `tool_name` | TEXT | MCP tool name |
| `command` | TEXT | Shell command |
| `raw_output` | TEXT | Full original output |
| `pruned_output` | TEXT | Digest sent to Claude |
| `volatility` | TEXT | "durable" or "volatile" |
| `category` | TEXT | Pruning category |
| `tokens_raw` | INT | tiktoken count (raw) |
| `tokens_pruned` | INT | tiktoken count (digest) |
| `tokens_saved` | INT | tokens_raw - tokens_pruned |
| `was_pruned` | INT | 0 or 1 |

Logs older than 7 days are deleted on server startup.

## Token Counting

Uses `tiktoken` with `cl100k_base` encoding — the closest publicly available
approximation to Claude's tokenizer. Suitable for relative benchmarking, not billing.

## Immutability

All data models (`ClassificationResult`, `PrunedResult`, `RawLogEntry`,
`ToolCallMetric`, `SessionStats`) are frozen dataclasses. No shared mutable state.

## MCP Tool Interface

```
snip_run(command, working_directory?) → string
get_raw_output(log_id) → string
get_session_stats() → string
```

## File Map

```
src/snip/
├── constants.py    # All thresholds, patterns, category mappings
├── tokenizer.py    # tiktoken wrapper
├── classifier.py   # classify() pure function
├── pruner.py       # prune() + per-category strategies
├── db.py           # SQLite schema + LogRepository
├── metrics.py      # Frozen dataclasses for metrics
├── server.py       # MCP server + tool handlers
├── config.py       # Claude Code config file manipulation
├── dashboard.py    # Rich live CLI dashboard
└── cli.py          # Click CLI: init, serve, benchmark
```
