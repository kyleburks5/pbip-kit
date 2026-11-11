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
## Gap 23: prerequisites for reloading external changes (done, check only)

**What pbik does now**: `pbik validate` warns on report or model files whose full path is 260 characters or longer,
and `pbik build` on each visual.json it writes past the limit (pbik's `<ID>_<name>` folders make paths longer).
`pbik project check` warns when the installed Desktop is 2.156.951.0 or older; `pbik desktop` (exit 3, Desktop open
but no bridge) says whether the Desktop is too old or the preview option is off. After `pbik desktop reload` pbik
notes that the reload resets filters, so a screenshot shows the default state. No report output change. Test 122.

**Provenance**: [L3] *Edit Power BI Desktop project files outside Power BI Desktop* (updated 2026-09-29),
"Prerequisites" (the August 2026 release or later, the preview option **Detect and reload external PBIP changes**,
every path under 260 characters) and "Considerations and limitations" (reloading resets filters). The cut-off
2.156.951.0 is the July 2026 release in the Desktop update archive (the gap 23 answer in pbik-roadmap-batch1.md):
Learn prints no version number for August 2026, so pbik treats anything up to July's build as too old.
## Gap 24, second half: roundtrip sees registered resources (done, check only)

**What pbik does now**: `pbik roundtrip` reads `StaticResources/RegisteredResources` on both sides (git revision or
`--before` copy, and the working tree) and lists, in a section of its own, resources Desktop added, deleted or
rewrote: JSON resources (the theme) key by key with the same proposal lines as `definition/`, other files (images) by
size and SHA-1. Read-only, as before. Test 123. Batch 1 did the pane-dependent half.

**Provenance**: [L1] *Power BI Desktop project report folder*, "RegisteredResources\" (the theme and images Desktop
keeps there); pbik's roundtrip.py (`SKIP_DIRS`, `side_from_git`, `side_from_folder`).
## Gap 3: images as a layout key (image visuals done; page images blocked)

**What pbik does now**: layout `image: "<file>"` or `{file, scaling}` on an image visual registers the file (the same
`_register` as `pbik resource add`, idempotent) before the build, then writes `general.imageUrl` as a
ResourcePackageItem (RegisteredResources, PackageType 1, the item name) and `imageScaling.imageScalingType`. Not
marked unverified: it is the form Desktop saved on the Patterns page (`design/templates/image.json`, harvested from
the Desktop-saved Patterns report) and the PNG route .claude/rules/svg.md records as tested in Desktop (Reps 6-7).
Test 124.

**Blocked**: a page background image and a wallpaper (`outspace`) image. S:page 2.1.0 #Background lists an `image`
property (and #PageFormattingObjects an `outspace` object) but says nothing of the value's shape, and no Desktop-saved
file in the kit has one. Next step: the Desktop checklist (set an image as the background of the smoke report's
Images page, save, roundtrip) shows the form.

**Provenance**: S:report 3.3.0 #ResourcePackageItem / #ResourcePackageItemType (Image); S:semanticQuery 1.4.0
#QueryResourcePackageItem; S:page 2.1.0 #Background; [L1] "RegisteredResources\"; `design/templates/image.json`;
pbik's theme.py (`_register`) and objects.py (`image_objects`).
## Gap 12: page settings and lifecycle (done, UNVERIFIED in Desktop)

**What pbik does now**: page `landing: true` writes pages.json `landingPageName` (owned: visual-map `landing`, removed
when the key goes); page `props` writes any page object property (`pageRefresh`, `pageSize`, `displayArea`,
`pageInformation`, `outspace`, `personalizeVisual`, `background`) with the same value notation as visual `props`,
each property checked against the cached page schema (warning, `--strict` error); `--prune` removes a page pbik made
that left layout.json (folder, `pageOrder`, `activePageName`, `landingPageName`; without `--prune` it is kept and
listed). Pages made in Desktop are never touched. Test 125.

**UNVERIFIED in Desktop**: `landingPageName` and the page objects (no Desktop-saved file in the kit has them). Page
removal writes no new form. Value types for `pageRefresh` (`duration`, `refreshType`, `checkEvery`) aren't in the
schema (properties listed, values open); the checklist sets one and roundtrip shows Desktop's form.

**Provenance**: S:pagesMetadata 1.1.0 `landingPageName` ("takes precedence over activePageName", the page name);
S:page 2.1.0 #PageFormattingObjects, #PageSize, #DisplayArea, #PageRefresh, #PageInformation, #Background; pbik's
build.py (`set_prop`, `prop_value`, `--prune` for visuals).
## Gap 25: registering new resources is outside what Microsoft documents (done: recorded, smoke item)

**What changed**: `pbik theme apply`, `pbik resource add` and a build that registers a layout `image` print a note
when they register a new resource; `/smoke` (and Copilot `/kit-smoke`) gains step 5, which rechecks on the reopened
`_smoke` page that the theme pbik registered (and a registered image, when the rep has one) still load;
docs/UPDATE-ROUTINE.md step 3 says so; design/known-gaps.md records the risk on the registered-images row. No report
output change. Covered by the existing theme and resource tests and test 124.

**Provenance**: [L1] *Power BI Desktop project report folder*, "RegisteredResources\": "Edits to RegisteredResources
files are only supported for already loaded resources"; .claude/rules/svg.md (the PNG route tested in Desktop, Reps
6-7); pbik's theme.py.
## Gap 4: filters beyond Categorical and Top N (done, UNVERIFIED in Desktop)

**What pbik does now** (`pbikit/fields.py`, `build.build_filter`): filter `type` Range (`min`, `max`: one Between),
Advanced with one or two text conditions (Contains, StartsWith, `is`, blank via a null Comparison, each negatable with
Not, joined by And / Or), and RelativeDate (`last` N `unit`s, today included). `displayName` and `ordinal` on any
filter; `filterOrder` (ascending, descending, custom) writes `filterSortOrder` on the visual, page or report. Top-level
`report.filters` writes report-level filters into report.json `filterConfig` (pbik's `pbik_` filters only; a measure
there is an error, as on a page). Each new filter is schema-checked as it is written. Test 127.

**UNVERIFIED in Desktop**: none of these forms is in a Desktop-saved file in the kit. The relative-date expression in
particular is assembled from the schema's DateSpan / DateAdd / Now building blocks; Desktop may write a different
(equivalent) tree, which the checklist's roundtrip will show.

**Left out**: Include, Exclude and Tuple (made by Desktop when you include or exclude data points), Passthrough
(a restatement only), VisualTopN, and RelativeTime (minutes and hours; DirectQuery). Not needed by a BRD so far.

**Provenance**: S:filterConfiguration 1.3.0 #FilterContainer (`type`, `displayName`, `ordinal`), `filterSortOrder`;
S:report 3.3.0 `filterConfig`; S:semanticQuery 1.4.0 #QueryBetweenExpression, #QueryContainsExpression,
#QueryStartsWithExpression, #QueryNotExpression, #QueryComparisonExpression, #QueryDateSpanExpression,
#QueryDateAddExpression, #QueryNowExpression, #TimeUnit; pbik's fields.py (the From / Where shape Desktop saved for
Categorical and Top N filters).
## Gap 2: per-member formatting (done; objects other than dataPoint.fill UNVERIFIED in Desktop)

**What pbik does now**: layout `members` writes one entry per member on selector
`{"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": <column, Entity SourceRef>, "Right": <literal>}}}]}`,
the literal typed like the column (`'Female'`, `2024L`). Values use the `props` notation (colours, tokens, theme
colours). Entries are owned per member and removed when they leave the layout. Test 128 compares the shape with the
Desktop-saved file.

**Verified form**: `dataPoint.fill` per category member is exactly what Desktop saved on the Rep 5 donut
(`tools/fixtures/rep5/.../mix-chart-gender/visual.json`, three slices). Series colours on a legend field, markers,
labels or small-multiple headers use the same selector in the schema but have no Desktop-saved example in the kit:
those are **UNVERIFIED in Desktop** and flagged by build and validate.

**Provenance**: S:formattingObjectDefinitions 1.5.0 #Selector, #DataRepetitionSelector (`scopeId`); S:semanticQuery
1.4.0 #QueryComparisonExpression, #QueryLiteralExpression; the Rep 5 fixture; pbik's fields.py (`typed_literal`).
## Gap 5: data bookmarks that save a state (selection and sort done, UNVERIFIED in Desktop)

**What pbik does now** (`pbikit/bookmarks.py`): a layout bookmark's `select: {ID: {field, values}}` saves that slicer's
selection as `singleVisual.objects.merge.general[0].properties.filter.filter` (the same Version 2 filter pbik writes
for a slicer's `selection`), and `sort: {ID: {field, direction}}` saves `singleVisual.orderBy` (QuerySortClause,
Direction 1 / 2). Those visuals become targets, and the bookmark captures data unless `data: false`, which is then a
layout error. Test 129.

**Left out**: filter states (`explorationState.filters`, a section's `filters` by name), `activeProjections`,
`expansionStates` and cross-highlights (`highlight`): their state shapes (FiltersState byName / byExpr, Decomposed
selectors) are deep and nothing in the kit shows Desktop's form. Rep 7's 3 bookmarks saved slicer states, which
`select` covers.

**UNVERIFIED in Desktop**: whether Desktop reads the slicer state from `objects.merge` exactly this way. The
checklist's roundtrip after applying the bookmark and saving shows it.

**Provenance**: S:bookmark 2.1.0 #ExplorationState, #SectionState, #VisualContainerState, #SingleVisualConfigState
(`objects`, `orderBy`), #DataViewObjectDefinitionUpdates (`merge`), #BookmarkOptions; S:semanticQuery 1.4.0
#QuerySortClause; pbik's bookmarks.py (Rep 5's saved form for display bookmarks) and fields.py (`selection_filter`).
## Gap 6: report-page tooltips (done, UNVERIFIED in Desktop)

**What pbik does now**: page `tooltip: true` writes `type: "Tooltip"` and `pageBinding: {name, type: "Tooltip"}` (a
stable name from the page key; both owned and removed when the key goes). Visual `tooltipPage: <page key>` writes
`visualContainerObjects.visualTooltip` `show: true` and `section: '<page name>'`; the target must be a tooltip page.
`pbik validate` errors when two pages share a `pageBinding.name` and when a visual's tooltip `section` isn't a Tooltip
page. Test 130.

**UNVERIFIED in Desktop, and one value missing**: visualTooltip `type` (default tooltip or report page) is an open
property in the schema with no values listed, and no Desktop-saved file in the kit has it, so pbik doesn't write it.
Desktop may then show the default tooltip. The checklist sets the tooltip to the report page in Desktop and saves:
roadmap shows `type`'s value, and pbik writes it next.

**Provenance**: S:page 2.1.0 `type` (Tooltip), #PageBinding, #BindingType; S:visualConfiguration 2.8.0 #VisualTooltip
(`show`, `type`, `section`); [L1] "Common PBIR errors" (pageBinding.name must be unique across the report).
## Gap 7: drill-through pages (done, UNVERIFIED in Desktop)

**What pbik does now**: page `drillthrough: {fields, keepFilters}` writes `type: "Drillthrough"`, a `pageBinding`
(stable name, `type: Drillthrough`, one parameter per field with `boundFilter` and `fieldExpr`,
`acceptsFilterContext` Default or None) and one page filter per field (`howCreated: Drillthrough`, no condition,
named `pbik_dt_*`) that the parameter binds. Page `filters` live beside them. Button `action: {type: Drillthrough,
page}` writes `visualLink` type `Drillthrough` and `drillthroughSection`. Everything is owned and removed when the key
goes. `pbik validate` errors on a drill-through button whose target isn't a Drillthrough page (and, from gap 6, on a
`pageBinding.name` used twice). Test 131.

**UNVERIFIED in Desktop**: the parameter / filter pairing and the visualLink `type` value `Drillthrough` (the schema
lists `drillthroughSection` but not the type's values). The checklist right-clicks a bar, drills through, saves, and
roundtrip shows what Desktop keeps.

**Provenance**: S:page 2.1.0 `type` (Drillthrough), #PageBinding (`parameters`, `acceptsFilterContext`), #BindingParameter
(`boundFilter`, `fieldExpr`); S:filterConfiguration 1.3.0 #FilterContainer `howCreated` (Drillthrough: "Created by
drill context that is applied to the page when using drill-through action"); S:visualConfiguration 2.8.0 #VisualLink
(`drillthroughSection`); [L1] "Common PBIR errors".
