# App visuals (v1.11)

Design note for teaching pbik to build reports that feel like an app: visuals that animate and morph between views,
zoom into an item, switch views with pills, select ranges and update their own headline, plus the page polish around
them. Later rounds: network/org layouts and 3D. A general kit capability: we learn techniques from Microsoft Learn, the
Power BI visuals SDK docs, Microsoft's MIT-licensed open-source visuals and the Deneb / Vega-Lite docs; we never copy
any creator's visuals, code, names or designs.

Status: step 1 (install and prove). Steps 2-6 below are the plan; each section says what is built and what is planned.

## 1. What "app-like" means for the kit

A page feels like an app when the visuals behave like one screen, not a set of charts:

| Move | What the person sees |
| --- | --- |
| Morph | the same items rearrange (grid, columns, scatter) instead of the chart being redrawn |
| Zoom | click an item to zoom in, Back or a breadcrumb to zoom out; the camera moves, nothing jumps |
| Pills | view switches inside the visual, no bookmarks or extra pages |
| Range select | drag a span; the rest of the page filters to it |
| Live headline | a sentence that says what the current view or selection shows ("North holds 14% of sales") |
| Focus | the selected items stay strong, everything else dims |
| Page polish | KPI cards with a mini chart, progress bars with a hatched forecast, pill tabs, a context strip |

The app-visual base is a **toolkit, not a template** (the person's requirement, 2026-11-16): no creative ceiling.

- **Drawing layers**: SVG, Canvas and WebGL in the same visual, chosen per element (Canvas or WebGL for thousands of
  animated items, SVG for text, focus rings and anything a screen reader needs).
- **Free-form layout**: shapes, cards, panels, text, images and icons placed anywhere, not only chart axes; several
  views or screens inside one visual with navigation between them.
- **Animation engine**: transitions, staggering, sequencing, easing, enter and exit effects, physics (d3-force),
  camera-style zoom and pan. Every move respects reduce-motion (the visual's own switch and the operating system's
  `prefers-reduced-motion`): it jumps to the end state.
- **Everything from the formatting pane and the theme**: colours, fonts, sizes, spacing, corner radius, shadows,
  motion speed and easing, labels. Defaults come from the report theme (which the kit makes from design/tokens.json);
  nothing is hard-coded.
- **Bundled assets**: fonts (Inter, OFL-1.1), icons the kit draws itself, shapes and GeoJSON / TopoJSON maps
  (world-atlas, us-atlas: Natural Earth / Census data, ISC). No network.
- **Data**: fetch more rows (`fetchMoreData`, up to the SDK's segment limit), hierarchies and drill
  (matrix data view, `drilldown` in capabilities), not just flat tables.
- **Interactions**: click, multi-select (Ctrl), hover, drag, brush, zoom, keyboard, context menu, and cross-filter in
  both directions (selection manager out, `filter` / highlight in).

## 2. Build routes

pbik picks the first route that delivers the look and the interaction, in this order (extends CLAUDE.md's
visual-method ladder: the ladder steps stay, the new routes slot in):

| Order | Route | Ladder step | When it wins | Certified / IT |
| --- | --- | --- | --- | --- |
| 1 | native | 1 | a native visual does it | nothing to approve |
| 2 | native + formatting / theme | 1 | formatting, conditional formatting or the theme closes the gap | nothing |
| 3 | SVG measure | 2 | an inline picture in a card or table cell (KPI mini bars, bullet bars, pills) | nothing |
| 4 | HTML visual (HTML Content) | 4 | static rich text or layout no native visual can draw | uncertified AppSource visual |
| 5 | Deneb (Vega-Lite) | 3 | a custom chart with click-to-filter and tooltips; no build per chart | certified AppSource: most likely allowed at work |
| 6 | kit custom visual (.pbiviz) | 4 | animation between views, or app-like interaction Deneb can't do | private visual: IT approval |

- **Route switches** (planned, step 5): design/specs/project.json `routes: {html: true, deneb: true, customVisual: true}`.
  A tenant that blocks one route turns it off; pbik then plans the next route down and builds each visual's recorded
  fallback (as `customVisuals: false` already does for Deneb today, which stays as the switch for both).
- Every route above native keeps CLAUDE.md's rules: say what native option was tried, record `build.nativeTried`,
  `build.reason` and the fallback register row, and ask before building it.
- Every kit custom visual also names a native or SVG fallback, like Deneb.

## 3. The toolchain (built in step 1)

Installed by the agent, **no admin rights**, into the kit tools folder **outside the repo**:
`%USERPROFILE%\.pbik-tools` (or the folder in `PBIK_TOOLS`). Not `%LOCALAPPDATA%`: apps installed from the Store (the
Claude desktop app is one) see a private, redirected copy of AppData\Local, so tools installed there from the chat are
invisible to Desktop and to a normal terminal (found in step 1).

Pins in the repo, nothing else: `tools/appvisuals/lock.json` (Node, Deneb, the Microsoft sources, Playwright's
Chromium, Three.js recorded only; each with its sha256), `tools/appvisuals/package.json` (exact versions) and
`package-lock.json` (the whole npm tree). `pbik tools install` refuses a download whose checksum doesn't match.

| Item | Version | Licence | Purpose |
| --- | --- | --- | --- |
| Node.js LTS (portable zip, nodejs.org, SHASUMS256 checked) | 26.13.1 (Lithium) | MIT | runs the build tools |
| powerbi-visuals-tools (pbiviz) | 7.2.1 | MIT | builds .pbiviz |
| TypeScript, powerbi-visuals-api, eslint, eslint-plugin-powerbi-visuals, typescript-eslint | 5.9.3, 5.11.0, 9.39.5, 1.1.1, 8.73.0 | Apache-2.0 / MIT | code and certification-style checks |
| D3 | 7.9.0 | ISC | drawing, transitions, d3-force |
| Power BI visuals utils (formatting model, tooltips, colours, data view, ...) | 6.x (package.json) | MIT | formatting pane, tooltips, theme colours |
| Vega, Vega-Lite, vega-embed | 6.4.0, 6.4.3, 7.1.0 (Deneb 2.0.1.0's own) | BSD-3-Clause | harness renders Deneb specs offline |
| Inter font, world-atlas, us-atlas, topojson-client | 5.3.0, 2.0.2, 3.0.1, 3.1.0 | OFL-1.1 / ISC | bundled fonts and maps |
| Microsoft Dot Plot source (microsoft/powerbi-visuals-dotplot @ e56f099) | 2.1.3.0 | MIT | base for the unit/dot chart and the app-visual starter |
| Microsoft Force Graph source (microsoft/PowerBI-visuals-ForceGraph @ 22ab914) | 3.0.3.0 | MIT | reference for d3-force and drag (network round) |
| Deneb .pbiviz (GitHub release; sha256 matches GitHub's digest) | 2.0.1.0 | MIT | offline copy; reports use AppSource Deneb |
| Playwright + Chromium | 1.63.0, chromium 1243 (reused) | Apache-2.0 | harness screenshots and recordings |
| Three.js | 0.187.0, recorded only | MIT | 3D, later round |

Microsoft's sample bar chart (PowerBI-visuals-sampleBarChart) has no licence file, so it is not used.

Commands (built): `pbik tools check [--json]` (installed / missing / wrong version and a one-line fix per item;
`pbik status` and tools/doctor.ps1 report it in plain words), `pbik tools install [--only ...]`, `pbik tools run
<pbiviz|eslint|tsc|node|npm|playwright> ...` (the kit's Node, no PATH changes).

Step 1 facts about the toolchain:
- pbiviz looks for powerbi-visuals-api in the visual's own `node_modules`; without it, it runs `npm install` there
  (which pulled in the Dot Plot's test tools and a browser download). The kit links the visual's `node_modules` to the
  shared one (a directory junction, no admin) and builds in `<tools>\builds\<visual>`, never in the repo.
- `pbiviz package` still tries to make a developer certificate (and fails quietly without `pwsh`); no certificate is
  needed or kept. The build command will turn this off.
- `pbiviz package --certification-audit` on the Dot Plot: lint clean, "No external requests found in the visual".
- `npm audit`: 4 moderate advisories, all in pbiviz's dev-server branch (`uuid` < 11.1.1 through `sockjs` and
  `webpack-dev-server`). The kit never runs the dev server (`pbiviz package` only), so they don't reach a visual.

## 4. Folder layout and commands (built in step 2)

| Where | What |
| --- | --- |
| `tools/appvisuals/` (repo) | pins (above); `template/` the app-visual starter (TypeScript + D3, from the Dot Plot, NOTICE.md); `harness/` the offline fake host (README.md lists every step); `deneb/` the Deneb starter spec and its test |
| `docs/patterns/app-visuals/` (repo, step 3) | "Use when" pages and reusable modules (morph, unit chart, drill zoom, pills, range select, headline, focus) |
| a project's `visuals/<name>/` | that visual's source, made by `pbik visual new` (committed with the project), with `test/*.json` harness scenarios |
| a project's `design/deneb/<name>.vl.json` | a Deneb chart's spec and `<name>.test.json` |
| `<tools>\builds\<hash>-<name>\` | the build copy, the `node_modules` junction, `dist\*.pbiviz`, `harness\visual.js/.css`, `kit-build.json` (never in the repo) |
| `_snapshots/visuals/<name>/<scenario>/` | harness screenshots, frame strips, report.json (git-ignored) |
| the report's `CustomVisuals\<guid>\` and report.json | the registered private visual, as Desktop stores one (section 5) |

Commands (`pbik visual ...`, the agent runs them):

| Command | Custom visual | Deneb chart |
| --- | --- | --- |
| `new <name> [--deneb]` | copies the template, gives it its own id (`pbik<Name><6 hex>`) | copies the starter spec and its test |
| `build <name>` | copies to the tools folder, links the shared packages, bundles the Inter font, runs `pbiviz package --certification-audit` (lint, external-requests audit) and the kit's bundle checks (no eval / new Function / fetch / XHR / WebSocket / dynamic import / external font; web addresses listed) | compiles the spec with the pinned Vega-Lite and runs pbik's spec checks (no url data or images) |
| `test <name> [--scenario f] [--record]` | the harness on the built bundle | the harness with Vega-Lite |
| `add <name> --report R [--layout L --id --page --box --bind Role=Field ...]` | registers the package in the report; with `--layout`, adds a `type: "custom"` entry with a table fallback | adds a `type: "deneb"` entry (cross-filter, tooltips, context menu on) with a table fallback |
| `refresh <name>` | the kit runtime (`src/kit`) from the template | - |
| `list [--report R]`, `remove <name> --report R` | builds and where each is used; unregisters one no page uses | - |

`pbik build` places `type: "custom"` visuals (`custom: <name>`, the visual's own role names in `bindings`): the
visualType is the built visual's id, and the package is registered on every build. `--no-custom-visuals` (or
project.json `customVisuals: false`) builds the fallback in the same folder, as for Deneb.

### The app-visual template (`tools/appvisuals/template`)

`src/kit/` is the toolkit, `src/visual.ts` the starter that uses it (a unit chart: one dot per row, grid by group and
stage, columns by stage, scatter by X and Y, clusters with physics).

| Module | What it gives every kit visual |
| --- | --- |
| `settings.ts` | formatting pane cards: Colours (accent, panel, text, by group, dimmed opacity; empty = theme), Text (font, sizes), Layout (padding, gap, corner radius, shadow, mark size), Motion (animate, duration, easing, stagger, reduce motion), Views (start view, pills, headline, labels, order, most items drawn), Interaction (tooltips, brush, zoom) |
| `theme.ts` | colours from the report theme (`colorPalette`), high contrast (foreground / background / selected only, strokes instead of transparency) |
| `motion.ts` | one tween for every layer: duration, easing, per-item stagger (capped), enter grow-in and exit shrink-out, colour blends, sequences, number tweens (camera, counters), d3-force physics settled to a target layout; reduce motion (pane switch or the system setting) jumps to the end |
| `layers.ts` | a WebGL canvas, a 2D canvas, an SVG layer and an HTML layer in one visual; marks pick SVG up to 600, Canvas up to 8,000, WebGL above (Canvas when WebGL is missing); one camera for all |
| `data.ts` | records from a categorical data view (fields by role, a selection id per row, highlights), fetch more data up to a limit, a tree from a matrix data view with selection ids (drill / expand), a stable hash instead of `Math.random` |
| `interaction.ts` | click, Ctrl / Shift / Cmd-click, clear on background, context menu, host selection callback (bookmarks), hit tests for every layer, hover tooltips, brush to select a range, wheel / Shift-drag zoom and pan, arrow-key focus with a live region; nothing bound when the host doesn't allow interactions |
| `scene.ts` | free-form HTML: pills (tablist), cards (clickable, keyboard), text, kit icons; screens with a back stack, Back and a breadcrumb; No data / Too many points / Loading states |
| `icons.ts` | the kit's own stroke icons (24 x 24) |
| `fonts.ts` | Inter registered from memory (`FontFace`), filled in at build time |

Strings are in `stringResources/en-US/resources.resjson` (localisation). Certification-style rules the template keeps:
no `innerHTML`, no `Math.random`, no network, no `eval`, everything bundled; `pbiviz package` lists no missing
recommended feature.

## 5. How PBIP stores each kind

- **Deneb (AppSource)**: known from a Desktop save (Patterns page, 2026-10-24; .claude/rules/pbik.md): `visualType`
  `deneb7E15AEF80B9E4D4F8E12924291ECE89A`, fields on the `dataset` role, the spec as one string in
  `vega.jsonSpec`, and report.json `publicCustomVisuals`. Re-checked in step 1 with Deneb 2.0.1.0 (Desktop save,
  2026-11-16): Desktop now also saves `developer.version` '2.0.1.0' and `vega.version` '6.4.3' (Vega-Lite), and fits
  `stateManagement.viewportHeight` under the title; everything pbik wrote stayed.
- **Deneb cross-filter**: off by default. Deneb's own capabilities (2.0.1.0) and its docs (deneb.guide,
  "interactivity-selection"): `vega.enableSelection` (bool), `selectionMode` simple / advanced, `selectionMaxDataPoints`
  (default 50, 1-250); in Deneb's editor it is Project setup > Cross-filtering > "Expose cross-filtering values for
  dataset rows", not the Format pane. In simple mode Deneb watches mark clicks itself and gives each row a
  `__selected__` field (`on`, `off`, `neutral`) that the spec styles; Vega-Lite `params` are not what filters the page.
  The Literal form pbik writes for it is checked in Desktop at the step 2 pause (click a bar, the table filters, a save
  keeps it).
- **Private .pbiviz**: Microsoft Learn ("Power BI Desktop project report folder", updated 2026-09-29) says only private
  visuals go into the report's `CustomVisuals\` folder; the report schema 3.3.0 has resource package type
  `CustomVisual`. The Desktop save in step 1 (import from file, placed with Region and Total Amount, saved) shows the
  exact form: the .pbiviz unzipped into `CustomVisuals\<guid>\` as `package.json` and
  `resources\<guid>.pbiviz.json` (the same JSON as in the package, re-indented with CRLF), and one report.json
  `resourcePackages` entry `{"name": "<guid>", "type": "CustomVisual", "items": [{"name": "<guid>.pbiviz.json",
  "path": "<guid>.pbiviz.json", "type": "CustomVisualMetadata"}]}`. The visual.json has `visualType` = the guid and the
  visual's own role names in `queryState` (Category, Values for the Dot Plot); Desktop added a default sort. No
  `CustomVisualJavascript` or CSS items: the script stays inside the .pbiviz.json.
- **Organizational visuals**: report.json `organizationCustomVisuals` (`name`, `path`, `disabled`); the visual itself is
  deployed by the tenant admin.

## 6. Risks

| Risk | What the kit does |
| --- | --- |
| The tenant blocks uncertified (SDK) visuals, or all custom visuals | route switches; every custom visual has a native or SVG fallback |
| A private visual isn't certified: no PDF / PowerPoint export or email subscription in some cases | pages marked `exported` build native or Deneb only; validate warns (the export rule, below) |
| The visual is the kit's code to maintain (SDK and Desktop updates) | pinned toolchain; /smoke and the harness after each update; build from the template, not per-visual forks |
| Performance with thousands of animated items | Canvas / WebGL layer, `fetchMoreData` limits, the "Too many points" state |
| Accessibility of drawn content | keyboard focus, high contrast mode, reduce-motion, alt text on the container, an SVG layer for what a screen reader needs |
| Supply chain (npm) | exact pins and a lockfile, checksums on every download, `--ignore-scripts`, `npm audit` recorded, MIT / ISC / BSD / Apache / OFL only |
| Deneb on AppSource updates itself | the harness pins Deneb 2.0.1.0's Vega versions; /smoke after an update |

## 7. What IT would need to approve at work

1. **Node.js** (portable zip, no installer, no admin) and **npm registry access** (registry.npmjs.org or a company
   mirror) on the developer's machine, for building visuals. Not needed by report viewers.
2. **Deneb**: the certified AppSource visual. Tenant setting "Allow visuals from AppSource" (or Deneb added to the
   organizational store). Most likely to be allowed.
3. **Kit custom visuals** (private .pbiviz), one of:
   - the tenant setting that allows visuals created with the Power BI SDK (uncertified) for the report's authors; or
   - better: the admin deploys each kit visual to the **organizational store** (reviewed once, versioned, can be
     turned off centrally). The kit's build gives IT the certification audit output (no external requests), the lint
     result and the licence list for that review.
4. **Playwright / Chromium** run only on the developer's machine for screenshots; nothing is sent anywhere.
5. Nothing in a visual calls the network, uses eval or loads fonts or scripts from a CDN.

At the maintainer's workplace (confirmed 2026-11-16) self-built custom visuals and Node.js are already allowed on work
machines, so for the work merge the HTML, Deneb and kit custom-visual routes all default to on; the route switches
(step 5) are for other tenants.

Desktop check after step 2 (2026-11-16, the scratch report, Desktop 2.159.1231.0): the kit starter drew from the
model's data, and clicking worked both ways, the starter and the Deneb chart (with `deneb.interactivity` as pbik
wrote it) filtering the page. A save round-trip of the Deneb switches is still to do (step 4).

## 8. Round 2: the later rounds brought in (2026-11-17)

### What every kit visual now does (template `src/kit`)

| Feature | How | Checked |
| --- | --- | --- |
| Bookmarks and saved state | `state.ts`: view, drill and camera in the `state` object, every property `"filterState": true` (Learn, "Add bookmark support"), written with `persistProperties` (debounced) and read back on update; selection restored by `registerOnSelectCallback` | harness `state` scenario: save, apply two bookmarks, reopen |
| Filter mode | `filter.ts`: Interaction > Clicks = Filter applies a BasicFilter (`applyJsonFilter`, powerbi-models MIT) on Item, Group or Stage, read back from `jsonFilters`; `supportsSynchronizingFilterState` for sync slicers | harness `state` scenario (values, multi, remove); sync slicers across pages: Desktop click list |
| Report page tooltips, drill-through | tooltips declare `canvas: true` and pass the item's identity; right-click opens Power BI's context menu with the identity (drill-through targets appear there) | Desktop click list |
| Rendering events | `renderingStarted` / `renderingFinished` / `renderingFailed` on every update; a failure is also written in the visual | harness `renderEvents` |
| Landing screen | No data state naming the fields to add (`supportsLandingPage`) | harness `nodata` per visual |
| Touch and phone size | taps select; a horizontal swipe switches the view; two fingers pinch-zoom; the brush is mouse-only | harness `phone` (360 x 600, touch) |
| Screen reader | SVG marks get `role="option"`, `aria-label` and `aria-selected`; Canvas / WebGL marks are read through the focus and the live region; cards, pills, rows and states have names | harness `ariaLabels` |
| First frame is final | the first draw and every resize show the end state at once (Motion `to(..., instant)`); only the person's changes and new data animate | harness `resize` scenario (1 x 1, then full size, golden with no waiting) |
| Visual regression | `"golden": true` on a shot compares it with `test/golden/<scenario>/<name>.png`; `pbik visual test --update-golden` accepts a new look; `pbik visual refresh` rebuilds and fails on an unexpected change (proved by shrinking the dots in the template) | all five visuals: 21 scenarios stable across runs |
| IT handoff pack | `pbik visual handoff <name>` writes `visuals/<name>/handoff/`: README (id, size, API, privileges, network audit, lint, kit checks, data roles, settings, saved state, licences of every imported package, version notes), icon, golden screenshots, NOTICE, the package | `deal-dots` pack |
| Polish score | a card and its image card count as one tile ("crowded"); headline and context-strip cards aren't numbers | Deals page 7 -> 8 |

### D3 extras and new patterns

- flubber 0.4.2 (MIT, unmaintained since 2018): shape morph, used by the map's Map <-> Bubbles (map.md, morph-layouts.md).
- topojson-client 3.1.0 with us-atlas states-albers-10m (ISC, pre-projected): the map pattern, no network (map.md).
- d3-flextree 2.1.2 (WTFPL) on d3-hierarchy: the org chart (network-org.md). WTFPL is permissive; some legal teams
  don't accept it, so it is named in the handoff pack.
- elkjs: **not installed** (removed 2026-11-17, the maintainer's decision). Flow and layered layouts are a possible
  later add; elkjs is EPL-2.0 or GPL-3.0 (weak copyleft), so IT or legal approves it first. 0.12.1 was measured
  before removal: 1.6 MB, no eval or new Function.
- Three.js 0.187.0 (MIT): the 3D pattern (3d-scene.md). Imported class by class: the site-blocks package is 245 KB
  (865 KB of script). Harness frame rate with software WebGL: 20 / 14 a second (24 sites / one open); Desktop with a
  GPU is to be checked. deck.gl not installed (luma.gl engine, geospatial focus, a second WebGL stack).

### Smooth clicks in Desktop (second review, 2026-11-17)

Measured in Desktop with the frame meter (kit/perf.ts), on the proof pages:

- Most of a click's freeze isn't the visual's own code: when a filter or a saved view arrives, Power BI re-draws the
  rest of the page (cards, tables, other visuals) on the thread the animation runs on. The kit sends filters after
  the move lands and saved views 1.5 s later, so the page catches up when nothing is moving.
- Kit visuals did real work on updates that brought nothing new (their own filter or save coming back): re-reading
  rows, re-running physics (up to 258 ms), rebuilding the map's shape morphs, and resizing (wiping) canvases. The
  update gate and the caches remove it.
- A click filter also filtered the slicers on the page; pbik build now writes NoFilter from kit visuals to slicers.

The before / after tables are in the review notes; the meter stays in every kit visual, off by default.

### Export, mobile and hidden pages

- Microsoft's FAQ: export to PDF and PowerPoint is a feature certified visuals keep; private visuals aren't
  certified. So **kit custom visuals aren't expected in PDF / PowerPoint exports or email subscriptions**; Deneb
  (certified) is. **Export rule (the maintainer's decision, 2026-11-17): a page that is exported or subscribed is
  marked `exported: true` in layout.json; on it pbik builds native or Deneb only (every kit visual as its fallback)
  and `pbik validate` warns on any private or uncertified custom visual left there.** /plan asks which pages are
  exported or subscribed. Desktop's own Export to PDF is on the click list; the Service and the
  mobile app need publishing and weren't checked here.
- Desktop doesn't run animation frames for a page that isn't in front: a screenshot of such a page caught the org
  chart before it laid out. Every kit visual now draws its final state on the first update and on every resize.
  One open item: Desktop's first capture of the People page right after opening, before the fix proved it on a
  second capture, still showed the org chart blank once; the PDF export check covers it.

### Harness changes

Bookmarks, reopen, touch (tap, swipe, pinch, phone size), WebGL on and off, 3D clicks by name, real-time frame
rates, probes, golden screenshots. Determinism fixes found on the way: the installed clock is now paused (it kept
flowing in real time, so a slow step let animations finish early), physics starts from half-pixel positions, and
cluster layouts are settled once per view.
