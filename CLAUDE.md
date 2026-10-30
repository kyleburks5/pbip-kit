# pbip-kit

Goal: build polished Power BI reports (PBIP + PBIR) from a requirements file (design/reference/brd.md) and HTML wireframes. Public data only.

## Rules
- Canvas 1920x1080 (custom page size), 32px margin, 12-column grid, 24px gutters. Compute positions from the grid.
- Read design/tokens.json before styling. Never hardcode colors or fonts.
- Use only the powerbi-authoring modeling MCP server for model changes, plus the daxlib-mcp server (.mcp.json) only to
  install the DAX Lib packages listed in design/udf/packages.json, at `/model approved`. Ignore Fabric-only tools.
- Don't change the semantic model, or delete files, without asking.
- Running /model approved, /build or /fix counts as permission to commit; otherwise commit only when I say so.
- Approval gates: brd.md after /brd, the /model approval list, and /build approved after I have reviewed the wireframe.
- What the agent may see: aggregates only unless cleared (docs/it-security.md).
- Build, validate and check through pbik (tools/pbik/README.md): `python tools/pbik/pbik.py <command>` (or `pbik` after
  `pip install --user -e tools\pbik`). pbik rules and Desktop quirks are in .claude/rules/pbik.md.
- pbik is the only report CLI. Some installed Data Goblins skills show commands for another CLI: use their knowledge, but do the step with pbik or pbi-bridge.ps1. If pbik can't do it, stop and tell me.
- GitHub Copilot mirrors these files (.github/copilot-instructions.md, .github/prompts/): after editing CLAUDE.md,
  .claude/rules or .claude/commands, run `python tools/copilot/sync.py` (tests and doctor.ps1 check it).
- Plugin versions are pinned (auto-update off). At the start of each session, compare the installed plugin versions (~/.claude/plugins/installed_plugins.json) with VERSIONS.md. If they differ, add a row to the changelog in VERSIONS.md with the date, the plugin, the old and new version, and a note to run /smoke (one card, one button slicer, one table) before building anything large.

## Accessibility
- Every data visual and image has alt text; text meets WCAG 2.1 AA contrast (button, navigator and slicer text in each
  state too); no text below 10pt (tokens `a11y.minFontPt`); tab order follows reading order. Details:
  docs/lessons/accessibility.md. `pbik validate` checks all four as warnings (pbikit/a11y.py). Fix them in layout.json,
  or note why one is accepted in the spec by visual ID.

## Native first
- Build with native Power BI visuals and settings. Use SVG measures, HTML or custom visuals only as
  a fallback when a native visual can't do it (for example, status pill chips inside a table column).
- Visual-method ladder: 1 native (incl. the page background), 2 SVG (a measure, or a static image), 3 Deneb (certified
  AppSource visual), 4 any other custom visual (.pbiviz, HTML Content; uncertified until checked, docs/it-security.md).
  /plan picks the lowest step that meets the design (docs/patterns/ gives the ladder per pattern) and records
  `build.step` and `build.reason` per visual ID; audit_ids.py checks that the step matches `build.method`.
- Before using a fallback, tell me in one line what native option you tried and why it fails, record it in
  layout.json (`build.nativeTried`, `build.reason`) and in the fallback register in the spec by visual ID, and ask me
  before building it.
- Keep fallback work (like an SVG map) in place but unused until the native option is confirmed
  everywhere, then propose removing it.
- SVG rules are in .claude/rules/svg.md (a listed DAX Lib package before new SVG code). Deneb fallbacks and
  `build.method` are checked by `pbik validate` and audit_ids.py (docs/lessons/build.md).

## Visual IDs
- Every visual has a stable ID `P<page>-V<nn>` in layout.json, never reused: a removed visual's ID goes to `retired`.
- Use the ID in the wireframe (`data-id`), the spec, the review, the fix notes and the visual folder name (`<ID>_<name>`).
- Number visual IDs in reading order (top to bottom, left to right) so tab order follows: pbik writes tab order as the
  visual number x 100. Where it can't follow (a visual added later), set `tabOrder` on that visual in layout.json (Rep 9).
- design/scripts/audit_ids.py and `pbik validate --layout` check the IDs; /plan, /build, /review and /fix run them.

## Workflow
0. `/brd`: draft design/reference/brd.md from the template and my brief. Wait for my review.
1. `/model`: profile the raw data in data/ (row counts, timings, an audit-mode recommendation) and propose the core model from brd.md. Wait for my approval before applying it; `/model approved` applies it through the Modeling MCP, recalculates, runs `pbik model check` and a DAX query that every new measure returns a value, and commits.
2. `/plan`: first the design ambition in design/specs/spec.md (per key number: baseline, normal, exceptions, partial or stale; every headline number needs a comparison) and the patterns from docs/patterns/ that show it; then update design/tokens.json, write design/specs/layout.json, design/specs/spec.md and design/specs/audit.json. A wireframe or reference image in design/reference/ (any layout style: grid, bento, rail, tabs, dense tables) is optional input; if there is one, it is the source for layout.json (design/scripts/ref_layout.py), with what Power BI can't reproduce listed by ID. Otherwise layout.json comes from the BRD and design/scripts/gen_wireframe_hf.py draws the high-fidelity wireframe in design/wireframes/ (gen_wireframe.py, the box wireframe, is the fallback).
3. `/build`: build with `pbik build` from layout.json (styling through the theme and tokens), then run `pbik validate`, design/scripts/audit_layout.py and design/scripts/audit_ids.py.
4. I save and reload in Desktop; `/review` screenshots, compares to the wireframe and design/checks.md, and runs the numbers audit.
5. `/fix`: fix the review items, re-check, repeat.
6. After each step, say what changed.
- `/theme` makes the colour scheme on its own (brand colours, a reference, or a preset: clean, bento, corporate;
  every text and state AA); /plan step 2 runs the same.
- `/smoke` after any tool or plugin update; `/update` after a Power BI Desktop update (docs/UPDATE-ROUTINE.md);
  `/validate` runs the numbers audit on its own.

## Audit modes
The numbers audit runs in full, sampled or aggregate-only mode (aggregate-only, with no row export, whenever
row-level access isn't cleared): /model recommends one and records it in design/reviews/model-check.md and design/specs/audit.json. The
modes, their provisional thresholds and what every mode keeps are in docs/lessons/audit-modes.md.

## Lessons
When a fix works, propose a lesson where docs/lessons/README.md places it (here only if it applies to every session; one in, one out) and wait for approval. Each lesson names the rep it came from; helpers named
Topic lessons live in docs/lessons/ and the commands point to them at the step that needs them: dax.md, build.md,
cards.md (shapes, containers, new card), slicers.md, charts.md (charts and tables), accessibility.md, audit-modes.md.
pbik and Desktop quirks are in .claude/rules/pbik.md, SVG in .claude/rules/svg.md, and every gap with its Desktop click
steps in design/known-gaps.md (the pre-pbik gaps are history in examples/known-gaps-pbir.md).

### Desktop, refresh and reload
- Refresh is allowed when the source files exist in data/. Never repoint a source, and never refresh a model whose source is missing. A Calculate-only recalculation is always allowed.
- After adding calculated columns or tables, run a Calculate-only recalculation (it reads no data source). If it fails with "base version must not be negative", reconnect the modeling MCP first.
- Never reload or refresh while Desktop shows unsaved changes. Check first (`pbik desktop state --fail-if-dirty`) and stop if it's dirty; `pbik desktop reload` refuses on its own.
- After the agent edits report files, and after any reload or refresh (it marks the report unsaved itself), close Desktop without saving and reopen before the next reload.
