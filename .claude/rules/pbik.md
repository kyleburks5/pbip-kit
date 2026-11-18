pbik rules (tools/pbik/README.md has every command) and the Desktop and PBIR facts that came with them.

## Running pbik
- Run `python tools/pbik/pbik.py <command>` from the project root (no install), `tools\pbik\pbik.cmd`, or `pbik` after
  `pip install --user -e tools\pbik`.
- Drive builds from layout.json: it carries everything structured (PowerShell 5.1 strips quotes from JSON arguments,
  so never pass JSON on the command line). There is no per-rep build.py since pbik 0.6.
- `pbik build` is idempotent: run it twice and the second run must print "No changes". It writes only files whose content
  changes, so a clean `git diff` after a rerun is the check.
- Visuals without an ID (`P<n>-V<nn>_` folder) are never touched by `pbik build`; `pbik validate` reports them as errors.
- Properties pbik wrote and that left layout.json are removed on the next build, from the list in
  design/specs/visual-map.json (`owned`). Don't edit that file; if it's lost, the next build still sets everything,
  but properties dropped from layout.json in the meantime stay until `--reset`.
- `pbik build --reset` rebuilds each visual from its template, so Desktop-made changes inside ID'd visuals are lost:
  ask first.
- Schema checks use the cache in tools/pbik/schemas/ (`pbik schemas fetch <Report>`, git-ignored). Microsoft doesn't
  publish every version Desktop writes (visualContainer 2.14.0 is a 404); those files get a "not cached" warning.
- design/specs/project.json `targetDesktop` caps the `$schema` versions pbik writes to what that Desktop supports
  (Microsoft's published schema CHANGELOGs, tools/pbik/schema-support.json); validate errors on newer ones. Its
  `catalog` names the settings catalog validate warns from. Never change the target without asking
  (docs/UPDATE-ROUTINE.md).
- `pbik desktop reload` refuses while Desktop has unsaved changes and reloads the report only, never the model
  (`reloadModelDefinition` false). Exit code 3 means the bridge isn't available: that is "not checked", not "clean".

## When the Desktop Bridge is missing (exit 3; tools/doctor.ps1 says so)
- Nothing else changes: build and validate run on disk. Put the reload in the numbered Desktop click list as manual
  steps instead of running `pbik desktop reload`: 1. In Desktop, File > Close (don't save). 2. Open
  `<Report>.pbip` again from File Explorer. 3. Check the title bar shows no unsaved mark before going on.
- Screenshots: ask me for one PNG per page at 100% zoom (View > Page view > Actual size; Win+Shift+S), saved to
  `_snapshots/<page>.png`, instead of `pbik desktop screenshot`. Note "screenshots by hand, not page-exact" in
  review.md; skip the fidelity check ("Fidelity check: skipped (no Desktop Bridge)").

## Desktop and PBIR facts
- Desktop flags the report "unsaved" after opening and after every reload. Never reload while it's unsaved: close
  without saving and reopen first.
- Page-only screenshots: `pbik desktop screenshot --report <Report> --page <display name> --out <png> --region 0,0,1920,1080`
  (bridge capture v2), no Filters strip.
- Page-navigation buttons target the page **name** (the page.json `name`, a hex id), not the display name; pbik writes
  the name and `pbik validate` flags a display name.
- Filter values must be typed like the column: `2024L` (whole number), `1.5D` (decimal number), `'text'`. A number
  written as text never matches; pbik types values from the TMDL and validate flags text numbers.
- Desktop test round 1 (2026-10-17), from the Rep 4-7 files Desktop saved: button `text` / `fill` / `outline` / `icon`
  formatting sits on `{id: default}` with `show` selector-less, or Desktop ignores it (pbik does this for `props`); a
  bar chart's fx colour is per data point (data wildcard, no column metadata); a horizontal bar chart's value-axis line
  is `y1AxisReferenceLine`; table column widths are `columnWidth` on the column's metadata; the theme's slicer
  `data.mode` Dropdown needs `slicerMode` on the visual for a list. On save Desktop adds `active: true` to the first
  category field and drops `isDefaultSort: false`; pbik writes both the same way.
- Bookmarks (Rep 5, as Desktop saved them): `options.targetVisualNames` with `applyOnlyToTargetVisuals`, and
  `suppressActiveSection` so applying one doesn't switch page; display bookmarks add `suppressData`, a reset of the
  pane slicers is a data bookmark with `suppressDisplay` and nothing saved. A hidden visual is
  `singleVisual.display.mode: "hidden"` under its page's section. A button's bookmark is the bookmark id, not its
  display name.
- Report extension measures (reportExtensions.json) are bound with `SourceRef.Schema = "extension"`; an ImageUrl measure
  needs `dataType` Text.
- No PBIR property hides the table sort indicator; it sits at the left edge of a right-aligned sorted column.
- cardVisual per-field objects in the theme need `"$id": "default"`; set `layout.calloutSize` (75) or the aboveValue
  label clips.
- A conditional-formatting rule on a cardVisual `referenceLabelDetail.detailFontColor` with a wildcard selector doesn't
  render (tables render the same rules fine). Use a hex-returning measure on the detail colour instead (the measure must
  be in the TMDL first).
- Table per-column header alignment: `columnFormatting` on the field's `metadata` selector with `alignment` and
  `styleHeader: true`; `columnHeaders` per field is ignored. Theme `total.totals: false` didn't hide totals; set it on
  the visual (`props: {"total.totals": false}`).
- A theme change shows in Desktop after a report reload; there is no need to reopen.
- report.json (layout `report`: filter pane, report settings) isn't applied by Desktop's reload during the preview
  (Learn, external editing, 2026-09-29): close without saving and reopen; `pbik build` says so when it changed.
  Automatic filters reach visual.json only after the filter pane has been opened once, so with a collapsed pane
  they may never be saved: expected, and `pbik roundtrip` labels them `pane`, not as fixes. Desktop saves them with
  no `howCreated` and no condition (name, field, type), not `howCreated: Auto` (smoke save, 2026-11-10).
- Deneb (Patterns page save, 2026-10-24): `visualType` deneb7E15AEF80B9E4D4F8E12924291ECE89A, fields on the
  `dataset` role, the spec as one string in `vega.jsonSpec`, `stateManagement` beside it, and report.json
  `publicCustomVisuals` listing the visual. Deneb 2.0.1.0 (scratch save, 2026-11-16) also saves `developer.version`
  ('2.0.1.0') and `vega.version` (the Vega-Lite version, '6.4.3'); still no provider or config. pbik writes Vega-Lite
  specs only. Cross-filtering is off until `vega.enableSelection` is true (Deneb's editor: Project setup >
  Cross-filtering, not the Format pane), with `selectionMode` simple and `selectionMaxDataPoints` (default 50, max
  250); in simple mode Deneb handles the clicks and the spec styles rows by the `__selected__` field (on/off/neutral).
- A private .pbiviz (scratch save, 2026-11-16): the package unzipped into `<Report>/CustomVisuals/<guid>/`
  (`package.json` and `resources/<guid>.pbiviz.json`, same content, re-indented with CRLF) and a report.json
  `resourcePackages` entry `{name: <guid>, type: CustomVisual, items: [{name/path: <guid>.pbiviz.json, type:
  CustomVisualMetadata}]}`; the visual.json `visualType` is the guid and its roles are the visual's own.
- Kit custom visuals in Desktop (v1.11 reviews, 2026-11-17): a visual's own filter (`applyJsonFilter`) doesn't
  filter the visual itself but makes Desktop re-query and redraw the rest of the page on the thread the visual
  animates on, and it also filters the page's slicers (pbik build writes NoFilter from kit visuals to slicers);
  Desktop sends an empty update (no data view) while it loads, before the rows; selections alone left cards and
  tables unchanged, real filters work. The new card scales an image to the tile's width, not to fit inside it.
- Button slicers (2026-11-17): a slicer whose formatting held text where Desktop saves a number (an unresolved token
  name, `'control.tileRadius'`) took no clicks, and a template's leftover `syncGroup` tied slicers on different
  fields together; the button-slicer template is now a clean harvest of one made in Desktop (no formatting), pbik
  build resolves or rejects token names, and validate flags both.
