# pbik 0.18.0

pbip-kit's own command line tool for PBIR reports and TMDL models. Python standard library only; `jsonschema` is
optional (schema checks).

It was written clean-room, from Microsoft's public PBIR and TMDL documentation, the `$schema` JSON schemas the files
declare, and files Power BI Desktop saved.

## Run it

```bat
python tools\pbik\pbik.py <command> ...         rem no install
tools\pbik\pbik.cmd <command> ...                rem same, through the wrapper
pip install --user -e tools\pbik                 rem then: pbik <command> ...  (or python -m pbikit)
```

Exit codes: 0 ok, 1 checks failed, 2 bad input, 3 Desktop bridge not available (`project check`: Desktop version not
found), 4 Desktop has unsaved changes, 5 Desktop is newer than targetDesktop (`project check`).

## Commands

### `templates harvest <Report>`
Copies each visual on the page named **Patterns** to `design/templates/<visualType>.<name>.json` (the visual name
without its ID), without its field bindings (`query`), name and position. Objects, container objects, filters and
conditional formatting stay as Desktop saved them. The largest visual of each type is also written as
`<visualType>.json`, the default `pbik build` uses; `index.json` lists every template and its source visual. `pbik build` takes
formatting only from a template: it drops every field-bound property or entry and the literal content (title and
subtitle text, text box paragraphs, button and slicer header text, a registered image, the action), which the layout
sets; template filters stay when the model has their fields (smoke 2026-10-19). Every selected state a template brings (button slicer
`selection:selected`, button or navigator `selected` / `press`) gets `tokens.colors.selected` as its fill, so a report
has one selected colour (an outline in the old colour follows). The state's text colour is set with it:
`tokens.colors.onSelected` when set, otherwise white or the dark primary, whichever contrasts more; text that still
fails 4.5:1 is a build warning. Anything layout.json sets wins.

```bat
pbik templates harvest "..\pbip-patterns\HR Overview.Report"
```

The kit's templates (`design/templates/`) come from the Patterns page of `..\pbip-patterns` (beside the kit folder; paths here are relative to the kit root,
where you run pbik):
`tools/patterns/build_patterns.py` makes it from a copy of Rep 8 (the best Desktop-saved example of each visual type
in Reps 4, 5 and 8, restyled to Rep 8; `tools/patterns/patterns.json` lists them), and Desktop saved it on
2026-10-19. To refresh: edit patterns.json, rebuild with `--page-only --force`, save in Desktop, harvest again.

### `build <Report> design/specs/layout.json`
Creates or updates pages and visuals by visual ID. Run it as often as you like: it writes only files whose content
changes, and a second run prints `No changes`. It writes the ID map `design/specs/visual-map.json`, which
`audit_ids.py` reads. Visuals, and pages pbik made, that left layout.json stay until you pass `--prune` (roadmap gap 12:
the page folder goes, and pages.json drops it from `pageOrder`, `activePageName` and `landingPageName`). Visuals without an ID (made in
Desktop) are never touched. A report that doesn't exist yet (`build "Orders Overview" ...` in a new project) is made
first as a clean, empty report folder (`pbikit/newreport.py`: no pages, the base theme, linked to
`<Name>.SemanticModel`, plus `<Name>.pbip`); nothing is copied from another report and an existing folder is never
touched (v1.7 walkthrough fix 1).

```bat
pbik build "Sales.Report" design\specs\layout.json
pbik build "Sales.Report" design\specs\layout.json --prune     rem also remove retired visuals
pbik build "Sales.Report" design\specs\layout.json --reset     rem rebuild every visual from its template
pbik build "Sales.Report" design\specs\layout.json --no-custom-visuals   rem each Deneb visual's fallback instead
```

Options: `--map`, `--tokens` (default `design/tokens.json`), `--templates` (default `design/templates`), `--strict`
(a property, setting or value outside Microsoft's cached schema stops the build: nothing is written; without it, a
warning).

Every `props` key, `container:` prop, page `filterPane` / `filterCards` property and `report` key is checked against
the cached Microsoft schema (`pbikit/schemaprops.py`, standard library). Microsoft's schema lists container, page and
report objects property by property, but leaves a visual's `objects` open for every visual type (any object, any
property): those pass here, and the settings catalog in `pbik validate` is what checks them per visual type. A schema
that isn't cached is skipped (`pbik schemas fetch`). The build also warns on a retiring visual (Map, Filled map), a Q&A
button and a deprecated page `displayOption` (as validate, below); the Q&A visual is warned by validate only.

`--reset` (and a Deneb / fallback swap) keeps the filters Desktop saved on the visual (automatic filters, and filters
made in the pane: any name not `pbik_` / `tpl_`), so a rebuild never loses them.

When tokens.json has `theme.recolourTemplates` (gen_tokens.py, `/theme`, sets it), a visual created from a template
has the template's literal colours mapped to the tokens by role: design/templates/palette.json lists the colours the
templates were drawn in and the token name each follows as text, line, shadow or fill (pbikit/recolour.py). The build
log lists them. Visuals already built keep theirs until `--reset` (design/known-gaps.md).

The layout keys are below; `tests/sample/layout.json` uses all of them except the 0.13 filter pane and report keys
(`report`, page `filterPane` / `filterCards`), which tests 110-118 add to copies. Colours are hex values or `tokens.colors`
names; font sizes are points or `tokens.fontPt` names; paddings and radii can name `tokens.container` values.
Fields use the layout notation: `[Measure]`, `Table[Column]`, `'Table name'[Column]`, `Sum(Table[Column])` (also `Median`,
`StDev`, `Variance` and `Percentile(Table[Column], 0.9)`, number columns only: Aggregation Function 6-8 and
Percentile, confirmed in Desktop 2026-11-11, roadmap gap 9; two fields with one name in a visual get unique
`nativeQueryRef`s, "Median of Amount", since Desktop refuses duplicates), checked
against the model's TMDL and `reportExtensions.json`.

| Where | Key | Writes |
| --- | --- | --- |
| top | `theme: "design/themes/pbip-polish.json"` | registers and applies the theme first (as `pbik theme apply`; path from the project root) |
| top | `annotate: true` | every page gets the annotation `pbik.page` (its layout key) and every visual `pbik.id` (its ID) and `pbik.layout` (12 hex of its layout.json entry); Desktop ignores annotations and keeps them ([L1] PBIR annotations). Confirmed in Desktop 2026-11-11 (roadmap gap 13) |
| top, page, visual | `annotations: {name: text}` (top: under `report`) | `annotations: [{name, value}]` on report.json, page.json or visual.json, in place: names layout.json sets are owned (removed when they leave it), others stay. `pbik validate` errors on a name used twice in a file and warns when a visual's `pbik.id` isn't its folder's ID (a copy). **UNVERIFIED in Desktop** |
| top | `report: {filterPane: {expanded, visible}, settings: {<setting>: value}}` | report.json, in place (filterConfig, themes, resources and Desktop's other settings stay): `objects.outspacePane` `expanded` (false = the pane opens collapsed) and `visible` (false = hidden in view mode), as Desktop saved `expanded` in Reps 1-7; `settings` (written in the schema's property order, as Desktop
saves them) = Microsoft's #ExplorationSettings (`exportDataMode`, `hideVisualContainerHeader`, `useEnhancedTooltips`, `pagesPosition`, `locale`, ...), each checked against the cached report schema (names and values). Each key remembers the value Desktop had and gets it back when it leaves layout.json (visual-map.json `reportOwned`). Desktop's reload doesn't apply report.json during the preview (Learn, external editing): close without saving and reopen. Pane state and settings other than `expanded` not yet Desktop-tested (roadmap batch 1) |
| page | `displayName`, `width`, `height`, `displayOption`, `hidden` | page.json; new pages get a stable 20-hex name |
| page | `active: true` (one page) | `pages.json` `activePageName`: the page the report opens on (default: the first page) |
| page | `background` (colour, or `{color, transparency, image, scaling}`) | `objects.background`; `image` (a PNG path from the project root) is registered and written as Desktop saved a canvas background image: `image.image {name, url: ResourcePackageItem, scaling: fit / fill / normal}` (pbik-smoke-bulk, 2026-11-11; roadmap gap 3) |
| page | `landing: true` (one page) | `pages.json` `landingPageName` (pagesMetadata 1.1.0): the page every user opens on, over `active`; pbik removes it when the key goes. Confirmed in Desktop 2026-11-11 (roadmap gap 12) |
| page | `props: {"object.property[@selector]": value}` | any page object (`pageSize`, `displayArea`, `pageInformation`, `outspace`, `pageRefresh`, `personalizeVisual`, `background`), values as in visual `props`, each checked against the cached page schema (#PageFormattingObjects is closed per object). The filter pane objects take `filterPane` / `filterCards`. Confirmed in Desktop 2026-11-11 (roadmap gap 12) |
| page | `filterPane: {backgroundColor, transparency, foregroundColor, titleSize, searchTextSize, headerSize, fontFamily, border, borderColor, checkboxAndApplyColor, inputBoxColor, width}` | the filter pane's look on this page: `objects.outspacePane`, no selector (page schema #OutspacePane); colours and sizes take tokens, `fontFamily` takes `regular` / `semibold` / a family. Not yet Desktop-tested |
| page | `filterCards: {applied: {...}, available: {...}}` (backgroundColor, transparency, border, borderColor, foregroundColor, textSize, fontFamily, inputBoxColor) | `objects.filterCard` on selector `{id: Applied}` / `{id: Available}` (the `$id`s Desktop's base themes use for filter cards). Not yet Desktop-tested |
| page | `filters` | page-level filters (as for visuals, below) |
| page | `drillthrough: {..., crossReport: true}` | `pageBinding.referenceScope: CrossReport`: other reports in the workspace can drill through to this page; needs the report setting `useCrossReportDrillthrough` (`report.settings`), else a build warning. Confirmed in Desktop 2026-11-11 (roadmap gap 29) |
| page | `drillthrough: {fields: ["T[C]"], keepFilters: true}` (or just the list) | a drill-through page: `type: Drillthrough`, `pageBinding {name, type: Drillthrough, parameters: [{name, boundFilter, fieldExpr}], acceptsFilterContext: None` only with `keepFilters: false`, as Desktop drops Default} and, per field, a page filter `howCreated: Drillthrough` with no condition (named `pbik_dt_*`), which its parameter's `boundFilter` names; page `filters` still work beside them. Owned. `pbik validate` warns when the page has no Back button (Desktop adds one only to pages made in Desktop). Confirmed in Desktop 2026-11-11 (roadmap gap 7) |
| page | `tooltip: true` | a report-page tooltip: page `type: Tooltip` and `pageBinding {name, type: Tooltip}` (name stable and unique across the report) and `parameters: []`, as Desktop saves it; give the page its tooltip size (`width`, `height`) and usually `hidden`. Owned. Confirmed in Desktop 2026-11-11 (roadmap gap 6) |
| page | `interactions: [{source, targets: [IDs] or "*", type}]` | `visualInteractions` (`NoFilter`, `DataFilter`, `HighlightFilter`) |
| page | `bookmarks: [{name, displayName, show: [IDs], hide: [IDs], targets: [IDs], data, display, changesPage}]` | `definition/bookmarks/<id>.bookmark.json` + `bookmarks.json`, as Desktop saved them in Rep 5. Applies only to the listed visuals; `data: false` (default) is display only (filters and slicer selections unchanged); `data: true, display: false` resets the targets' selections; `changesPage: false` (default) doesn't switch page. Ids are stable (page key + name); pbik's bookmarks are owned like its visuals (`--prune` removes dropped ones); Desktop's are never touched |
| page | bookmark `select: {ID: {field, values}}`, `sort: {ID: {field, direction}}` (or a list) | a data bookmark that saves a slicer selection (the visual's `singleVisual.objects.merge.general` `filter`, the same filter as `selection`) and a sort (`singleVisual.orderBy`, Direction 1 ascending / 2 descending); those visuals join the targets and `data` defaults to true (`data: false` with them is an error). Page and report filter states aren't written. Confirmed in Desktop 2026-11-11 (roadmap gap 5) |
| page | bookmark `spotlight: [IDs]`, `focus: ID` or `{visual: ID, table: accessible / normal}` | display modes beside `hidden`: `spotlight` and `maximize` (focus mode; `table` opens the data table, `accessible` being the screen-reader one) on those visuals' `singleVisual.display`; a visual takes one mode. Confirmed in Desktop 2026-11-11 (roadmap gap 28). `elevate` is an error: Desktop dropped the elevation mode on save |
| page | `bookmarkGroups: [{name, displayName, bookmarks: [names]}]` | a group item in `bookmarks.json` (a grouped bookmark isn't also listed on its own) |
| visual | `id`, `name`, `page`, `type`, `x`, `y`, `w`, `h`, `z` | folder and name `<ID>_<name>`; z = layer × 1000 + visual number; tab order = visual number × 100 (number IDs in reading order) |
| visual | `tabOrder: <whole number>` | `position.tabOrder` when reading order can't follow the IDs (Rep 9: a header slicer before an earlier-numbered subtitle); keep the × 100 scale, e.g. 350 between V03 and V04 |
| visual | `template` | start from `design/templates/<template>.json` (default: `<type>.json` if it exists) |
| visual | `bindings: {Role: [field or {field, displayName, active} or {fieldParameter, project, selected, displayName}]}` | `query.queryState`; `nativeQueryRef` stays the field's own name, as Desktop saves it. Shapes, text boxes, buttons and navigators without bindings get Desktop's empty `query: {queryState: {}}` (a template without a query, or `emptyQuery: false`, writes none). A `fieldParameter` item projects the parameter's fields from its calculated table in the TMDL, in parameter order, plus `fieldParameters`: `project: "all"` (default, every field, the Rep 3 form) or `"selected"` (one field, `selected` = its label, as Desktop saved it in Rep 5) |
| visual | binding item `{hierarchy: "Table[Hierarchy]", level: "Year"}` | a hierarchy level as the field (`HierarchyLevel` of `Hierarchy` of the table), queryRef `Table.Hierarchy.Level`, nativeQueryRef the level; the hierarchy and level are checked against the table's TMDL; the first level `active: true`, the others `active: false`, as Desktop saves them. Model hierarchies only: Desktop's automatic date hierarchy (PropertyVariationSource) isn't written. Confirmed in Desktop 2026-11-11 (roadmap gap 8) |
| visual | `expand` | a build error for now: Desktop kept the `expansionStates` pbik wrote but drew the matrix collapsed (2026-11-11). Expand the matrix in Desktop and save; `pbik roundtrip` shows the form (roadmap gap 8) |
| visual | binding item `{calc: "<name>", expression: "<DAX>", dataType}` | a visual calculation: `NativeVisualCalculation {Language: dax, Expression, Name}`, queryRef the name; the DAX isn't checked. Confirmed in Desktop 2026-11-11 (roadmap gap 10) |
| visual | binding item `{sparkline: "[Measure]", by: "T[C]"}` (tables, matrices) | a sparkline column: `SparklineData {Measure, Groupings: [by], PointsPerSparkline: 52}`. Confirmed in Desktop 2026-11-11 (roadmap gap 10) |
| visual | `sort: {field, direction, default}` (or a list) | `query.sortDefinition`; `default: true` writes `isDefaultSort` (Desktop keeps true, drops false) |
| visual | `filters: [{field, values, invert, hidden, locked}]` | categorical filter, values typed by the column (2024L, 1.5D, 'text') |
| visual | `filters: [{type: "TopN", field, by, n, direction: "Top" or "Bottom"}]` | Top N filter |
| visual | `filters: [{field: "[Measure]", op: "=" / ">" / ">=" / "<" / "<=", value: <number>}]` | a measure filter ("show items when the value is ..."): an `Advanced` filter with one Comparison, the value as a decimal (0D). Visuals only: a measure filter in a page's `filters` stops the build with an error (Power BI filters on measures per visual). Not Desktop-tested yet (kit v1.2) |
| visual, page, top `report` | `filters: [{field, type: "Range", min, max}]` | a range: the pane's Advanced mode, `>=` min And `<=` max, values typed by the column (a `type: Range` Between was shown by Desktop as Basic "is (All)", 2026-11-11). Confirmed in Desktop 2026-11-11 (roadmap gap 4) |
| visual, page, top `report` | `filters: [{field, type: "Advanced", conditions: [{op, value}], join: and / or}]` | the pane's Advanced mode on a column, one or two conditions: `contains`, `doesNotContain`, `startsWith`, `doesNotStartWith`, `is`, `isNot`, `isBlank`, `isNotBlank`. **UNVERIFIED** |
| visual, page, top `report` | `filters: [{field, type: "RelativeDate", last, unit: days / weeks / months / years}]` | in the last N units, today included (Between DateSpan(DateAdd(DateAdd(Now, 1 day), -N unit)) and DateSpan(Now)), from the schema's date expressions. Confirmed in Desktop 2026-11-11 (roadmap gap 4) |
| top | `report: {filters: [...]}` | report-level filters in report.json `filterConfig` (any type above except a measure filter); pbik's own (`pbik_`) only, Desktop's stay. Confirmed in Desktop 2026-11-11 (roadmap gap 4) |
| any filter | `displayName`, `ordinal`; and `filterOrder: ascending / descending / custom` on the visual, page or `report` | the filter card's name, its place when the order is custom (`ordinal`), and `filterConfig.filterSortOrder`. Confirmed in Desktop 2026-11-11 (roadmap gap 4) |
| visual | `type: "htmlContent<GUID>"` (the HTML Content visual, any version) | `objects.compatibility.legacyRendering` true, and the visual in report.json `publicCustomVisuals` (pbikit/htmlcontent.py, from the visual's capabilities.json; not Desktop-tested yet). Under 43px tall: a build and validate warning. A custom visual: ladder step 4, uncertified until checked (docs/it-security.md) |
| visual | `selection: {field, values}` | slicer default selection (`objects.general.filter`) |
| visual | `referenceLines: [{axis: value, value2 or category; value: number or [Measure]; label, color, style, width, dataLabel}]` | `y1` / `y2` / `xAxisReferenceLine`; on a horizontal bar chart the value axis is still y1 (`x` there is an error) |
| visual | `columnWidths: {field: px}` (tables, matrices) | `columnWidth` on each column's metadata selector |
| visual | `columnWidths: "fit"`, or `"fit"` as a value next to fixed px (tables, matrices) | widths computed from the box (`pbikit/tablefit.py`): inner width = box less container padding less `tokens.table.scrollbarReserve` (16px); each column at least its header width at the header font, or 120 text / 64 number / 90 date / 100 image; columns of one kind share one width; the rest shared text 2 : others 1; whole pixels that add up exactly. A matrix sizes one stepped Rows column; fields on Columns, field parameters or a box too narrow are build errors |
| visual | `slicerMode: list / dropdown / between / before / after` (classic slicer) | `data.mode` (overrides the theme's Dropdown) |
| visual | `sync: {group, fieldChanges, filterChanges}` (or just the group name; slicers) | `visual.syncGroup`: slicers with the same group on any page share their selection |
| visual | `emptyQuery: true / false` | force or drop the empty `query` on a visual without fields |
| visual | `action: {type: PageNavigation, page: <page key or display name>}` | `visualLink`, target written as the page **name** (id) |
| visual | `action: {type: Drillthrough, page: <page key>}` | `visualLink` type Drillthrough and `drillthroughSection` (the page's name); the page must have `drillthrough`. Confirmed in Desktop 2026-11-11: greyed until a data point is selected (roadmap gap 7) |
| visual | `action: {type: ClearAllSlicers / Back / Bookmark (bookmark) / WebUrl (url)}` | `visualLink`; `bookmark` is a layout bookmark name on the same page (`P2/name` for another page) or the id of a bookmark made in Desktop; pbik writes the real id |
| visual | `container: {background, border, shadow, padding, title, subtitle, header, altText, keepLayerOrder, spacing}` or `"off"` | `visualContainerObjects`; `false` turns a layer off; `title: {measure}` binds the text to a measure; `altText` and `keepLayerOrder` go to `general`, `spacing: {vertical, belowTitle, belowSubtitle, belowTitleArea}` (px or `tokens.container` names) turns on `customizeSpacing` (as Desktop saved them in Rep 7) |
| visual | `text: "..."` or `[{runs: [{text, font, size, color}], align}]` | text box paragraphs |
| visual | `style: {fill, outline, transparency, radius}` (shapes) | shape fill / outline / corners on selector `{id: default}` |
| visual | `cf: [{type: "measure", object, property, measure, target, perPoint, kind}]` | colour (or value with `kind: "value"`) from a measure |
| visual | `cf: [{type: "field", object, property, field, ...}]` | the same from an aggregated column: `First(T[C])` / `Min(T[C])` (Aggregation Function 3, as Desktop saved it in Rep 6 and 7), e.g. a team colour or logo column; a bare column is an error |
| visual | `cf: [{type: "rules", object, property, field, target, rules: [{op, value, color}] or [{min, max, color}], else}]` | `Conditional` cases |
| visual | `cf: [{type: "dataBars", field, positive, negative, axis, hideText}]` | `columnFormatting.dataBars` |
| visual | `cf: [{type: "gradient", object, property, field, target, min, mid, max}]` | `FillRule` linear gradient |
| visual | `cf: [{type: "image", measure or field}]` | new card image from a measure or an aggregated column (`imageType` imageUrl) |
| visual | `referenceLabels: {field, titleOff, layout, valueColor, valueSize, valueFont, titleColor, titleSize, titleFont, detailSize, displayUnits, labels: [{title, value, detail, detailColor, detailBackground, blankAs}]}` | new card reference labels through `objects.ref_labels`, with stable ids (`field-<uuid5 of ID, field, title>`); every setting on the label's id'd selector |
| visual | `props: {"object.property@selector": value}` (`container:` prefix for container objects) | any other property; selector `default`, `hover`, `selected`, `*`, `[Field]`, `none`, `"object@selector": {}` for an entry with no properties (Desktop keeps some, e.g. `columnFormatting: [{}]`), or any selector as JSON (`"referenceLabel.value@{\"metadata\": \"_Measures.Revenue\", \"id\": \"field-…\"}"`). Without one, button, new card, button slicer and shape objects go on `{id: default}` as Desktop saves them (button `show` stays selector-less) |
| visual | `navigator: {fill, outline, radius, font, size, colors: {default, hover, selected}, transparency: {default, hover, selected}}` (page / bookmark navigators) | tile states as Desktop saved them in Rep 5 and 8: `fill` / `outline` `show` selector-less, fill colour and transparency, outline (the selected tile only) and text colour per state id, font and size on `default`, rounded tiles (`rectangleRoundedByPixel`) |
| visual | `type: "deneb"`, `bindings: {dataset: [...]}`, `deneb: {spec}` (a Vega-Lite spec inline, or a JSON file path from the project root), `fallback: {type, bindings, props, ..., build}` | a Deneb visual as Desktop saved one on the Patterns page (2026-10-24, `pbikit/deneb.py`): `visualType` deneb7E15AEF80B9E4D4F8E12924291ECE89A, the fields on the `dataset` role, `vega.jsonSpec` (the spec as one string, CRLF), `stateManagement` (field configuration: format on for measures; denebMetaVersion '2'; viewport = the box), and the visual in report.json `publicCustomVisuals`. Vega-Lite only (no provider or config was saved). A spec with a `url` (external data or images) or nothing to draw is a build error. The fallback (native or SVG) takes the ID, name, page, box, z, container, tab order and filters, but not the title or subtitle: a fallback sets its own (`fallback.container.title`, required when the Deneb visual has one); `--no-custom-visuals` builds it in the same folder, and switching back and forth is allowed (any other type change still needs a new ID). visual-map.json records `built: deneb / fallback` |
| visual | `image: "design/images/logo.png"` or `{file, scaling: fit / fill / normal}` (image visuals) | registers the file (as `pbik resource add`, path from the project root) and binds it: `general.imageUrl` = ResourcePackageItem (RegisteredResources, PackageType 1), `imageScaling.imageScalingType`, the form Desktop saved on the Patterns page (`design/templates/image.json`). Give it `container.altText`, or mark it `decorative`. A page background or wallpaper image isn't a key yet (roadmap gap 3: its form isn't known) |
| visual | `members: [{field: "T[C]", object: "dataPoint", property: "fill", values: {member: value}}]` (or one dict) | one formatting entry per category member on selector `data: [{scopeId: Comparison(column = member)}]`, the member typed like the column, as Desktop saved the Rep 5 donut's slice colours (roadmap gap 2). Values as in `props`. Owned per member. `dataPoint.fill` is Desktop's own form; any other object or property is **UNVERIFIED in Desktop** |
| visual | `tooltipPage: <page key>` | `visualContainerObjects.visualTooltip` `show` and `section` (that page's name); the page must have `tooltip: true`. visualTooltip `type` isn't needed: Desktop shows the tooltip page with `section` alone. Confirmed in Desktop 2026-11-11 (roadmap gap 6) |
| visual | `mobile: {x, y, w, h, z}` | `mobile.json` beside visual.json (visualContainerMobileState 2.8.0) with the visual's position on the page's mobile layout; owned (removed when the key goes). Phone-layout formatting (`objects`) isn't written. Confirmed in Desktop 2026-11-11 (roadmap gap 11) |
| visual | `queryOptions: {binnedLineSample, overlappingPointsSample}` | `query.options` `allowBinnedLineSample` / `allowOverlappingPointsSample` (better sampling for line and scatter charts). Owned. Confirmed in Desktop 2026-11-11 (roadmap gap 16). `angle` (position.angle) is a build error: Desktop kept it but didn't draw the visual |
| visual | `shapeMap: "design/maps/x.topo.json"` or `{file, projection}` (shape map visuals) | registers the TopoJSON as a ShapeMap resource and binds it as Desktop saved an uploaded map (pbik-smoke-bulk, 2026-11-11; roadmap gap 14): `objects.shape` `datasourceType 'file_upload'`, `map.geoJson {type 'packaged', name, content: ResourcePackageItem}`, `projectionEnum` (default `albersUsa`) |
| visual | `hidden` | `isHidden` |
| visual | `decorative: true` (shapes, images that only decorate) | hidden from the tab order: `position.tabOrder: -9999000`, the form Desktop saved for a tab stop hidden in its Selection pane (pbik-smoke-bulk, 2026-11-11; roadmap gap 21); an explicit `tabOrder` wins. Recorded in visual-map.json; `pbik validate` skips its alt text and the reading-order check. A shape with no alt text and no `decorative` is a warning; `decorative` with `container.altText` is a build error |
| visual (group) | `background` (`{color, transparency}` or false), `altText`, `lockAspect` | `visualGroup.objects` (background, general.altText, lockAspect), selector-less, owned per property; formatting Desktop set on the group stays. **UNVERIFIED in Desktop** (roadmap gap 27) |
| visual | `type: "group"`, `members: [IDs]`, `displayName`, `mode` (default `ScaleMode`), optional `x`/`y`/`w`/`h` | a visual group: a `<ID>_<name>` folder whose visual.json has `visualGroup` and no `visual`. Members (visuals or groups, same page, one group each) get `parentGroupName` (owned: it goes when they leave the group) and a position relative to the group, as Desktop saves them; layout.json keeps page coordinates. Without a box the group spans its members. A bookmark that hides or shows a group writes `visualContainerGroups` |

Property values in `props`: `true`/`false`, numbers (written as `12D`; whole numbers as `0D`, not `0.0D`), `{"int": 12}` (`12L`), a `tokens.fontPt` name on a
size property (`"kpi"` → `27D`) or a `tokens.container` name on a radius/padding/width property, colours (`"#hex"`, a
token name on a colour property, `{"color": "teal"}`, or a theme colour: `"theme:0"`, `"theme:0:-0.6"` or
`{"theme": 0, "percent": -0.6}`, written as `ThemeDataColor`: Desktop's ColorId, where 0 is the theme background,
1 the foreground and 2 onwards `dataColors[0]` onwards, and a shade from -1 (darker) to 1 (lighter)), `{"fx": "[Measure]"}`
(colour from a measure, or `First(T[C])` from a column), `{"expr": "[Measure]"}`, `{"raw": <PBIR JSON>}`, anything else as text.

Text boxes get 6px of headroom and 12px extra height (`textFit: false` turns it off); `audit_layout.py` expects it.
Properties written by an earlier build and no longer in layout.json are removed on the next build (the ID map keeps
the list).

Batch 4 roundtrip fixes: a button's `text` becomes its label (`objects.text.text` on `{id: default}`, the form Desktop
saves; `props: {"text.text": ...}` is the same), never text box paragraphs; a matrix's first `Rows` field is written
`active: true` when a later one is `active: false`, as Desktop saves it.

### `measure ext add <Report> <name> --expression <DAX> --data-category ImageUrl`
Adds or updates a report-level extension measure in `definition/reportExtensions.json`. Visuals bind it with
`SourceRef.Schema = "extension"`. Use it for SVG measures a card image or table column shows.

```bat
pbik measure ext add "Sales.Report" "img Revenue bar" --expression "[Revenue bar SVG]" --data-category ImageUrl
pbik measure ext list "Sales.Report"
pbik measure ext remove "Sales.Report" "img Revenue bar"
```

Options: `--data-type` (Text by default), `--table` (default `_Measures`), `--format-string`, `--description`.

### `theme apply <Report> <theme.json>`
Copies the theme to `StaticResources/RegisteredResources/`, lists it in `report.json` and sets it as
`themeCollection.customTheme` over the base theme. Running it again changes nothing.

```bat
python design\scripts\gen_theme.py
pbik theme apply "Sales.Report" design\themes\pbip-polish.json
```

### `resource add <Report> <image>`
Registers an image once (the same name is reused, never copied as `<name>_2.png`). Bind it as a
`ResourcePackageItem` (`objects.image_objects` in pbikit).

`--type ShapeMap` registers a TopoJSON map for the shape map visual instead (item type ShapeMap, roadmap gap 14,
**UNVERIFIED in Desktop**): pbik can't bind it to the visual yet, so pick it in Desktop (Format > Map settings) and
save. `pbik validate` errors on a registered resource whose file is missing.

```bat
pbik resource add "Sales.Report" design\images\court.png
pbik resource add "Sales.Report" design\maps\regions.topo.json --type ShapeMap
```

### `validate <Report> [--layout design/specs/layout.json]`
Schema checks against each file's `$schema`, plus the kit rules:

- every visual has an ID (`<P<n>-V<nn>>_<name>` folder and name), no ID twice, and with `--layout` the IDs match;
- page-navigation buttons target a page name (id), not a display name;
- `pages.json`: every `pageOrder` entry (and `activePageName`) has a page folder, and every page folder is in
  `pageOrder`;
- `%` inside SVG text is written as `%25` (model and extension measures); a measure calling DaxLib.SVG passes raw `#`
  colours, not `%23` (its output keeps a raw `%`, so `%23` draws nothing in Desktop, v0.4.1);
- visuals stay inside the page;
- filter values on numeric columns are numbers, not text (`'2024'` never matches);
- lessons promoted to checks (warnings, `lesson_checks`): a button slicer under 40px without padding Custom 0 top and
  bottom (S-01), a dropdown slicer with a header under 76px (S-03), a selector-less `dataPoint.fill` on a chart with
  more than one series (CH-02); an HTML Content visual under 43px;
- a size property holds a number, not text (`fontSize 'kpi'` is ignored by Desktop); button text off `{id: default}` is a warning;
- every bound field exists in the model's TMDL or in `reportExtensions.json`; an extension measure references no other
  extension measure (visuals using such a chain failed in Desktop, v0.4);
- Deneb visuals: the spec (`vega.jsonSpec`) is valid JSON and Vega-Lite with something to draw, loads nothing by
  `url` (errors); its `data` is `{"name": "dataset"}` and its encoding fields are in the visual's dataset (warnings:
  the Patterns save drew "Nation" / "Medals", which it doesn't have); report.json `publicCustomVisuals` lists the
  visual; with `--layout`, every `type: "deneb"` visual has a native or SVG `fallback` (errors);
- bookmarks: a button pointing to a missing bookmark, a bookmark listing a visual that isn't on its page, a bookmark
  that would hide or show visuals on a different page than the button that applies it, and `bookmarks.json` entries
  without a file (files not listed are a warning);
- button slicers (warnings): no `layout.rowCount` / `columnCount` (Desktop then picks its own tile width and
  scrolls), more items than tiles, or a label wider than its tile at the slicer's font size. The items come from the
  open Desktop model with `--port <n>` or `--port auto` (newest `msmdsrv.port.txt`, a `DISTINCT` query through
  `.claude/scripts/run-dax.ps1`); otherwise from the visual's `items` in layout.json (a count, or the labels). Label
  widths are Segoe UI estimates, so check a warning in Desktop. Slicers with neither are listed in a `note` line.

- accessibility (warnings, `pbikit/a11y.py`, CLAUDE.md "Accessibility"): alt text on every data visual and image;
  WCAG AA contrast of literal text colours against what is behind them (the visual's own background, a state's own
  fill on buttons, navigators and button slicers, else the topmost opaque shape or visual underneath, else the page);
  no text below `tokens.a11y.minFontPt` (10pt); tab order in reading order; a shape without alt text that layout.json
  doesn't mark `decorative` (one warning per page; decorative visuals are listed in a note to hide from the tab order
  in Desktop); and Learn's checklist (roadmap gap 22): alt text over 250 characters, a text box whose text isn't in
  its alt text, data visuals without a sort order of their own (one warning per page). `--no-a11y` skips them.
- target Desktop (project.json `targetDesktop`): a file whose `$schema` version is newer than that Desktop supports;
- service limits (errors, roadmap gap 18): more than 1,000 pages, 1,000 visuals on a page or 1,000 registered
  resource files, or more than 300 MB of resources or of report files (Learn, PBIR considerations and limitations);
- paths (roadmap gap 23): a report or model file whose full path is 260 characters or longer (Desktop can't reload
  or open it; Learn, external editing). `pbik build` warns on each visual.json it writes past the limit;
- Microsoft's schema, property by property (warnings; errors with `--strict`, `pbikit/schemaprops.py`): a container,
  page or report property, or a report setting or value, not in the cached schema (visuals: the `owned` list next to
  `--layout`, else every property). A visual's `objects` are open in the schema, so the settings catalog checks those.
  With `jsonschema` installed the full schema pass still errors on the same file, because the object is closed in the
  schema and Desktop may not open it;
- UNVERIFIED in Desktop (warnings, `pbikit/unverified.py`, roadmap batch 2): every feature pbik writes from Microsoft's
  schema only that no Desktop save has confirmed yet, with the files it is in. `pbik build` prints the same per
  feature it writes and checks the JSON it writes for them against the cached schema (a warning; `--strict` an
  error, nothing written);
- retiring and deprecated (warnings, `pbikit/deprecations.py`, roadmap gap 20): the Q&A visual (validate only; type
  id `qnaVisual` unconfirmed: Desktop 2.159.883.0 no longer offers the visual) and a button's Q&A action (Q&A goes away
  in February 2027), Map and Filled map (Bing Maps, scheduled for deprecation; use Azure Maps),
  and page `displayOption` `DeprecatedDynamic` / `ActualSizeTopLeft` (read from the schema's Deprecated mark);
- filter pane (report.json `outspacePane`): hidden in view mode (`visible` false) while filters that aren't hidden
  remain (a warning: users can't reach them); collapsed (`expanded` false) prints a note: automatic filters reach the
  files only after the pane has been opened once, which is expected, not a loss;
- settings catalog (warnings): a property, value type or selector pbik wrote (the `owned` list in `visual-map.json`
  next to `--layout`; without it, every property of an ID'd visual) that no Desktop-saved file in
  the catalog (`tools/pbik/catalogs/home.json`, or project.json `catalog`) has. Desktop may ignore or rewrite such a setting: check it in Desktop, or find the form
  Desktop saves. `--catalog <file>` uses another catalog, `--no-catalog` skips the check.

```bat
pbik validate "Sales.Report" --layout design\specs\layout.json
pbik validate "Sales.Report" --layout design\specs\layout.json --port auto
pbik validate "Sales.Report" --layout design\specs\layout.json --strict     rem schema misses are errors
```

Three levels: errors, warnings and notes. Notes are for the record and never count as problems, so a clean build
reports `0 error(s), 0 warning(s)` (v1.7 walkthrough fix 6): a schema version newer than any Microsoft has published
(a 404, not a cache gap: visualContainer 2.14.0 under Desktop 2.159), and settings pbik itself writes that no
Desktop-saved file in the catalog holds yet but that Desktop has shown as intended (`catalog.CONFIRMED_WRITES`, each
with where it was seen). In the main flow, `plan approve` writes design/specs/spec.md with every visual by ID and the
fallback register (marked as the main flow), and audit_ids.py doesn't ask it for the /plan-only sections.
Tables and matrices built with the kit's tokens (`table.alignNumberHeaders` true) get each number column's header
right-aligned over its numbers (`columnFormatting` alignment 'Right', styleHeader); picture and text measures, a
column whose alignment layout.json sets, and `alignNumbers: false` are left alone. Older reps' tokens don't have the
switch, so they build as before.

### `roundtrip <Report> [--rev REV] [--to REV] [--before <copy>] [--out <md>]`
After a report pbik built is saved once in Desktop, lists what Desktop rewrote, by visual ID, as proposed pbik
fixes: keys Desktop added (write them too), keys it dropped (stop writing them), values it rewrote, the same value in
another JSON form (`32.0` -> `32`), a new `$schema` version, and key or entry order. Object entries are matched by
selector. Fixes seen on many visuals are counted at the top. Read-only: it changes nothing.

Filters are matched by name. Differences that follow the filter pane, not pbik, are labelled `pane` and listed apart,
never as fixes: an automatic filter Desktop saved once the pane had been opened (`howCreated: Auto`, or as
Desktop 2.159.883.0 saves them: name, field and type only, no `howCreated` and no condition) (Microsoft Learn:
automatic filters persist only after the pane has been expanded), and the pane's `expanded` / `visible` state as the
author left it (the layout's `report.filterPane` sets it on the next build). Registered resources
(`StaticResources/RegisteredResources`: the theme pbik registered, images) are compared in their own section: a JSON
resource key by key, any other file by content hash, so Desktop rewriting the theme or an image shows up (roadmap
gap 24).

pbik's side is the last commit (the kit commits after every build) and Desktop's the working tree; `--rev` / `--to`
pick two revisions, `--before` a copy of the report as pbik wrote it.

```bat
pbik roundtrip "Sales.Report" --out design\reviews\roundtrip.md
pbik roundtrip "..\pbip-patterns\HR Overview.Report" --rev HEAD~1 --to HEAD
```

The Patterns page save (2026-10-19) showed: whole-number positions written as `32.0` (build_patterns, fixed), an
empty `visualContainerObjects` Desktop drops, visualContainer 2.13.0 moved to 2.14.0 on buttons, and the final
newline dropped on every file (pbik keeps it on purpose: it marks files Desktop hasn't saved).


Visuals Desktop added without an ID are listed with a proposed ID (next free on the page, `retired` skipped), folder
name and alt text from their fields; `--name-new` renames the folder, sets the name and alt text and renames every
reference (interactions, bookmarks, groups), and prints the layout.json entries to add (with `desktopPosition`).
After every hand polish: roundtrip, then update layout.json so a rebuild prints "No changes" (lesson B-13).
Bookmarks pbik made that the author moves into a bookmark group made in Desktop are left alone from then on (file,
place and membership); the build log says so.
### `catalog refresh <folders> [--name <name>] | catalog show | catalog list`
The settings catalog (`tools/pbik/catalogs/home.json`, `pbikit/catalog.py`): every formatting property, value type
(`bool`, `number`, `int`, `text`, `color:literal`, `color:theme`, `color:measure`, `measure`, `paragraphs`, ...) and
selector shape (`none`, `id:default`, `metadata`, `data:dataViewWildcard+metadata`, `id:field-*`, ...) found in
visual.json and page.json files Power BI Desktop saved, per visual type (objects), for all visuals (container
objects) and for pages. A file counts as Desktop-saved when it has no final newline: Desktop writes none and pbik
always writes one (`--all` reads every file). `refresh` merges new folders into the catalog and lists what is new;
run it after every Desktop save of a rep and after every Desktop update.

```bat
pbik catalog refresh ..\pbip-rep8 ..\pbip-patterns
pbik catalog show --type cardVisual --object referenceLabel
pbik catalog refresh --name work ..\pbip-patterns-work     rem tools\pbik\catalogs\work.json
pbik catalog list                                                      rem each catalog and its Desktop version
```

Named catalogs (`--name home`, `--name work`; letters, digits, `-`, `_`) are one machine's Desktop each:
`tools/pbik/catalogs/<name>.json`, with the Desktop version that saved the files (detected, or `--desktop <version>`;
its date moves only when the version does). A rep's design/specs/project.json `catalog` names the one
`pbik validate` uses; without one it is `home` (moved from `tools/pbik/catalog.json` in pbik 0.8.0), and
`--catalog <file>` wins over both.
Harvesting a work catalog from the Patterns report saved in the work Desktop: docs/UPDATE-ROUTINE.md.

Built on 2026-10-19 from pbip-rep4, pbip-rep5, pbip-rep8, pbik-parity (Desktop-saved files only), pbik-parity-rep5
and pbip-patterns: 491 settings.

Schemas come from a local cache. `pbik schemas fetch <Report>` downloads the declared schemas (and the ones they
reference) from `https://developer.microsoft.com/json-schemas/` into `tools/pbik/schemas/` (git-ignored). Without
`jsonschema`, or for a schema not in the cache, validate runs the kit rules and warns that schema checks were
skipped. Microsoft doesn't publish every version Desktop writes (visualContainer 2.14.0 returned 404 on 2026-10-17).
`--project` also fetches the target Desktop's versions. `PBIK_SCHEMA_CACHE=<folder>` uses another cache folder (the
tests point it at small stand-in schemas, so they need no download).

### `schemas support [--refresh] | schemas lower <Report> | project show | project record | project check`
Version-aware builds (`pbikit/versions.py`, docs/UPDATE-ROUTINE.md). A rep's `design/specs/project.json`:

```json
{"targetDesktop": "2.152.882.0", "catalog": "work", "desktop": {"version": "2.159.883.0", "recorded": "2026-10-29"}}
```

- `targetDesktop` (a Desktop version, or `"latest"`, the default without a project.json): `pbik build` writes each
  file's `$schema` at the newest version that Desktop supports (and lowers report.json's and version.json's;
  "target Desktop ... capped" in its output); `pbik validate` errors on a file declaring a newer version and
  schema-checks against the older schemas. `build` reads the project.json next to layout.json, `validate` the one in
  `<project>/design/specs/`; `--project` on either names another.
- `customVisuals: false` (optional; leave it out where custom visuals work): this laptop or tenant blocks custom
  visuals (Deneb). `pbik build` then builds each Deneb visual's fallback, as `--no-custom-visuals`, every time;
  `pbik validate` warns on a Deneb visual still in the report. `tools/doctor.ps1` says when to set it.
- What a target supports comes from `tools/pbik/schema-support.json`: each schema's release month from the
  CHANGELOG.md Microsoft publishes beside it (github.com/microsoft/json-schemas), and each Desktop release's month from
  the Desktop update archive on Microsoft Learn. `schemas support --refresh` re-reads both (online); `schemas support`
  prints them. A Desktop version Learn doesn't list takes the release before it; one newer than every listed release
  isn't pinned (Desktop writes versions Microsoft hasn't published yet).
- `schemas lower <Report>`: lowers every file's `$schema` to the target (to open a Desktop-saved report, such as the
  Patterns report, in an older Desktop). The files get pbik's final newline, so they count as Desktop-saved again only
  once that Desktop saves them.
- `project show` prints the target, its release and the schema version per kind; `project record [--version X]`
  writes this machine's Desktop version (Store package or the MSI install) to `desktop` (/model does it). It never
  changes the target. Desktop installed from the MSI (IT-managed) reports `2.155.756.0 (26.06)+<hash>`: pbik takes the
  leading version number, here and in `project check`.
- `project check [--version X]` compares this machine's Desktop with `targetDesktop` (/build runs it first): exit 5
  when Desktop is newer ("run /update first"), 3 when its version can't be found, a warning (exit 0) when it is older,
  0 when they match or the target is `"latest"`. A target of `2.155` matches every 2.155 build. It also warns when
  Desktop is older than the August 2026 release that reloading external changes needs (2.156.951.0, July 2026, or
  older; roadmap gap 23).

```bat
pbik schemas support --refresh
pbik project show
pbik project record
pbik project check
pbik schemas lower "..\pbip-patterns-work\HR Overview.Report"
```

### `copy page <from Report> <page> <to Report> --key P<n> [--as <name>] [--bookmarks]`
Copies a page into another report (roadmap gap 17; Microsoft Learn names copying pages between reports as a PBIR
scenario): the page gets the name `pbik build` would give layout page `<key>`, visual IDs move to that page number
(`P2-V04_x` -> `P5-V04_x`, with `parentGroupName` and `visualInteractions`), page and visual filter names, the
`pageBinding` name and its parameters are renamed so they stay unique (Learn, Common PBIR errors), and `--bookmarks`
brings the bookmarks that belong to that page alone, rewritten to the copy. Buttons pointing at pages the target
lacks are listed. Fields aren't changed: run `pbik validate` on the target. The copy is Desktop's own JSON; check it
opens in Desktop (batch 2 checklist).

```bat
pbik copy page "..\pbip-rep8\HR Overview.Report" "Workforce" "Sales.Report" --key P5 --bookmarks
```

### `values <Report> [--out <md>]`
Lists the model values written into the report files, for a privacy review (roadmap gap 19; Microsoft Learn warns that
filter and slicer values are saved in the files): every literal in report, page and visual filters, slicer selections,
per-member selectors (`scopeId`) and bookmark states, by file and field. Formatting literals aren't listed. Read-only.
Check the list against docs/it-security.md before committing.

```bat
pbik values "Sales.Report" --out design\reviews\values.md
```

### `info <Report> [--json]`
Pages, and visuals by ID, type, position, z and fields.

```bat
pbik info "Sales.Report"
```

### `model check <SemanticModel> [--folder Model]`
Reads the TMDL and fails on: a measure without a description (`///`), a number measure without a format string
(text measures are recognised from their DAX, `pbikit/daxtype.py`: a string, a `&` concatenation, FORMAT, UNICHAR
and the other text functions, IF / SWITCH / COALESCE with a text branch, SELECTEDVALUE / MIN / MAX of a text column,
or a text VAR or measure; declared `dataType: string` / `dataCategory: ImageUrl` still count, and no `formatString: @`
is needed. On Rep 8 it recognises all 20 measures that carried `@`), a DAX reference to a
table, column or measure that doesn't exist (measures, calculated columns, calculated tables), and a relationship
or sort-by column that points to a missing column. It counts the model's user-defined functions (functions.tmdl, e.g.
DAX Lib packages) and fails on a call to a function whose first name part is a package's but which the model doesn't
define (`DaxLib.SVG.Viz.Nope`). `--folder` limits the measure checks to one display folder.

```bat
pbik model check "Sales.SemanticModel" --folder Model
```

### `desktop state | reload | screenshot | open | close`
Runs `.claude/scripts/pbi-bridge.ps1` (found above the current folder, or `--bridge <path>`). If PowerShell, the
script or the Desktop Bridge isn't available, pbik says so and exits with code 3; when Desktop is open but has no
bridge, it adds whether this Desktop is too old for reloading (before August 2026) or needs the preview option
**Detect and reload external PBIP changes** (roadmap gap 23). After a reload it reminds you that reloading resets
filters and slicer selections, so a screenshot shows the default state.

```bat
pbik desktop state --fail-if-dirty                            rem exit 4 when Desktop has unsaved changes
pbik desktop reload                                           rem report only; refuses while unsaved
pbik desktop screenshot --report "Sales.Report" --page "Overview" --out _snapshots\p1.png --region 0,0,1920,1080
```
`desktop open` opens the project's report in Desktop. `desktop close` (v1.7, decision D1) closes it without saving only
when it is proven that its only unsaved changes are its own reload marks: the agent's `desktop reload` recorded
Desktop's state right after the reload (.pbik/desktop.json), there is one Desktop window and it is that one, its state
now is the same (times aside), and the report files changed only by `pbik build`. Any doubt, or any change by the
person: it leaves Desktop open, says why, and the agent asks the person to close it.

## Chat-only use (docs/design/phase1-usability.md)

While Desktop is still opening (the bridge answers HostNotReady, or, within two minutes of `desktop open`, has no pipe
yet), every bridge command waits up to `PBIK_DESKTOP_WAIT` seconds (300) with a plain "Still waiting for Power BI
Desktop to finish opening" line every 30 seconds, then says "still opening" (exit 5) instead of a raw "not ready"
error. `desktop open` waits until Desktop answers (`--no-wait` returns at once); `screenshot` makes the output folder.

### `--report json <command>`, `--in <project>`, `project init <name> [--parent] [--class] [--from-pack]`, `open`

`pbik --report json <any command>` prints `{ok, command, exit, facts, needs, next}`: errors and warnings as needs, and
person-only steps as `{"kind": "gate", "gate", "task"}`. The agent answers in docs/PLAIN-WORDS.md words and never
shows a path or a command. `project init` (v1.7) copies the kit's tracked files into `projects/<name>` inside the kit
(git-ignored by the kit; each project has its own git repository; the export check fails on any tracked project file),
sets the data class (default restricted), writes design/status.json and makes a first commit; with `--from-pack` it
starts from a model pack at the plan step. The agent keeps working in the same chat with `pbik --in <name> ...` (before
the command) and `open` opens the project folder in File Explorer.

### `project setup [--name N] [--class C]`, `project master --here`

One folder = one project (v1.7): the person copies or clones the master kit into a new folder and opens it; on first
run `project setup` turns that folder into the project, in place (pbikit/projectsetup.py): the master-only files in
tools/master-only.txt go (the master keeps them), the **Model** and **Reference** drop folders are made (git-ignored,
each with a README; pbikit/drops.py), the data class (restricted unless said otherwise) and design/status.json are
written, and the project gets its own git: a new repository for a plain copy; a clone keeps its history with its
`origin` renamed `kit`. A `projects` folder copied from the old setup is left alone. `status` tells the master kit
(`.pbik/master-here` holds its own path: written once by `project master --here`; a copy or clone lives elsewhere), a
fresh copy and a project apart; it never builds in the master kit. `project init <name>` still makes a project for
someone who'd rather the agent copied the kit: its own folder beside the kit, never inside it.

### `status [--done <stage>] [--mode] [--path] [--report-type] [--pack] [--class] [--plan-hash] [--score] [--json]`

design/status.json (committed, no data): the stages done and the next one (start, model, page purpose, plan, theme,
build, checks, polish, result, live, wrap-up), the build option and its switches, the path taken, the report type, the
pack, the data class, the approved plan's hash and the last polish score. `status` prints the plain line a new chat
starts with ("Sales: you're past the plan picture; next is the colours (quick build, data restricted)"), and in a
guided build adds "Pause here" after a stage it stops at. In the kit folder it lists every project, the last one used
first.

### `start detect | inputs | starters`, `layout from-report <X.Report> [--out]`

`start detect` reads the inputs folder (design/reference/inputs/) and picks the path: from report (a `.Report` folder),
from wireframe (HTML), from picture (an image: a wireframe or any report's screenshot), or starter layouts
(requirements only, or nothing); a `.pbix`, `.pbit` or data file is named and never read. `start inputs` opens the
folder. `start starters --kpi M ... --date F --category F` fills docs/layouts/starters/ (executive summary, trend
dashboard, detail table: existing layouts and patterns only, on the 12-column grid) into
design/specs/starters/<name>.layout.json. `layout from-report` reads an existing report's PBIR pages and visuals
(positions, types, fields; never data) through the wireframe mapping (design/scripts/ref_layout.py) into a draft
layout.json with the fields as bindings.

`start check` (at the start of every build): one plain line per drop folder, what it holds by name and what is
missing, then one next line. It lists names only (the Model folder is read by `model intake`, never here) and never
opens File Explorer; `start inputs` and `model intake --open` only make the folders. Projects made before the
one-folder setup keep design/reference/model and design/reference/inputs.

`layout polish` (v1.7 walkthrough fix 15, pbikit/polish.py) writes the kit's polish defaults into layout.json before
the plan picture, so they are part of what the person approves: each KPI's comparison becomes last year's value with
the change beside it as the detail, ▲ / ▼ (the planned measure's format) and green / red (a planned colour measure on
the detail colour: the form Rep 2 confirmed in Desktop), at body size, the number centred; a table's "vs" column gets
a colour measure on its font colour; a header band (a decorative shape, keepLayerOrder) goes behind the title and the
filter, and the filter loses its own box. The measures it needs go into generate.json `plannedMeasures`. It never
removes anything, says what it couldn't do and why, and a second run changes nothing. Line charts drawn straight,
larger titles, axis labels and legends, and bar labels in auto units come from the theme (gen_theme.py, kit tokens).
`plan compare` (two renderers): after the build, fidelity_check.py puts the Desktop screenshot beside the approved
preview (design/plan/approved.html, kept by `plan approve`) and lists positions, kinds and titles that differ; the
preview's example numbers are never compared. `score` has 15 checks, shown out of 10 (checks 11-15: design/checks.md).

### `plan show | picture | open | check | approve`

The plan as a picture: `plan show [--purpose P1=...] [--assume ...]` draws each page of layout.json (the high-fidelity
wireframe in headless Edge, no ID badges) into design/plan/page-<n>.png and writes design/plan/plan.md: each page's
purpose, each KPI with its measure and comparison, the assumptions, each fallback with the native option tried, and the
build option, data class and model. `plan picture <layout> --out <folder>` draws any layout (the starters). `plan open`
opens the pictures beside the chat (VS Code editor tabs through `code`, else the picture viewer). `plan approve` (the
person said OK in the chat) records the plan's hash in status.json and plan.json and writes the Page purpose section of
design/specs/spec.md; `plan check` exits 1 when the layout or plan changed after the OK.

Edge gets absolute paths (it resolves a relative screenshot path against its own folder, so with `--in` the picture
landed elsewhere). While a page draws, a "Still drawing the plan picture" line every 30 seconds (`pbikit/progress.py`,
also in `.pbik/progress.txt`). If the browser still fails, a simpler preview (the boxes, drawn without a browser) is
written instead, with the plain reason in the output: never an empty report (v1.7 walkthrough fixes 3 and 4).

The picture is the fast preview (one of two renderers): layout.json, tokens, the theme and the templates' look, drawn
with example values (design/scripts/example_values.py: made up from a seed per visual, the same measure the same in
every visual, months in calendar order, never data), every table column, each card's comparison as its title and an
example value (never a raw measure name). Its text contrast is checked on the picture itself (check_contrast.py), and
a faint text is listed before the OK. `--assume` replaces the list each time. `plan check` compares only what the
person approved (`plan.structure`: pages, and per visual its type, what it shows and its grid cell): the kit's own
fixes and polish after the OK keep it, and a change says what moved, appeared, went or shows different numbers.
`project check` exits 6 when the installed Desktop is newer than the one VERSIONS.md records as tested: the main flow
runs the after-update checks first (walkthrough fix 9).

### `mode [guided|quick] [--report-type]`, `score [<Report>] [--item n=pass] [--final] [--hand-minutes N]`

`mode` sets the build option, or without a value prints the default and why: guided until a quick build of that report
type reached 7/10 (the personal build history, %USERPROFILE%\.pbik\builds.jsonl, no names or data), then the last
choice, or a team pack folder's team.json `defaultMode`; it also suggests a guided build when the last 3 quick builds
of the type average below 7 or below the guided ones. `score` gives the polish score: ten items, 2, 4, 5, 6, 8, 9 and 10
from the files (grid, built types and fields against layout.json, no colours or fonts written into the layout, no
overlaps or crowded pages, accessibility warnings, validate errors), 1, 3 and 7 from the agent's own checks
(`--item 1=pass`: matches the approved picture, labelled as the agent's judgment; KPI cards filled; interactions
working), unchecked items counted 0. It writes design/reviews/polish.md; `--final` records the build in the history;
`--hand-minutes` (wrap-up) adds the person's hand-polish minutes.

### `gate prepare <gate> ...`, `gate open | wait | run <gate>`, `gate tasks`

Person-only steps: Approve the model, Approve the name map, Approve model changes, Connect to the live model, Back to
the synthetic model, Loosen the data class, Share the model pack. The agent runs `gate prepare` (a plain summary and a
hash of what is approved, in `.pbik/gates/`, git-ignored; option-table rows are never in it), then `gate open` (the
approval window in its own process; it returns at once) and `gate wait` (up to 30 minutes). The window shows the
summary (and, for the model, the rows kept), a 4-character code drawn as a picture (made in the window's process and
written nowhere), a box to type it, and Yes / No; three wrong codes decline. On Yes the step runs with the approver
from git's user name and the Windows login, and is logged in design/reviews/approvals.md. Refusals: the content
changed after `prepare`; screen control used in the last 10 minutes (the Claude Code hook tools/hooks/guard_gates.py
leaves a marker; it also blocks key and window drivers while a window is open); another window open. `gate run` shows
the same window in the foreground (the optional Command Palette tasks in .vscode/tasks.json, written by `gate tasks`).

v1.7 walkthrough: the window is a plain Yes / No, brought in front of every other window (SetForegroundWindow from its
own process). The 4-character code picture and box appear only when screen control is active (the hook's marker, or
`PBIK_GATE_CODE=1`); then Yes needs the code and three wrong tries decline. Screen control no longer refuses the window.

### `model intake [--root] [--folder] [--open]`

The model drop folder `design/reference/model/` (git-ignored, also in the root .gitignore): the user drops a copy of a
TMDL folder, a TMDL `createOrReplace` script, a `.SemanticModel` folder or a TMSL / JSON export. Intake deletes every
data file first, from names alone (any `.abf` such as cache.abf, `.pbi` and `data` folders, `.pbix`, `.pbit`,
`.parquet`, `.csv`, `.xlsx`, `.xls`, `.cache`), permanently, and warns; then detects the format (one model at a time;
a `.pbix` can't be read), writes the contract and logs what it read and deleted in design/reviews/model-intake.md. `--open` only makes the folder and opens it in File
Explorer for the user (it reads nothing).
A Claude Code hook (tools/hooks/guard_model_folder.py, .claude/settings.json, run by the project folder so it works
from any working folder, and failing closed) stops the agent opening the folder itself; Copilot follows the same rule in
its instructions. Intake also recognises a model approved before by its table and column names (no values) in the
pack folders: the project starts from that pack with no model approval, and never with a looser data class.

### Rule library, grouped approval, pack folders (`model packs`, `model rules`)

`synth contract` applies the project's own rules, then the kit's rule library (tools/pbik/rules/library.json: M code,
connections, RLS and entity tables synthesized or not reproduced; small option tables with a label and an order column
keep their rows, a person confirming them); `--no-library` skips it. The *Approve the model* summary groups the flags:
"87 handled by rules, 20 option table(s) to keep, 5 need you"; it can't be prepared while any need a person.
project.json `packFolders` (paths, or `{"path", "team": true}`) and the person's own settings (`model packs
--add-folder <folder> [--team]`, %USERPROFILE%\.pbik\settings.json, so no machine path is committed) are where packs
are found: `model packs` lists them,
`project init --from-pack <model name>` starts from one, and `model intake` in a project started from a pack writes only
the drift (design/specs/drift.json) for *Approve model changes*. Sharing to a team folder is the *Share the model pack*
task; a team folder's `team.json` `{"registrars": {"<class>": [names]}}` limits who may share per data class.
`model rules` writes design/reviews/rule-proposals.md: rules a person made for every table of a kind that the library
doesn't have, for review at the next kit update.

### `bind picker [--open] [--scan]`: Desktop as the model picker

`bind picker --open` makes `design/reference/live/` (git-ignored) and opens it; the user, in Desktop, connects a new
report to the published model (Get data > Power BI semantic models), saves it as a Power BI project there, and closes.
`--scan` says which model the newest pick connects to (also project.json `pickerFolders`, picks of the last day);
`gate prepare bind-live --report <R> --from picked` prepares *Connect to the live model* from it: no typed names or IDs.
Both byConnection forms are read (the current connection string with `semanticmodelid`, and the older
`pbiModelDatabaseName`). Verify at work: a real published model and Desktop 2.155's saved form.

### `step start|end <step> [--outcome]`, `step note <what> --interaction`

The agent marks each workflow step (.pbik/steps.jsonl, git-ignored) and each interaction (a reply from the person or
an approval window); `python tools/usage.py` joins them with Claude
Code's session transcripts (each message's token usage, counted once) and writes design/reviews/usage.md: minutes and
input, cache write, cache read and output tokens per step, with the Phase 1 targets (first setup 30-45 minutes, reuse
about 10) and the interaction count, checked against the person's messages in the transcript. Copilot usage is filled
in by hand from GitHub's usage page (verify at work).

## Synthetic to live (docs/design/synth-to-live.md)

### `project class [public|internal|restricted] [--guard dax|screenshot]`

project.json `dataClass` (default internal). Lowering it is person-only (typed confirmation; refused in an agent's
shell). Restricted: while the report is bound live, or with no synthetic model, `desktop screenshot` and
run-dax.ps1 refuse; `--guard` prints why and exits 2.

### `synth contract <TMDL folder | createOrReplace script> [--root .] [--out]`, `synth resolve`, `synth approve --by`

The contract (design/specs/contract.json): tables, typed columns, sort-by, measures with DAX, relationships, and
flags: `enter-data`, `m-code`, `connection` (also model parameters), `rls`, `entity` (account, member and similar
tables). It never copies M code, connection strings, RLS filters or row values. Reads a TMDL folder, a TMDL
`createOrReplace` script or a TMSL (JSON) script. `synth resolve F3 synthesize --why ...` (or `resolve <kind>
<resolution> --every`) records a rule (`rules`: kind, table or `*`, resolution, why); a new contract from the same
model is pre-filled from the rules. `synth approve --by <name>` is person-only: it prints every flag and its
resolution, asks for the model name typed, and records by, date and a hash; any later change voids it.
`keep rows: option labels` (Enter-data flags only; a warning above 200 rows, refused above 1000; never a table marked `entity` or flagged as
entity data) keeps an option or toggle table's exact rows and order: approve prints every kept table's rows and asks
for `KEEP <n>` (n = rows kept), then stores them in the contract (covered by the approval hash); `synth generate`
writes them as they are.

### `synth slice <layout.json>`, `synth generate <Name>`, `synth verify <Name>.SemanticModel`

`slice` (approved contract only) writes generate.json `slice`: every field layout.json names, the measures they need
(DAX references, followed), relationship keys between kept tables and sort-by columns; `plannedMeasures`
(`{name: {table, expression, formatString}}`) are measures the pages need that the live model doesn't have yet.
Names used that are in neither are listed (exit 1). `generate` writes `<Name>.SemanticModel`: every table a
calculated table with an inline DATATABLE, values from `seed` (same seed, same files), dimension keys unique, fact keys
drawn from them, a date key covering `dateRange`, hints per table: `rows`, `fact`, and the shape of date columns so
charts and year-over-year measures look real: `trend` (growth per year, 0.1 = +10% rows a year), `seasonality` (12
monthly weights, Jan..Dec), `monthEnd` (true, or a list of date columns: month-end dates; on a date key it keeps only
month ends), e.g. `"hints": {"Orders": {"rows": 3000, "trend": 0.1, "seasonality": [1,1,1,1,1,1,1,1,1,1,1,3]}}`;
`model.tmdl` carries
`annotation PBIK_Synthetic`, planned measures `PBIK_Planned`. `verify` compares it with the contract slice (types,
DAX, relationships); a type change listed in generate.json `deviations` is a note. UNVERIFIED in Desktop until the
smoke report opens on one.

`synth generate` sorts month names by the month number (walkthrough fix 8): a text Month column without a sort-by
column gets the table's Month No / MonthNumber column (added to the slice if needed), and says so; with no such column
it says exactly why months will sort A to Z. Number measures without a format get one with thousands separators
(`#,0`, averages `#,0.00`), and a whole-number or decimal format without separators gets them (`0` -> `#,0`).

### `bind check | prepare | live | local <Report>`

- `check`: every field reference (visual queries, sorts, conditional formatting, filters at every level, slicer state,
  bookmarks, drillthrough and tooltip bindings, report-level measures and their DAX) exists in the synthetic model
  and, through design/specs/bind-map.json when there is one, in the contract; column types match. A name in neither
  the synthetic model nor the map is listed as a `stale reference` with its file and JSON path (a leftover to remove
  in Desktop or layout.json), apart from map errors. Exit 1 on either. Not alarms: columns DAX defines itself in
  report-level measures (names given as strings in ADDCOLUMNS, SELECTCOLUMNS, SUMMARIZE, ROW, DATATABLE; `[Value]`,
  `[Value1..n]` of GENERATESERIES and table constructors; `@` names; columns of VAR tables), report-level measures
  used as visual filters (`Schema: extension` on the filter's From entry), and a type difference generate.json
  `deviations` records (a note). Filter values are typed against the live column types (contract, through the
  map) in every saved filter: text on a number column or a number on a text column is an error; `pbik validate`
  does the same against the report's own model (In, Comparison and Between conditions, any level).
- `prepare [--port auto]`: planned measures the report uses become report-level measures (reportExtensions.json),
  planned dependencies inlined as `CALCULATE ( ... )`, references marked `Schema: extension`; the synthetic model is
  regenerated without them. With `--port` the values before and after are compared first (nothing written when they
  differ); without it pbik says the values weren't checked.
- `live --by <name> (--workspace W --model M --id <ID or link> | --from <Desktop-saved Report>)`: person-only (types
  the model name). Refuses while Desktop is open, with an unapproved contract or a failing check. Backs up the report
  (`.pbik/bind/backup`, git-ignored), rewrites references per the map, writes definition.pbir `byConnection`
  (`Data Source="powerbi://api.powerbi.com/v1.0/myorg/<W>";initial catalog=<M>;...;semanticmodelid=<ID>`, UNVERIFIED in
  Desktop: `--from` copies Desktop's own string), and records `.pbik/bind/state.json` (the restricted lock). `--id`
  takes the bare ID or a link with `/datasets/<id>/`, `/semanticmodels/<id>/` or `/modeling/<id>/` (a report or
  workspace ID isn't taken). A workspace name with stray or double spaces, mixed `_`/`-`/space separators, or one
  that differs from a workspace bound before (project.json `workspaces`) only in case or separators warns and
  recommends the Desktop route (`--from` a report Desktop saved connected to the model).
- `local [--restore-backup]`: refuses while Desktop is open. A file unchanged since `bind live` (hash in state.json)
  comes back from the backup byte for byte; a file changed or added while live is mapped back (names, and the labels
  live added) and listed; definition.pbir comes from the backup. `--restore-backup` puts the whole backup back
  (files made while live removed) after a typed `restore`.
- `map draft` writes design/specs/bind-map.json (optional; no map = names must match): every synthetic name the report
  uses that the contract lacks, matched to the most similar contract name (case, spaces, `_`/`-` ignored, shared
  words count; names the synthetic model already has aren't candidates), `unmatched` for the rest. Shape:
  `{"tables": {"Orders": "Order Lines"}, "fields": {"Orders[Amount]": "Net Amount", "_Measures[Total Units]":
  "Units Sold"}, "acceptDax": ["Per Unit"], "liveLabels": false}`; a field value may name another table
  (`"Table[Name]"`). A report-level measure whose DAX the map changes fails the check until listed in `acceptDax`.
  Headers keep the synthetic labels (`displayName` added where a field is renamed) unless `liveLabels` is true.
- `map approve --by`: person-only; reruns the check through the map, prints it, asks for the contract's model name
  typed. `bind live` refuses a map that isn't approved or changed since.

### `model register <project> --to <packs>`, `project new [folder] --from-pack <pack>`, `model drift`, `model approve`

Model packs reuse an approved contract (resolutions and the rules behind them), generate.json (settings and
deviations), the synthetic model and any bind map across projects: `<packs>/<model>/pack.json` (versions with date
and approver, the project's data class) and `v<N>/`. `register` refuses a folder inside the kit, the project or any
git repository (`--allow-repo` allows one that isn't the kit's or the project's) and writes a `.gitignore` of `*`:
packs are never committed. `project new` copies the current version
into a folder (refuses one that has a contract), sets project.json `dataClass` and `pack`, and the project starts at
/plan. `drift <pack> <new TMDL>` writes `drift.json` and lists only what changed (tables, columns and types, measures,
relationships, new flags pre-filled from the saved rules). `approve <pack> --by` (person-only, types the model name)
approves the list, writes `v<N+1>` and regenerates only the affected tables (changed ones and the tables that draw
keys from them); the other table files are copied byte for byte.

### KPI cards (`pbik validate`, lesson C-10)

A KPI card (a cardVisual whose folder or layout name says `kpi`, layout `kpi: true`, or a `kpi` template) is its
own container: validate warns when its container background is off or a shape sits behind it (unless the shape
matches the card within 1px), and per row of KPI cards when width, height or gaps differ by more than 1px, the row
doesn't span the content width (page width minus the layout grid margin) or doesn't line up with the row below.
`design/scripts/card_space.py <Report> --page <name> --png <screenshot>` (the polish loop, /review) flags a card
whose largest empty band is over 35% of its height or width; it runs on synthetic or sample data only (pbik's
synthetic model, or a public project). `template: "cardVisual.kpi-delta-card"` follows the rule (written by hand,
not Desktop-saved yet).

### Names are case-insensitive

As in DAX, table, column and measure names match whatever their case: the TMDL reader's tables, columns and
measures are case-insensitive dicts that keep the TMDL spelling (`names.CIDict`), so validate, build, model check,
the synth and bind commands and the bind map all compare names that way.

## Python helpers

`pbikit/objects.py` holds the pure-Python builders carried over from the kit's v0.2 helpers (literals,
fields, `put`, `chrome_off`, `shape_objects`, `ref_labels`, `label_above_bars`, `navigator_states`, ...). pbik build
uses them behind its layout keys. Since 0.6 a rep has no `design/scripts/build.py`: Rep 8's last patches (navigator
states, the page that opens first, the theme) are layout keys, and a rebuild of Rep 8 from layout.json alone is
byte-identical to its build.py output (2026-10-19). `design/scripts/pbik_helpers.py` stays for `smoke.py`; the
earlier reps' build scripts are in `archive/examples/` (home copy of the kit, not shipped).

## Tests

```bat
python tools\pbik\tests\test_pbik.py
```

They copy a saved PBIP (`PBIK_TEST_SOURCE`, default the Rep 4 fixture `tools\fixtures\rep4`, tools/fixtures/README.md)
into a temp folder, never editing the source; a missing source fails the run, never skips it. Then they build the two-page `tests/sample/layout.json` (SVG extension
measure, Top N filter, conditional formatting, navigation buttons), check that a second build changes nothing, run
validate and model check, and break copies on purpose to check each rule fires.


`python tools/run_tests.py` runs every suite in the master kit; in a report project (a kit copy with a `*.pbip` or
design/specs/layout.json) it runs only the suites related to the files changed since the last commit (fast mode,
`RELATED` in run_tests.py). `--all` and `--regression` run everything; `--changed` forces fast mode.
## Not yet

See "pbik can't write it yet" in the kit's `design/known-gaps.md` for the full list with workarounds. In short:
filter states in data bookmarks, drill-through and tooltip pages, mobile
layout, shape maps with an uploaded map file, a page background or wallpaper image, new card small multiples (`pbik_helpers.small_multiples_grid`), and custom, Python, R or Deneb visuals.

Checked in Desktop: the smoke page (card, button slicer, table, 2026-10-18), Rep 5 parity (filter pane, Clear, sync
slicers, field parameters, bookmarks) and the 0.5 check page (theme colours, `general` and `spacing`, visual groups,
formatting from a column aggregation, 2026-10-18).

## Regression suite

```bat
python tools\regression\regress.py            rem every golden case; exit 1 if any output changed
python tools\regression\regress.py --update   rem accept the new output after reviewing the listed differences
```

Golden builds of the Rep 4 parity, Rep 5 parity (Overview, Workforce Mix) and Rep 8 layouts, rebuilt from layout.json
alone in scratch copies of self-contained inputs (`tools/regression/cases/`). Each run checks a second build is
"No changes" and lists every changed file and JSON path. **Run it after every pbik change and after every Power BI
Desktop update.**
