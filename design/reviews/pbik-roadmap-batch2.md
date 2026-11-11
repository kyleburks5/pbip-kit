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
## Gap 8: hierarchies and drill (done, UNVERIFIED in Desktop)

**What pbik does now**: a binding item `{hierarchy: "Table[Hierarchy]", level}` projects
`{"HierarchyLevel": {"Expression": {"Hierarchy": {"Expression": {"SourceRef": {"Entity": T}}, "Hierarchy": H}},
"Level": L}}` with queryRef `T.H.L`; the hierarchy and level must exist in the table's TMDL (`hierarchy` / `level`
lines). `expand: "all"` on a matrix writes `expansionStates` with every Rows level but the last expanded. Test 132.

**Left out**: the automatic date hierarchy (`PropertyVariationSource`: needs the column's variation name from a
model with auto date/time, which the kit's models turn off), per-member expansion (`identityValues`), and
`isDrillDisabled`, which the schema says only specific custom visuals use.

**UNVERIFIED in Desktop**: the queryRef form and the expansion state. The checklist's roundtrip after a save shows
both (Desktop may add `active` or rewrite the queryRef).

**Provenance**: S:semanticQuery 1.4.0 #QueryHierarchyExpression, #QueryHierarchyLevelExpression; S:visualConfiguration
2.8.0 #ExpansionState, #RootExpansionState, #LevelExpansionState, #Query (`isDrillDisabled`); TMDL `hierarchy` /
`level` as in the Rep 5 fixture's Date table; pbik's build.py (projection shape).
## Gap 27: visual group formatting (done, UNVERIFIED in Desktop)

**What pbik does now**: on a `type: "group"` visual, `background` ({color, transparency} or false), `altText` and
`lockAspect` write `visualGroup.objects` (background `show` / `color` / `transparency`, general `altText`,
lockAspect `show`), selector-less and owned per property. pbik used to rewrite `visualGroup` whole on every build,
which dropped formatting set in Desktop; it now keeps `objects` and changes only its own properties. Test 133.

**Provenance**: S:visualContainer 2.13.0 #VisualGroupConfig, #VisualGroupFormattingObjects,
#VisualGroupGeneralFormattingObjects (`altText`); S:visualConfiguration 2.8.0 #Background, #LockAspect; [L7] (a group
can be announced as one item with alt text); pbik's build.py (groups, `build.py:1094-1095` in the roadmap).
## Gap 18: service size limits (done, check only)

**What pbik does now**: `pbik validate` errors when a report has more than 1,000 pages, a page more than 1,000
visuals, more than 1,000 registered resource files, or more than 300 MB of registered resources or of report
definition files. Never hit at kit scale; a cheap guard. Test 134 (limits lowered through `check_limits`).

**Provenance**: [L1] *Power BI Desktop project report folder*, "PBIR considerations and limitations" (the five
limits).
## Gap 19: data values in report files (done, check only)

**What pbik does now**: `pbik values <Report> [--out <md>]` (new, `pbikit/values.py`) lists every literal in report,
page and visual filters, slicer selections (`objects.*.filter`), per-member selectors (`scopeId`) and bookmark states,
grouped by file, kind and the field it is compared with. Formatting literals (colours, sizes, text) aren't listed.
Read-only; meant for the privacy review in docs/it-security.md before a commit. Test 135.

**Provenance**: [L1] *Power BI Desktop project report folder*, "PBIR folder and files" (Important note: filter and
slicer values are saved in the files); S:semanticQuery 1.4.0 (#QueryInExpression, #QueryComparisonExpression,
#QueryBetweenExpression, #QueryLiteralExpression); pbik's validate.py (`walk_in_filters`).
## Gap 26: newer native visuals without a template (warning done; templates blocked)

**What pbik does now**: `pbik build` warns when a visual's type has no template in `design/templates/` (it builds
the bare visual with Desktop's defaults), naming the harvest route and the newer visuals still missing: the list
slicer, the input slicer, Azure Maps (the replacement gap 20 points to) and the Gantt chart. Test 136.

**Blocked**: the templates themselves. pbik builds only types with a harvested template, and a template must come
from a Desktop save (the kit's rule: Desktop-saved files, never hand-written). Their `visualType` ids aren't in any
Desktop-saved file in the kit. Next step (Desktop checklist): add the four visuals to the Patterns page, save,
`pbik templates harvest` and `pbik catalog refresh`. The plot area background (October 2026) reaches the catalog the
same way.

**Provenance**: [L4] *What's new in the October 2026 Power BI update*, "Reporting" (Gantt preview, list slicer
dropdown, plot area background); [L6] (Azure Maps); `design/templates/` listing; pbik's build.py and templates.py.
## Gap 9: aggregations (done, UNVERIFIED in Desktop)

**What pbik does now**: the field notation takes `Median(T[C])`, `StDev(T[C])` / `StandardDeviation`,
`Variance(T[C])` / `Var` (Aggregation Function 6, 7, 8; number columns only) and `Percentile(T[C], k)`
(`{"Percentile": {"Expression": <column>, "K": k}}`, k from 0 to 1, Exclusive left at its default false). Their
queryRefs follow pbik's `Function(Table.Column)` pattern (`Median(sales.Units)`, `Percentile(sales.Units, 0.9)`). Test
137.

**UNVERIFIED in Desktop**: the four new ones, and the queryRef names (Desktop may name them differently). Avg, Max,
CountNonNull and DistinctCount (Function 1, 4, 5, 2) were already written but not yet seen in a Desktop save
(known-gaps); the checklist covers them too.

**Provenance**: S:semanticQuery 1.4.0 #QueryAggregationExpression, #QueryAggregateFunction (6 Median,
7 StandardDeviation, 8 Variance), #QueryPercentileExpression (`K`, `Exclusive`); pbik's objects.py (`AGG_NAMES`,
`qref`) and fields.py.
## Gap 10: visual calculations and sparklines (done, UNVERIFIED in Desktop)

**What pbik does now**: a binding item `{calc, expression, dataType}` projects a visual calculation
(`NativeVisualCalculation`, Language `dax`, queryRef = its name); `{sparkline: "[Measure]", by: "T[C]"}` in a table
or matrix projects `SparklineData` with one grouping and `PointsPerSparkline` 52 (the schema's only value). The
calculation's DAX isn't parsed (it runs over the visual's own matrix, not the model). Test 138.

**UNVERIFIED in Desktop**: both forms and their queryRefs (pbik names a sparkline
`SparklineData(<measure>_[<column>])`, a guess at Desktop's naming; roundtrip will show the real one). Sparkline
formatting (line colour, markers) stays with `props` until a Desktop save shows its objects.

**Provenance**: S:semanticQuery 1.4.0 #QueryNativeVisualCalc (`Language` dax, `Expression`, `Name`, `DataType` enum),
#QuerySparklineDataExpression (`Measure`, `Groupings`, `PointsPerSparkline` const 52); S:visualConfiguration 2.8.0
#ProjectionState; pbik's build.py (projection shape).
## Gap 11: mobile layout (position done, UNVERIFIED in Desktop)

**What pbik does now**: visual `mobile: {x, y, w, h, z}` writes `mobile.json` in the visual's folder (`$schema`
visualContainerMobileState 2.8.0, `position`), schema-checked; pbik owns the files it wrote (visual-map `mobile`)
and removes one when the key goes. Mobile-only formatting (`objects`, `visualContainerObjects` in mobile.json) isn't
written: no layout key yet. Test 139.

**UNVERIFIED in Desktop**: whether Desktop shows the phone layout from mobile.json alone. Learn lists the report's
own `mobileState.json` as not supported for external editing (roadmap: Out), and pbik doesn't write it; Desktop
may need the page's mobile layout opened once. The checklist opens View > Mobile layout and saves.

**Provenance**: S:visualContainerMobileState 2.8.0 (`objects`, `visualContainerObjects`, `position`
#VisualContainerPosition); [L1] "PBIR folder and files" (mobile.json per visual); [L3] "Considerations and
limitations" (mobileState.json not supported externally).
## Gap 14: shape maps with an uploaded map (registration done, UNVERIFIED in Desktop; binding blocked)

**What pbik does now**: `pbik resource add <Report> <map.topo.json> --type ShapeMap` registers a TopoJSON file as an
item of type ShapeMap in RegisteredResources (same idempotent `_register` as images; warns when the file isn't a
Topology). `pbik validate` now errors on any RegisteredResources item whose file is missing. Test 140.

**Blocked**: binding the registered map to a shape map visual. The schema has no shape-map object (a visual's
`objects` are open) and the only Desktop-saved shape map the kit has seen (pbik-smoke-013 scratch page, batch 1 notes)
used a built-in map from SharedResources (`Shapemaps/usa.states.topo.json`), not an uploaded one. Next step
(checklist): pick the uploaded map in Desktop, save, roundtrip.

**Provenance**: S:report 3.3.0 #ResourcePackage, #ResourcePackageItem, #ResourcePackageItemType (ShapeMap),
#ResourcePackageType (RegisteredResources, SharedResources); pbik-roadmap-batch1.md (the SharedResources ShapeMap item
Desktop saved); pbik's theme.py.
## Gap 16: other visual options (angle and query options done, UNVERIFIED in Desktop; dataFunction blocked)

**What pbik does now**: visual `angle` writes `position.angle` (removed when the key goes); `queryOptions:
{binnedLineSample, overlappingPointsSample}` writes `query.options` (`allowBinnedLineSample`,
`allowOverlappingPointsSample`), owned and schema-checked. Test 141.

**Blocked**: the `dataFunction` visual link. It runs a Fabric user data function (translytical task flows); the kit
ignores Fabric-only tools (CLAUDE.md), and the schema lists the property without its value's shape. Q&A links stay a
validate warning (gap 20).

**Provenance**: S:visualContainer 2.13.0 #VisualContainerPosition (`angle`); S:visualConfiguration 2.8.0 #Query
(`options`), #VisualQueryOptions, #VisualLink (`dataFunction`).
## Gap 17: copy a page between reports (done; check in Desktop)

**What pbik does now**: `pbik copy page <from> <page> <to> --key P<n> [--as <name>] [--bookmarks]` (new,
`pbikit/copy.py`) copies a page folder into another report: the page takes the name `pbik build` would give layout
page `<key>` (so a later layout entry adopts it), visual IDs move to the new page number (folders, `name`,
`parentGroupName`, `visualInteractions`), page and visual filter names and the `pageBinding` name and parameters are
renamed (stable, unique) with `boundFilter` following, and it is appended to `pageOrder`. `--bookmarks` copies each
bookmark whose sections are that page alone, with visual names, targets, groups and active section rewritten, and
lists it in bookmarks.json. Navigation or drill-through buttons pointing at pages the target lacks are warned.
Fields aren't changed; `pbik validate` on the target catches any the model lacks. Test 143.

**Not marked unverified** (it writes no new form: the copy is the source's own JSON with names changed), but the
checklist opens a copied page in Desktop once. Copying a single visual is left out: `pbik build` owns visuals by ID,
and a layout entry with a template does that job.

**Provenance**: [L1] "PBIR format" (copying pages and bookmarks between reports as a scenario), "Common PBIR errors"
(pageBinding.name unique; a copied bookmark keeps its configuration only with its visuals); [L2]; pbik's report.py
(`stable_name`, page naming) and build.py.
## Gap 28: bookmark display modes beyond hidden (done, UNVERIFIED in Desktop)

**What pbik does now**: a layout bookmark's `spotlight: [IDs]`, `elevate: [IDs]` and `focus: ID` (or `{visual, table:
accessible / normal}`) write `singleVisual.display.mode` `spotlight`, `elevation` and `maximize` (with
`maximizedOptions.dataTable` for the data table; `accessible` is the screen-reader table Learn's focus-mode section
describes). Those visuals join the targets. A visual given two modes, or a bad `table`, is a layout error. Test 142.

**Provenance**: S:bookmark 2.1.0 #VisualContainerDisplayState (`mode`, `maximizedOptions.dataTable` enum accessible /
normal), #VisualContainerDisplayMode (maximize, spotlight, elevation, hidden); [L7] "Focus mode", "Show data table";
pbik's bookmarks.py (`hidden`, as Desktop saved it in Rep 5).
## Gap 29: cross-report drill-through (done, UNVERIFIED in Desktop)

**What pbik does now**: page `drillthrough: {..., crossReport: true}` adds `referenceScope: "CrossReport"` to the
page's pageBinding. The report setting `useCrossReportDrillthrough` is gap 1's `report.settings` key; `pbik build`
warns when neither layout.json nor report.json turns it on. Test 144. Testing it needs two reports published to one
workspace in the Service, which the kit doesn't do, so the Desktop checklist only checks the setting and the page
survive a save.

**Provenance**: S:page 2.1.0 #PageBinding (`referenceScope`: Default, CrossReport, "for cross-report drillthrough");
S:report 3.3.0 #ExplorationSettings (`useCrossReportDrillthrough`).
## Gap 15: other custom visuals (skipped: needs your decision)

Not built. Registering an organization-store visual (`organizationCustomVisuals`) or embedding a private `.pbiviz`
(`CustomVisuals/`, `CustomVisualJavascript` resource items) is visual-method ladder step 4, which CLAUDE.md says to
ask about before building, and docs/it-security.md treats such visuals as uncertified until checked. Whether pbik
should write them at all, and under which check, is a policy decision. The schema forms are known (S:report 3.3.0
`organizationCustomVisuals`, #OrganizationCustomVisual, #ResourcePackageType CustomVisual /
OrganizationalStoreCustomVisual), so it is a small gap once decided.
## Desktop checklist (pbik-smoke-bulk)

`..\pbik-smoke-bulk\Smoke.pbip` (beside the kit folder) is the smoke report for this batch. It uses synthetic data only:
`Sales` holds 216 inline rows (`#table`: 4 regions x 3 categories x 18 months to November 2026), with no file or
connection. `Date`, `Month` and a `Calendar` hierarchy (Year > Month) were added to the batch 1 smoke model. There is
one page per gap, named after its gap number. It was built with `pbik build --strict` against Microsoft's cached schemas,
and `pbik validate --strict` reports 0 errors. Page 19, "17 Copied page", was made with `pbik copy page`.
`_pbik-built\` holds the report exactly as pbik wrote it, for roundtrip. `..\pbik-smoke-bulk-draft\` is a first attempt
from before the gap 17 fix, kept only because nothing gets deleted without asking; it can be deleted.

Before you start: open `Smoke.pbip` in Desktop 2.159.883.0 and click **Refresh**. Refresh reads only the inline rows.
The report opens on "12 Page settings" (the landing page).

1. **Gap 12, landing page and page props:** the report opens on "12 Page settings". That page's content is vertically
   centred (`displayArea` Middle).
2. **Gap 13, annotations:** nothing to see. After the save, roundtrip should list no change to `annotations`.
3. **Gap 21, tab order:** on "21-22 Accessibility", go to View > Selection > Tab order and hide `P1-V02_band` from the
   tab order. The save shows the hidden form, which pbik's `decorative` key will then write.
4. **Gap 3, images:** on "3 Images" the teal square shows (registered PNG). Then set any image as that page's
   **canvas background** (Format page > Canvas background > Image). This is the page-image form that isn't known yet.
5. **Gap 25, registered resources:** the theme's colours and font apply on every page, and the image in step 4 loads.
6. **Gap 4, filters:** open the filter pane. On "4 Filters", the page filters show in this order: "Years 2025-2026"
   (Range), Category (Advanced: starts with "Al" or contains "mm"), and Date (relative: last 12 months). The report
   filter on Region is hidden. Only Alpha and Gamma bars from Dec 2025 to Nov 2026 show.
7. **Gap 2, per-member colours:** on "2 Per-member colours" the donut slices are teal, slate, light teal and gold, and
   the column chart's North bar is red.
8. **Gaps 5 and 28, bookmarks:** on "5 28 Bookmarks":
   - Alpha selects Alpha in the slicer and sorts the chart ascending.
   - Spotlight dims everything but the chart and lifts the slicer (elevation).
   - Focus opens the table in focus mode with the accessible data table.
   Leave the page as you found it before saving.
9. **Gap 6, tooltip page:** on "6 Tooltip source", hover a bar. If the default tooltip shows instead of the "6 Tooltip
   page" card, set the chart's Format > General > Tooltips > Type to Report page, Page "6 Tooltip page". The save then
   shows visualTooltip `type`.
10. **Gaps 7 and 29, drill-through:** on "6 Tooltip source", right-click a bar > Drill through > "7 29 Drill-through",
    and also try the "Drill to detail" button. The detail table filters to that region. In File > Options > Current
    file > Report settings, cross-report drill-through is on.
11. **Gap 8, hierarchy:** on "8 Hierarchy" the matrix shows Year with Month expanded under it.
12. **Gap 9, aggregations:** on "9 Aggregations" the table shows Average, Max, Count, Count (Distinct), Median,
    Standard deviation, Variance and the 90th percentile of Amount per region.
13. **Gap 10, visual calculations and sparklines:** on "10 Visual calcs and sparklines" the table has a "Running total"
    column and a sparkline of Total Amount by Month.
14. **Gap 11, mobile layout:** go to View > Mobile layout on "11 Mobile layout": the card sits top-left at 320x160.
15. **Gap 14, shape map:** on "14 Shape map", in Format > Map settings, pick the uploaded `regions.topo.json`
    (registered by pbik). The save shows the binding.
16. **Gap 16, rotation and query options:** on "16 Rotation and query options" the text box is rotated 90 degrees,
    and the line chart draws.
17. **Gap 27, group formatting:** on "27 Group" the two cards sit on a light grey group background. In the Selection
    pane, the group's alt text is "Two headline cards".
18. **Gap 17, copied page:** "17 Copied page" opens like "5 28 Bookmarks", and its three buttons apply their own copied
    bookmarks.
19. **Gap 26, new visuals:** "26 New visuals" shows a bare list slicer, or an error tile if `listSlicer` isn't the type
    id. Separately, for the templates: add a list slicer, an input slicer, an Azure map and a Gantt chart to the
    Patterns page in `..\pbip-patterns`, save, then run `pbik templates harvest` and `pbik catalog refresh`
    (docs/UPDATE-ROUTINE.md step 4).
20. Save once (Ctrl+S) and close Desktop. Then, from `..\pbik-smoke-bulk`, run the roundtrip command below.

Note anything that didn't render in step 1-19 next to its step number; together with the roundtrip output that is
what the follow-up needs.

**Roundtrip, after you save** (run from `..\pbik-smoke-bulk`):

```bat
python ..\pbip-kit-export\tools\pbik\pbik.py roundtrip Smoke.Report --before _pbik-built\Smoke.Report --out roundtrip.md
```

Reading it:
- Anything under "Proposed pbik fixes" on a gap's page is a form to correct.
- An "added" line on steps 3, 4, 9 and 15 is the missing form those gaps need.
- The "Registered resources" section should say Desktop kept the theme, the PNG and the map.
- Pane-dependent lines are expected.
## Desktop check results (Desktop 2.159.883.0, 2026-11-11)

Kyle went through the checklist on `..\pbik-smoke-bulk` with Claude: Claude screenshotted each page through the
Desktop Bridge, Kyle did the clicks and the five "set it in Desktop" steps, saved once, and Claude ran
`pbik roundtrip Smoke.Report --before _pbik-built\Smoke.Report` (`..\pbik-smoke-bulk\roundtrip.md`).

| Gap | Result in Desktop | What the save showed | Follow-up |
|---|---|---|---|
| 2 | Pass: donut slices and the column chart's North bar take their member colours | kept | none |
| 3 | Pass (image visual). Page background image set by hand | `objects.background.image.image {name, url: ResourcePackageItem, scaling}` | write it (layout page `background.image`) |
| 4 | Partial. Advanced text conditions, RelativeDate, displayName, ordinal, custom order and the hidden report filter pass (the chart matches Alpha + Gamma over the last 12 months to the unit). **Range fails**: the pane reads it as Basic filtering "is (All)" | Desktop rewrote `type: Range` to `Categorical`, keeping the Between | write a range as Advanced with two comparisons |
| 5 | Pass: Alpha ticks the slicer and sorts the chart ascending | kept | none |
| 6 | Pass: hovering shows the tooltip page, without visualTooltip `type` | Desktop adds `pageBinding.parameters: []` | write `parameters: []` |
| 7 | Pass: right-click drill-through and the button (greyed until a bar is selected) pass the region; the page has no Back button | Desktop drops `acceptsFilterContext: Default` | stop writing Default; warn when a drill-through page has no Back button |
| 8 | Partial: hierarchy-level fields render; **expand all doesn't expand** | `active` true / false on the level projections; `isCollapsed` dropped; Desktop keeps the rest but draws it collapsed | write `active`; make `expand` an error until a Desktop-expanded save shows the form |
| 9 | **Fail**: "two expressions with identical native reference name 'Amount'" | aggregations otherwise recognised (Median, Standard deviation, Variance, Percentile.Inc) | unique nativeQueryRef per projection |
| 10 | **Fail**: the same error ('Total Amount': the sparkline and the measure) | | the same fix |
| 11 | Pass: the card sits top-left at the phone's width | Desktop adds `position.tabOrder: 0` and moves mobile.json to 2.9.0 | write `tabOrder: 0` |
| 12 | Pass: opens on the landing page; displayArea Middle centres the canvas | kept | none |
| 13 | Pass: annotations kept | kept | none |
| 14 | Map picked in Desktop | `objects.shape {datasourceType 'file_upload', map.geoJson {type 'packaged', name, content: ResourcePackageItem}, projectionEnum}`; Desktop registered its own copy (`regions.topo<digits>.json`, type ShapeMap) and dropped pbik's unused one | write the binding (layout `shapeMap`) |
| 16 | Partial: query options pass; **`angle` fails**: the rotated text box neither draws nor selects (Desktop kept `position.angle`) | | make `angle` an error |
| 17 | Pass: the copied page renders and its buttons apply its own bookmarks | kept | none |
| 21 | Tab stop hidden by hand | `position.tabOrder: -9999000` (Desktop also renumbered the others x 1000) | `decorative` writes -9999000 |
| 25 | Pass: theme and registered PNG load | | none |
| 26 | Pass: `listSlicer` is the type id (a bare list slicer renders); templates not harvested yet | Desktop adds `active: true` on its Values field | write `active`; templates stay a Patterns-page task |
| 27 | **Fail (background)**: no group background draws in edit view | Desktop kept background, altText and lockAspect as written | keep unverified; check in reading view |
| 28 | Spotlight and focus (with the accessible table) pass; **elevation fails** | Desktop dropped `display: {mode: elevation}` from the saved bookmark | make `elevate` an error |
| 29 | Pass: the page's Cross-report toggle is On and the report setting is ticked | kept | none |
## Second Desktop pass (2026-11-11)

Range filter (gap 4), aggregations (gap 9) and visual calculations and sparklines (gap 10) pass after the fixes and
are no longer listed as unverified. The group background (gap 27) still doesn't draw, though Desktop keeps it: it
stays UNVERIFIED. Released as pbik 0.14.0 (kit v1.4). Left for later: gap 15 (a decision) and the gap 26 templates (a
Patterns page save in ..\pbip-patterns).
