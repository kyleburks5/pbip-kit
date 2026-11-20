# Merge notes: v1.5 to v1.12.0

For merging this kit into a work copy that was taken at v1.4 or earlier. One section per batch, oldest first: what
was added or changed, the settings and defaults, what the Copilot files need, and the tests to run before going on.
Merge one batch at a time, run its tests, commit, then start the next. Paths are relative to the kit root.

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
