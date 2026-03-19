# Contributing

## Development

> **End users:** install via `pip install git+https://github.com/umairhaque03/snip.git`
> The package is not on PyPI — do not use `pip install snip`.

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

## Running tests

Tests require no external services. SQLite databases are created in temp directories and cleaned up automatically.

```bash
pytest                                         # Run all tests
pytest tests/test_pruner.py                   # Run a specific module
pytest --cov --cov-report=term-missing        # With coverage detail
```

## Inspecting stored output

Raw output is stored in SQLite at `~/.snip/snip.db`.

```bash
sqlite3 ~/.snip/snip.db "SELECT id, command, created_at FROM raw_logs ORDER BY created_at DESC LIMIT 10;"
```

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
