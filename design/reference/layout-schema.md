# layout.json schema and visual IDs

`design/specs/layout.json` is the single source for the wireframe, the build and the audits. `/plan` writes it;
`pbik build` builds the report from it alone (tools/pbik/README.md lists every build key). There is no per-rep
build.py (pbik 0.6): what layout.json can't express is a pbik gap (design/known-gaps.md).

## Visual IDs

- Format `P<page>-V<nn>`: page number, then a two-digit (or longer) visual number, for example `P1-V13`.
- An ID belongs to one visual for the life of the project. When a visual is removed, move its ID to `retired`;
  never give it to another visual. A new visual takes the next free number on its page.
- Renaming a visual keeps its ID. Changing what it is (another type or purpose) takes a new ID.
- The ID is used everywhere the visual is mentioned:
  - wireframe: `data-id="P1-V13"` on the element, and the badge text;
  - spec: the done-when line, the build-method table and the fallback register;
  - review and fix: the first column of every finding (`design/reviews/review.md`), and the fix notes;
  - report: the visual folder and name `<id>_<name>` (`P1-V13_kpi-cards`);
  - `design/specs/visual-map.json`: ID → page, name, type, build method, PBIR folder, written by `pbik build`.
- `design/scripts/audit_ids.py` checks all of these: missing, duplicate, retired or reused IDs, and folders, wireframe
  elements or spec rows without a layout entry. `/build` and `/fix` run it.

## Top level

| Key | Holds |
| --- | --- |
| `pages` | `{"P1": {"displayName": "Overview", "background": "background", "active": true, "filters": [...], "interactions": [...]}}`; `active` marks the page that opens first (one page); keep display names short (page navigator labels) |
| `privacy` | required for wireframe numbers: `{"count": "[Group Size]", "minGroup": 5, "identifiers": ["DataTable[EmployeeID]"], "maxRows": 500}`. wireframe_data.py queries each visual with the count, hides groups under `minGroup` (plus one more when exactly one would be hidden), and refuses to save when a visual groups by an identifier, a query looks row-level or a small group remains |
| `theme` | optional: the theme file pbik build registers and applies first (`design/themes/pbip-polish.json`, from gen_theme.py) |
| `vega` | optional: how the high-fidelity wireframe draws Deneb specs. `"cdn"` (default): Vega-Lite itself, from pinned scripts on cdn.jsdelivr.net loaded when the page opens, with the built-in subset renderer when they don't load; `"offline"`: a page that loads nothing, drawn by the subset renderer. Use `"offline"` at work (docs/it-security.md) |
| `measureTable` | optional: home table for `[Measure]` when there is no model on disk (pbik finds it in the TMDL otherwise) |
| `grid` | canvas, margin, columns, gutter (from `tokens.canvas`); the canvas height is `tokens.canvas.height`, 1080 by default (`ref_layout.py --canvas-height` for one reference) |
| `retired` | IDs no longer in use, never reused |
| `panels` | optional: `{"<key>": {"visuals": {"card": "<shape id>", "<role>": "<id>"}}}`; audit_layout checks z-order |
| `visuals` | one entry per visual, below |

## A visual

| Key | Holds |
| --- | --- |
| `id`, `name`, `page`, `type` | ID, kebab-case name, page key, PBIR visual type (`cardVisual`, `shape`, `textbox`, ...) |
| `cols`, `x`, `y`, `w`, `h`, `z` | grid columns and the box computed from them; z = layer |
| `desktopPosition` | optional: Desktop's exact position after a hand polish (`{"x": 40.25, "y": 96.5, "z": 7000, "width": 600.75, "height": 300, "tabOrder": 55}`, fractions kept), copied from roundtrip; it wins over the grid box, z and tabOrder |
| `fields` | layout notation: `[Measure]`, `Table[Column]`, `First(Table[Column])` (for the wireframe and the spec) |
| `bindings` entries can be `{"field": ..., "active": false}` (e.g. a matrix's saved second row level, as Desktop saved it) | |
| `bindings`, `sort`, `filters` (columns: values or Top N; measures: `{field, op, value}`, visuals only), `referenceLines`, `action`, `container`, `text`, `cf`, `props`, `selection`, `template`, `navigator` |
| `container.altText` | required on every data visual (bindings, not a slicer) and every image: one sentence on what it shows; /plan writes it, gen_wireframe_hf.py and `pbik validate` flag a missing one | what `pbik build` writes (tools/pbik/README.md) |
| `members`, `displayName`, `mode` | groups (`type: "group"`): the member IDs (visuals or groups on the same page), the name in the Selection pane, `ScaleMode` (default); `x`/`y`/`w`/`h` optional (default: the members' box). Members keep page coordinates here; pbik writes them relative to the group |
| `items` | button slicers: the item count or the list of labels, for `pbik validate`'s fit check when Desktop isn't open (`--port auto` reads them from the model) |
| `style` | token names (`"fill": "card"`, `"transparency": "glass.panel"`, `"outline": "border"`, `"shadow": true`) |
| `build` | see below |
| `doneWhen` | what must be true on screen (copied to the spec) |
| `notes` | anything else |

### `build`: the visual-method ladder

```json
"build": {"method": "native", "step": 1, "reason": "Line chart with markers-only current series"}
"build": {"method": "svg-measure", "step": 2, "nativeTried": "Button slicer per-button image from data",
          "reason": "Desktop neither rendered nor saved it (known-gaps)", "register": "F2"}
"build": {"method": "deneb", "step": 3, "nativeTried": "Line chart markers", "reason": "Hollow partial point",
          "register": "F3"}
```

| Step | `method` | What |
| --- | --- | --- |
| 1 native | `native`, `page-background` | a Power BI visual and its settings |
| 2 SVG | `svg-measure`, `image` (a registered PNG drawn from SVG) | a DAX measure drawing SVG in a new card or table column, or a static image (.claude/rules/svg.md) |
| 3 Deneb | `deneb` | the certified Deneb visual with a Vega-Lite spec (`deneb`, `fallback` below) |
| 4 custom visual | `custom-visual`, `html-measure` (HTML Content visual) | any other custom visual: uncertified until IT checks it (docs/it-security.md) |

- Every visual has `step` (it must match `method`) and `reason`: why this is the lowest step that meets the design.
  /plan picks the step from docs/patterns/ (the ladder per pattern); audit_ids.py checks it (design/scripts/ladder.py).
- Step 2 and up are fallbacks: they need `nativeTried`, `reason`, and a row in the spec's fallback register keyed by
  the visual ID. Ask before building one (CLAUDE.md "Native first").
- Step 4 also needs `itCheck`: who cleared the visual for this tenant, and when.
- The wireframe's tags (press T) come from `method`.

### Deneb visuals (step 3)

```json
{"id": "P2-V01", "name": "range-by-region", "page": "P2", "type": "deneb", "x": 32, "y": 80, "w": 900, "h": 420,
 "bindings": {"dataset": ["Region[Region]", "[Band Low]", "[Band High]", "[Value]"]},
 "deneb": {"spec": "design/deneb/P2-V01.vl.json"},
 "fallback": {"type": "clusteredBarChart", "bindings": {"Category": ["Region[Region]"], "Y": ["[Value]"]},
              "build": {"method": "native", "step": 1, "reason": "Bars without the band"}},
 "container": {"altText": "Each region's value against its usual range"},
 "build": {"method": "deneb", "step": 3, "nativeTried": "Line chart with error bars", "reason": "Band per row",
           "register": "F3"}}
```

- `deneb.spec`: a Vega-Lite spec, inline or a JSON file (keep files in design/deneb/ named by visual ID). It reads
  `{"data": {"name": "dataset"}}`; the dataset's field names are the bound fields' names (`Region`, `Band Low`).
  Colours: `pbiColor(n)` (the theme's data colours), never a hex value (CLAUDE.md "never hardcode colours").
- `fallback` is required: a native or SVG visual that shows the same numbers, with its own `container.title` (and
  `subtitle`) when the Deneb visual has one; the Deneb visual's words describe the Deneb chart. `pbik build --no-custom-visuals`
  builds it instead, in the same folder.
- The wireframe draws the spec (gen_wireframe_hf.py). Review it with the `reports:deneb-reviewer` agent first.

### `pattern`

The pattern a visual draws, from docs/patterns/ (`range-band`, `dumbbell`, `small-multiples-expected`,
`brushed-range`, `partial-period`, `freshness-line`, `exception-list`, `direct-labels`). gen_wireframe_hf.py draws a
visual with a `pattern` through that pattern's renderer; pbik build ignores the key.
