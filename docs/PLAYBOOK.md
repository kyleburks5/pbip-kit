# Playbook

How the kit works, step by step. For the commands in order, see [QUICKSTART.md](QUICKSTART.md).

Contents: [Workflow](#how-the-workflow-works) · [Commands](#the-commands) · [Visual-method ladder](#the-visual-method-ladder)
· [pbik](#pbik) · [Themes and patterns](#themes-and-patterns) · [DAX Lib](#dax-lib) · [Lessons](#the-lessons-system)
· [Git](#git-habits) · [Updates](#the-update-routine) · [Troubleshooting](#troubleshooting) · [Scripts](#scripts)
· [Glossary](#glossary)

## How the workflow works

One report project goes through the same loop:

```text
/brd  ->  /model  ->  /model approved  ->  /plan  ->  /build approved  ->  /review  ->  /fix  ->  /review ...
 you       you check    the model is      you check    report files      screenshots   fixes
 review    the list     applied           the          built and         and audits    and re-checks
 brd.md                                   wireframe    validated
```

Ideas behind it:

- **Files, not clicks.** The report (PBIR) and the model (TMDL) are plain files. The assistant writes them on disk;
  Desktop opens them. Everything is under Git, so every step can be compared and undone.
- **One source for the report.** `design/specs/layout.json` holds every visual: position, fields, styling, filters,
  actions. The wireframe, the build and the audits all read it. To change the report, change layout.json and
  rebuild. There is no hand-written build code.
- **Stable visual IDs.** Every visual has an ID `P<page>-V<nn>` (P1-V04: page 1, visual 4). The ID is used in the
  wireframe, the spec, the review, the fix notes and the visual's folder name. An ID is never reused; a removed
  visual's ID goes to `retired`. IDs are numbered in reading order, so tab order follows.
- **Three approval gates.** You approve `brd.md` after `/brd`, the model list at `/model`, and the wireframe before
  `/build approved`. Nothing changes the model without your approval.
- **Grid and tokens.** Pages are 1920 x 1080 with a 32px margin and a 12-column grid with 24px gutters. Colours,
  fonts and spacing come from `design/tokens.json`, never typed into a visual.
- **Accessibility is checked.** Every data visual and image has alt text, text meets WCAG 2.1 AA contrast in every
  state, no text is below 10pt, and tab order follows reading order. `pbik validate` warns on each.
- **Aggregates only.** The assistant sees counts, sums and other totals, not rows, unless row-level access is cleared
  in `docs/it-security.md`.

### Audit modes

The numbers audit compares each key value in the report with a recompute from the raw columns. `/model` measures the
data and recommends a mode:

| Mode | When |
| --- | --- |
| full | the data is small enough to recompute every key value in every state |
| sampled | too large for that: a sample of states and members |
| aggregate-only | row-level access isn't cleared: totals only, no row export |

The thresholds and what each mode keeps are in [lessons/audit-modes.md](lessons/audit-modes.md).

## The commands

In Copilot, each command starts with `kit-` (`/kit-plan`). The command files are in `.claude/commands/`.

### `/brd <brief>`

- **Reads:** your brief, `design/reference/brd-template.md`, `docs/it-security.md`, references in
  `design/reference/`, and the file names and sizes in `data/` (not the rows).
- **Produces:** `design/reference/brd.md`, with guesses marked "confirm" and unknowns marked "open".
- **Done when:** you have answered every open and confirm item and approved brd.md. Stops if the data isn't public
  and not cleared.

### `/model` and `/model approved`

- **Reads:** brd.md, the raw tables loaded in the open Desktop, `docs/lessons/dax.md`, `docs/lessons/audit-modes.md`.
- **Produces (`/model`):** a profile of every table (row counts, keys, blanks, timings), an audit mode, and one
  approval list: cleaning, relationships, a date table, base measures, formats, any DAX Lib packages. Changes nothing.
- **Produces (`/model approved`):** the model applied through the Modeling MCP, the TMDL on disk,
  `design/reviews/model-check.md`, the Desktop version in `design/specs/project.json`, brd.md section 8, a commit.
- **Done when:** `pbik model check` passes and one DAX query returns a value for every new measure. Then save in
  Desktop.

### `/plan <design brief>`

- **Reads:** brd.md, the model (look only), tokens, `design/reference/layout-schema.md`, known gaps, checks,
  lessons, and any wireframe or reference image in `design/reference/`.
- **Produces:** a "Design ambition" table at the top of `design/specs/spec.md` (per key number: baseline, normal,
  exceptions, partial or stale), the colour tokens and theme, `design/specs/layout.json`, the wireframe in
  `design/wireframes/wireframe.html`, the rest of the spec (native visual, done-when line, build order, fallback
  register, by visual ID) and `design/specs/audit.json`.
- **Done when:** `audit_ids.py` and `check_contrast.py` pass (0 fail), and you approve the wireframe.
- With a reference, the reference is the layout source (`ref_layout.py`); what Power BI can't reproduce is listed by
  visual ID. Without one, the layout comes from brd.md and the high-fidelity wireframe is drawn with real
  aggregates (groups under 5 hidden).

### `/theme <brand colours, reference or preset>`

- **Reads:** your colours, a reference in `design/reference/`, or a preset in `design/themes/presets/`.
- **Produces:** `design/tokens.json`, the theme in `design/themes/`, and `design/reviews/theme.md` (every colour that
  moved to pass AA, from and to).
- **Done when:** every text and state passes WCAG 2.1 AA, and the wireframe contrast check prints 0 fail. `/plan`
  runs the same step; use `/theme` to change colours on their own.

### `/build approved`

- **Reads:** layout.json, tokens, the spec's done-when lines, `design/checks.md`, `.claude/rules/pbik.md`,
  `.claude/rules/svg.md` and the build lessons.
- **Checks first:** `pbik project check`; it stops when Desktop is newer than `targetDesktop` (run `/update`).
- **Produces:** the report files (`pbik build`), `design/specs/visual-map.json`, a commit, and a numbered Desktop
  click list.
- **Done when:** a second `pbik build` prints "No changes", `pbik validate` passes, and `audit_layout.py`,
  `audit_ids.py` (and `audit_svg.py` for SVG measures) pass. It stops if the model needs a change beyond the
  approved list, a new fallback is needed, or something can't be expressed in layout.json (a "pbik gap").

### `/review`

- **Reads:** the open report (screenshots through the Desktop Bridge), the wireframe, the spec, `design/checks.md`,
  `design/specs/audit.json`.
- **Produces:** `design/reviews/review.md` (one ranked table: ID, item, severity, what is wrong, likely cause,
  fixable or tooling limit), `design/reviews/audit.dax`, and the fidelity check in `design/reviews/fidelity/`.
- **Done when:** every visual has been checked against its done-when line and the numbers audit has run. It fixes
  nothing.

### `/fix [items]`

- **Reads:** review.md (high and medium items by default, or the IDs you name) and the lesson file for each topic.
- **Produces:** layout.json changes, a rebuild, a reload, new screenshots, an updated spec and known gaps, proposed
  lessons, a commit.
- **Done when:** each fixed item meets its done-when line, up to two rounds. Lessons wait for your approval.

### `/validate`

The numbers audit on its own, look only: each key value recomputed from the raw columns, compared with the model's
measure and what the report shows, including the first year, the empty case and divide-by-zero. One table: ID,
value, expected, model, shown, status.

### `/smoke`

After any tool or plugin update. Builds one card, one button slicer and one table on a `_smoke` page
(`design/scripts/smoke.py`), and you check them in Desktop. Records the versions and the result in VERSIONS.md.

### `/update`

After a Power BI Desktop update. Runs [UPDATE-ROUTINE.md](UPDATE-ROUTINE.md): record the version, the regression
suite, `/smoke`, new visuals or settings through the Patterns page, harvest and refresh the catalog, propose a
release.

### `/wrapup`

At the end of a report, after the last `/fix` is approved. Lists the lessons the report produced with where each goes
by the placement order ([lessons/README.md](lessons/README.md)) and the CLAUDE.md rules a new check now enforces,
writes them, shows the diff and waits for your approval; then runs the tests and the regression suite and commits.

## The visual-method ladder

`/plan` picks the lowest step that meets the design, and records `build.method`, `build.step` and `build.reason` for
each visual in layout.json. `audit_ids.py` checks the step matches the method.

| Step | Method (`build.method`) | Use it for | Rules |
| --- | --- | --- | --- |
| 1 | `native`: a built-in Power BI visual or setting, including the page background | almost everything | the default |
| 2 | `svg-measure`: a DAX measure that returns an SVG image, or a static SVG image | what no native visual draws, such as status pills or dumbbells in a table | a DAX Lib package first (DaxLib.SVG), then new SVG code; `.claude/rules/svg.md` |
| 3 | `deneb`: a Vega-Lite spec in the certified Deneb visual | bespoke charts native and SVG can't draw | always has a native or SVG `fallback`; no `url` data; [custom-visuals.md](custom-visuals.md) |
| 4 | `custom-visual` or `html-measure`: any other .pbiviz or HTML Content | last resort | needs an IT check (`build.itCheck`); the kit has no tooling to build one |

Before any step above 1, the assistant tells you which native option it tried and why it fails, records it in
layout.json (`build.nativeTried`, `build.reason`) and in the spec's fallback register, and asks you first. Fallback
work stays in place but unused until the native option is confirmed everywhere.

Where custom visuals are blocked, set `"customVisuals": false` in `design/specs/project.json`: `pbik build` then builds
each Deneb visual's fallback.

## pbik

pbik is the kit's only report tool. It needs only Python's standard library. Run it from the project root:

```bat
python tools\pbik\pbik.py <command>
```

Or install it once (`pip install --user -e tools\pbik`) and type `pbik <command>`. The full reference, with every
layout key, is [tools/pbik/README.md](../tools/pbik/README.md).

| Command | Does |
| --- | --- |
| `build <Report> design\specs\layout.json` | Creates or updates pages and visuals by ID. Writes only what changed; a second run prints "No changes". `--prune` removes retired visuals; `--reset` rebuilds from templates (Desktop changes inside ID'd visuals are lost: ask first); `--no-custom-visuals` builds the fallbacks |
| `validate <Report> --layout design\specs\layout.json` | Schema checks and kit rules: IDs, page targets, filter types, SVG `%`, fields in the model, Deneb specs, bookmarks, slicer fit, accessibility, target Desktop, the settings catalog. `--port auto` reads slicer items from the open model |
| `model check <Model>.SemanticModel` | Descriptions, format strings, broken references, relationships, DAX Lib functions |
| `info <Report>` | Pages and visuals by ID, type, position and fields |
| `theme apply <Report> <theme.json>` | Registers and applies a theme |
| `measure ext add / list / remove <Report> ...` | Report extension measures (for SVG images) |
| `resource add <Report> <image>` | Registers an image once |
| `templates harvest <Report>` | Copies the Patterns page's visuals to `design/templates/` |
| `catalog refresh / show / list` | The settings catalog: what Desktop has saved, per visual type |
| `roundtrip <Report>` | After a Desktop save, lists what Desktop rewrote, by visual ID (read only) |
| `schemas fetch <Report>` / `schemas support` / `schemas lower <Report>` | The schema cache; schema versions by Desktop release; lower a report's schemas for an older Desktop |
| `project show` / `project record` / `project check` | The target Desktop and catalog in `design/specs/project.json`; record this machine's Desktop version; check it against the target (`/build` runs it first) |
| `desktop state / reload / screenshot` | Through the Desktop Bridge: unsaved check, report-only reload, page screenshots |

Exit codes: 0 ok, 1 checks failed, 2 bad input, 3 Desktop Bridge not available, 4 Desktop has unsaved changes, 5 Desktop is newer than the target (run `/update`).

Rules worth knowing ([.claude/rules/pbik.md](../.claude/rules/pbik.md) has them all):

- Drive builds from layout.json only. Never pass JSON on the command line (PowerShell strips the quotes).
- Visuals without an ID (made in Desktop) are never touched by `pbik build`, and `pbik validate` reports them.
- Properties pbik wrote and that left layout.json are removed on the next build (`visual-map.json` keeps the list;
  don't edit it).
- If something can't be expressed in layout.json, even with `props` and `{"raw": ...}`, it is a pbik gap: report it
  and add it to `design/known-gaps.md`.

## Themes and patterns

### Colours and tokens

`design/tokens.json` holds every colour, font size, spacing, radius and shadow. `design/scripts/gen_tokens.py` makes
it from one source, first match wins:

1. Brand colours: `--brand "#0E1A2B,#F2B705"` or by role (`primary=`, `brand=`, `bad=`, `good=`, `second=`), with
   `--mode dark` for a dark report.
2. A reference: `--from design\reference\<image or html>`.
3. A preset: `--preset clean` (default), `bento` or `corporate` ([design/themes/presets/README.md](../design/themes/presets/README.md)).

Any colour that fails WCAG 2.1 AA is moved, in lightness only, until it passes; `design/reviews/theme.md` lists what
moved. `design/scripts/gen_theme.py` then writes the Power BI theme. New visuals pick up the palette on templates'
own colours (`theme.recolourTemplates`); visuals built before keep theirs until a `--reset`.

### Templates

Each visual starts from a template in `design/templates/`, harvested from a Patterns page that Desktop saved
(`tools/patterns/`). pbik takes only formatting from a template, never fields or text. Selected states get
`tokens.colors.selected`, so a report has one selected colour.

### Layout styles

[docs/layouts/](layouts/README.md) has one small HTML reference per style: grid, bento, rail, tabs and dense table.
Copy one to `design/reference/` as a starting point, or bring your own wireframe or screenshot; `/plan` maps it to
layout.json with `ref_layout.py`.

### Patterns

[docs/patterns/](patterns/README.md) are designs that answer "compared with what?" and "is anything wrong?". `/plan`
names one on each visual that draws it (`pattern` in layout.json):

| Pattern | Question |
| --- | --- |
| `range-band` | Is this period inside its usual range? |
| `dumbbell` | How far did each member move, and which way? |
| `small-multiples-expected` | Which members are off their expected path? |
| `brushed-range` | What happens in the period I pick? |
| `partial-period` | Is the last point complete, or still filling up? |
| `freshness-line` | How current is this data? |
| `exception-list` | Which members need attention, worst first? |
| `direct-labels` | Which line is which, without a legend? |

Every headline number has a comparison drawn next to it. Normal is drawn quietly; exceptions take the accent colour.
Colour is never the only signal.

## DAX Lib

DAX Lib (daxlib.org) publishes packages of DAX user-defined functions. The kit uses only the packages listed in
`design/udf/packages.json`, each with a checked licence: DaxLib.SVG (SVG measures), DataTides.ColourContrast and
DataTides.SignificantChange.

- `/plan` names the package function per visual ID and puts a package that isn't installed on the model approval
  list.
- `/model approved` installs it through the daxlib-mcp server (`.mcp.json`, pinned to `@daxlib/mcp@0.1.0`), then
  records it under `installed` in packages.json.
- DAX Lib needs compatibility level 1702 or later. Raising it is its own approval item; daxlib-mcp never raises it.
- Where npm is blocked, the same packages are vendored in `design/udf/vendor/` and installed through the Modeling
  MCP: `python design\udf\vendored.py --check`, then `python design\udf\vendored.py DaxLib.SVG --out <file>`
  ([design/udf/README.md](../design/udf/README.md)).
- DaxLib.SVG takes raw `#RRGGBB` colours, not `%23`. `pbik validate` flags the wrong form.

## The lessons system

When a fix works, the assistant proposes a lesson and waits for your approval. It goes in the first place that fits
([lessons/README.md](lessons/README.md)):

1. **A check**: a `pbik validate` rule or a test, if a script can tell right from wrong.
2. **A template or token**, if it is about how a visual looks.
3. **The command file** (`.claude/commands/<step>.md`), if it applies to one step only.
4. **A topic file** in `docs/lessons/` (dax, build, cards, slicers, charts, accessibility, audit-modes), or a rules
   file in `.claude/rules/`, if it is background.
5. **CLAUDE.md**, only if it applies to every session. One in, one out: CLAUDE.md stays under 150 lines (a test
   checks).

Each proposal says where it goes and why not higher. When a check starts enforcing a rule, the rule is proposed for
retirement. At the end of a report, `/wrapup` places the remaining lessons, runs the tests and commits.

After editing `CLAUDE.md`, `.claude/rules/` or `.claude/commands/`, run `python tools\copilot\sync.py` so Copilot gets
the same text.

## Git habits

- **One branch per piece of work.** Keep `master` (or `main`) for finished work.
- **When the assistant commits.** `/model approved`, `/build` and `/fix` commit on their own. Otherwise it commits only
  when you say so.
- **Commit pbik's output before Desktop saves.** `pbik roundtrip` compares the last commit (what pbik wrote) with the
  working tree (what Desktop saved), so commit the build first, then save in Desktop.
- **A clean rebuild leaves a clean diff.** Run `pbik build` twice: the second run prints "No changes" and
  `git diff` shows nothing.
- **Never commit data.** `data/` is git-ignored, and so are Desktop's local settings and cache.
- **Ask before deleting.** The assistant doesn't delete files or change the model without asking.
- **Tag releases of the kit** as `v<MAJOR>.<MINOR>.<PATCH>` and add a row to VERSIONS.md "Releases".

## The update routine

Versions are pinned and recorded in [VERSIONS.md](../VERSIONS.md). Plugin auto-update is off.

- **Freeze versions during a report.** Update between reports, one component at a time.
- **After a tool or plugin update:** `/smoke`, then record the new version in VERSIONS.md.
- **After a Power BI Desktop update:** `/update` ([UPDATE-ROUTINE.md](UPDATE-ROUTINE.md)): record the version,
  `pbik schemas support --refresh`, `python tools\run_tests.py --regression`, `/smoke`, new settings through the
  Patterns page, `pbik templates harvest` and `pbik catalog refresh`, then a release row.
- **An older Desktop elsewhere:** set `targetDesktop` in `design/specs/project.json` to that version. pbik then writes
  only schema versions that Desktop supports, and `pbik validate` errors on newer ones. Don't change the target
  without agreeing it first.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| pbik exits 3 ("bridge not available") | The Desktop Bridge isn't there. That means "not checked", not "clean". Reload by hand: File > Close (don't save), open the `.pbip` again, check the title bar shows no unsaved mark. Take screenshots by hand at 100% zoom into `_snapshots\<page>.png` |
| pbik exits 4, or "unsaved changes" | Desktop marks a report unsaved after opening and after every reload. Close without saving and reopen before the next reload |
| The second `pbik build` doesn't print "No changes" | Something in layout.json or a template isn't stable. Check `git diff` and report it |
| `pbik validate`: visual without an ID | A visual made in Desktop. Give it an ID in layout.json, or remove it in Desktop |
| `pbik validate`: "not cached" schema warning | Run `pbik schemas fetch <Report>` with network access. Microsoft doesn't publish every version Desktop writes, so a few may stay uncached |
| `pbik validate`: settings catalog warning | Desktop has never saved that setting. Check it in Desktop, or find the form Desktop saves (`pbik catalog show`) |
| A filter matches nothing | Numbers written as text never match. pbik types values from the TMDL; check the column type |
| SVG colours draw black or nothing | In hand-written SVG, write `%` as `%25`. With DaxLib.SVG, use raw `#` colours. Run `audit_svg.py` |
| Visuals show "Error fetching data" | An extension measure references another extension measure. Make each one self-contained |
| A button slicer scrolls or hides buttons | Give it a row and column grid (`layout.rowCount`, `columnCount`); see [lessons/slicers.md](lessons/slicers.md) |
| A theme change doesn't show | Reload the report (`pbik desktop reload`) |
| Recalculation fails: "base version must not be negative" | Reconnect the Modeling MCP, then retry |
| daxlib-mcp refuses to install | Raise the compatibility level to 1702 first (its own approval item). If npm is blocked, use the vendored copy |
| Deneb doesn't load | Custom visuals are blocked. Set `"customVisuals": false` in `design/specs/project.json` and rebuild |
| Copilot shows `${input:...}` or old prompt names | Run `python tools\copilot\sync.py` and reload the VS Code window |
| Copilot can't change the model | Start `powerbi-authoring-local` in **MCP: List Servers** and tick its tools ([WORK-SETUP.md](WORK-SETUP.md)) |
| Edge screenshots time out | Set `EDGE_WAIT` to more seconds (default 30) and rerun |
| Files locked while Desktop saves | Move the project out of OneDrive, or pause sync |
| Anything else | Check [design/known-gaps.md](../design/known-gaps.md): every gap with its Desktop click steps |

## Scripts

In `design/scripts/`. The commands run them; you rarely need to.

| Script | Does |
| --- | --- |
| `gen_tokens.py` | tokens.json from brand colours, a reference or a preset, every text and state AA |
| `gen_theme.py` | the Power BI theme from the tokens |
| `ref_layout.py` | a draft layout.json from a reference (HTML, or a boxes file for an image) |
| `ref_palette.py` | a reference's palette |
| `wireframe_data.py` | the wireframe's numbers: one aggregate query per visual, small groups hidden |
| `gen_wireframe_hf.py` | the high-fidelity wireframe (B toggles ID badges, T the visual-type tags) |
| `gen_wireframe.py` | the box wireframe (fallback) |
| `check_contrast.py` | WCAG AA of every text on the wireframe |
| `fidelity_check.py` | the wireframe against Desktop, side by side |
| `audit_layout.py` | positions, panels, shadows and z-order against layout.json and the tokens |
| `audit_ids.py` | visual IDs across layout, wireframe, spec, review and report; ladder steps; headline comparisons |
| `audit_numbers.py` | key values against raw recomputes, and numbers drawn inside SVGs |
| `audit_svg.py` | every SVG measure well-formed in every audit state |
| `svg_to_png.py` | renders SVG files to PNG for registering as images |
| `smoke.py` | the `/smoke` page |
| `colour.py`, `edge_page.py`, `pbik_helpers.py`, `ambition.py`, `ladder.py` | helpers the others use |

Tests: `python tools\run_tests.py` runs every suite; `--regression` adds the golden builds
(`tools\regression\regress.py`).

## Glossary

| Term | Meaning |
| --- | --- |
| **Alt text** | A one-sentence description of a visual for screen readers (`container.altText`) |
| **Approval gate** | A point where the assistant stops until you approve: brd.md, the model list, the wireframe |
| **Audit mode** | How the numbers audit runs: full, sampled or aggregate-only |
| **BRD** | Business requirements document: `design/reference/brd.md`, what the report must show and for whom |
| **Catalog (settings catalog)** | Every formatting setting Desktop has saved, per visual type, on one machine (`tools/pbik/catalogs/<name>.json`). `pbik validate` warns on settings outside it |
| **Compatibility level** | The model's feature level (`database.tmdl`). DAX user-defined functions need 1702 |
| **Deneb** | A certified custom visual that draws Vega-Lite specs. Ladder step 3 |
| **Desktop Bridge** | A Desktop preview feature that lets scripts reload the report and take screenshots (`.claude/scripts/pbi-bridge.ps1`) |
| **Done-when line** | One line per visual in spec.md saying what must be true on screen |
| **DAX Lib** | daxlib.org: published packages of DAX user-defined functions |
| **Extension measure** | A measure stored in the report (`reportExtensions.json`), not the model. Used for SVG images |
| **Fallback** | A method above ladder step 1, or the native or SVG visual a Deneb visual falls back to |
| **Fallback register** | The table in spec.md listing each non-native visual: native option tried, why it fails, the fallback, your approval |
| **Fidelity check** | The wireframe and Desktop screenshots side by side, with the visuals that differ |
| **Golden build** | A saved pbik output the regression suite compares against |
| **Known gaps** | `design/known-gaps.md`: what Desktop or pbik can't do, with workarounds |
| **layout.json** | `design/specs/layout.json`: every page and visual. The single source for the wireframe, build and audits |
| **Lesson** | Something learned the hard way, placed by `docs/lessons/README.md` |
| **MCP server** | A tool server the assistant calls: the Modeling MCP changes the model; daxlib-mcp installs DAX Lib packages |
| **Modeling MCP** | Microsoft's Power BI Modeling MCP server. The only route for model changes |
| **Native** | A built-in Power BI visual or setting. Ladder step 1 |
| **Pattern** | A design from `docs/patterns/` that answers a question such as "compared with what?" |
| **Patterns page** | A report page Desktop saved with one example of each visual type; the templates and catalog come from it |
| **pbik** | The kit's own command line tool for PBIR and TMDL (`tools/pbik/`) |
| **pbik gap** | Something layout.json can't express yet. Reported and added to known gaps |
| **.pbiviz** | A packaged custom visual. Ladder step 4 |
| **PBIP** | Power BI Project: a report and model saved as folders of files |
| **PBIR** | The report format in a PBIP: one JSON file per page and visual |
| **Rep** | One report project run through the kit, from `/brd` to the last `/fix` |
| **Regression suite** | Golden builds rebuilt and compared after every pbik change or Desktop update |
| **Roundtrip** | Comparing what pbik wrote with what Desktop saved (`pbik roundtrip`) |
| **Smoke test** | `/smoke`: one card, one button slicer and one table, checked in Desktop after an update |
| **Spec** | `design/specs/spec.md`: design ambition, done-when lines, model changes, build order, fallback register |
| **SVG measure** | A DAX measure that returns an SVG image as a data URI. Ladder step 2 |
| **Target Desktop** | The oldest Desktop that must open the report (`design/specs/project.json`) |
| **Template** | A Desktop-saved visual in `design/templates/` that pbik takes formatting from |
| **TMDL** | The model format in a PBIP: text files for tables, measures and relationships |
| **Tokens** | `design/tokens.json`: named colours, font sizes, spacing, radius and shadow |
| **Visual ID** | `P<page>-V<nn>`, a visual's permanent name across every file |
| **Wireframe** | `design/wireframes/wireframe.html`: the report drawn from layout.json before it is built |
