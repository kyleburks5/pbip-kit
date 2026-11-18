# Visual harness

An offline stand-in for Power BI, so the agent can check a visual without Desktop: a fake host (host.js), a page that
loads a built visual or a Deneb spec (page.js, page.html), and a Playwright runner (run.mjs). `pbik visual test
<name> [--scenario file] [--record]` runs it with the kit's Node; screenshots, frame strips and report.json go to
`_snapshots/visuals/<name>/<scenario>/` (git-ignored). Nothing here talks to the network: the runner blocks every
request that isn't a local file and fails the run if the visual tried one.

What it fakes (from the visuals API's public types, not from Power BI): data views from rows (categorical, with
highlights and segments), selection ids and the selection manager, tooltips, the colour palette (the project theme's
data colours, or the high-contrast palette), rendering events, fetch more data, localisation. Deneb: Vega-Lite with
Deneb 2.0.1.0's own Vega versions, `pbiColor` and a simple `pbiFormat`, and simple-mode cross-filter (`__selected__`
on / off / neutral, click and Ctrl-click). The Deneb click handling imitates Deneb's documented behaviour; Desktop
stays the final check.

The clock is frozen (Playwright clock) for custom visuals, so `wait` and `frames` steps show exact moments of an
animation; `--record` also records a real-time video.

## Scenario

```json
{"viewport": {"width": 900, "height": 560}, "theme": "optional theme.json (default: the project's)",
 "highContrast": false, "reducedMotion": false, "allowInteractions": true, "objects": {"motion": {"speed": 650}},
 "data": {"generate": {"n": 240, "seed": 7, "fields": {"Deal": {"id": "D-"}, "Region": {"pick": ["North", "South"],
          "weights": [3, 1]}, "Value": {"normal": [42, 14]}, "Days": {"uniform": [2, 120]}}},
          "roles": {"Item": "Deal", "Group": "Region", "X": "Days", "Y": "Value"}, "measures": ["X", "Y"],
          "formats": {"Value": "#,0.0"}, "window": 0},
 "steps": [...]}
```

`data.rows` (or `rowsFile`) gives rows directly. `generate` fields: `id` (prefix), `pick` (with `weights`), `uniform`
[min, max], `normal` [mean, sd], `from` (another field, `times`, `noise`). `window` sends the rows in segments so the
visual has to fetch more. Deneb scenarios have `kind: "deneb"`, `spec` and `deneb: {crossFilter, tooltips}`.

## Steps

| Step | Does |
| --- | --- |
| `{"shot": "name"}` | screenshot of the visual; `"golden": true` (or a tolerance such as 0.02) compares it with `test/golden/<scenario>/<name>.png` (made on the first run, replaced with `pbik visual test --update-golden`); a difference writes `<name>.diff.png` |
| `{"frames": {"name", "every": ms, "count"}}` | screenshots every `every` ms, plus `<name>-strip.png` |
| `{"wait": ms}`, `{"settle": true}` | move the clock (settle: 6 s) |
| `{"pill": "Scatter"}` | click a pill (a tab) by its name |
| `{"clickText": "North"}` | click text inside the visual (labels, Back, crumbs) |
| `{"clickMark": i, "ctrl": true}` | click the i-th mark (negative counts from the end) |
| `{"dblclickMark": i}`, `{"contextMark": i}`, `{"hoverMark": i}` | double-click, right-click, hover a mark |
| `{"click": [x, y]}`, `{"dblclick": [x, y]}`, `{"drag": {"from": [x, y], "to": [x, y]}}` | at a point in the visual |
| `{"clickSelector": "css", "index": n}` | click an element (Deneb marks: `path[aria-roledescription='bar']`) |
| `{"focus": ".kit-svg"}`, `{"key": "ArrowRight", "times": 3}` | keyboard |
| `{"objects": {...}}` | new formatting pane values (a format update) |
| `{"highlight": {"Region": ["East"]}}`, `{"filter": {...}}` | cross-filter coming in (null clears) |
| `{"resize": [w, h]}` | a new viewport |
| `{"bookmark": "save <name>"}`, `{"bookmark": "apply <name>"}` | what a bookmark keeps (filterState properties, the visual's filter, its selection) and restoring it |
| `{"reopen": true}` | a new visual instance with what the report saved (closing and reopening the report) |
| `{"tap": [x, y]}`, `{"tapText": "By team"}`, `{"swipe": {"from", "to"}}`, `{"pinch": {"at", "scale"}}` | touch (scenario `mobile: true` or `touch: true`) |
| `{"click3d": "Site 05"}`, `{"hover3d": "Site 10"}` | a 3D object by name (the visual's `kitProject`) |
| `{"perf": ms, "mode": "orbit"}` | frames a second while the visual moves in real time (`mode`: what the visual's `kitPerf` drives, such as `orbit` or `fly`; scenario `realtime: true`): report.json `perf` with `fps`, `slow` (share of frames over 50 ms, the ones that look frozen) and `worst` (ms) |
| `{"measure": {"click3d": "Site 05"}, "ms": 1200}` | the same numbers while a click (`click3d`, `clickText`, or `clickSelector` with `index`) plays out in real time: works on any build, so before / after compare |
| `{"profile": {"clickText": "Tree"}, "ms": 1500}` | Chrome's sampling profiler while the click plays out: report.json `profile`, the top functions by own time in ms (`(program)` is the browser drawing) |
| `{"transition": {"clickText": "North"}, "name": "open", "ms": 700, "every": 25}` | a screen change frame by frame on the frozen clock: the ink (area of every drawn shape and text times its effective opacity) at each step; check with `noBlank` |
| `{"markMoves": "name"}` | remember how many morphs and entrances the visual has run (its `kitMoves`); check with `movesSince` |
| `{"probe": "js expression"}` | evaluate in the page and record the value in report.json `probes` (debugging) |
| `{"expect": {...}}` | checks: `selectCalls`, `minSelectCalls`, `lastMulti`, `lastSelectCount`, `clears`, `contextMenus`, `tooltips`, `fetchMore`, `marks`, `text`, `noRenderFailures`, `renderEvents` |

Checks also take `persisted` (saved state), `filterValues`, `lastFilterSize`, `filterRemoved`, `camera` (zoomed or
not), `ariaLabels`, `pill` (which pill is on), `selectorText` ({css: text}: exactly one element matches and shows the
text, such as the panel row lit for the floor under the pointer), `tooltipFields` (the last tooltip's field names, in
order), `state` (values from the visual's `kitState()` debug hook) and `noOverlap` (the headline, each item of the
Back / pills row, panels and visible labels never overlap; labels clipped under the header don't count) and `minTextPx` (every visible text, at the size it is drawn after
zoom, is at least that many pixels), `noBlank` (a named `transition` never fell below `minInk`, default 0.6, of
the screens it joins), `movesSince` ({mark, max}: no more morphs since a `markMoves`) and `smooth` ({longest, frozen}: the last `perf` / `measure` had no frame over
`longest` ms and under `frozen` % frozen frames).

Scenario switches: `emptyFirst` (default true: an empty update first, as Desktop sends while loading), `roundTrip` (ms Desktop takes to send the rows again after the visual's filter or save; default
400, as measured in Desktop: the visual must keep moving through it), `mobile` (phone: touch and a mobile user agent), `touch`, `webgl` (SwiftShader so WebGL works
headless), `noWebgl` (WebGL off: a visual's fallback), `realtime` (no frozen clock: frame rates), `highContrast`,
`reducedMotion`.

Every run also checks: no page errors and no network requests.

Determinism: the clock is installed and paused, so only `wait`, `settle` and `frames` move time (Playwright's
installed clock otherwise keeps flowing in real time, and a slow step would let an animation finish early). Physics
layouts start from half-pixel positions and are settled once per view, so goldens are the same run after run.
