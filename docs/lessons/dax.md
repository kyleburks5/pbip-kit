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
| D-10 | Pass a measure to a UDF as an expression when it is worked out per month | – |
| D-11 | Test a function with a metric and a period that have data | – |
| D-12 | Headline measures work in the current filters and are never blank | the live-headline pattern's checks (a DAX query per audit state, including a slicer on another column and the empty case); kit visuals use `count()` (kit/words.ts) |
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

## D-10 Pass a measure to a UDF as an expression when it is worked out per month
- **Rule:** A UDF parameter that takes a measure it evaluates per month (a small chart) is `EXPR`, not `VAL`; bind a
  value taken from a row context to a `VAR` before passing it in.
- **Why:** as `VAL` the function gets one number and the chart is flat; a column of an outer table passed straight
  in failed with "Column cannot be found".
- **Enforced by:** not enforced (read when writing or changing a UDF; `pbik udf inline` keeps `EXPR` lazy)
- **Source:** UDF KPI card study, Study 2 (2026-11-15), G-07

## D-11 Test a function with a metric and a period that have data
- **Rule:** Test a function or measure query-scoped with a real selection that has data, and test the empty case
  on purpose as a separate state.
- **Why:** with nothing picked every input was blank, and the run drew cards for empty values that looked like a pass.
- **Enforced by:** not enforced (read at query-scoped tests; audit.json keeps the empty state separate)
- **Source:** UDF KPI card study, Study 2 (2026-11-15), G-12

## D-12 Headline measures work in the current filters and are never blank
- **Rule:** A lowest / highest headline ranks the members the page shows (`VALUES`, not a member column's
  `ALLSELECTED`), breaks ties in a fixed order, returns a sentence for none, one and several, and its counts agree
  with their noun ("1 site", not "1 sites" or "site(s)").
- **Why:** "Site 10 has the lowest status" came from all 24 sites while the page showed West, so the card read "--".
- **Enforced by:** the live-headline pattern's checks (a DAX query per audit state, including a slicer on another
  column and the empty case); kit visuals use `count()` (kit/words.ts)
- **Source:** v1.11 Desktop review, 2026-11-17
