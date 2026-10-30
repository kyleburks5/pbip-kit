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
- Deneb (Patterns page save, 2026-10-24): `visualType` deneb7E15AEF80B9E4D4F8E12924291ECE89A, fields on the
  `dataset` role, the spec as one string in `vega.jsonSpec`, `stateManagement` beside it, and report.json
  `publicCustomVisuals` listing the visual. The saved file has no Deneb version, provider or config: the version shows
  only in Desktop (the visual's About). pbik writes Vega-Lite specs only.
