# Model and DAX

Moved from CLAUDE.md (v1-simplify, 2026-10-29); placement rules in docs/lessons/README.md. Read by /model (proposing and applying measures), /plan (audit states) and /fix (measure fixes).

- Test new DAX as query-scoped `DEFINE COLUMN` / `DEFINE MEASURE` against the open Desktop model first, then write it to the TMDL with the modeling MCP (ConnectFolder, then ExportToTmdlFolder). Desktop stays unchanged.
- A query-scoped `DEFINE MEASURE` doesn't reach model measures that reference it. When testing a changed measure, redefine every measure in the chain the audit reads.
- In DAX a blank counts as less than any number, so guard rank, threshold and status measures with `ISBLANK` before comparing.
- Test every ranked measure in a filter state where some members have no rows (for example a month and category where some stores sold nothing), not only in the default state.
- A sort-by column must not reference the column it sorts, even indirectly: Desktop refuses to load the model ("circular dependency"). Build the sort column from the same source columns as the sorted one (Rep 7).
- pbik checks fields against the model's TMDL on disk. Measures created in Desktop must be saved before `pbik build` can bind them. *(`pbik validate` errors on a field missing from the TMDL.)*
- When you add an audit check for a bug, run it once against the old definition (query-scoped `DEFINE MEASURE`) to confirm it fails before the fix.
- An extension measure (reportExtensions.json) must not reference another extension measure: every visual using such a chain failed with "Error fetching data" in Desktop, and the same DAX made self-contained (model measures only, shared logic repeated in VARs) worked (v0.4 Desktop check, Rep 10 scratch). `pbik validate` flags a chain. *(`pbik validate` errors on a chain, test 89.)*
- A count of rows that meet a condition (within SLA, on time) returns 0, not blank, when there are rows but none meet it: `IF ( ISBLANK ( [Rows] ), BLANK (), <count> + 0 )`. A blank turns the matching % blank and breaks text measures built from it ("within SLA ()") (Rep 9).
