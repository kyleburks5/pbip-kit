# Model and DAX

Read by /model (proposing and applying measures), /plan (audit states) and /fix (measure fixes). Format and placement:
docs/lessons/README.md.

## Index
<!-- lessons:index -->
| ID | Lesson | Enforced by |
| --- | --- | --- |
| D-01 | Test new DAX query-scoped first | – |
| D-02 | Redefine every measure in the chain | – |
| D-03 | Guard comparisons with ISBLANK | – |
| D-04 | Test ranked measures in a sparse state | design/specs/audit.json sparse state (/plan writes one) |
| D-05 | A sort-by column never references the column it sorts | – |
| D-06 | Save Desktop-made measures before building | `pbik validate` errors on a field missing from the TMDL |
| D-07 | A new audit check must fail on the old definition | – |
| D-08 | Extension measures reference model measures only | `pbik validate` errors on a chain (test 89) |
| D-09 | Conditional counts return 0, not blank | – |
<!-- /lessons:index -->

## D-01 Test new DAX query-scoped first
- **Rule:** Test new DAX as `DEFINE COLUMN` / `DEFINE MEASURE` against the open Desktop model, then write it to the TMDL
  with the modeling MCP (ConnectFolder, then ExportToTmdlFolder).
- **Why:** Desktop and the model stay unchanged until the DAX is known to work.
- **Enforced by:** not enforced (read at /model)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## D-02 Redefine every measure in the chain
- **Rule:** When testing a changed measure query-scoped, redefine every measure in the chain the audit reads.
- **Why:** a query-scoped `DEFINE MEASURE` doesn't reach model measures that reference it.
- **Enforced by:** not enforced (read at /model and /fix)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## D-03 Guard comparisons with ISBLANK
- **Rule:** Guard rank, threshold and status measures with `ISBLANK` before comparing.
- **Why:** in DAX a blank counts as less than any number.
- **Enforced by:** not enforced (the audit's sparse state catches it)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## D-04 Test ranked measures in a sparse state
- **Rule:** Test every ranked measure where some members have no rows (a month and category where some stores sold
  nothing), not only in the default state.
- **Why:** ranks over members without rows only go wrong in such a state.
- **Enforced by:** design/specs/audit.json sparse state (/plan writes one)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## D-05 A sort-by column never references the column it sorts
- **Rule:** Build a sort column from the same source columns as the sorted one, never from the sorted column.
- **Why:** Desktop refused to load the model ("circular dependency"), even for an indirect reference.
- **Enforced by:** not enforced (read at /model)
- **Source:** Rep 7

## D-06 Save Desktop-made measures before building
- **Rule:** Save measures created in Desktop before `pbik build` binds them.
- **Why:** pbik checks fields against the model's TMDL on disk.
- **Enforced by:** `pbik validate` errors on a field missing from the TMDL
- **Source:** kit v0.3

## D-07 A new audit check must fail on the old definition
- **Rule:** Run a new audit check once against the old definition (query-scoped `DEFINE MEASURE`) and see it fail.
- **Why:** a check that never failed may not test the bug.
- **Enforced by:** not enforced (read at /fix)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## D-08 Extension measures reference model measures only
- **Rule:** Keep each report extension measure self-contained: model measures only, shared logic repeated in VARs.
- **Why:** every visual using an extension-measure chain failed with "Error fetching data"; the same DAX
  self-contained worked.
- **Enforced by:** `pbik validate` errors on a chain (test 89)
- **Source:** v0.4 Desktop check (Rep 10 scratch)

## D-09 Conditional counts return 0, not blank
- **Rule:** `IF ( ISBLANK ( [Rows] ), BLANK (), <count> + 0 )` for a count of rows that meet a condition.
- **Why:** a blank turned the matching % blank and broke text measures built from it ("within SLA ()").
- **Enforced by:** not enforced (read at /model)
- **Source:** Rep 9
