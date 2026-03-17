# snip Benchmark Results

Rule-based token pruning benchmarked against a fixed corpus of representative tool outputs.

**Overall token reduction: 80.6%** (9,480 tokens saved out of 11,760 raw tokens)

## Results by File

| File | Category | Raw Tokens | Pruned Tokens | Tokens Saved | % Reduction |
| --- | --- | ---: | ---: | ---: | ---: |
| ls_large.txt ✓ | directory_listing | 2,277 | 124 | 2,153 | 94.6% |
| pip_install.txt ✓ | install_log | 2,030 | 110 | 1,920 | 94.6% |
| test_pass.txt ✓ | test_output | 1,836 | 52 | 1,784 | 97.2% |
| test_fail.txt ✓ | test_output | 1,073 | 229 | 844 | 78.7% |
| build_log_fail.txt ✓ | build_log | 1,056 | 295 | 761 | 72.1% |
| grep_results.txt ✓ | grep_results | 1,062 | 313 | 749 | 70.5% |
| build_log_success.txt ✓ | build_log | 761 | 60 | 701 | 92.1% |
| git_log.txt ✓ | git_output | 1,442 | 874 | 568 | 39.4% |
| file_read_python.txt | durable | 223 | 223 | 0 | 0.0% |
| **TOTAL** | — | **11,760** | **2,280** | **9,480** | **80.6%** |

## Summary

- Files processed: 9
- Files pruned: 8
- Total raw tokens: 11,760
- Total pruned tokens: 2,280
- Total tokens saved: 9,480
- Overall context reduction: 80.6%

_Reproduced with: `snip benchmark`_
