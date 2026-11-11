# pbik 0.13.0

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
Desktop) are never touched.

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
Fields use the layout notation: `[Measure]`, `Table[Column]`, `'Table name'[Column]`, `Sum(Table[Column])`, checked
against the model's TMDL and `reportExtensions.json`.

| Where | Key | Writes |
| --- | --- | --- |
| top | `theme: "design/themes/pbip-polish.json"` | registers and applies the theme first (as `pbik theme apply`; path from the project root) |
| top | `annotate: true` | every page gets the annotation `pbik.page` (its layout key) and every visual `pbik.id` (its ID) and `pbik.layout` (12 hex of its layout.json entry); Desktop ignores annotations and keeps them ([L1] PBIR annotations). **UNVERIFIED in Desktop** (roadmap gap 13) |
| top, page, visual | `annotations: {name: text}` (top: under `report`) | `annotations: [{name, value}]` on report.json, page.json or visual.json, in place: names layout.json sets are owned (removed when they leave it), others stay. `pbik validate` errors on a name used twice in a file and warns when a visual's `pbik.id` isn't its folder's ID (a copy). **UNVERIFIED in Desktop** |
| top | `report: {filterPane: {expanded, visible}, settings: {<setting>: value}}` | report.json, in place (filterConfig, themes, resources and Desktop's other settings stay): `objects.outspacePane` `expanded` (false = the pane opens collapsed) and `visible` (false = hidden in view mode), as Desktop saved `expanded` in Reps 1-7; `settings` (written in the schema's property order, as Desktop
saves them) = Microsoft's #ExplorationSettings (`exportDataMode`, `hideVisualContainerHeader`, `useEnhancedTooltips`, `pagesPosition`, `locale`, ...), each checked against the cached report schema (names and values). Each key remembers the value Desktop had and gets it back when it leaves layout.json (visual-map.json `reportOwned`). Desktop's reload doesn't apply report.json during the preview (Learn, external editing): close without saving and reopen. Pane state and settings other than `expanded` not yet Desktop-tested (roadmap batch 1) |
| page | `displayName`, `width`, `height`, `displayOption`, `hidden` | page.json; new pages get a stable 20-hex name |
| page | `active: true` (one page) | `pages.json` `activePageName`: the page the report opens on (default: the first page) |
| page | `background` (colour, or `{color, transparency}`) | `objects.background` |
| page | `landing: true` (one page) | `pages.json` `landingPageName` (pagesMetadata 1.1.0): the page every user opens on, over `active`; pbik removes it when the key goes. **UNVERIFIED in Desktop** (roadmap gap 12) |
| page | `props: {"object.property[@selector]": value}` | any page object (`pageSize`, `displayArea`, `pageInformation`, `outspace`, `pageRefresh`, `personalizeVisual`, `background`), values as in visual `props`, each checked against the cached page schema (#PageFormattingObjects is closed per object). The filter pane objects take `filterPane` / `filterCards`. **UNVERIFIED in Desktop** (roadmap gap 12) |
| page | `filterPane: {backgroundColor, transparency, foregroundColor, titleSize, searchTextSize, headerSize, fontFamily, border, borderColor, checkboxAndApplyColor, inputBoxColor, width}` | the filter pane's look on this page: `objects.outspacePane`, no selector (page schema #OutspacePane); colours and sizes take tokens, `fontFamily` takes `regular` / `semibold` / a family. Not yet Desktop-tested |
| page | `filterCards: {applied: {...}, available: {...}}` (backgroundColor, transparency, border, borderColor, foregroundColor, textSize, fontFamily, inputBoxColor) | `objects.filterCard` on selector `{id: Applied}` / `{id: Available}` (the `$id`s Desktop's base themes use for filter cards). Not yet Desktop-tested |
| page | `filters` | page-level filters (as for visuals, below) |
| page | `interactions: [{source, targets: [IDs] or "*", type}]` | `visualInteractions` (`NoFilter`, `DataFilter`, `HighlightFilter`) |
| page | `bookmarks: [{name, displayName, show: [IDs], hide: [IDs], targets: [IDs], data, display, changesPage}]` | `definition/bookmarks/<id>.bookmark.json` + `bookmarks.json`, as Desktop saved them in Rep 5. Applies only to the listed visuals; `data: false` (default) is display only (filters and slicer selections unchanged); `data: true, display: false` resets the targets' selections; `changesPage: false` (default) doesn't switch page. Ids are stable (page key + name); pbik's bookmarks are owned like its visuals (`--prune` removes dropped ones); Desktop's are never touched |
| page | bookmark `select: {ID: {field, values}}`, `sort: {ID: {field, direction}}` (or a list) | a data bookmark that saves a slicer selection (the visual's `singleVisual.objects.merge.general` `filter`, the same filter as `selection`) and a sort (`singleVisual.orderBy`, Direction 1 ascending / 2 descending); those visuals join the targets and `data` defaults to true (`data: false` with them is an error). Page and report filter states aren't written. **UNVERIFIED in Desktop** (roadmap gap 5) |
| page | `bookmarkGroups: [{name, displayName, bookmarks: [names]}]` | a group item in `bookmarks.json` (a grouped bookmark isn't also listed on its own) |
| visual | `id`, `name`, `page`, `type`, `x`, `y`, `w`, `h`, `z` | folder and name `<ID>_<name>`; z = layer × 1000 + visual number; tab order = visual number × 100 (number IDs in reading order) |
| visual | `tabOrder: <whole number>` | `position.tabOrder` when reading order can't follow the IDs (Rep 9: a header slicer before an earlier-numbered subtitle); keep the × 100 scale, e.g. 350 between V03 and V04 |
| visual | `template` | start from `design/templates/<template>.json` (default: `<type>.json` if it exists) |
| visual | `bindings: {Role: [field or {field, displayName, active} or {fieldParameter, project, selected, displayName}]}` | `query.queryState`; `nativeQueryRef` stays the field's own name, as Desktop saves it. Shapes, text boxes, buttons and navigators without bindings get Desktop's empty `query: {queryState: {}}` (a template without a query, or `emptyQuery: false`, writes none). A `fieldParameter` item projects the parameter's fields from its calculated table in the TMDL, in parameter order, plus `fieldParameters`: `project: "all"` (default, every field, the Rep 3 form) or `"selected"` (one field, `selected` = its label, as Desktop saved it in Rep 5) |
| visual | `sort: {field, direction, default}` (or a list) | `query.sortDefinition`; `default: true` writes `isDefaultSort` (Desktop keeps true, drops false) |
| visual | `filters: [{field, values, invert, hidden, locked}]` | categorical filter, values typed by the column (2024L, 1.5D, 'text') |
| visual | `filters: [{type: "TopN", field, by, n, direction: "Top" or "Bottom"}]` | Top N filter |
| visual | `filters: [{field: "[Measure]", op: "=" / ">" / ">=" / "<" / "<=", value: <number>}]` | a measure filter ("show items when the value is ..."): an `Advanced` filter with one Comparison, the value as a decimal (0D). Visuals only: a measure filter in a page's `filters` stops the build with an error (Power BI filters on measures per visual). Not Desktop-tested yet (kit v1.2) |
| visual, page, top `report` | `filters: [{field, type: "Range", min, max}]` | a Range filter, one Between condition, values typed by the column. **UNVERIFIED in Desktop** (roadmap gap 4) |
| visual, page, top `report` | `filters: [{field, type: "Advanced", conditions: [{op, value}], join: and / or}]` | the pane's Advanced mode on a column, one or two conditions: `contains`, `doesNotContain`, `startsWith`, `doesNotStartWith`, `is`, `isNot`, `isBlank`, `isNotBlank`. **UNVERIFIED** |
| visual, page, top `report` | `filters: [{field, type: "RelativeDate", last, unit: days / weeks / months / years}]` | in the last N units, today included (Between DateSpan(DateAdd(DateAdd(Now, 1 day), -N unit)) and DateSpan(Now)), from the schema's date expressions. **UNVERIFIED** |
| top | `report: {filters: [...]}` | report-level filters in report.json `filterConfig` (any type above except a measure filter); pbik's own (`pbik_`) only, Desktop's stay. **UNVERIFIED** |
| any filter | `displayName`, `ordinal`; and `filterOrder: ascending / descending / custom` on the visual, page or `report` | the filter card's name, its place when the order is custom (`ordinal`), and `filterConfig.filterSortOrder`. **UNVERIFIED** |
| visual | `type: "htmlContent<GUID>"` (the HTML Content visual, any version) | `objects.compatibility.legacyRendering` true, and the visual in report.json `publicCustomVisuals` (pbikit/htmlcontent.py, from the visual's capabilities.json; not Desktop-tested yet). Under 43px tall: a build and validate warning. A custom visual: ladder step 4, uncertified until checked (docs/it-security.md) |
| visual | `selection: {field, values}` | slicer default selection (`objects.general.filter`) |
| visual | `referenceLines: [{axis: value, value2 or category; value: number or [Measure]; label, color, style, width, dataLabel}]` | `y1` / `y2` / `xAxisReferenceLine`; on a horizontal bar chart the value axis is still y1 (`x` there is an error) |
| visual | `columnWidths: {field: px}` (tables, matrices) | `columnWidth` on each column's metadata selector |
| visual | `columnWidths: "fit"`, or `"fit"` as a value next to fixed px (tables, matrices) | widths computed from the box (`pbikit/tablefit.py`): inner width = box less container padding less `tokens.table.scrollbarReserve` (16px); each column at least its header width at the header font, or 120 text / 64 number / 90 date / 100 image; columns of one kind share one width; the rest shared text 2 : others 1; whole pixels that add up exactly. A matrix sizes one stepped Rows column; fields on Columns, field parameters or a box too narrow are build errors |
| visual | `slicerMode: list / dropdown / between / before / after` (classic slicer) | `data.mode` (overrides the theme's Dropdown) |
| visual | `sync: {group, fieldChanges, filterChanges}` (or just the group name; slicers) | `visual.syncGroup`: slicers with the same group on any page share their selection |
| visual | `emptyQuery: true / false` | force or drop the empty `query` on a visual without fields |
| visual | `action: {type: PageNavigation, page: <page key or display name>}` | `visualLink`, target written as the page **name** (id) |
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
| visual | `hidden` | `isHidden` |
| visual | `decorative: true` (shapes, images that only decorate) | recorded in visual-map.json; `pbik validate` then skips its alt text and its tab stop, and lists it in a note to hide from the tab order in Desktop (View > Selection, Tab order): the PBIR form of "hidden from tab order" isn't in Microsoft's schema, so pbik doesn't write it yet (roadmap gap 21). A shape with no alt text and no `decorative` is a warning; `decorative` with `container.altText` is a build error |
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

```bat
pbik resource add "Sales.Report" design\images\court.png
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

### `desktop state | reload | screenshot`
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
