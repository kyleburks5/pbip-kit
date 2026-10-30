# Test fixtures

Frozen copies of three reps, so every test suite runs on a clean clone (`python tools/run_tests.py`). Each holds the
`.pbip`, the `*.Report` folder (without `.pbi/`), the `*.SemanticModel` definition (`definition/`, `definition.pbism`,
`.platform`; no `.pbi/cache.abf`) and `design/tokens.json`. They hold no data: no source files, no model cache, no
screenshots. The Power Query source paths point at a generic `C:\pbip-data\...` folder that doesn't exist; the tests
never refresh.

| Folder | Rep | Used by | Data source (THIRD-PARTY.md) |
| --- | --- | --- | --- |
| `rep4/` | Rep 4, Toy Sales | `tools/pbik/tests/test_pbik.py` (`PBIK_TEST_SOURCE` overrides it); the Patterns builder test | Maven Toys (Maven Analytics, public) |
| `rep5/` | Rep 5, HR OVERVIEW | `tools/patterns/test_patterns.py` | public HR practice dataset |
| `rep8/` | Rep 8, HR Overview | `tools/patterns/test_patterns.py` (`PATTERNS_TEST_SOURCE` overrides it) | public HR practice dataset |

A missing or empty fixture fails the tests; it never skips them. Copied 2026-10-29 from the Rep 4, 5 and 8 projects
as they stood at kit v1.0. Don't edit them by hand: a change to a fixture changes what the tests check.
