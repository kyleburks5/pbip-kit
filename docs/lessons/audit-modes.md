# Audit modes

Read by /model (recommends a mode), /plan (audit.json), /validate and /review (the numbers audit). Format and
placement: docs/lessons/README.md.

## Index
<!-- lessons:index -->
| ID | Lesson | Enforced by |
| --- | --- | --- |
| AM-01 | Pick the audit mode from the profile | – |
| AM-02 | Always record the timings | – |
| AM-03 | What every mode keeps | design/scripts/audit_numbers.py and audit_svg.py (the states in design/specs/audit.json) |
<!-- /lessons:index -->

## AM-01 Pick the audit mode from the profile
- **Rule:** /model recommends full, sampled or aggregate-only from the profile (table under Reference) and records it
  in design/reviews/model-check.md and design/specs/audit.json; aggregate-only whenever row-level access isn't cleared.
- **Why:** a full recompute doesn't scale, and row export isn't allowed everywhere (docs/it-security.md).
- **Enforced by:** not enforced (read at /model; the thresholds are provisional and untested)
- **Source:** CLAUDE.md before v0.5 (every rep so far ran in full mode on small data)

## AM-02 Always record the timings
- **Rule:** /model records a full-table COUNTROWS and one raw recompute per key value, whatever the mode.
- **Why:** the thresholds are revised from these timings after the first sampled or aggregate-only run.
- **Enforced by:** not enforced (read at /model)
- **Source:** CLAUDE.md before v0.5

## AM-03 What every mode keeps
- **Rule:** Every mode checks that parts add up to totals, the first-year and blank prior-year cases, the empty case,
  divide by zero, and the numbers inside SVG measures.
- **Why:** not recorded when the lesson was written; they are the audit's minimum in any mode.
- **Enforced by:** design/scripts/audit_numbers.py and audit_svg.py (the states in design/specs/audit.json)
- **Source:** CLAUDE.md before v0.5

## Reference

| Mode | When (provisional) | How |
| --- | --- | --- |
| full | Largest table up to ~1M rows, each raw recompute under ~10 s | Recompute every key value in every audit state from the raw columns |
| sampled | Up to ~10M rows, or recomputes under ~60 s | Grand totals and main-dimension subtotals in full; per-member values for a sample (top 5, bottom 5, 5 random, the empty case) |
| aggregate-only | Above that, or row-level access not cleared | Grouped DAX over raw columns (`SUMMARIZECOLUMNS`) at the grain of each key value only; no row export to data.json; wireframe numbers from aggregated queries |
