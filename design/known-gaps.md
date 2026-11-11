# Known gaps

Things Desktop (or PBIR) can't do the way the design needs, and what pbik can't write yet, with the workaround and any
Desktop click steps.
Sources: the fallback registers of Rep 2 and Rep 3 (`archive/examples/` in the home copy of the kit, not shipped), and what each rep ran
into. Check here before planning a build. Each project builds with `pbik build` from layout.json alone (tools/pbik/README.md; no per-rep build.py since pbik 0.6); helpers named `pbik_helpers.<name>` are the Rep 6 and Rep 7 builders in `design/scripts/pbik_helpers.py`; helpers named `build.py <name>` with a Rep 2-5 tag are in that rep's script in `archive/examples/`. Items marked *pending* were fixed on disk but not yet seen in Desktop. The pre-pbik gaps (up to v0.2) are history in `examples/known-gaps-pbir.md`.

## pbik can't write it yet (no build code since pbik 0.6: a `props` `{"raw": ...}` entry copied from a Desktop-saved file, or Desktop; otherwise /build stops and reports the gap)

| Gap | Workaround |
|---|---|
| **Theme colour indices** (`theme:<ColorId>`) are Desktop's, not the dataColors index: 0 is the theme background, 1 the foreground, 2 onwards dataColors[0] onwards (0.5 Desktop check, 2026-10-18). A new card's container background sits behind its tile fill, so colour the tile with `fillCustom.fillColor`. | Count from 2 for data colours. |
| **Data bookmarks that save a selection** (slicer states per visual, `explorationState.filters`; bookmark `select` and `sort` since the batch 2 run, 2026-11-10, UNVERIFIED in Desktop; filter states still not): Rep 7 has 3 ("2 Point vs. 3 Point", "All Shots", "by Zones"), each saving 2 slicer states and hiding 6 visuals. (Display bookmarks, groups in bookmarks, and data bookmarks that reset selections: layout.json `bookmarks` since 0.4 and 0.5.) | Save the bookmark in Desktop and keep it; buttons can point at its id. |
| **Mobile layout, drill-through and tooltip pages** (none in Reps 1-7). (Sync slicers: `sync` since 0.3; field parameters: a `fieldParameter` binding; visual groups: `type: "group"` since 0.5.) | Patch visual.json / page.json from a Desktop-saved example. |
| **Per-member formatting** (`data` selectors with `scopeId`, one entry per category member; layout `members` since the batch 2 run, 2026-11-10: `dataPoint.fill` as Desktop saved it, other objects unverified): Rep 7 31 (scatter points, bubbles, markers, small-multiple headers), Rep 5 5 (donut slices). | A JSON selector in `props` (`"dataPoint.fill@{...scopeId...}"`), one member at a time; or a colour measure with `cf` type `measure`. |
| **Registered images as a layout key** (`ResourcePackageItem`): Rep 6 5 image visuals, Rep 7 6 image visuals and 1 card. Since the batch 2 run (2026-11-10) image visuals take layout `image`; a page background or wallpaper image still can't be written (form unknown). Registering a new resource from outside Desktop isn't documented by Microsoft (Learn, RegisteredResources): it works in 2.159.883.0, rechecked at every /smoke and /update (roadmap gap 25). | `pbik resource add`, then `props` `"general.imageUrl": {"raw": ...}` with the `ResourcePackageItem` JSON (the `image.json` template, from the Patterns page). |
| **Shape maps with an uploaded map file** (`shape.map.geoJson`, shared resource): Rep 2 3. | Insert the map in Desktop and keep the saved JSON; `pbik resource add` registers images only. |
| **report.json settings** (`objects.outspacePane.expanded: false`, the collapsed filter pane): all 7 reps. Since pbik 0.13 a layout key (`report.filterPane`, `report.settings`, page `filterPane` / `filterCards`), not yet Desktop-tested (pbik-smoke-013). Desktop's reload doesn't apply report.json during the preview: close and reopen after a change. | Until the Desktop check: set once in Desktop as before; layout keys it doesn't list stay as Desktop wrote them. |
| **Advanced filters** (comparison, contains, relative date) and report-level filters. Since the batch 2 run (2026-11-10) layout `filters` take Range, Advanced text conditions and RelativeDate, and `report.filters` writes report-level filters, all UNVERIFIED in Desktop until the checklist's save. | Categorical and Top N only; patch others from a Desktop-saved filter. |
| **New card small multiples.** (Reference labels: layout.json `referenceLabels` since pbik 0.2; any other compound selector: a JSON selector in `props`.) | `props` with `{"raw": ...}` copied from a Desktop-saved card (`pbikit.objects.small_multiples_grid` shows the shape). |
| **Custom visuals** (AppSource GUIDs, .pbiviz packages) and Python/R/Deneb visuals. | Not built by pbik; insert in Desktop and keep the saved JSON. |
| **Aggregation queryRefs other than Sum and Min** (`Avg(...)`, `Max(...)`, `CountNonNull(...)`) follow the pattern but haven't been seen in a Desktop-saved file. | Check one in Desktop before relying on a metadata selector built from it. |
| **Rules-based conditional formatting** (`Conditional` cases) follows the semanticQuery schema but has no Desktop-saved example in the kit yet. | Check it in Desktop on the first use; fall back to a hex-returning measure (`cf` type `measure`). |
| **`columnWidths: "fit"` can't size** a matrix with fields on Columns (one set of value columns per member, unknown on disk), field-parameter columns, or value widths it can't estimate (it sizes from header labels and column kinds, not the data). | Set those widths by hand in `columnWidths`; check fitted tables once in Desktop. |
| **Accessibility checks see literal colours only**: text coloured by a measure or a theme index, and text over an image or a semi-transparent stack, isn't contrast-checked; the tab-order rule is reading order by box position, which can disagree with a deliberate order (a header button before the subtitle, Rep 8). | Check those in Desktop; note an accepted tab order in the spec by visual ID. Rep 8's open findings: 24 data visuals without alt text, white on teal (4.0:1) in selected button slicers (colors.selected #037C84 passes at 4.98:1), header tab order. |
| **Wireframe privacy covers one visual at a time**: groups under `minGroup` are hidden (plus one more when exactly one would be), but differencing across two visuals with different filters, or a combination of categories that each pass on their own, isn't checked (docs/it-security.md). | Keep groupings coarse; add any column that narrows to a person to `privacy.identifiers`. |
| **Template reference lines** (Rep 9): the clusteredBarChart template's "Company" line, bound to a Rep 8 measure, drew at 0 as "Company: 0" when its value was dropped. Fixed in pbik 0.6.1: a template line bound to a field is dropped whole. | Give the visual its own `referenceLines` in layout.json. |
| **Tab order is the visual number** (Rep 9: the header's year slicer P1-V06 couldn't come before the subtitle P1-V04). pbik 0.6.1 adds a per-visual `tabOrder` key; the default stays visual number x 100. | Number IDs in reading order (CLAUDE.md Visual IDs); set `tabOrder` where a visual added later breaks it. |
| **Card label clipped at the left edge** (Rep 9 review item 1: "nteractions"): Desktop draws a left-aligned label from the card's edge. The kit's KPI card templates carry `padding.leftMargin` 4 (Custom) since pbik 0.6.1; a re-harvest must keep it (test 32g). Confirmed in Desktop on 2026-10-23 (pbik-smoke-061, page _padcheck, 3x close-ups of "Interactions" with container padding 0, as in Rep 9): with card padding 4 the "I" has a clear gap; with padding 0 it sits on the card's edge; moving the card 4px right and 4px narrower changes nothing (the content moves with the card). With the template's container padding (20px) nothing clips either way. | Keep `padding.leftMargin` 4 on any left-aligned card, most of all with container padding 0. |
| **Template content**: a harvested template still holds Desktop's content (titles, text, reference labels, series colours bound to Rep 8 measures). pbik build takes formatting only from it since the 2026-10-19 smoke; the layout must set every title, text and field-bound setting itself. | Set them in layout.json (`container.title`, `text`, `referenceLabels`, `props dataPoint.fill@[M]`, `cf`). |
| **Slicer padding as int**: `pbik_helpers.button_slicer_padding` writes `leftMargin` / `rightMargin` / `rectangleRoundedCurve` as `16L`; every Desktop-saved file has them as numbers (`16D`), so the settings catalog warns. No visible effect at the 2026-10-19 smoke. | Leave it until a roundtrip shows Desktop rewriting it; then switch the helper to `n()`. |
| **Schemas Microsoft doesn't publish** (visualContainer 2.14.0 returned 404, 2026-10-17): `pbik validate` skips those files with a warning. | Kit rules still run on them. |

### Bookmark support in pbik (built in 0.4, from this plan)

Done in 0.4: 1 (the `bookmarks` / `bookmarkGroups` keys), 2 (buttons by bookmark name), 4 (validate rules) and
5 (ownership and prune). Still open: 3 (data bookmarks that save a selection) and 6 (the Desktop check). The plan as
written:

From the six Desktop-saved bookmarks in Rep 5 (`definition/bookmarks/*.bookmark.json` plus `bookmarks.json`):
1. **A layout key per page**, e.g. `bookmarks: [{id, displayName, show: [IDs], hide: [IDs], target: [IDs], data: false}]`.
   pbik writes `<name>.bookmark.json` with `explorationState.activeSection` = the page name and
   `sections.<page>.visualContainers.<visual name>.singleVisual.display.mode` "hidden" for each hidden visual, and
   `options` (`targetVisualNames`, `applyOnlyToTargetVisuals`, `suppressData` for display-only bookmarks), as
   pbik writes from the layout `bookmarks` key (0.4). A stable bookmark name (hash of page key and bookmark id) so a rebuild
   doesn't duplicate it, and `bookmarks.json` items (and groups) kept in layout order next to bookmarks made in Desktop.
2. **Buttons by bookmark id**: `action: {type: "Bookmark", bookmark: "<layout id>"}` resolves to the written name,
   like page navigation resolves page keys.
3. **Data bookmarks** (filters and slicer state): `explorationState.filters` and per-visual `filters`/`objects`
   copied from a Desktop-saved bookmark; capture-by-hand first, then a layout key if it repeats.
4. **validate**: every Bookmark action targets an existing bookmark; every bookmark's visual names exist on its
   page; no bookmark points at a page that isn't in pages.json.
5. **Ownership and prune**: bookmarks pbik wrote are listed in the ID map, removed with `--prune` when they leave the
   layout; bookmarks made in Desktop are never touched.
6. **A Desktop check** that the pane open/close pair (Rep 5) works on a rebuilt page, before relying on it.

## Design flexibility: limits (v0.8, v1-design)

| Limit | Why | Until then |
|---|---|---|
| **A new palette on visuals already built.** pbik build recolours template colours (design/templates/palette.json) only when it creates a visual from its template; layout props and the theme follow the tokens on every build. | A template's literal colours aren't owned by the layout, so a rebuild can't tell them from Desktop edits. | `pbik build --reset` (ask first: Desktop edits inside ID'd visuals are lost), or set the colour in layout props. |
| **Dark themes not yet opened in Desktop.** The Rep 8 dark build passes `pbik validate` and the wireframe check; Desktop's own chrome (the dropdown slicer's popup list, tooltips, the visual header icons, the filter pane) takes its colours from the theme in ways the wireframe doesn't draw. | Proved on disk and in the wireframe only (2026-10-29). | Open a dark build in Desktop before the first dark rep; record what needs theme keys here. |
| **Image references give colours and boxes, not structure.** ref_palette.py reads an image's colours (no fonts, corners or shadows); the boxes come from the agent looking at the image and writing boxes.json. | No image library or OCR in the kit (standard library and headless Edge only). | Check the draft layout against the image; prefer an HTML reference when there is one. |
| **Chart marks are checked as token pairs.** gen_tokens.py holds brand, bad and secondary marks at 3:1 on the card; the light comparison series (brandLight, secondLight) are below 3:1 by design and need a label or legend. check_contrast.py measures text only. | WCAG 1.4.11 applies to marks needed to read the chart. | Label comparison series directly or in a legend. |

## Wireframe and fidelity check: later (v0.6, from Rep 10)

| Later | Why | Until then |
|---|---|---|
| **Pixel-level comparison in the fidelity check.** fidelity_check.py compares position, type and main text per visual; drawing differences inside a visual (clipped text, a missing label, tick steps, cell colours) show only in the screenshot pairs. A per-visual image difference over each visual's box (both PNGs scaled to the page size), flagging boxes above a threshold, would list them. | Rep 10 (2026-10-29): the first live run listed only the brand text box, while the screenshot pairs still showed wireframe drawing errors (chips cut off, the matrix's last column clipped, table colours, axis ticks, label positions), fixed before v0.6. | Look at every screenshot pair in fidelity.html at /review, as .claude/commands/review.md says. |
| **A per-project privacy setting for public, non-personal data.** wireframe_data.py always hides groups under `privacy.minGroup` (and one more, so a hidden one can't be derived), which suits personal data but hides real values in public data. A layout.json setting (for example `privacy.public: true`, allowed only where docs/it-security.md clears the source as public and non-personal) would show every group. | Rep 10 (Olympic results, public): the medal matrix P2-V04 shows "–" for 51 cells under 5 athletes where Desktop shows 0 or 3, and the matrix's row order needed separate row totals. | Read those cells in Desktop; keep minGroup 5. Changing the privacy rule is a docs/it-security.md decision first. |

## Desktop and PBIR gaps (work around them in layout.json or Desktop)

| Gap | Workaround | Desktop click steps |
|---|---|---|
| **"Desktop-saved" is detected by the missing final newline**: `pbik catalog refresh` (the settings catalog) and `pbik roundtrip` (its newline line) treat a file without a final newline as saved by Desktop, because Desktop writes none and pbik always writes one (seen on every file of the Patterns page save, 2026-10-19). It is a heuristic, not a marker Microsoft documents: a Desktop update that adds a final newline, an editor or git setting that adds or strips one, or a file pbik never touched but another tool wrote without one would be misclassified. Files written with CRLF are fine (only the last byte counts). | After every Desktop update, run `/smoke` and check that the smoke report's files still have no final newline (`pbik catalog refresh <smoke copy>` must list them; 0 settings means the rule broke). Keep `.gitattributes` / editors from changing final newlines in report folders. `--all` scans every file if the rule ever fails; then rebuild the catalog only from folders known to be Desktop-saved. | None. |
| **New card small multiples with no category draw nothing**: in the empty case (a member with rows but none in the small-multiple category) there is no small multiple, so `showBlankAs` never applies (Rep 7 review). | Accepted in Rep 7: the other cards showed zeros. A model-side fix needs a measure that returns 0 for every category. Check the empty case on every review (checks.md). | — |
| **New card padding is ignored** (`padding` with paddingSelection Custom on `{id: default}`): Desktop drew the card's content from the very top (Rep 7 player card, fix 3). | Don't rely on card padding to place content: make the card transparent, size and centre the visual itself, and put the glass on a shape behind it (Rep 7 player card). | — |
| **New card reference labels in "tabular" style clip** in narrow tiles: titles and values get fixed columns ("vs. Te…", "▼0.9 …", "Per sh…") (Rep 7). | Use the starter's "sentence" style, centred, below the value, with `referenceLabel.backgroundShow` for a tinted strip. Confirmed in Desktop. | Format → Reference labels → Layout → Style: Sentence. |
| **`smallMultiplesAccentBar` with a measure colour doesn't render**, either on the per-Rows selector or selector-less (Rep 7 zone cards, rounds 2–3). | Colour the small-multiple header instead (`smallMultiplesHeader.backgroundColor` = measure on `{data: [{roles: ["Rows"]}]}`, the starter's pattern). Confirmed in Desktop. | — |
| **Shape fill without a selector is ignored**: a shape's `fill.fillColor` / `transparency` and `outline.lineColor` only apply on `selector: {id: default}`; without it Desktop draws the theme's first data colour (Rep 7: three cyan panels). | layout.json `style` (or `pbik_helpers.shape_objects()`) writes `show` selector-less and colour/transparency on `{id: default}`, as the starter's Desktop-saved shape. Confirmed in Desktop (fix round 1). | None. |
| **New card small multiples in one row**: `smallMultiplesLayout.orientation` is 2 = Horizontal, 1 = Vertical, **0 = Grid**; `style` "Table" (default) shares one grid, **"Cards"** gives each cell its own tile. With 2 / Table, rowCount and columnCount are ignored (Rep 7, and the starter). | Orientation 0, style Cards, plus `smallMultiplesCellBackGround` / `smallMultiplesBorder` / `smallMultiplesOuterShape` for the glass cell. Confirmed in Desktop (fix round 2). | Format → Multi-category layout → Arrangement Grid, Style Tiles. |
| **`report.snapshot.capture/v2` with a region sometimes returns the Desktop window** (ribbon included, 1200x675) when the window is small; v1 (no region) returned the canvas (Rep 7 fix round 2). | Retake with v1, or ask for the window maximised. | — |
| **Button slicer per-button image from data** (image "Select from data" → a column or measure): pbik's `cf` image is for new cards only. | Rep 2: the Desktop route neither rendered nor saved, so the icons used cards behind the slicer. **Rep 7:** the starter report's Desktop-saved button slicers show images from a column (`image` with selector `{id: default, data: [dataViewWildcard 1]}` = Aggregation of `logo img col` / `img[face image]`). Rep 7 `build.py picker()` copied that JSON from the starter's saved slicer and restyled it (not carried into the kit: copy the JSON from a Desktop-saved slicer). *pending Desktop check* | — |
| **A card image from a measure needs a declared Text type.** Desktop doesn't write data types for model measures. | A report extension measure wrapper: `pbik measure ext add <Report> "img X" --expression "[Model Measure]" --data-category ImageUrl`. | None. |
| **Table column font colour per field:** `values.field(X).fontColor` doesn't render. | `columnFormatting.field(X).fontColor` + `columnFormatting.field(X).styleValues true`. | None. |
| **Table headers can't be hidden.** | White on white, 6pt, no outline. | None. |
| **Field parameter on a chart:** binding the parameter's display column draws one bar named after the selected factor. | The chart projects every underlying field in parameter order plus a sibling `fieldParameters` entry (index 0, length n). pbik writes it from a layout.json `fieldParameter` binding (0.3); Rep 3's original patch is `archive/examples/rep3/build.py` `field_parameter_category`. Confirmed in Desktop (Department and Pay band). | None. |
| **Subtitle property name** is `subTitle` (not `subtitle`). | Use `subTitle` (layout.json `container.subtitle` writes it). | None. |
| **Button slicer outline colour** is `outline.<state>.lineColor`, not `color`. | Use `lineColor`. | None. |
| **A shadow without `preset` Custom**: Power BI applies its default preset (own angle and distance) and the shadow differs from shapes set with `preset Custom`. New cards use `shadowCustom.shadowPositionPreset`. | Write `dropShadow.*` with `preset Custom` (layout.json `container.shadow` does); on new cards also `shadowPositionPreset Custom`. Check with `design/scripts/audit_layout.py`. *pending* | None. |
| **Dropdown slicer with a header clips below ~76px**. | Give the filter row 76px (Rep 4). | None. |
| **New card reference label without a detail** (`card-reference` with no `--detail`) still draws the default detail placeholder "--" (Rep 4 review). | Add an explicit `referenceLabelDetail` entry with `show: false` and the same selector (metadata + id) as `referenceLabel` (Rep 4 `build.py` `detail_off`). Confirmed in Desktop (fix round 1). | None. |
| **Table sort indicator** shows in the header (Rep 4 store tables, next to Value/City). | Accepted: no PBIR property hides it (.claude/rules/pbik.md). | None. |
| **"Clear all slicers" button action** resets every slicer on the page (Microsoft docs), so a pane Clear would also wipe the Year and the What Changed metric; in Rep 5 it didn't clear the button slicers at all. | Clear Filters = a data-only bookmark per page over the five pane slicers with no selection (`suppressDisplay`, `applyOnlyToTargetVisuals`), `build.py` `clear_bookmark()`. Verified in Desktop. | In Desktop: clear the pane slicers, select them, Bookmarks → Add → uncheck Display, Selected visuals → point Clear's action at it. |
| **Button corner radius**: `shape` (tileShape, rectangleRoundedCurve) without a selector draws square corners (Rep 5: Filters button). | `build.py` `shape_default()` adds `selector: {id: default}` to every button's shape. *pending Desktop check* | Format → Button → Shape → Rounded corners. |
| **AppSource custom visual GUID** can't be looked up locally, and a wrong GUID validates clean but renders empty (Rep 5: HTML Content). | Use the native alternative until the GUID is confirmed from a Desktop-saved `report.json` or the `.pbiviz` `package.json`. | Insert → More visuals → AppSource → HTML Content, save; then rebuild those visuals. |
| **Page navigator labels are the page display names**; no per-button text. A long name wraps in a narrow tile ("Workforce Overview" in 133px). | Rep 5 fix 1: page renamed "Overview" (display name only); the page title text box keeps "Workforce Overview". | — |
| **New card reference-label detail (chip) has square corners and no side padding** (Rep 6 review item 5): no radius or padding property for the detail background. | Accepted (fix round 1): square chip; text and colours are right. | — |
| **Continuous X axis has no tick interval**: the histogram labels every 2 or 5 days, not every day (Rep 6 review item 6). A categorical axis would label every day but loses the X-axis constant line. | Accepted: continuous axis kept for the average line. | — |
| **Dropdown slicer inner box** (Rep 6, Year dropdown): a light-outlined value box drew inside a styled rounded container; `items.outlineStyle` 0 and `general.outlineColor` didn't remove it. | **Fixed (your final adjustment, 2026-10-12):** turn the container background and border **off** and let the dropdown's own box (`items.background`) be the control. (Rep 6 header.) | Format → General → Effects → Background off, Visual border off. |
| **New card: no spacing between the value and the reference label** (Rep 6 KPI chip): `referenceLabel.paddingTop` 8, merged into the field-id selector, doesn't show. | Accepted (2026-10-12). Untried: `layout` spacing between callout and reference label, or a larger `calloutSize`. | Format → Reference labels → Spacing. |
| **X-axis constant line label overlaps the tallest bar** (Rep 6 histograms, "avg: 2.95" over day 3): the label sits right of the line at the top of the plot. | Accepted (2026-10-12). Untried: `dataLabelVerticalPosition` 'under'. | Analytics → X-axis constant line → Data label → Vertical position. |
| **Auto value-axis end = the data max**, so the tallest column touches the top of the plot and runs into the title, subtitle or labels (Rep 6 final review F4). | A Y-axis max measure, `MAXX ( VALUES ( <axis column> ), [Measure] ) * 1.3` (the starter's `_ Y Axis Max`), bound to `valueAxis.end` with `visuals cf --measure` (Rep 6 histograms); no literal end set after it. Also gives the X-axis constant line label room above the bars. *pending Desktop check* | Format → Y axis → Range → Maximum → fx → the measure. |
| **Category label above each bar** (bar chart) (Rep 6). | Rounds 3–4: Y axis = Category (values and title off); X = a zero measure (`_ Blank`) first, then the measure; `labels` entry for the zero series (selector metadata) with `labelPosition` OutsideEnd, `labelOverflow`, title and value off (`enableTitleDataLabel`/`enableValueDataLabel` false), detail on (`enableDetailDataLabel`); **plus** a per-data-point entry, selector `{data: [dataViewWildcard matchingOption 1], metadata: <zero measure>, highlightMatching: 1}`, with `dynamicLabelDetail` = Aggregation(Column Category, Function 3). That's the form Desktop saved; a series-level `dynamicLabelValue` or `dynamicLabelDetail` alone (column or measure) validated but drew nothing (rounds 1 and 3). `pbik_helpers.label_above_bars()`. **Confirmed in Desktop on all four Top 5 charts (round 4, 2026-10-12); recorded in docs/lessons/charts.md.** | Format → Data labels → Series: the zero measure → Title off, Value off, Detail on → field Category. |
| **A selector-less `dataPoint.fill` is ignored on a chart with two series** (Rep 6 fix 1): the Top 5 bars drew theme data colour 2. | Colour each series by `selector.metadata` = its queryRef (layout.json `props` `dataPoint.fill@[Measure]`). | Format → Bars → Series → colour. |
| **100% stacked bar draws an empty-chart placeholder** (Rep 6 fix 1–2): first with measures only (no axis field); with the axis field added it still did, in a 52px visual with `categoryAxis.innerPadding` 62 (Power BI's range is 0–50) under a title. | Axis field (the channel column, filtered to one value: one bar), visual 64px tall, inner padding 40. *pending Desktop check* | — |
| **Dropdown slicer value box outline** draws light inside a styled container (Rep 6 fix 1). | `general.outlineColor` = the box fill, `outlineWeight` 1; the container border carries the rounded edge. *pending Desktop check* | Format → Slicer settings → ... border colour. |

## Desktop or visual behaviour

| Gap | Workaround |
|---|---|
| **Shape visuals ignore the theme fill** and use the first theme data colour. | Set fill, outline, corners and shadow on each shape from the tokens (docs/lessons/cards.md). |
| **Built-in Shape Map (Albers USA) draws Hawaii below Texas**, inside the South auto-zoom frame. It can't be removed by script without hiding the grey neighbours. | SVG map for the South (fallback below). |
| **Scaling commas in format strings** must come right before the decimal point: `#,0,,.0"M"`, not `#,0.0,,"M"`. | Use the correct form (fixed in Rep 2). |
| **Measure edits in Desktop then report-file edits:** saving Desktop afterwards drops the file edits. | Save model changes first, then edit report files, then close without saving and reopen. |
| **Button slicer text disappears in short buttons** (30–32px): the default inner padding leaves no room. | `padding.default` Custom, top/bottom 0, left 12, right 8 (`paddingIndividual` is refused on button slicers). Confirmed. |
| **Button slicer second label** (`label.position`) is only aboveValue/belowValue. | Counts per button go in the tooltip (fallback register). |
| **New card reference line clips** at 136px with the theme's `layout.calloutSize` 75. | `layout.calloutSize` 60 with 20px padding (fix round 2). *pending* |
| **Text card shows a white box** on a coloured band. | Turn off every layer: container background, `fillCustom`, `cardCalloutArea`, `layout.background*`, `outline`, `shadowCustom`. Confirmed. |
| **Power BI draws the CSS shadow darker** than the wireframe. | `tokens.container.pbiShadow` (blur 4, distance 1, transparency 95), preset Custom on every shadow (see below). *pending* |
| **Stacked column labels sit inside the bar only**, so a label in the bar colour is invisible. | White labels, `labels.labelOverflow` true. Confirmed. |
| **Table data bars draw under the numbers.** | Separate bar-only column from a report-level copy of the measure (`vs company bar`), numbers in their own column. Confirmed. |
| **Sort-by column calculated from the same column** is circular in Analysis Services. | Sort a calculated copy (`Age group` = `[AgeGroup]`) by the order column. |
| **Modeling MCP refuses column definitions on a calculated table** (Rep 5). | Create the table without columns, then declare them in its TMDL (`column X`, `sourceColumn: [X]`, `sortByColumn`), as Desktop does for field parameters; reload with ConnectFolder to check. Values come from a Calculate-only recalculation after reopen. |
| **DAX strings have no `\"` escape** (Rep 5: a format string expression). | Double the quote inside DAX strings (`""M""`); query-scoped tests don't cover `formatStringDefinition`, so check those by eye or with a `DEFINE MEASURE` that returns the string. |
| **Modeling MCP Calculate refresh fails** ("base version must not be negative") after a rolled-back change. | Disconnect and reconnect the MCP, then run `RefreshWithXMLA` type Calculate. |
| **Chart data labels get a pale background box** by default (combo chart). | `labels.enableBackground` false, globally and per field. *pending* |
| **Bar chart category labels truncate** ("Research & Develo...") at the default axis width. | `categoryAxis.maxMarginFactor` 35. *pending* |
| **A failed first build can leave container layers on a visual** (kpi-headcount kept a container background). | The build sets container background, border and shadow off on new cards every run. |
| **New card corner radius is ignored** unless `shapeCustomRectangle.tileShape` is `rectangleRoundedByPixel`. | Set the tile shape with the radius; `audit_layout.py` checks it. Confirmed (fix round 3, 2024 and 2020). |
| **New card shows "--" for a blank reference-label detail** (an empty pill in the first year). | KPI value `showBlankAs` "–": confirmed. Detail `showBlankAs` '' does **not** work: Desktop treats it as unset and shows "(Blank)" in the pill (fix round 3, 2020). Proposed: `showBlankAs` ' ' plus a pill background equal to the card colour when the delta text is blank (report measure). *open* |
| **Multi-select new button slicer drew every button in the selected style with nothing selected** (Rep 4 Quarter; the identical status slicer on page 2 rendered normally; the cause wasn't confirmed, possibly the Year slicer filtering the same Date table). | Use a dropdown slicer for such filters (Rep 4 Quarter, like Month). Confirmed in Desktop (fix round 1). |
| **Auto display units on data labels and KPI values** chose millions for $30K–$100K values ("$0.1M") and showed full numbers on cards with a `\$#,0` measure format. | Labels: `labels.labelDisplayUnits` 1000 + `labelPrecision` 1. Cards: `value.default.labelDisplayUnits` 0 (Auto) + `labelPrecision` 2 (0 for $300K). Confirmed (fix round 1). |
| **Table scrollbar although all rows fit** (store tables, row padding 8; risk table, padding 7). | Row padding 5 (5-row tables, 316px) and 6 (15-row table, 652px). Confirmed (fix round 1). |
| **Line chart defaults:** axis starts at the data minimum and lines are smoothed. | `valueAxis.start` 0, `lineStyles.lineChartType` linear. Confirmed (fix round 1). |
| **Bar label precision** stays at 1 decimal in Auto millions ($2.3M vs the wireframe's $2.31M). *Open, low* | `labels.labelPrecision` 2, or Thousands below $1M. Not applied (Rep 4, logged only). |
| **Dropdown slicer look:** a faint grey container box and an underline selector instead of the wireframe's bordered 40px control. *Open, low* | Container border off may remove the box; the underline selector is a tooling limit. |
| **Buttons have no "disabled" state** (Reset can't grey out when nothing is filtered), and the default fill showed pale grey. *Open, low* | Fill: set `fill.show` false explicitly per state; disabled look: tooling limit. |
| **Legend labels, column headers and per-value slicer colours can't follow a selection** (Rep 4: trend legend "This year / Last year", store tables "Value" header, one selected colour on the status slicer). | Accepted (tooling limits): titles and subtitles carry the year and metric (fx). |
| **Table with a field parameter drops its measure columns** (Rep 5 fix 1): with the parameter's fields and the measures together in a `tableEx` Values role, only the category column draws, with a scripted binding and with Desktop's own (Desktop even saved `length: 1` and `active: true` on a measure). | Use a matrix (`pivotTable`): the parameter's fields alone in Rows (every field, `fieldParameters` index 0), the measures in Values. Verified in Desktop: dumbbells and Change render. `build.py` `change()`. | — |
| **Gauge colour fx**: a literal `calloutValue.color` set after `visuals cf --measure` replaces the measure, and `cf` writes the labels rule with a series wildcard selector a gauge ignores (Rep 5 fix 1). | `build.py` `gauge_fx()` puts both measures on the selector-less objects. Verified in Desktop (2020). |
| **SVG text with a raw `%`** ("24%") makes the whole data URI invalid; Power BI then skips decoding, so the `%23` colours stay encoded and every fill draws black, while the text still shows (Rep 5 fix 1: Likert, termination-rate bars, dumbbell). | Write `%` inside SVG text as `%25` (Rep 5 `gen_model.py`). `design/scripts/audit_svg.py` flags any `%` that isn't a `%XX` escape. |
| **`ALLSELECTED` in a conditional-formatting measure** (matrix font colour) kept each cell's own filters, so every cell was its own maximum and all text drew white (Rep 5 fix 1, heatmap). | Use `ALL` over the axis columns for the scale (`fmt Heatmap font`). |
| **Query-scoped `DEFINE MEASURE` doesn't reach model measures that reference it** in this Desktop build: `[6_TerminationRate]` kept using the loaded `4_Terminations` (Rep 5 fix 1). | When testing a changed measure, also redefine every measure in the chain that the audit reads. |
| **Desktop save rewrites visual.json** (key order, `$schema` 2.13.0) and drops `columnHeaders.customColumnWidth`; column widths and all bindings stay. | Harmless; treat Desktop's save as the new baseline before the next `build.py` run. |

## Fallbacks in use, Rep 3 (from the Rep 3 spec, home copy only)

| Item | Fallback | Native option tried |
|---|---|---|
| Headcount on each rail button | Shown in the button tooltip | Button slicer Label to the right of the value: position allows only above/below, which doesn't fit 32px buttons |

## Fallbacks in use, Rep 2 (history)

| Item | Fallback | Native option tried |
|---|---|---|
| South map | SVG map (`Map SVG` via report wrapper `Map Image South`) in a new card's image area | Native Shape Map: Hawaii's inset falls inside the frame |
| Sidebar icons | Three new cards (`icon-*`, filtered by `Metric_Sel[Metric]`, `Metric Icon Image` wrapper) behind a transparent button slicer; 50% selected highlight | Button slicer per-button image from `Metric Icon` |
| Map fallback, unused | `Map Image` (generic `Map SVG` wrapper) kept for possible SVG maps | Kept per "Native first"; propose removing once the Shape Map is confirmed everywhere |

## Open at the end of Rep 2

- **Sidebar icons:** the first try showed white squares (the card's white callout area). Making every background layer transparent removed them, but `image.transparency` 100 also hid the icon itself (the schema calls it background transparency). It's now removed; check in Desktop that the icons render.
  Lesson: on a new card, `image.transparency` fades the image; turn off `fillCustom`, `cardCalloutArea`, `layout` and container backgrounds instead.
- **Profit and Orders switching hasn't been checked in Desktop.**
- **Icon cards and the metric slicer:** the button slicer filters `Metric_Sel` for the whole page, so with Sales
  selected the Profit and Orders icon cards had no row and showed nothing. Fixed with visual interactions
  `metric-buttons -> icon-*` = NoFilter (layout.json page `interactions`). Lesson: any visual filtered to one slicer
  value must have that slicer's interaction turned off.
  Confirmed in Desktop (2026-10-02): all three icons render with the NoFilter interactions. Note: re-opening the file
  inside a running Desktop window keeps the old definition; fully close and restart Desktop to load file edits.

## Modeling notes (Rep 4)

- **In DAX a blank counts as less than any number** (`BLANK() < 7` and `BLANK() <= 15` are TRUE). Guard rank and
  status measures with ISBLANK first: `IF ( NOT ISBLANK ( _r ) && _r <= 15, … )`. Rep 4: the risk table showed 157
  unstocked pairs as "0.00" rows (fix round 1), and the first Stock Status draft put idle stock in Low. Fix round 2:
  the Top/Bottom store measures showed stores with no sales in Feb 2023 + Electronics at −100% vs PY.
- **Test ranked measures in a sparse filter state**, not only the default: a month and category where some members
  have no rows (Rep 4: Feb 2023 + Electronics). `audit.dax` keeps that state as a permanent check.

- **Field parameter display column** (`Metric[Metric]`) is part of a composite key with `Metric Fields`, so
  `SELECTEDVALUE ( Metric[Metric] )` errors in a measure. Read `Metric[Metric Order]` instead.
- **ALLSELECTED / ALL take columns from one table only.** For pairs across tables use
  `CROSSJOIN ( ALLSELECTED ( T1[c] ), ALLSELECTED ( T2[c] ) )`.
- **Status counts under a status slicer** need `KEEPFILTERS`, or the measure's own filter overrides the slicer.
- **Test DAX before writing it:** run the definitions as query-scoped `DEFINE COLUMN` / `DEFINE MEASURE` against the
  open Desktop model (Desktop stays clean), then write the TMDL with the modeling MCP (ConnectFolder → create →
  ExportToTmdlFolder). This caught all three bugs above in Rep 4.
- **Calculated columns written to the TMDL on disk have no values** until a Calculate-only recalculation after
  Desktop reopens.
