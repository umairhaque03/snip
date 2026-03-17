"""
Central registry of thresholds, command-to-category mappings, and regex patterns.

All values are module-level constants — never mutate at runtime.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Pruning threshold
# ---------------------------------------------------------------------------

# Volatile outputs with more lines than this will be pruned.
PRUNE_LINE_THRESHOLD: int = 50

# Hard ceiling on MCP result size (characters). Claude Code rejects results
# exceeding ~1 M chars; we cap well below that to stay safe.
MCP_MAX_RESULT_CHARS: int = 200_000

# Default number of days to retain raw logs in SQLite before cleanup.
LOG_RETENTION_DAYS: int = 7

# Default SQLite database path (resolved at runtime relative to home dir).
DB_RELATIVE_PATH: str = ".snip/snip.db"

# tiktoken encoding to use for token counting.
# cl100k_base is the closest public approximation to Claude's tokenizer.
TIKTOKEN_ENCODING: str = "cl100k_base"

# ---------------------------------------------------------------------------
# Volatility classification: command → category
# ---------------------------------------------------------------------------
# Keys are exact command names or prefixes (checked via str.startswith).
# Values are category strings used by the pruner registry.

# Durable command prefixes — outputs pass through unchanged.
DURABLE_COMMANDS: frozenset[str] = frozenset(
    [
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "bat",
    ]
)

# MCP tool names that are always Durable.
DURABLE_MCP_TOOLS: frozenset[str] = frozenset(
    [
        "Read",
        "read_file",
    ]
)

# Command prefix → category mappings for Volatile outputs.
# Checked in order; first match wins.
VOLATILE_COMMAND_PREFIXES: list[tuple[str, str]] = [
    # Directory listings
    ("ls", "directory_listing"),
    ("find", "directory_listing"),
    ("tree", "directory_listing"),
    ("dir", "directory_listing"),
    # Search results
    ("grep", "grep_results"),
    ("rg", "grep_results"),
    ("ag", "grep_results"),
    ("ack", "grep_results"),
    ("ripgrep", "grep_results"),
    # Test runners
    ("pytest", "test_output"),
    ("python -m pytest", "test_output"),
    ("jest", "test_output"),
    ("mocha", "test_output"),
    ("vitest", "test_output"),
    ("cargo test", "test_output"),
    ("go test", "test_output"),
    ("npm test", "test_output"),
    ("yarn test", "test_output"),
    ("pnpm test", "test_output"),
    ("npx jest", "test_output"),
    # Build systems
    ("make", "build_log"),
    ("cmake", "build_log"),
    ("cargo build", "build_log"),
    ("go build", "build_log"),
    ("npm run build", "build_log"),
    ("yarn build", "build_log"),
    ("pnpm build", "build_log"),
    ("tsc", "build_log"),
    ("webpack", "build_log"),
    ("vite build", "build_log"),
    ("gradle", "build_log"),
    ("mvn", "build_log"),
    # Git metadata
    ("git log", "git_output"),
    ("git status", "git_output"),
    ("git diff --stat", "git_output"),
    ("git branch", "git_output"),
    ("git remote", "git_output"),
    # Package installs
    ("pip install", "install_log"),
    ("pip3 install", "install_log"),
    ("npm install", "install_log"),
    ("yarn install", "install_log"),
    ("pnpm install", "install_log"),
    ("cargo install", "install_log"),
    ("go get", "install_log"),
    ("apt install", "install_log"),
    ("apt-get install", "install_log"),
    ("brew install", "install_log"),
]

# MCP tool names that produce Volatile output.
VOLATILE_MCP_TOOLS: dict[str, str] = {
    "Glob": "directory_listing",
    "Grep": "grep_results",
    "Bash": "generic_volatile",  # further refined by command content
}

# ---------------------------------------------------------------------------
# Content-based heuristics (fallback classification)
# ---------------------------------------------------------------------------

# Patterns that suggest the output is code (Durable).
CODE_INDICATOR_PATTERNS: list[str] = [
    r"^(def |class |function |const |let |var |import |from |export )",
    r"^(async def |async function |public |private |protected |static )",
    r"^\s+(return |yield |raise |throw |await )",
    r"(=>|->)\s",
    r"^\s*[{}()\[\]];?\s*$",
]

# Patterns that strongly suggest Volatile output.
VOLATILE_CONTENT_PATTERNS: list[str] = [
    # ls-style output
    r"^(total \d+|-[rwx-]{9}|d[rwx-]{9})",
    # grep-style file:line: pattern
    r"^[^\s]+:\d+:",
    # test result lines
    r"(PASSED|FAILED|ERROR|SKIP|passed|failed|error|skipped)\s*[\[\(]",
    # progress indicators
    r"\d+%\s*(complete|done|\|)",
    # log timestamps
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
    # build output indicators
    r"^(Compiling|Linking|Building|Running|Installing|Downloading|Resolving)\s",
]

# ---------------------------------------------------------------------------
# Digest formatting
# ---------------------------------------------------------------------------

BRAINFOG_TAG: str = "[snip]"
RETRIEVAL_HINT_TEMPLATE: str = (
    "[Pruned from {line_count} lines. "
    "Use get_raw_output(id='{log_id}') for full output]"
)

# Number of lines to show verbatim in head/tail digests.
DIGEST_HEAD_LINES: int = 10
DIGEST_TAIL_LINES: int = 10

# Max verbatim match lines shown in grep digest.
GREP_DIGEST_HEAD: int = 5
GREP_DIGEST_TAIL: int = 5

# Max failing tests shown in test output digest.
MAX_FAILING_TESTS_SHOWN: int = 10

# Max traceback lines shown per failing test.
TRACEBACK_LINES_PER_TEST: int = 3

# Max warning lines shown in build log digest.
MAX_BUILD_WARNINGS_SHOWN: int = 5

# Max git entries shown in git output digest.
GIT_DIGEST_MAX_ENTRIES: int = 10

# Max packages listed in install log digest.
INSTALL_DIGEST_MAX_PACKAGES: int = 5
