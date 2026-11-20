# Merge notes: v1.5 to v1.12.0

For merging this kit into a work copy that was taken at v1.4 or earlier. One section per batch, oldest first: what
was added or changed, the settings and defaults, what the Copilot files need, and the tests to run before going on.
Merge one batch at a time, run its tests, commit, then start the next. Paths are relative to the kit root. Each
batch below gives the changes with their purpose, settings, Copilot updates and tests; the
[appendix](#appendix-every-file-by-batch) lists every file each batch added, changed or removed, one line each
(v1.12.1).

The quick flow is **/start** in Claude Code and **/kit-start** in GitHub Copilot (.github/prompts/kit-start.prompt.md):
it detects what you give (requirements, a wireframe, a picture, a report), shows the plan as a picture, then builds
guided (a stop after each stage) or quick (stops only at the plan picture and approvals).

## Before you start

- Tag the work copy (`git tag pre-merge-<date>`) and keep the work kit's own files listed under
  [Known conflicts](#known-conflicts-with-a-work-kit) open beside the diff.
- Python 3.10+, git. From v1.11 the app-visual tools (Node, powerbi-visuals-tools, Playwright) install outside the
  repo with `pbik tools install`; nothing in the repo needs them unless a kit custom visual is built.
- After every batch: `python tools/copilot/sync.py` (rebuilds .github/copilot-instructions.md and .github/prompts
  from CLAUDE.md, .claude/rules and .claude/commands), then the batch's tests, then `python tools/run_tests.py`.

## Work defaults (set once after the merge)

| Default | Where | Value at work |
| --- | --- | --- |
| Build routes: HTML, Deneb, kit custom visuals all on | design/specs/project.json `routes` | `{"html": true, "deneb": true, "customVisual": true}` (custom visuals and Node are allowed at work) |
| Privacy mode on (small counts suppressed) | project.json `honestData` | `{"minSample": 11, "mode": "suppress"}`; `"catalog": "work"` makes `suppress` the default; the threshold is `minSample` |
| Org chart layout d3.tree (ISC only) | each org-chart kit visual: layout props `"tree.layout@none": "d3tree"` | Standard (d3.tree) instead of Compact (d3-flextree, WTFPL), unless legal accepts WTFPL |
| Fonts: Segoe UI family | design/tokens.json `font.weights` (presets already use Segoe UI Regular / Semibold / Light) | keep Segoe UI; no web fonts |
| Left-aligned KPI cards | tokens.json `card.align` | `left` (every preset ships `left`; `pbik layout polish` applies it) |
| Panel style layout palette | design/themes/presets/panel-style.json `memberPalette` | blue, green, teal, red, then purple, amber (a member's own `color` in the spec wins) |
| Desktop target | project.json `targetDesktop` | the work Desktop's version (see [Desktop versions](#desktop-versions)) |

## v1.5–v1.6 (pbik 0.15.0–0.16.0): synthetic to live, model packs, roadmap batches 3 and 4

**Added**
- tools/pbik/pbikit/synth.py, synthgen.py: the made-up model (`pbik synth contract / resolve / approve / slice /
  generate / verify`): a contract from the real model's metadata, made-up rows, never real data.
- bind.py, bindrefs.py, names.py: `pbik bind check / prepare / live / local / map`: switch a report from the made-up
  model to the live one and back; design/specs/bind-map.json maps renamed fields.
- packs.py: model packs (`model register / drift / approve`, `project new --from-pack`).
- dataclass_.py: `pbik project class` (public, internal, restricted) and its guards.
- filtertypes.py: filter values typed like the column (`2024L`, `1.5D`, `'text'`).
- kpicards.py, design/scripts/card_space.py, design/templates/cardVisual.kpi-delta-card.json: the KPI card rule
  (cards fill their space; the change line coloured by direction).
- namenew.py: `pbik roundtrip --name-new` (IDs for visuals made in Desktop).
- tools/export_check.py, tools/export_allow.txt: the export check (no personal paths, names or data in the kit).
- Patterns: headline-banner, page-header-stack, ranked-bar-table, tabs-underline, text-link-button, two-kpi-card.
- docs/design/synth-to-live.md; design/reviews/pbik-roadmap-batch3.md, batch4.md.

**Changed**: validate (visual headers off, header-band check, status badges contrast), layout fidelity
(`desktopPosition`, `active: false`, Desktop bookmark groups left alone), button labels as `objects.text.text`.

**Settings**: project.json `class`; bind-map.json; theme `visualHeader` off.

**Copilot**: CLAUDE.md gained the synthetic-to-live and project-class rules: sync. No new prompts.

**Tests**: suites pbik, synth, bind, layout (`python tools/run_tests.py --changed`); then `python tools/export_check.py`.

## v1.7 (pbik 0.19.0): the main flow

**Added**
- .claude/commands/start.md, status.md and their prompts kit-start, kit-status: the main flow and "where am I".
- pbikit: start.py, plan.py (the plan as a picture), polish.py (`pbik layout polish`), score.py (`pbik score`, 15
  checks out of 10), gates.py (approval windows), status.py, steps.py, progress.py, history.py (build history),
  projectsetup.py / projectinit.py (one folder = one project), intake.py (`pbik model intake`, deletes data files
  first), fromreport.py (`layout from-report`), picker.py, newreport.py, rules.py, drops.py, summary.py.
- design/scripts/example_values.py: example numbers in the plan picture.
- docs: PLAIN-WORDS.md, PHASE1-WALKTHROUGH.md, PHASE1-COLLEAGUE-TEST.md, design/phase1-usability.md; starter layouts
  docs/layouts/starters/ (executive-summary, trend-dashboard, detail-table).
- tools/hooks/ (guard_model_folder.py, guard_gates.py, count_messages.py), tools/usage.py, tools/master-only.txt,
  .vscode/tasks.json.

**Changed**: CLAUDE.md rules (chat only, plain words, one folder = one project, Model and Reference folders,
approval gates), the step commands (/brd, /model, /plan, /build) keep their own gates.

**Settings**: design/status.json (stage, mode guided / quick); `%USERPROFILE%\.pbik\builds.jsonl` (build history, no
names or data); hooks in .claude/settings.json.

**Copilot**: new prompts kit-start and kit-status; the instructions file grows the main-flow section: sync, then
check that the work copy's own Copilot additions survived (sync rewrites the generated files).

**Tests**: suites phase1, walkthrough, live, v17 (`python tools/run_tests.py --changed` runs the suites the batch touched).

## v1.8 (pbik 0.20.0): rail + panel, the UDF KPI card toolbelt

**Added**
- docs/patterns/rail-panel.md, panel.md, svg-kpi-card.md; design/themes/presets/rail-panel.json;
  docs/layouts/starters/profile-explorer.json.
- harvestclean.py: `pbik templates harvest --clean` and 13 clean templates in design/templates/ (header-title, rule,
  image-list, image-cards, panel, profile-card, kpi-row-chips, two-kpi-card, tabs-underline, titled image,
  scatter-on-image, svg-kpi-card, svg-kpi-card-buttons).
- udf.py and design/udf/library/park-kpi/ (33 KPI card functions, used with the author's permission; provenance in
  design/udf/udf-kpi-library-provenance.md): `pbik udf list / show / check / render / install / inline / desktop`.
- Lessons C-12, D-10, D-11, B-14.

**Settings**: layout `udfCard` (mode `inline` default, `measure`, `calc`); tokens `font.weights`.

**Copilot**: .claude/rules/svg.md gained the UDF toolbelt section: sync.

**Tests**: suites harvest, udf, pbik (`python tools/run_tests.py --changed` runs the suites the batch touched).

## v1.9 (pbik 0.21.0): UDF card fixes

**Changed**: udf.py and the park-kpi functions K-08 to K-11 (no empty icon tile, "No data" card, arrows); card image
settings as Desktop saved them; automatic lower-is-better colours (`lowerIsBetter`); the model's own date table for
`'Date'`; index `minSize` with a validate warning.

**Settings**: layout `lowerIsBetter` (a measure name list, or set automatically by polish for returns and costs); the
library index `minSize` per chart style (validate warns below it).

**Copilot**: none. **Tests**: suites udf (`python tools/run_tests.py --changed` runs the suites the batch touched).

## v1.10 (pbik 0.22.0): polish score

**Added**: gridsnap.py (build snaps to the grid; hand-placed visuals listed, not moved).
**Changed**: build writes missing alt text; score lists each visual out of line; N/A checks with their reason.
Lessons B-15 new, A-01 every visual, B-02 and B-07 retired. Regression goldens refreshed (alt text, small snaps).

**Settings**: layout `snap: false` or `desktopPosition` to keep a hand-placed visual.

**Copilot**: none. **Tests**: suites v17, pbik, regression (`python tools/run_tests.py --changed` runs the suites the batch touched).

## v1.11–v1.11.1 (pbik 0.23.0): app-like visuals

**Added**
- tools/appvisuals/: the app-visual template (TypeScript; kit/ scene, motion, morph, filter, updates, theme, words,
  patterns), the offline harness (Playwright), Deneb starter, lock.json (pinned tool versions with checksums).
- pbikit: apptools.py (`pbik tools check / install / run`), appvisual.py (`pbik visual new / build / test / add /
  refresh / list / remove / handoff`); deneb.py gained Deneb interactivity.
- docs/design/app-visuals.md, docs/patterns/app-visuals/ (17 patterns: focus-dim, live-headline, kpi-mini-bars,
  map, network-org, morph-layouts, pills-and-badges, unit-chart, 3d-scene, describe-a-visual, ...).
- design/templates/advancedSlicerVisual.button-slicer.json (harvested from a Desktop-made slicer).

**Changed**: build registers kit visuals as Desktop stores a private .pbiviz; NoFilter from kit visuals to slicers;
token names resolved or rejected (build stops on an unknown token: minor, but layouts with unclickable slicers stop);
validate: shapes above clickable visuals, sync groups across fields, kit visual filters reaching slicers.

**Settings**: project.json `routes` (see Work defaults), `exported` pages build native or Deneb; `customVisuals:
false` turns Deneb and kit visuals off. Licences: every kit visual ships NOTICE.md (MIT, ISC, BSD, WTFPL for
d3-flextree) and `pbik visual handoff` writes the IT pack.

**Copilot**: CLAUDE.md "Native first" ladder now names routes 3-4: sync. docs/COPILOT.md: Node is needed only for
`pbik tools`.

**Tests**: `pbik tools check`, suites pbik, patterns, kit (`python tools/run_tests.py --changed`), and `pbik visual test --all` in a project with a kit visual.

## v1.12.0 (pbik 0.24.0): batch studies, house styles

**Added**
- Panel style layout: tools/pbik/pbikit/panelstyle.py (`pbik layout panels`), icons.py (kit-drawn icons),
  design/themes/presets/panel-style.json, docs/patterns/panel-style-layout.md, threshold-histogram.md,
  label-above-bars.md; regression case `panel-style`.
- Dark glass and the spatial canvas: design/themes/presets/dark-glass.json, docs/patterns/spatial-canvas.md,
  honest-data.md, breakdown-wall.md; tools/appvisuals/starters/spatial-canvas (court, pitch, floor plans; Dots /
  Zones / Ranked), template kit/patterns/spatial.ts, honest.ts, quality.ts; design/scripts/space_svg.py.
- honest.py: the small-sample threshold and privacy mode (project.json `honestData`).
- design/reviews/batch-studies-part-d.md (the three rebuilds against their originals).

**Changed**
- `pbik build` makes or updates the made-up model before the first build when the plan changed, and says when a
  changed contract leaves it as it was.
- The plan picture (gen_wireframe_hf.py, example_values.py) computes example values from the model's own DAX and
  draws Desktop's defaults.
- Polish rules: matching and rail pickers (title room from the theme), back buttons, target lines, drill-card
  comparisons, kept picker labels, pill colours on dark themes, sort-by scope, label collisions, tab order set to
  reading order.
- Kit visuals: a column in a value well is summed; capability colours typed as colours; the readout keeps its padding
  inside its width.
- Validate and score: reading order reads the band, then each full-height panel as a column; old layouts (pages as a
  list) are scored; text measures, sentence cards, diverging gradients and left-aligned cards with a comparison line
  are judged correctly.
- House styles: with no look named, /plan picks the panel style layout for 2-6 members side by side, rail + panel or
  dark glass for an explorer page, and names the alternative in one line.

**Settings**: tokens `card.align`, `fontPt` (minimum 10), preset `memberPalette`; generate.json `rowsPerYear`,
`hints` (`weights`, `rates`, `derive`, `points`), `plannedColumns` with `sortBy`; project.json `honestData`.

**Copilot**: .claude/commands/plan.md and start.md changed (house styles, made-up model before the first build):
sync, and check the work copy's own prompt edits.

**Tests**: suites v111, wireframe, design, regression (`python tools/run_tests.py --changed` runs the suites the batch touched), then the whole suite with `--regression`.

## Known conflicts with a work kit

| Work kit file | Kit file it meets | What to do |
| --- | --- | --- |
| its own bind map | design/specs/bind-map.json, bind.py (v1.5) | Keep the work map as the source. bind.py reads `bind-map.json` (renamed columns and measures, `acceptDax`): convert the work map to that shape, or point bind.py's `self.map` at the work file. Run `pbik bind check` on one work project before switching any live. |
| the MEE model pack, modelpack.py | packs.py, `model register / drift / approve` (v1.5) | Two pack mechanisms. Keep modelpack.py for MEE; don't register MEE through packs.py until both agree on the fingerprint. They share no file names; `project new --from-pack` uses packs.py only. |
| cardVisual.kpi-card.json | cardVisual.kpi-delta-card.json, kpi-row-chips, svg-kpi-card (v1.5, v1.8) | No name clash. Keep the work template for work reports (`template: "cardVisual.kpi-card"` in layout.json); the kit's polish sets card alignment and comparison lines on any card. Check C-07/C-10 (validate) against the work card once. |
| kpicards.py | tools/pbik/pbikit/kpicards.py (v1.5; v1.12 skips panel-style panels) | **Same file name.** Diff function by function: validate imports the kit's `check` and panel helpers. Move work-only functions into a new module (for example kpicards_work.py) and keep the kit's file. |
| audit_kpi_fill.py | design/scripts/card_space.py, score check 3 "KPI cards filled" | No clash; both can run. Keep the work audit in the /review step. |
| lessons C26 / B22 | docs/lessons cards.md (C-01 to C-12), build.md (B-01 to B-16) | Kit IDs are `C-NN` / `B-NN` and `python tools/lessons.py check` enforces the format and budgets. Renumber the work lessons as the next free IDs (C-13, B-17), or keep them in a work-only lessons file the check skips. |
| Desktop 2.155 pin | project.json `targetDesktop`, tools/pbik/schema-support.json | Set `targetDesktop` to the work version (2.155.756.0): pbik then caps every `$schema` to what 2.155 supports and validate errors on newer ones. See below for what is confirmed only on 2.159. |

## Desktop versions

Everything pbik writes is capped by `targetDesktop`, so builds open on 2.155. What has been confirmed in Desktop so far
was confirmed on **2.159** (2.159.883.0 and 2.159.1231.0):

| Needs 2.159+ or is confirmed only there | Works on 2.155 by design |
| --- | --- |
| UDFs on by default (no preview switch): `udfCard` modes `measure` and `calc`, `pbik udf install` (2.155: verify the preview switch first; `inline` works anywhere) | native visuals, theme, layout keys, bookmarks, drill-through, filters (schemas capped) |
| visualContainer 2.13.0 features (September 2026 schemas): pbik lowers them when the target is older | the made-up model (calculated tables, TMDL) |
| The Desktop Bridge (`pbik desktop open / reload / screenshot`, capture v2 regions); without it the manual steps in .claude/rules/pbik.md apply | the plan picture, score, validate, regression (no Desktop) |
| Kit custom visuals and Deneb 2.0.1.0 were reviewed on 2.159.1231.0; API 5.11 visuals should load on 2.155, but run `/smoke` there first | panel style layout, rail + panel, dark glass (native only, except the spatial canvas) |
| The new card's reference label titles (`referenceLabelTitle`), confirmed on 2.159.1231 | button slicers from the harvested template |

On a 2.155 machine: set `targetDesktop`, run `/smoke` (one card, one button slicer, one table), then one kit visual.

## After the last batch

1. `python tools/run_tests.py --regression` (all suites and the five regression cases).
2. `python tools/export_check.py` and `python tools/lessons.py check`.
3. `python tools/copilot/sync.py`, then confirm the work copy's Copilot additions are still there.
4. Set the work defaults above, then `/start` on one small work report end to end.

## Appendix: every file by batch

Status, path and one line on what the file is for (from its own description), for each batch in the order above. Folders of many like files are one row. `git diff --stat <old tag> <new tag>` shows the line counts.

### v1.5–v1.6 (v1.4 → v1.6): 86 rows

| Status | File | Purpose |
| --- | --- | --- |
| changed | `.claude/commands/plan.md` | /plan: design ambition, patterns, tokens, layout.json, spec and audit |
| changed | `.claude/commands/review.md` | /review: Desktop is reopened |
| changed | `.claude/commands/smoke.md` | /smoke: Smoke test after a tool or plugin update |
| changed | `.claude/scripts/run-dax.ps1` | runs a DAX query against Desktop's model (the numbers audit and measure checks) |
| changed | `.github/prompts/kit-plan.prompt.md` | Copilot mirror of /plan |
| changed | `.github/prompts/kit-review.prompt.md` | Step 4: screenshot the report, compare with the wireframe and checks, run the numbers audit |
| changed | `.github/prompts/kit-smoke.prompt.md` | After a tool, plugin or Desktop update |
| changed | `.gitignore` | files git never tracks (data, caches, tool folders, builds) |
| changed | `README.md` | the kit's front page |
| changed | `VERSIONS.md` | pinned versions, releases and the changelog |
| changed | `design/known-gaps.md` | Known gaps: Things Desktop (or PBIR) can't do the way the design needs, and what pbik can't write yet, with the workaround and any |
| changed | `design/reference/layout-schema.md` | layout.json schema and visual IDs |
| changed | `design/reviews/pbik-roadmap-batch1.md` | pbik roadmap batch 1 (pbik 0.13.0, 2026-11-10) |
| changed | `design/reviews/pbik-roadmap-batch2.md` | pbik roadmap batch 2 (bulk run, 2026-11-10) |
| added | `design/reviews/pbik-roadmap-batch3.md` | pbik roadmap batch 3 (2026-11-13) |
| added | `design/reviews/pbik-roadmap-batch4.md` | pbik roadmap batch 4 (2026-11-13) |
| changed | `design/scripts/audit_ids.py` | Visual ID audit: every visual has one stable ID (P<page>-V<nn>) that the layout, wireframe, spec, review, fix, visual-map and report folders all agree on |
| added | `design/scripts/card_space.py` | Polish-loop screenshot check |
| changed | `design/scripts/gen_theme.py` | Generate design/themes/pbip-polish.json (Power BI report theme) from design/tokens.json |
| changed | `design/scripts/gen_tokens.py` | /theme: build design/tokens.json from brand colours, a reference (image or HTML) or a preset, with every text and state colour moved until it passes WCAG 2.1 AA |
| added | `design/scripts/pattern_choices.py` | The spec's "Pattern choices" section (batch 3 items 13-14), checked by audit_ids.py |
| changed | `design/scripts/ref_layout.py` | /plan from a reference of any layout style |
| changed | `design/scripts/test_design.py` | Design-flexibility tests |
| changed | `design/scripts/test_wireframe.py` | Tests for the high-fidelity wireframe (gen_wireframe_hf.py) and its data step (wireframe_data.py) |
| added/changed | `design/templates/*.json` | visual templates harvested from Desktop-saved files |
| changed | `design/themes/pbip-polish.json` | the kit's report theme, generated from tokens.json (gen_theme.py) |
| changed | `design/tokens.json` | the kit's default design tokens (colours, fonts, sizes) |
| changed | `docs/IT-REQUEST.md` | Request to IT: tools for building Power BI reports with pbip-kit |
| added | `docs/design/synth-to-live.md` | Synthetic to live (design, batch 3) |
| changed | `docs/it-security.md` | IT and security notes |
| changed | `docs/lessons/README.md` | Lessons: format, placement and upkeep |
| changed | `docs/lessons/build.md` | Build method: Read by /plan (layout.json keys), /build and /fix |
| changed | `docs/lessons/cards.md` | Shapes, containers and new cards |
| changed | `docs/patterns/README.md` | the pattern library index (Use when, Avoid when, Styles) |
| changed | `docs/patterns/brushed-range.md` | Brushed range selection |
| changed | `docs/patterns/direct-labels.md` | Direct labels instead of legends |
| changed | `docs/patterns/dumbbell.md` | Dumbbell rows with change labels |
| changed | `docs/patterns/exception-list.md` | Exception list: **Question it answers:** which members need attention, worst first? |
| changed | `docs/patterns/freshness-line.md` | Data freshness line: **Question it answers:** how current is this, and can I trust it today? |
| added | `docs/patterns/headline-banner.md` | Headline banner: **Question it answers:** what is the one thing to know on this page right now? |
| added | `docs/patterns/page-header-stack.md` | Page header stack: **Question it answers:** where am I, what is this page for, and what should I read first? |
| changed | `docs/patterns/partial-period.md` | Partial-period markers (hollow point) |
| changed | `docs/patterns/range-band.md` | Range band with current-period dots |
| added | `docs/patterns/ranked-bar-table.md` | Ranked bar table: **Question it answers:** who ranks where, by how much, which way are they moving, and are they OK? |
| changed | `docs/patterns/small-multiples-expected.md` | Small multiples against an expected line |
| added | `docs/patterns/tabs-underline.md` | Tabs with underline: **Question it answers:** which view am I on, and what else is there? |
| added | `docs/patterns/text-link-button.md` | Text link button: **Question it answers:** where do I go for more? |
| added | `docs/patterns/two-kpi-card.md` | Two-KPI tinted card: **Question it answers:** how do two related numbers stand against each other (actual and target, this year and last)? |
| added | `tools/export_allow.txt` | export check allow-list (each entry with its reason) |
| added | `tools/export_check.py` | Clean-export check: run it before every push (README "Before you push") |
| changed | `tools/pbik/README.md` | every pbik command, its options and what it writes |
| changed | `tools/pbik/pbikit/__init__.py` | pbik's version number |
| added | `tools/pbik/pbikit/bind.py` | bind: move a report from its synthetic model to the published one and back (docs/design/synth-to-live.md) |
| added | `tools/pbik/pbikit/bindrefs.py` | Every place a PBIR report references a model field, found and rewritten through a name map (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/bookmarks.py` | Bookmarks from layout.json (pbik build), in the shape Power BI Desktop saved them in Rep 5 |
| changed | `tools/pbik/pbikit/build.py` | `pbik build`: layout.json to PBIR files (idempotent) |
| changed | `tools/pbik/pbikit/cli.py` | pbik's command line: every command and option |
| added | `tools/pbik/pbikit/dataclass_.py` | Project data classes (public / internal / restricted), the restricted guard, and person-only confirmation |
| changed | `tools/pbik/pbikit/deprecations.py` | Retiring and deprecated visuals and options (roadmap gap 20) |
| changed | `tools/pbik/pbikit/desktop.py` | pbik desktop state / reload / screenshot |
| added | `tools/pbik/pbikit/filtertypes.py` | Filter values typed against the model's column types (batch 3 item 5) |
| added | `tools/pbik/pbikit/kpicards.py` | KPI card rule (batch 3 item 10, docs/lessons/cards.md C-10) |
| added | `tools/pbik/pbikit/namenew.py` | Visuals Desktop added without a pbik ID (batch 3 item 11) |
| added | `tools/pbik/pbikit/names.py` | Name comparison the way DAX does it |
| added | `tools/pbik/pbikit/packs.py` | Model packs (batch 3 item 15) |
| changed | `tools/pbik/pbikit/roundtrip.py` | pbik roundtrip: after a report pbik built is saved once in Desktop, list what Desktop rewrote, by visual ID, as proposed pbik fixes |
| added | `tools/pbik/pbikit/synth.py` | Synthetic models: the contract, its approval, the slice, generation and verification (docs/design/synth-to-live.md) |
| added | `tools/pbik/pbikit/synthgen.py` | Generate and verify a synthetic model from the approved contract and generate.json (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/tmdl.py` | Read a semantic model's TMDL folder (tables, columns, measures, relationships) and check DAX references |
| changed | `tools/pbik/pbikit/validate.py` | `pbik validate`: schema, catalog, layout, accessibility and lesson checks |
| changed | `tools/pbik/setup.cfg` | pbik package metadata and version (pip install -e) |
| added | `tools/pbik/tests/bind_sample.py` | A made-up PBIR report on the synthetic sample model, referencing fields everywhere a report can |
| added | `tools/pbik/tests/synth_sample/` | invented "Example Live" model for the synth and bind tests |
| added | `tools/pbik/tests/test_bind.py` | bind tests (docs/design/synth-to-live.md) on the made-up sample model and report (bind_sample.py) |
| added | `tools/pbik/tests/test_layout_rules.py` | Layout rules (batch 3 items 10, 11 and 14) on made-up sample pages |
| changed | `tools/pbik/tests/test_pbik.py` | pbik tests on a scratch copy of a saved PBIP (never the original) |
| added | `tools/pbik/tests/test_synth.py` | Synthetic-to-live tests (docs/design/synth-to-live.md) on made-up sample data only |
| changed | `tools/regression/cases/rep4-parity/` | regression case rep4-parity: inputs and golden build |
| changed | `tools/regression/cases/rep5-parity-overview/` | regression case rep5-parity-overview: inputs and golden build |
| changed | `tools/regression/cases/rep5-parity-workforce-mix/` | regression case rep5-parity-workforce-mix: inputs and golden build |
| changed | `tools/regression/cases/rep8/` | regression case rep8: inputs and golden build |
| changed | `tools/run_tests.py` | Run the kit test suites, then (with --regression) the golden builds |
| added | `tools/tests/sample/README.md` | Sample design files the kit tests read instead of the project's own (batch 3 item 17) |
| added | `tools/tests/sample/pbip-polish.json` | a copy of the default theme for the tests |
| added | `tools/tests/sample/tokens.json` | Neutral starting tokens for pbip-kit v0.2 |
| changed | `tools/tests/test_kit.py` | Kit tests outside pbik |

### v1.7 (v1.6 → v1.7): 89 rows

| Status | File | Purpose |
| --- | --- | --- |
| changed | `.claude/commands/plan.md` | /plan: design ambition, patterns, tokens, layout.json, spec and audit |
| added | `.claude/commands/start.md` | the main flow (/start): detect inputs, plan picture, guided or quick build, polish score |
| added | `.claude/commands/status.md` | /status: where the project is, in plain words |
| changed | `.claude/commands/theme.md` | /theme: Make the colour scheme for this rep |
| changed | `.claude/settings.json` | Claude Code project settings: hooks (model-folder guard, gates, message count) and permissions |
| changed | `.github/copilot-instructions.md` | Copilot instructions generated from CLAUDE.md and .claude/rules (tools/copilot/sync.py) |
| changed | `.github/prompts/kit-plan.prompt.md` | Copilot mirror of /plan |
| added | `.github/prompts/kit-start.prompt.md` | Copilot mirror of /start (/kit-start) |
| added | `.github/prompts/kit-status.prompt.md` | Copilot mirror of /status |
| changed | `.github/prompts/kit-theme.prompt.md` | The colour scheme: brand colours, a reference or a preset, every text and state WCAG AA |
| changed | `.gitignore` | files git never tracks (data, caches, tool folders, builds) |
| added | `.vscode/tasks.json` | VS Code tasks for the main pbik steps |
| changed | `CLAUDE.md` | the kit's rules for the agent |
| changed | `VERSIONS.md` | pinned versions, releases and the changelog |
| changed | `design/checks.md` | Common defects to check on every review |
| changed | `design/reviews/pbik-roadmap-batch4.md` | pbik roadmap batch 4 (2026-11-13) |
| changed | `design/scripts/audit_ids.py` | Visual ID audit: every visual has one stable ID (P<page>-V<nn>) that the layout, wireframe, spec, review, fix, visual-map and report folders all agree on |
| changed | `design/scripts/edge_page.py` | Headless Edge for pages the kit draws |
| added | `design/scripts/example_values.py` | Example values for the fast HTML preview (the plan picture and quick changes) |
| changed | `design/scripts/fidelity_check.py` | Fidelity check: does the high-fidelity wireframe draw what Power BI Desktop shows? |
| changed | `design/scripts/gen_theme.py` | Generate design/themes/pbip-polish.json (Power BI report theme) from design/tokens.json |
| changed | `design/scripts/gen_wireframe_hf.py` | High-fidelity wireframe (the kit default) |
| changed | `design/scripts/ref_layout.py` | /plan from a reference of any layout style |
| changed | `design/scripts/svg_to_png.py` | Render SVG files to transparent PNGs with headless Edge (no image library needed) |
| changed | `design/themes/pbip-polish.json` | the kit's report theme, generated from tokens.json (gen_theme.py) |
| changed | `design/tokens.json` | the kit's default design tokens (colours, fonts, sizes) |
| changed | `docs/COPILOT.md` | Running the kit in VS Code Copilot Chat |
| added | `docs/PHASE1-COLLEAGUE-TEST.md` | Colleague test (v1.7) |
| added | `docs/PHASE1-WALKTHROUGH.md` | Walkthrough (v1.7): one folder per project, guided build, quick build, and no wireframe |
| added | `docs/PLAIN-WORDS.md` | Plain words: What the agent says to the user, so Claude Code and GitHub Copilot say the same thing |
| changed | `docs/QUICKSTART.md` | Quickstart: From a copy of the kit to a finished report |
| added | `docs/design/phase1-usability.md` | Phase 1: usability (design) |
| changed | `docs/it-security.md` | IT and security notes |
| changed | `docs/layouts/README.md` | Layout styles: Small HTML references, one per layout style, that `/plan` maps to layout.json with design/scripts/ref_layout.py |
| added | `docs/layouts/starters/detail-table.json` | starter layout: a detail table page with pickers |
| added | `docs/layouts/starters/executive-summary.json` | starter layout: KPI cards, a trend and a breakdown |
| added | `docs/layouts/starters/trend-dashboard.json` | starter layout: trends over time with comparisons |
| changed | `tools/copilot/sync.py` | Keep the GitHub Copilot files in step with the Claude Code ones (work laptops may have Copilot only) |
| changed | `tools/export_check.py` | Clean-export check: run it before every push (README "Before you push") |
| added | `tools/hooks/count_messages.py` | Claude Code UserPromptSubmit hook |
| added | `tools/hooks/guard_gates.py` | Claude Code PreToolUse hook for the approval window (docs/design/phase1-usability.md, A8) |
| added | `tools/hooks/guard_model_folder.py` | Claude Code PreToolUse hook |
| added | `tools/master-only.txt` | files only the master kit needs (left out of project copies) |
| changed | `tools/pbik/README.md` | every pbik command, its options and what it writes |
| changed | `tools/pbik/pbikit/__init__.py` | pbik's version number |
| changed | `tools/pbik/pbikit/bind.py` | bind: move a report from its synthetic model to the published one and back (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/build.py` | `pbik build`: layout.json to PBIR files (idempotent) |
| changed | `tools/pbik/pbikit/catalog.py` | Settings catalog: every formatting property, value type and selector shape found in files Power BI Desktop saved |
| changed | `tools/pbik/pbikit/cli.py` | pbik's command line: every command and option |
| changed | `tools/pbik/pbikit/desktop.py` | pbik desktop state / reload / screenshot |
| added | `tools/pbik/pbikit/drops.py` | The project's two drop folders (one folder = one project, v1.7) |
| added | `tools/pbik/pbikit/fromreport.py` | `pbik layout from-report <X.Report> [--out F]` |
| added | `tools/pbik/pbikit/gates.py` | Person-only gates: an approval window the agent opens itself (docs/design/phase1-usability.md, A8 and B2) |
| added | `tools/pbik/pbikit/history.py` | Build history and the build option (docs/design/phase1-usability.md, A4) |
| added | `tools/pbik/pbikit/intake.py` | `pbik model intake`: the model drop folder (docs/design/phase1-usability.md, section 3) |
| added | `tools/pbik/pbikit/newreport.py` | A clean, empty report folder for a new project (walkthrough fix 1, v1.7) |
| changed | `tools/pbik/pbikit/packs.py` | Model packs (batch 3 item 15) |
| added | `tools/pbik/pbikit/picker.py` | Desktop as the model picker for bind live (docs/design/phase1-usability.md, section 5) |
| added | `tools/pbik/pbikit/plan.py` | The plan as a picture (docs/design/phase1-usability.md, A3) |
| added | `tools/pbik/pbikit/polish.py` | `pbik layout polish` |
| added | `tools/pbik/pbikit/progress.py` | Plain progress lines during long waits (walkthrough fix 4, v1.7) |
| added | `tools/pbik/pbikit/projectinit.py` | `pbik project init <name>` |
| added | `tools/pbik/pbikit/projectsetup.py` | One folder = one project (v1.7) |
| changed | `tools/pbik/pbikit/recolour.py` | Template colours to the current palette (pbik build, when tokens.json has theme.recolourTemplates) |
| added | `tools/pbik/pbikit/rules.py` | Flag grouping and plain-language explanations (docs/PLAIN-WORDS.md) |
| added | `tools/pbik/pbikit/score.py` | `pbik score`: the polish score, on every build's final screen and in the wrap-up (phase1-usability.md, A6) |
| added | `tools/pbik/pbikit/start.py` | The start of a build |
| added | `tools/pbik/pbikit/status.py` | `pbik status`: where a project is, in one plain line (docs/design/phase1-usability.md, A7) |
| added | `tools/pbik/pbikit/steps.py` | `pbik step start/end <step>` |
| added | `tools/pbik/pbikit/summary.py` | `pbik --report json <command>` |
| changed | `tools/pbik/pbikit/synth.py` | Synthetic models: the contract, its approval, the slice, generation and verification (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/synthgen.py` | Generate and verify a synthetic model from the approved contract and generate.json (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/validate.py` | `pbik validate`: schema, catalog, layout, accessibility and lesson checks |
| changed | `tools/pbik/pbikit/versions.py` | Power BI Desktop version targets |
| added | `tools/pbik/rules/library.json` | Generic flag rules (docs/design/phase1-usability.md, section 4) |
| changed | `tools/pbik/setup.cfg` | pbik package metadata and version (pip install -e) |
| added | `tools/pbik/skeleton/Fluent2-CY26SU09.json` | Fluent2-CY26SU09 |
| added | `tools/pbik/tests/big_model.py` | A large made-up semantic model for the Phase 1 tests |
| changed | `tools/pbik/tests/test_bind.py` | bind tests (docs/design/synth-to-live.md) on the made-up sample model and report (bind_sample.py) |
| added | `tools/pbik/tests/test_live.py` | The switch to live and back (v1.7 live walkthrough, CRITICAL 1-4), made-up model and report only |
| changed | `tools/pbik/tests/test_pbik.py` | pbik tests on a scratch copy of a saved PBIP (never the original) |
| added | `tools/pbik/tests/test_phase1.py` | Phase 1 usability tests (docs/design/phase1-usability.md) on made-up data only |
| changed | `tools/pbik/tests/test_synth.py` | Synthetic-to-live tests (docs/design/synth-to-live.md) on made-up sample data only |
| added | `tools/pbik/tests/test_v17.py` | v1.7 tests (docs/design/phase1-usability.md, Part A) on made-up data only |
| added | `tools/pbik/tests/test_walkthrough.py` | Walkthrough fixes (v1.7, Phase 1 walkthrough of 2026-11-14), made-up data only |
| changed | `tools/run_tests.py` | Run the kit test suites, then (with --regression) the golden builds |
| changed | `tools/tests/test_kit.py` | Kit tests outside pbik |
| added | `tools/usage.py` | Tokens per build step (docs/design/phase1-usability.md, section 6) |
| added | `tools/walkthrough/make_inputs.py` | The walkthrough's made-up inputs, made to work together (v1.7 walkthrough fix 11) |

### v1.8 (v1.7 → v1.8): 68 rows

| Status | File | Purpose |
| --- | --- | --- |
| changed | `.claude/commands/plan.md` | /plan: design ambition, patterns, tokens, layout.json, spec and audit |
| changed | `.claude/commands/start.md` | the main flow (/start): detect inputs, plan picture, guided or quick build, polish score |
| changed | `.claude/commands/theme.md` | /theme: Make the colour scheme for this rep |
| changed | `.claude/rules/svg.md` | Static SVG images (icons, court lines, wallpaper) |
| changed | `.github/copilot-instructions.md` | Copilot instructions generated from CLAUDE.md and .claude/rules (tools/copilot/sync.py) |
| changed | `.github/prompts/kit-plan.prompt.md` | Copilot mirror of /plan |
| changed | `.github/prompts/kit-start.prompt.md` | Copilot mirror of /start (/kit-start) |
| changed | `.github/prompts/kit-theme.prompt.md` | The colour scheme: brand colours, a reference or a preset, every text and state WCAG AA |
| changed | `VERSIONS.md` | pinned versions, releases and the changelog |
| changed | `design/reference/layout-schema.md` | layout.json schema and visual IDs |
| added | `design/reviews/harvest-udf-kpi.md` | Clean harvest: udf-kpi-study |
| changed | `design/reviews/pbik-roadmap.md` | the pbik coverage roadmap, gap status and release roadmap |
| changed | `design/scripts/gen_theme.py` | Generate design/themes/pbip-polish.json (Power BI report theme) from design/tokens.json |
| changed | `design/scripts/gen_wireframe_hf.py` | High-fidelity wireframe (the kit default) |
| changed | `design/scripts/test_wireframe.py` | Tests for the high-fidelity wireframe (gen_wireframe_hf.py) and its data step (wireframe_data.py) |
| added/changed | `design/templates/*.json` | visual templates harvested from Desktop-saved files |
| changed | `design/themes/presets/README.md` | theme presets and the Styles table (house styles) |
| added | `design/themes/presets/rail-panel.json` | Rail + panel preset (study 2026-11-15, GENERIC) |
| changed | `design/tokens.json` | the kit's default design tokens (colours, fonts, sizes) |
| changed | `design/udf/README.md` | DAX functions: DAX Lib packages |
| added | `design/udf/library/index_udf.py` | Rebuild a kit UDF library's index.json from its files (UDF KPI card study, 2026-11-15 |
| added | `design/udf/library/park-kpi/CHANGES.md` | Kit changes to the author's functions |
| added | `design/udf/library/park-kpi/Park.*.tmdl` | the park-kpi UDF functions (KPI cards, micro charts, helpers), kit copies used with the author's permission |
| added | `design/udf/library/park-kpi/README.md` | UDF KPI card library (Park.*) — kit copy |
| added | `design/udf/library/park-kpi/index.json` | UDF KPI card library, kit copy (study 2026-11-15) |
| added | `design/udf/udf-kpi-library-provenance.md` | Provenance: UDF KPI card library (study 2026-11-15) |
| changed | `docs/layouts/README.md` | Layout styles: Small HTML references, one per layout style, that `/plan` maps to layout.json with design/scripts/ref_layout.py |
| added | `docs/layouts/starters/profile-explorer.json` | starter layout: rail with two pickers, tabs, one panel (rail + panel) |
| changed | `docs/lessons/README.md` | Lessons: format, placement and upkeep |
| changed | `docs/lessons/build.md` | Build method: Read by /plan (layout.json keys), /build and /fix |
| changed | `docs/lessons/cards.md` | Shapes, containers and new cards |
| changed | `docs/lessons/dax.md` | Model and DAX: Read by /model (proposing and applying measures), /plan (audit states) and /fix (measure fixes) |
| changed | `docs/patterns/README.md` | the pattern library index (Use when, Avoid when, Styles) |
| changed | `docs/patterns/gallery-layout.json` | the pattern gallery page's layout (every pattern on one report) |
| changed | `docs/patterns/gallery.html` | the pattern gallery page: every pattern drawn as the plan picture draws it |
| changed | `docs/patterns/page-header-stack.md` | Page header stack: **Question it answers:** where am I, what is this page for, and what should I read first? |
| added | `docs/patterns/panel.md` | Shared panel: **Question it answers:** which numbers and charts belong together? |
| added | `docs/patterns/rail-panel.md` | Rail + panel layout: **Question it answers:** which member am I looking at, and what is its whole story? |
| added | `docs/patterns/svg-kpi-card.md` | SVG KPI card: design/reviews/pbik-roadmap.md) |
| changed | `docs/patterns/tabs-underline.md` | Tabs with underline: **Question it answers:** which view am I on, and what else is there? |
| changed | `docs/patterns/two-kpi-card.md` | Two-KPI tinted card: **Question it answers:** how do two related numbers stand against each other (actual and target, this year and last)? |
| changed | `tools/pbik/README.md` | every pbik command, its options and what it writes |
| changed | `tools/pbik/pbikit/__init__.py` | pbik's version number |
| changed | `tools/pbik/pbikit/bind.py` | bind: move a report from its synthetic model to the published one and back (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/build.py` | `pbik build`: layout.json to PBIR files (idempotent) |
| changed | `tools/pbik/pbikit/cli.py` | pbik's command line: every command and option |
| added | `tools/pbik/pbikit/harvestclean.py` | pbik templates harvest --clean |
| changed | `tools/pbik/pbikit/kpicards.py` | KPI card rule (batch 3 item 10, docs/lessons/cards.md C-10) |
| changed | `tools/pbik/pbikit/plan.py` | The plan as a picture (docs/design/phase1-usability.md, A3) |
| changed | `tools/pbik/pbikit/score.py` | `pbik score`: the polish score, on every build's final screen and in the wrap-up (phase1-usability.md, A6) |
| changed | `tools/pbik/pbikit/start.py` | The start of a build |
| changed | `tools/pbik/pbikit/synth.py` | Synthetic models: the contract, its approval, the slice, generation and verification (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/synthgen.py` | Generate and verify a synthetic model from the approved contract and generate.json (docs/design/synth-to-live.md) |
| added | `tools/pbik/pbikit/udf.py` | Kit UDF libraries: an optional toolbelt of DAX user-defined functions (UDF KPI card study, 2026-11-15) |
| changed | `tools/pbik/pbikit/unverified.py` | Features pbik writes that no Desktop save has confirmed yet |
| changed | `tools/pbik/pbikit/validate.py` | `pbik validate`: schema, catalog, layout, accessibility and lesson checks |
| changed | `tools/pbik/setup.cfg` | pbik package metadata and version (pip install -e) |
| added | `tools/pbik/tests/test_harvestclean.py` | pbik templates harvest --clean |
| changed | `tools/pbik/tests/test_layout_rules.py` | Layout rules (batch 3 items 10, 11 and 14) on made-up sample pages |
| changed | `tools/pbik/tests/test_pbik.py` | pbik tests on a scratch copy of a saved PBIP (never the original) |
| added | `tools/pbik/tests/test_udf.py` | UDF toolbelt tests (UDF KPI card study, 2026-11-15) |
| changed | `tools/pbik/tests/test_v17.py` | v1.7 tests (docs/design/phase1-usability.md, Part A) on made-up data only |
| changed | `tools/regression/cases/rep4-parity/` | regression case rep4-parity: inputs and golden build |
| changed | `tools/regression/cases/rep5-parity-overview/` | regression case rep5-parity-overview: inputs and golden build |
| changed | `tools/regression/cases/rep5-parity-workforce-mix/` | regression case rep5-parity-workforce-mix: inputs and golden build |
| changed | `tools/regression/cases/rep8/` | regression case rep8: inputs and golden build |
| changed | `tools/run_tests.py` | Run the kit test suites, then (with --regression) the golden builds |
| changed | `tools/tests/test_kit.py` | Kit tests outside pbik |

### v1.9 (v1.8 → v1.9): 20 rows

| Status | File | Purpose |
| --- | --- | --- |
| changed | `.claude/rules/svg.md` | Static SVG images (icons, court lines, wallpaper) |
| changed | `.github/copilot-instructions.md` | Copilot instructions generated from CLAUDE.md and .claude/rules (tools/copilot/sync.py) |
| changed | `VERSIONS.md` | pinned versions, releases and the changelog |
| changed | `design/reviews/pbik-roadmap.md` | the pbik coverage roadmap, gap status and release roadmap |
| changed | `design/udf/library/index_udf.py` | Rebuild a kit UDF library's index.json from its files (UDF KPI card study, 2026-11-15 |
| changed | `design/udf/library/park-kpi/CHANGES.md` | Kit changes to the author's functions |
| changed | `design/udf/library/park-kpi/Park.*.tmdl` | the park-kpi UDF functions (KPI cards, micro charts, helpers), kit copies used with the author's permission |
| changed | `design/udf/library/park-kpi/index.json` | UDF KPI card library, kit copy (study 2026-11-15) |
| changed | `docs/lessons/cards.md` | Shapes, containers and new cards |
| changed | `docs/patterns/svg-kpi-card.md` | SVG KPI card: design/reviews/pbik-roadmap.md) |
| changed | `tools/pbik/README.md` | every pbik command, its options and what it writes |
| changed | `tools/pbik/pbikit/__init__.py` | pbik's version number |
| changed | `tools/pbik/pbikit/build.py` | `pbik build`: layout.json to PBIR files (idempotent) |
| changed | `tools/pbik/pbikit/cli.py` | pbik's command line: every command and option |
| changed | `tools/pbik/pbikit/polish.py` | `pbik layout polish` |
| changed | `tools/pbik/pbikit/synthgen.py` | Generate and verify a synthetic model from the approved contract and generate.json (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/udf.py` | Kit UDF libraries: an optional toolbelt of DAX user-defined functions (UDF KPI card study, 2026-11-15) |
| changed | `tools/pbik/pbikit/validate.py` | `pbik validate`: schema, catalog, layout, accessibility and lesson checks |
| changed | `tools/pbik/setup.cfg` | pbik package metadata and version (pip install -e) |
| changed | `tools/pbik/tests/test_udf.py` | UDF toolbelt tests (UDF KPI card study, 2026-11-15) |

### v1.10 (v1.9 → v1.10): 21 rows

| Status | File | Purpose |
| --- | --- | --- |
| changed | `VERSIONS.md` | pinned versions, releases and the changelog |
| changed | `design/scripts/test_wireframe.py` | Tests for the high-fidelity wireframe (gen_wireframe_hf.py) and its data step (wireframe_data.py) |
| changed | `docs/PLAIN-WORDS.md` | Plain words: What the agent says to the user, so Claude Code and GitHub Copilot say the same thing |
| changed | `docs/lessons/README.md` | Lessons: format, placement and upkeep |
| changed | `docs/lessons/_retired.md` | Retired lessons: Lessons /tidy took out of the topic files |
| changed | `docs/lessons/accessibility.md` | Accessibility: Read by /plan (alt text, colours), /build and /fix |
| changed | `docs/lessons/build.md` | Build method: Read by /plan (layout.json keys), /build and /fix |
| changed | `tools/pbik/README.md` | every pbik command, its options and what it writes |
| changed | `tools/pbik/pbikit/__init__.py` | pbik's version number |
| changed | `tools/pbik/pbikit/a11y.py` | Accessibility checks for pbik validate (warnings |
| changed | `tools/pbik/pbikit/build.py` | `pbik build`: layout.json to PBIR files (idempotent) |
| added | `tools/pbik/pbikit/gridsnap.py` | The layout grid: which visuals are out of line and by how much, and the snap `pbik build` makes before the score (v1.10) |
| changed | `tools/pbik/pbikit/score.py` | `pbik score`: the polish score, on every build's final screen and in the wrap-up (phase1-usability.md, A6) |
| changed | `tools/pbik/setup.cfg` | pbik package metadata and version (pip install -e) |
| changed | `tools/pbik/tests/test_pbik.py` | pbik tests on a scratch copy of a saved PBIP (never the original) |
| changed | `tools/pbik/tests/test_v17.py` | v1.7 tests (docs/design/phase1-usability.md, Part A) on made-up data only |
| changed | `tools/pbik/tests/test_walkthrough.py` | Walkthrough fixes (v1.7, Phase 1 walkthrough of 2026-11-14), made-up data only |
| changed | `tools/regression/cases/rep4-parity/` | regression case rep4-parity: inputs and golden build |
| changed | `tools/regression/cases/rep5-parity-overview/` | regression case rep5-parity-overview: inputs and golden build |
| changed | `tools/regression/cases/rep5-parity-workforce-mix/` | regression case rep5-parity-workforce-mix: inputs and golden build |
| changed | `tools/regression/cases/rep8/` | regression case rep8: inputs and golden build |

### v1.11–v1.11.1 (v1.10 → v1.11.1): 83 rows

| Status | File | Purpose |
| --- | --- | --- |
| changed | `.claude/commands/plan.md` | /plan: design ambition, patterns, tokens, layout.json, spec and audit |
| changed | `.claude/rules/pbik.md` | Running pbik: pbik rules (tools/pbik/README.md has every command) and the Desktop and PBIR facts that came with them |
| changed | `.github/copilot-instructions.md` | Copilot instructions generated from CLAUDE.md and .claude/rules (tools/copilot/sync.py) |
| changed | `.github/prompts/kit-plan.prompt.md` | Copilot mirror of /plan |
| changed | `.gitignore` | files git never tracks (data, caches, tool folders, builds) |
| changed | `VERSIONS.md` | pinned versions, releases and the changelog |
| changed | `design/reviews/pbik-roadmap.md` | the pbik coverage roadmap, gap status and release roadmap |
| changed | `design/scripts/gen_wireframe_hf.py` | High-fidelity wireframe (the kit default) |
| changed | `design/specs/project.json` | project settings: target Desktop, catalog, build routes |
| changed | `design/templates/*.json` | visual templates harvested from Desktop-saved files |
| changed | `docs/PLAIN-WORDS.md` | Plain words: What the agent says to the user, so Claude Code and GitHub Copilot say the same thing |
| changed | `docs/PLAYBOOK.md` | Playbook: How the kit works, step by step |
| changed | `docs/WORK-SETUP.md` | Work setup: VS Code with GitHub Copilot |
| added | `docs/design/app-visuals.md` | App visuals (v1.11): Design note for teaching pbik to build reports that feel like an app |
| changed | `docs/lessons/README.md` | Lessons: format, placement and upkeep |
| changed | `docs/lessons/build.md` | Build method: Read by /plan (layout.json keys), /build and /fix |
| changed | `docs/lessons/cards.md` | Shapes, containers and new cards |
| changed | `docs/lessons/dax.md` | Model and DAX: Read by /model (proposing and applying measures), /plan (audit states) and /fix (measure fixes) |
| changed | `docs/lessons/slicers.md` | Slicers and navigation |
| changed | `docs/patterns/README.md` | the pattern library index (Use when, Avoid when, Styles) |
| added | `docs/patterns/app-visuals/*.md` | app-visual pattern pages (Use when, build route, settings) |
| added | `tools/appvisuals/deneb/starter.test.json` | Made-up categories for the Deneb starter (pbik visual test) |
| added | `tools/appvisuals/deneb/starter.vl.json` | the Deneb starter spec (Vega-Lite) pbik copies for a new Deneb visual |
| added | `tools/appvisuals/harness/` | the offline harness: a fake Power BI host, page and runner (Playwright) |
| added | `tools/appvisuals/lock.json` | The app-visual toolchain, pinned (docs/design/app-visuals.md) |
| added | `tools/appvisuals/package-lock.json` | pbik-appvisual-tools |
| added | `tools/appvisuals/package.json` | The kit's app-visual toolchain (docs/design/app-visuals.md) |
| added | `tools/appvisuals/template/NOTICE.md` | Notices: The pbip-kit app-visual template started from Microsoft's Dot Plot visual |
| added | `tools/appvisuals/template/assets/icon.png` | the default icon of a kit custom visual |
| added | `tools/appvisuals/template/capabilities.json` | the app-visual template's data roles, objects and settings |
| added | `tools/appvisuals/template/eslint.config.mjs` | ", "dist/**", ".vscode/**", ".tmp/**"], |
| added | `tools/appvisuals/template/package.json` | pbip-kit app visual. Packages come from the kit tools folder (pbik visual build links them) |
| added | `tools/appvisuals/template/pbiviz.json` | the app-visual template's package metadata (placeholder author and support link) |
| added | `tools/appvisuals/template/src/kit/data.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/filter.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/fonts.generated.ts` | Placeholder: `pbik visual build` replaces this file in the build copy with the bundled fonts (base64) |
| added | `tools/appvisuals/template/src/kit/fonts.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/icons.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/interaction.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/layers.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/morph.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/motion.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/patterns/drill.ts` | pbip-kit pattern modules |
| added | `tools/appvisuals/template/src/kit/patterns/emphasis.ts` | pbip-kit pattern modules |
| added | `tools/appvisuals/template/src/kit/patterns/headline.ts` | pbip-kit pattern modules |
| added | `tools/appvisuals/template/src/kit/patterns/layouts.ts` | pbip-kit pattern modules |
| added | `tools/appvisuals/template/src/kit/patterns/range.ts` | pbip-kit pattern modules |
| added | `tools/appvisuals/template/src/kit/perf.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/scene.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/settings.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/state.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/theme.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/updates.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/kit/vendor-types.d.ts` | Morph one SVG path into another |
| added | `tools/appvisuals/template/src/kit/words.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/src/visual.ts` | pbip-kit app-visual template |
| added | `tools/appvisuals/template/stringResources/en-US/resources.resjson` | display strings |
| added | `tools/appvisuals/template/style/visual.less` | the frame meter (debug |
| added | `tools/appvisuals/template/test/` | harness scenarios for the app-visual template |
| added | `tools/appvisuals/template/tsconfig.json` | TypeScript settings for kit custom visuals |
| changed | `tools/doctor.ps1` | checks the machine: tools, versions, the Desktop Bridge and the Copilot mirror |
| changed | `tools/export_check.py` | Clean-export check: run it before every push (README "Before you push") |
| changed | `tools/pbik/README.md` | every pbik command, its options and what it writes |
| changed | `tools/pbik/pbikit/__init__.py` | pbik's version number |
| added | `tools/pbik/pbikit/apptools.py` | `pbik tools`: the app-visual toolchain (docs/design/app-visuals.md), installed without admin rights into the kit tools folder outside the repo (%USERPROFILE%\.pbik-tools,… |
| added | `tools/pbik/pbikit/appvisual.py` | `pbik visual`: kit custom visuals (.pbiviz from the app-visual template) and Deneb specs (docs/design/app-visuals.md) |
| changed | `tools/pbik/pbikit/build.py` | `pbik build`: layout.json to PBIR files (idempotent) |
| changed | `tools/pbik/pbikit/cli.py` | pbik's command line: every command and option |
| changed | `tools/pbik/pbikit/deneb.py` | Deneb visuals (visual-method ladder step 3) |
| changed | `tools/pbik/pbikit/desktop.py` | pbik desktop state / reload / screenshot |
| changed | `tools/pbik/pbikit/gridsnap.py` | The layout grid: which visuals are out of line and by how much, and the snap `pbik build` makes before the score (v1.10) |
| changed | `tools/pbik/pbikit/score.py` | `pbik score`: the polish score, on every build's final screen and in the wrap-up (phase1-usability.md, A6) |
| changed | `tools/pbik/pbikit/status.py` | `pbik status`: where a project is, in one plain line (docs/design/phase1-usability.md, A7) |
| changed | `tools/pbik/pbikit/templates.py` | pbik templates harvest |
| changed | `tools/pbik/pbikit/tmdl.py` | Read a semantic model's TMDL folder (tables, columns, measures, relationships) and check DAX references |
| changed | `tools/pbik/pbikit/unverified.py` | Features pbik writes that no Desktop save has confirmed yet |
| changed | `tools/pbik/pbikit/validate.py` | `pbik validate`: schema, catalog, layout, accessibility and lesson checks |
| changed | `tools/pbik/setup.cfg` | pbik package metadata and version (pip install -e) |
| added | `tools/pbik/tests/sample/templates/advancedSlicerVisual.json` | button slicer template for the pbik tests |
| changed | `tools/pbik/tests/test_pbik.py` | pbik tests on a scratch copy of a saved PBIP (never the original) |
| added | `tools/pbik/tests/test_v111.py` | v1.11 tests (app-like visuals, the Desktop review of 2026-11-17) on made-up data only |
| changed | `tools/run_tests.py` | Run the kit test suites, then (with --regression) the golden builds |
| changed | `tools/tests/test_kit.py` | Kit tests outside pbik |

### v1.12.0 (v1.11.1 → v1.12.0): 83 rows

| Status | File | Purpose |
| --- | --- | --- |
| changed | `.claude/commands/plan.md` | /plan: design ambition, patterns, tokens, layout.json, spec and audit |
| changed | `.claude/commands/start.md` | the main flow (/start): detect inputs, plan picture, guided or quick build, polish score |
| changed | `.github/prompts/kit-plan.prompt.md` | Copilot mirror of /plan |
| changed | `.github/prompts/kit-start.prompt.md` | Copilot mirror of /start (/kit-start) |
| added | `MERGE-NOTES.md` | these merge notes (also docs/MERGE-NOTES.md) |
| changed | `VERSIONS.md` | pinned versions, releases and the changelog |
| added | `design/reviews/batch-studies-part-d.md` | Batch studies, Part D |
| changed | `design/reviews/pbik-roadmap.md` | the pbik coverage roadmap, gap status and release roadmap |
| changed | `design/scripts/ambition.py` | Design ambition checks (/plan step 1, before choosing visuals) |
| changed | `design/scripts/check_contrast.py` | WCAG 2.1 AA contrast of every text on the drawn wireframe (design/wireframes/wireframe.html), as a viewer sees it |
| changed | `design/scripts/edge_page.py` | Headless Edge for pages the kit draws |
| changed | `design/scripts/example_values.py` | Example values for the fast HTML preview (the plan picture and quick changes) |
| changed | `design/scripts/fidelity_check.py` | Fidelity check: does the high-fidelity wireframe draw what Power BI Desktop shows? |
| changed | `design/scripts/gen_theme.py` | Generate design/themes/pbip-polish.json (Power BI report theme) from design/tokens.json |
| changed | `design/scripts/gen_tokens.py` | /theme: build design/tokens.json from brand colours, a reference (image or HTML) or a preset, with every text and state colour moved until it passes WCAG 2.1 AA |
| changed | `design/scripts/gen_wireframe_hf.py` | High-fidelity wireframe (the kit default) |
| changed | `design/scripts/pattern_choices.py` | The spec's "Pattern choices" section (batch 3 items 13-14), checked by audit_ids.py |
| added | `design/scripts/space_svg.py` | Pictures of the spatial canvas's built-in spaces, for the native route (docs/patterns/spatial-canvas.md, step 1) |
| changed | `design/scripts/test_wireframe.py` | Tests for the high-fidelity wireframe (gen_wireframe_hf.py) and its data step (wireframe_data.py) |
| changed | `design/themes/presets/README.md` | theme presets and the Styles table (house styles) |
| changed | `design/themes/presets/bento.json` | Bento preset: tiles of mixed spans on a warm canvas, large corners, no borders, near-flat shadow |
| changed | `design/themes/presets/clean.json` | The default preset (/theme with no brand colours or reference) |
| changed | `design/themes/presets/corporate.json` | Corporate preset: navy and blue, square-ish corners, 1px borders instead of shadows |
| added | `design/themes/presets/dark-glass.json` | Dark glass preset (the maintainer's house style, study 2026-11-18, GENERIC) |
| added | `design/themes/presets/panel-style.json` | Panel style layout preset (the maintainer's house style, learned from Rep 9, v1.12, GENERIC) |
| changed | `design/themes/presets/rail-panel.json` | Rail + panel preset (study 2026-11-15, GENERIC) |
| changed | `design/tokens.json` | the kit's default design tokens (colours, fonts, sizes) |
| added | `docs/MERGE-NOTES.md` | these merge notes |
| changed | `docs/design/app-visuals.md` | App visuals (v1.11): Design note for teaching pbik to build reports that feel like an app |
| changed | `docs/lessons/build.md` | Build method: Read by /plan (layout.json keys), /build and /fix |
| changed | `docs/patterns/README.md` | the pattern library index (Use when, Avoid when, Styles) |
| changed | `docs/patterns/app-visuals/*.md` | app-visual pattern pages (Use when, build route, settings) |
| added | `docs/patterns/breakdown-wall.md` | Breakdown wall: **Question it answers:** for the measure I pick, how does every way of slicing it compare with last year? |
| changed | `docs/patterns/exception-list.md` | Exception list: **Question it answers:** which members need attention, worst first? |
| changed | `docs/patterns/gallery-layout.json` | the pattern gallery page's layout (every pattern on one report) |
| added | `docs/patterns/honest-data.md` | Honest data: **Question it answers:** can I trust this number, and is it good for its kind? |
| added | `docs/patterns/label-above-bars.md` | Label-above bars: **Question it answers:** which few items are biggest, with room for their full names? |
| added | `docs/patterns/panel-style-layout.md` | Panel style layout: GENERIC) |
| changed | `docs/patterns/rail-panel.md` | Rail + panel layout: **Question it answers:** which member am I looking at, and what is its whole story? |
| added | `docs/patterns/spatial-canvas.md` | Spatial canvas: **Question it answers:** where in a space do things happen, and which areas run hot or cold? |
| added | `docs/patterns/threshold-histogram.md` | Threshold histogram: **Question it answers:** how is a duration or amount spread out, and how much of it is inside the limit? |
| changed | `tools/appvisuals/harness/` | the offline harness: a fake Power BI host, page and runner (Playwright) |
| added | `tools/appvisuals/starters/spatial-canvas/capabilities.json` | the spatial canvas starter's data roles (X, Y, Item, Zone, Outcome, Benchmark) and settings |
| added | `tools/appvisuals/starters/spatial-canvas/src/settings.ts` | Spatial canvas: formatting pane |
| added | `tools/appvisuals/starters/spatial-canvas/src/visual.ts` | Spatial canvas (kit proof visual) |
| added | `tools/appvisuals/starters/spatial-canvas/test/` | harness scenarios and goldens for the spatial-canvas starter |
| changed | `tools/appvisuals/template/src/kit/interaction.ts` | pbip-kit app-visual template |
| changed | `tools/appvisuals/template/src/kit/layers.ts` | pbip-kit app-visual template |
| changed | `tools/appvisuals/template/src/kit/motion.ts` | pbip-kit app-visual template |
| changed | `tools/appvisuals/template/src/kit/patterns/headline.ts` | pbip-kit pattern modules |
| added | `tools/appvisuals/template/src/kit/patterns/honest.ts` | pbip-kit pattern modules |
| added | `tools/appvisuals/template/src/kit/patterns/spatial.ts` | pbip-kit pattern modules |
| added | `tools/appvisuals/template/src/kit/quality.ts` | pbip-kit app-visual template |
| changed | `tools/appvisuals/template/src/kit/scene.ts` | pbip-kit app-visual template |
| changed | `tools/appvisuals/template/src/visual.ts` | pbip-kit app-visual template |
| changed | `tools/appvisuals/template/style/visual.less` | the frame meter (debug |
| changed | `tools/export_check.py` | Clean-export check: run it before every push (README "Before you push") |
| changed | `tools/pbik/README.md` | every pbik command, its options and what it writes |
| changed | `tools/pbik/pbikit/__init__.py` | pbik's version number |
| changed | `tools/pbik/pbikit/a11y.py` | Accessibility checks for pbik validate (warnings |
| changed | `tools/pbik/pbikit/appvisual.py` | `pbik visual`: kit custom visuals (.pbiviz from the app-visual template) and Deneb specs (docs/design/app-visuals.md) |
| changed | `tools/pbik/pbikit/build.py` | `pbik build`: layout.json to PBIR files (idempotent) |
| changed | `tools/pbik/pbikit/catalog.py` | Settings catalog: every formatting property, value type and selector shape found in files Power BI Desktop saved |
| changed | `tools/pbik/pbikit/cli.py` | pbik's command line: every command and option |
| changed | `tools/pbik/pbikit/gridsnap.py` | The layout grid: which visuals are out of line and by how much, and the snap `pbik build` makes before the score (v1.10) |
| added | `tools/pbik/pbikit/honest.py` | Honest data settings (docs/patterns/honest-data.md) |
| added | `tools/pbik/pbikit/icons.py` | The kit's own icons (v1.12, panel style layout) |
| changed | `tools/pbik/pbikit/kpicards.py` | KPI card rule (batch 3 item 10, docs/lessons/cards.md C-10) |
| added | `tools/pbik/pbikit/panelstyle.py` | `pbik layout panels` |
| changed | `tools/pbik/pbikit/plan.py` | The plan as a picture (docs/design/phase1-usability.md, A3) |
| changed | `tools/pbik/pbikit/polish.py` | `pbik layout polish` |
| changed | `tools/pbik/pbikit/score.py` | `pbik score`: the polish score, on every build's final screen and in the wrap-up (phase1-usability.md, A6) |
| changed | `tools/pbik/pbikit/synth.py` | Synthetic models: the contract, its approval, the slice, generation and verification (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/synthgen.py` | Generate and verify a synthetic model from the approved contract and generate.json (docs/design/synth-to-live.md) |
| changed | `tools/pbik/pbikit/tmdl.py` | Read a semantic model's TMDL folder (tables, columns, measures, relationships) and check DAX references |
| changed | `tools/pbik/pbikit/validate.py` | `pbik validate`: schema, catalog, layout, accessibility and lesson checks |
| changed | `tools/pbik/setup.cfg` | pbik package metadata and version (pip install -e) |
| changed | `tools/pbik/tests/test_v111.py` | v1.11 tests (app-like visuals, the Desktop review of 2026-11-17) on made-up data only |
| changed | `tools/pbik/tests/test_walkthrough.py` | Walkthrough fixes (v1.7, Phase 1 walkthrough of 2026-11-14), made-up data only |
| changed | `tools/regression/cases.json` | Golden builds (tools/regression/regress.py) |
| added | `tools/regression/cases/panel-style/` | regression case panel-style: inputs and golden build |
| changed | `tools/regression/regress.py` | Regression suite: golden builds of the Rep 4 parity, Rep 5 parity (two pages), Rep 8 and panel style layouts |
| changed | `tools/tests/sample/tokens.json` | Neutral starting tokens for pbip-kit v0.2 |
