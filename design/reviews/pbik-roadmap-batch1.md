# pbik roadmap batch 1 (pbik 0.13.0, 2026-11-10)

Items (a) report settings and filter pane (gaps 1 and 24), (b) schema-checked props, (c) retiring and deprecated
visuals (gap 20), plus the gap 23 question (report only, nothing changed). Tests 110-118 in
`tools/pbik/tests/test_pbik.py`; regression suite unchanged (no existing layout builds differently). **Not
Desktop-tested yet**: the smoke report `..\pbik-smoke-013` (beside the kit folder) is built for the check below.

## (a) Report settings and filter pane (gap 1, with gap 24)

**What pbik does now**

- Layout `report.filterPane: {expanded, visible}` -> report.json `objects.outspacePane` (no selector), and
  `report.settings: {...}` -> report.json `settings`. Written in place: `filterConfig`, `section`, themes, resources and
  any setting the layout doesn't name stay as Desktop wrote them. Each key pbik sets records the value Desktop had
  (visual-map.json `reportOwned`) and gets it back when the key leaves layout.json.
- Page `filterPane` -> page `objects.outspacePane` (the pane's look on that page); page
  `filterCards: {applied, available}` -> page `objects.filterCard` on selector `{id: Applied}` / `{id: Available}`.
- Every name and value is checked against the cached report and page schemas (item b); bad report keys are build errors.
- `pbik build` says when report.json changed: Desktop's reload doesn't apply report.json during the preview, so close
  without saving and reopen (also in `.claude/rules/pbik.md`).

**Gap 24: a collapsed pane must not lose filters**

- pbik's own filters are explicit `filterConfig` entries (`howCreated: User`), so they're saved whatever the pane
  state. A collapsed pane (`expanded: false`) only changes how the report opens.
- Automatic filters (`howCreated: Auto`) reach visual.json only after the pane has been expanded once. With a pane
  collapsed by default they may never be saved. That is expected, not a loss: Power BI regenerates them from the
  visual's fields. `pbik validate` prints a note saying so.
- What could actually lose filters was `pbik build --reset` (and a Deneb / fallback swap): it rebuilt the visual from
  its template and dropped the filters Desktop had saved on it. It now keeps every filter not named `pbik_` / `tpl_`
  (test 113).
- `visible: false` hides the pane in view mode, so filters that aren't `hidden` can't be reached. Build warns;
  validate lists them.

**How roundtrip treats pane-driven changes**

Filters are now matched by name. An automatic filter Desktop added, and the pane's `expanded` / `visible` state as
the author left it, are labelled `pane` and listed apart as "Pane-dependent, not pbik fixes". They're never
proposed for writing. The layout's `report.filterPane` resets the pane state on the next build. A filter Desktop added
that isn't automatic (`User`, `Include`, ...) is still an "added" proposal. Roundtrip still skips `StaticResources`
(the other half of gap 24; not in this batch).

**Provenance**

- Microsoft's PBIR schemas (MIT, as cached by `pbik schemas fetch`, read 2026-11-10): report 3.3.0
  #ReportFormattingObjects, #OutspacePane (`expanded`, `visible`), #ExplorationSettings (names, types, enum values);
  page 2.1.0 #PageFormattingObjects, #OutspacePane, #FilterCard; filterConfiguration 1.3.0 #FilterContainer
  `howCreated` (Auto = "created automatically when a field is used in the visual").
- Desktop-saved files: report.json `outspacePane.expanded: false` (no selector, literal `false`) and the six
  `settings` keys, as Desktop saved them in the Rep 4, 5 and 8 fixtures (`tools/fixtures/*/definition/report.json`).
  The filter card ids `Applied` / `Available` come from `filterCard` `$id`s in Desktop's own base themes
  (Fluent2-CY26SU09, CY24SU10 in the fixtures' StaticResources). `outspacePane` there has no `$id`, hence no selector.
- Microsoft Learn: *Power BI Desktop project report folder*, "PBIR considerations and limitations" (automatic filters
  persist only after the filter pane has been expanded); *Edit Power BI Desktop project files outside Power BI Desktop*
  (updated 2026-09-29), "Considerations and limitations": during the reload preview `report.json` can't be edited
  externally, and reloading resets filters.
- **Not used**: the Desktop-saved sample `filter-pane.Report` named in the brief wasn't on
  the build machine. Nothing Desktop saved shows `visible`, page
  `outspacePane` or `filterCard`. Those forms come from the schema and the base theme only, until the smoke check.

## (b) Schema-checked props

**What pbik does now** (`pbikit/schemaprops.py`, standard library; `jsonschema` not needed):

- `pbik build` checks every `props` key, `container:` prop, page `filterPane` / `filterCards` property, report
  setting (name and value) and report pane key against the cached schema. A miss is a warning; `--strict` makes it
  an error and nothing is written.
- `pbik validate` does the same for the properties pbik owns (`--layout`'s visual-map.json, else every property), for
  page objects and for report.json. Misses are warnings; `--strict` makes them errors.
- A schema version Microsoft hasn't published (visualContainer 2.14.0, which the kit's templates carry) is checked
  against the newest older cached version, and a miss there stays a warning even with `--strict`.
- An uncached schema is skipped, as before.

**Limit you should know**: Microsoft's schema has no per-visual-type property list. A visual's `objects` is
#DataViewObjectDefinitions, which allows any object name and any property for every visual type. So "not in the
schema for that visual type" can only be checked for container objects (closed per object), page objects and
report.json. A visual's own `objects` pass the schema check. The settings catalog (Desktop-saved properties per
visual type) stays what warns on those. The objects that are closed are also closed for the full `jsonschema` pass,
so with jsonschema installed `pbik validate` still reports the same miss as a schema error, strict or not. Desktop may
refuse a file that fails its schema, so I left that error in place rather than demote it.

**Provenance**: microsoft/json-schemas (MIT): visualContainer 2.13.0, visualConfiguration 2.8.0
(#VisualContainerFormattingObjects), formattingObjectDefinitions 1.5.0 (#DataViewObjectDefinitions), page 2.1.0,
report 3.3.0, all from pbik's cache (git-ignored). The tests use small hand-written stand-in schemas
(`PBIK_SCHEMA_CACHE`), not copies of Microsoft's files, so the kit still ships no schema and owes no notice.

## (c) Retiring and deprecated visuals and options (gap 20)

**What pbik does now** (`pbikit/deprecations.py`): `pbik validate` and `pbik build` warn on:

- the Q&A visual (`qnaVisual`): **validate only**, see the type ids below;
- a button whose action is Q&A (`visualLink` type Q&A or a `qna` property);
- Map (`map`) and Filled map (`filledMap`): Bing Maps;
- page `displayOption` `DeprecatedDynamic` and `ActualSizeTopLeft`, read from the cached page schema's "Deprecated"
  mark (a built-in list when the schema isn't cached).

**Provenance**

- [L5] *Limitations of Power BI Q&A* (updated 2026-09-10), Important: Q&A goes away in February 2027.
- [L6] *Convert Map and Filled map visuals to an Azure Maps visual* (updated 2026-01-21), Important: Bing Maps visuals
  are scheduled for deprecation, no date set.
- [L8] *Power BI Report skill* (updated 2026-10-02), Considerations: avoid Q&A, Bing Maps and filled maps.
- page 2.1.0 #PageDisplayOption (both values described "Deprecated"); visualConfiguration 2.8.0 #VisualLink (`qna`).
- Type ids: `map` and `azureMap` appear in Desktop's base themes in the fixtures. **`qnaVisual` and `filledMap` are
  unconfirmed**: Learn prints no type ids and no kit file Desktop saved has them. Confirm `filledMap` from one Desktop save
  (insert it on a scratch page, save, read `visualType`). The Q&A visual can't be confirmed that way: on 2026-11-10
  Kyle found it in neither Visualizations nor Insert in Desktop 2.159.883.0. Its id stays unconfirmed and its warning
  stays in `pbik validate` only (for files made elsewhere or in an older Desktop); `pbik build` doesn't warn on it.

## Gap 23: which Desktop first reloads external changes (report only, nothing changed)

- Microsoft Learn, *Edit Power BI Desktop project files outside Power BI Desktop* (updated 2026-09-29),
  Prerequisites: "Install the August 2026 release or later of Power BI Desktop". The preview option is
  **Detect and reload external PBIP changes** (Options > Preview features, then restart). Each project file path must
  stay under 260 characters.
- Learn gives no version number for the August 2026 release. The Desktop update archive (updated 2026-11-02) has no
  version numbers for August or September 2026. The last numbered releases are **2.156.951.0 (July 2026)** and
  **2.155.756.0 (June 2026)**. So the first qualifying build is newer than 2.156.951.0, and its exact number isn't
  published.
- **Desktop 2.155 does not qualify.** 2.155.756.0 is the June 2026 release (and the MSI build string
  `2.155.756.0 (26.06)` says June too), two releases before August. On 2.155 the reload and the Desktop Bridge aren't
  available, so `pbik desktop reload` returns exit 3. Use the manual close-and-reopen steps in `.claude/rules/pbik.md`.
  This machine's 2.159.883.0 qualifies.

## Desktop check (pbik-smoke-013)

`..\pbik-smoke-013\Smoke.pbip` (beside the kit folder): synthetic model only (`Sales`, 24 rows in an inline `#table`, no file or
connection; measures Total Amount and Row Count). It has one page, "Filter pane": two cards, a column chart with a
visual filter on Year, a table with a hidden Region filter, and a page filter on Category. A copy of the files as
pbik built them is in `_pbik-built/` for `pbik roundtrip --before`.

1. Open `Smoke.pbip` in Desktop (data is empty until **Refresh**. Refresh reads only the inline rows, no source).
2. The filter pane opens **collapsed**.
3. Expand it: the pane is 300px wide on the card colour with a border; applied filter cards (Category, Year) are
   tinted teal with a teal border, available cards plain; the table's Region filter isn't shown in Reading view.
4. File > Options and settings > Options > Current file > Report settings: export data is **No export allowed**;
   "Hide the visual header in reading view" is on; modern visual tooltips are on.
5. Save once in Desktop. Then run
   `python ..\pbip-kit-export\tools\pbik\pbik.py roundtrip Smoke.Report --before _pbik-built\Smoke.Report` from the
   smoke folder. Expected: automatic filters (if any) and `expanded: true` are under "Pane-dependent". Every
   page `outspacePane` / `filterCard` property and every setting should be kept. Anything listed as dropped or
   rewritten there is a form to fix.

## Desktop check results (Desktop 2.159.883.0, 2026-11-10)

Kyle opened pbik-smoke-013, saved once, and ran `pbik roundtrip --before _pbik-built\Smoke.Report`.

- **Kept on save, nothing rewritten**: report.json `outspacePane` (`expanded: false`, `visible: true`), the three
  settings pbik set (`exportDataMode`, `hideVisualContainerHeader`, `useEnhancedTooltips`), page `outspacePane` (all
  ten properties, no selector) and page `filterCard` on `{id: Applied}` / `{id: Available}`. Desktop accepted every
  form pbik writes for gap 1, and Kyle checked the filter pane formatting renders as intended (2026-11-10).
- **Automatic filters, as Desktop saves them**: after the pane was opened, Desktop added two to the table (P1-V06),
  one per field it shows (Sales[Category]: `Categorical`; [Total Amount]: `Advanced`), with **no `howCreated` and no
  condition**, not the schema's `howCreated: "Auto"`. Roundtrip first listed them as "added" proposals.
  Fixed: `fields.is_automatic` takes either form, so roundtrip labels both `pane` and validate's hidden-pane check skips
  them (tests 114b, 118). The chart and cards got none: Desktop saves them per visual, only for visuals selected while
  the pane was open. This is gap 24 as Learn describes it.
- **Settings order**: Desktop writes report.json `settings` in the schema's property order (`hideVisualContainerHeader`
  first). pbik now sorts them that way when the report schema is cached, and a rebuild of the built copy matches
  Desktop's order exactly.
- **Not pbik fixes**: P1-V06 moved by about 1px in Desktop (x 1285 -> 1285.47, y 344 -> 345.35). The next build puts
  it back on the grid. A scratch page "Page 1" with a `shapeMap` visual (Sales[Region], an uploaded US states map)
  adds `pageOrder` and a SharedResources `ShapeMap` item (`Shapemaps/usa.states.topo.json`), the form gap 14 needs.
- **Type ids**: the Q&A visual isn't offered by this Desktop (neither Visualizations nor Insert), so `qnaVisual` stays
  unconfirmed and its warning is validate-only. The scratch page holds a shape map, not a filled map, so `filledMap`
  is still unconfirmed.
