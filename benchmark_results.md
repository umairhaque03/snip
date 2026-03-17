# snip Benchmark Results

Rule-based token pruning benchmarked against a fixed corpus of representative tool outputs.

**Overall token reduction: 39.4%** (2,718 tokens saved out of 6,897 raw tokens)

## Results by File

| File | Category | Raw Tokens | Pruned Tokens | Tokens Saved | % Reduction |
| --- | --- | ---: | ---: | ---: | ---: |
| ls_large.txt ✓ | directory_listing | 2,277 | 125 | 2,152 | 94.5% |
| git_log.txt ✓ | git_output | 1,442 | 876 | 566 | 39.3% |
| build_log_fail.txt | build_log | 395 | 395 | 0 | 0.0% |
| build_log_success.txt | build_log | 93 | 93 | 0 | 0.0% |
| file_read_python.txt | durable | 223 | 223 | 0 | 0.0% |
| grep_results.txt | grep_results | 701 | 701 | 0 | 0.0% |
| pip_install.txt | install_log | 1,110 | 1,110 | 0 | 0.0% |
| test_fail.txt | test_output | 504 | 504 | 0 | 0.0% |
| test_pass.txt | test_output | 152 | 152 | 0 | 0.0% |
| **TOTAL** | — | **6,897** | **4,179** | **2,718** | **39.4%** |

## Summary

- Files processed: 9
- Files pruned: 2
- Total raw tokens: 6,897
- Total pruned tokens: 4,179
- Total tokens saved: 2,718
- Overall context reduction: 39.4%

_Reproduced with: `snip benchmark`_
