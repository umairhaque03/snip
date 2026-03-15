# BrainFog

> Reduce token bloat in agentic AI workflows.

BrainFog is an MCP server that sits between Claude Code and shell tool outputs. It classifies each output as **Durable** (code, file reads) or **Volatile** (directory listings, test output, build logs), prunes Volatile outputs over 50 lines into compact digests, and stores the full raw output in a local SQLite database for on-demand retrieval.

## Installation

```bash
pip install brainfog
brainfog init   # auto-registers into Claude Code MCP config
```

## How It Works

1. Claude calls `brainfog_intercept` instead of running shell commands directly
2. BrainFog executes the command, classifies the output, and prunes if needed
3. Claude gets a compact digest — the raw output is saved to `~/.brainfog/brainfog.db`
4. Claude can call `get_raw_output(id="...")` any time to retrieve the full output

## MCP Tools

| Tool | Description |
|------|-------------|
| `brainfog_intercept` | Execute a command with output optimization |
| `get_raw_output` | Retrieve full output for a pruned result by ID |
| `get_session_stats` | Token savings summary for the current session |

## Benchmark

Run a reproducible benchmark against the built-in test corpus:

```bash
brainfog benchmark
```

# BrainFog Benchmark Results

Rule-based token pruning benchmarked against a fixed corpus of representative tool outputs.

**Overall token reduction: 39.2%** (2,742 tokens saved out of 7,003 raw tokens)

## Results by File

| File | Category | Raw Tokens | Pruned Tokens | Tokens Saved | % Reduction |
| --- | --- | ---: | ---: | ---: | ---: |
| ls_large.txt ✓ | directory_listing | 2,304 | 131 | 2,173 | 94.3% |
| git_log.txt ✓ | git_output | 1,442 | 873 | 569 | 39.5% |
| build_log_fail.txt | build_log | 422 | 422 | 0 | 0.0% |
| build_log_success.txt | build_log | 98 | 98 | 0 | 0.0% |
| file_read_python.txt | durable | 223 | 223 | 0 | 0.0% |
| grep_results.txt | grep_results | 738 | 738 | 0 | 0.0% |
| pip_install.txt | install_log | 1,112 | 1,112 | 0 | 0.0% |
| test_fail.txt | test_output | 510 | 510 | 0 | 0.0% |
| test_pass.txt | test_output | 154 | 154 | 0 | 0.0% |
| **TOTAL** | — | **7,003** | **4,261** | **2,742** | **39.2%** |

## Summary

- Files processed: 9
- Files pruned: 2
- Total raw tokens: 7,003
- Total pruned tokens: 4,261
- Total tokens saved: 2,742
- Overall context reduction: 39.2%

_Reproduced with: `brainfog benchmark`_


## Development

```bash
pip install -e ".[dev]"
pytest --cov
```
