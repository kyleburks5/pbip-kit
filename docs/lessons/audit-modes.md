# Audit modes

Moved from CLAUDE.md (v1-simplify, 2026-10-29); placement rules in docs/lessons/README.md. Read by /model (recommends a mode), /plan (audit.json), /validate and /review (the numbers audit).

The numbers audit (validate.md, audit_numbers.py) runs in one of three modes, recommended by /model from the profile
and recorded in design/reviews/model-check.md and design/specs/audit.json.
**The thresholds are provisional and untested:** every rep so far ran in full mode on small data. Revise them after
the first sampled or aggregate-only run, from the timings /model records.

| Mode | When (provisional) | How |
| --- | --- | --- |
| full | Largest table up to ~1M rows, each raw recompute under ~10 s | Recompute every key value in every audit state from the raw columns |
| sampled | Up to ~10M rows, or recomputes under ~60 s | Grand totals and main-dimension subtotals in full; per-member values for a sample (top 5, bottom 5, 5 random, the empty case) |
| aggregate-only | Above that, or row-level access not cleared | Grouped DAX over raw columns (`SUMMARIZECOLUMNS`) at the grain of each key value only; no row export to data.json; wireframe numbers from aggregated queries |

- /model always records the timings (full-table COUNTROWS and one raw recompute per key value), whatever the mode.
- Every mode keeps: parts add up to totals, the first-year and blank prior-year cases, the empty case, divide by zero,
  and the numbers inside SVG measures.
