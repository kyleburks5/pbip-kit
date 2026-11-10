# pbik roadmap batch 2 (bulk run, 2026-11-10)

All remaining gaps of design/reviews/pbik-roadmap.md in its suggested order, one commit per gap (`gap <n>: <name>`),
from tag `pre-bulk-2026-11-10`. Tests 119 onwards in `tools/pbik/tests/test_pbik.py`.

Sources, and only these: the Microsoft Learn pages and PBIR schemas the roadmap cites (schemas as cached by
`pbik schemas fetch`, read 2026-11-10), pbik's own code, and Desktop-saved files already in the kit
(`tools/fixtures/rep4`, `rep5`, `rep8`, and `design/templates/`, harvested from the Desktop-saved Patterns page). The
Desktop-saved sample folder named in the brief (`samples` in the user's home folder) doesn't exist on this machine, so no
sample from it was used.

Gaps that write new report JSON are marked **UNVERIFIED in Desktop**: built from the schema, schema-checked by
`pbik build` (warning; `--strict` error) and by `pbik validate`, and listed by both as unverified
(`pbikit/unverified.py`) until a Desktop save confirms them. The Desktop checklist at the end covers each.

## Gap 21: decorative visuals and the tab order (check done; write blocked)

**What pbik does now**: layout `decorative: true` on a visual is recorded in visual-map.json. `pbik validate` (a11y)
warns once per page on shapes with no alt text that aren't marked decorative; skips alt text and the reading-order
check for decorative visuals; and prints a note listing decorative visuals that still have a tab stop, to hide in
Desktop (View > Selection, Tab order). `decorative` together with `container.altText` is a build error. Test 119.

**Blocked**: writing "hidden from tab order". visualContainer 2.13.0 #VisualContainerPosition has `tabOrder` as a
plain number with no hidden value, and no Desktop-saved file in the kit has a hidden tab stop. Next step: the Desktop
checklist item (hide P1-V01 from the tab order in the smoke report, save, run roundtrip) shows the form; then
`decorative` writes it.

**Provenance**: [L7] *Design Power BI reports for accessibility* (updated 2026-09-29), "Tab order" and the checklist
items "Shapes" and "Images" (decorative ones hidden from the tab order); S:visualContainer 2.13.0
#VisualContainerPosition; pbik's a11y.py.

## Gap 22: Learn's accessibility checklist (done, check only)

**What pbik does now** (`pbik validate`, a11y warnings, no report output change): alt text longer than 250
characters; a text box whose text isn't contained in its alt text (screen readers read the alt text); data visuals
with fields but no `query.sortDefinition` (the accessible Show data table follows the visual's sort), one warning per
page listing them. Cards, KPIs, gauges, slicers, images, shapes, buttons and navigators are skipped by the sort rule
(one value, or no data). Test 120.

**Provenance**: [L7] *Design Power BI reports for accessibility* (updated 2026-09-29): "Alt text" (250-character
limit), checklist "Textbox" and "Sort order"; S:visualConfiguration 2.8.0 #VisualContainerGeneralFormattingObjects
(`altText`), #SortDefinition; pbik's a11y.py.
## Gap 13: annotations (done, UNVERIFIED in Desktop)

**What pbik does now**: layout `annotate: true` stamps `pbik.page` on pages and `pbik.id` / `pbik.layout` (12 hex of
the visual's layout entry) on visuals and groups; `annotations: {name: text}` on a visual, a page or `report` writes
`annotations: [{name, value}]` in place. Names layout.json sets are owned (visual-map `owned` / `reportOwned`) and
removed when they leave it; other annotations stay. `pbik validate` errors on a name used twice in one file and warns
when `pbik.id` differs from the folder's ID. Test 121.

This gap also adds the batch's safety net: `pbikit/unverified.py` (each unverified feature: `pbik build` prints it,
`pbik validate` lists the files that carry it) and `schemaprops.tree_issues`, which checks every key of a JSON
fragment pbik writes against the cached schema (warning, `--strict` error; a version Microsoft hasn't published is
checked against the newest older one and stays a warning).

**Provenance**: [L1] *Power BI Desktop project report folder*, "PBIR annotations" (annotations on report, page and
visual; Desktop keeps them); S:report 3.3.0, S:page 2.1.0, S:visualContainer 2.13.0 `annotations` and #Annotation
(`name`, `value` strings, "Unique name"). Extension-measure annotations (S:reportExtension 1.0.0) aren't written: no
layout key reaches them yet.
