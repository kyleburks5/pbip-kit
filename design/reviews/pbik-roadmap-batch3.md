# pbik roadmap batch 3 (2026-11-13)

From tag `pre-batch3-2026-11-13`, one commit per item (`batch3 item <n>: <name>`), plus one commit of fixes the smoke
dry run found. Built from the brief only. Every test uses made-up data: the sample model
`tools/pbik/tests/synth_sample/Example Live.SemanticModel` and the report in `tools/pbik/tests/bind_sample.py`. New
suites: `synth`, `bind`, `layout` (tools/run_tests.py). Design: docs/design/synth-to-live.md.

## Status

| Item | Status | Where |
| --- | --- | --- |
| 0a data classes | done | `pbik project class`; guard in `desktop screenshot` and run-dax.ps1 |
| 0b-0c contract, approval | done | `pbik synth contract / resolve / approve` |
| 0d slice, generate, verify | done, UNVERIFIED in Desktop (calculated DATATABLE tables) | `pbik synth slice / generate / verify` |
| 0e-0h bind check, prepare, live, local | done; live's `byConnection` string UNVERIFIED in Desktop | `pbik bind ...` |
| 1 bind map | done | `pbik bind map draft / approve`, rewrite on live |
| 2 stale references | done | `bind check` |
| 3 exact local restore | done | `bind local [--restore-backup]` |
| 4 fewer false alarms | done | `bind check`, `tmdl.virtual_names` |
| 5 filter value types | done | `pbik validate`, `bind check` (filtertypes.py) |
| 6 model ID links, workspace warnings | done | `bind live --id`, project.json `workspaces` |
| 7 keep option-table rows | done | resolution `keep rows: option labels`, `KEEP <n>` at approve |
| 8 shape hints | done | generate.json hints `trend`, `seasonality`, `monthEnd` |
| 9 case-insensitive names | done | `names.CIDict` in the TMDL reader, `names` helpers everywhere new |
| 10 KPI card rule | done; template hand-written (replace with a Desktop-polished card) | validate (kpicards.py), card_space.py, `cardVisual.kpi-delta-card` |
| 11 layout fidelity | done | `desktopPosition`, binding `active: false`, Desktop bookmark groups, `roundtrip --name-new` |
| 12 lessons | done | C-07 (reworded), C-10, C-11, B-13; known-gaps "does card padding work?" open |
| 13 pattern pages | done | Use when / Avoid when on every pattern; /plan "Pattern choices" |
| 14 audit_ids, canvas height | done | pattern_choices.py; `ref_layout.py --canvas-height` |
| 15 model packs | done | `pbik model register / drift / approve`, `pbik project new --from-pack` |
| 16 fast test mode | done | `run_tests.py` (`--all`, `--changed`, `--regression`) |
| 17 test robustness | done | tools/tests/sample/; test 51 skips while Desktop is open |

Blocked: none.

## Decisions taken (change them if you disagree)

- Person-only steps (`synth approve`, `bind map approve`, `bind live`, `model approve`, lowering the data class,
  `bind local --restore-backup`) refuse when stdin isn't a terminal or `CLAUDECODE` is set: an agent can't run them.
- `KEEP <n>`: n is the number of rows kept (all kept tables together). Option tables: a warning above 200 rows, refused above 1000 (raised from 50 on 2026-11-13).
- Stale references fail `bind check` (exit 1) like map errors, but are listed apart.
- Headers keep synthetic labels by adding `displayName` where bind live renames a field; `bind local` removes them.
- Packs refuse any git repository unless `--allow-repo` (never the kit's or the project's own); `register` writes a
  `.gitignore` of `*` either way.
- Fast mode: the master kit (no `*.pbip`, no design/specs/layout.json) still runs every suite by default.
- Not done: no pbik version bump or tag (VERSIONS.md says new commands are a minor release: pbik 0.15.0, kit v1.5).

## Desktop checklist (pbik-smoke-batch3)

`..\pbik-smoke-batch3\` (beside the kit folder) is the smoke project: made-up data only, data class restricted.
`make_smoke.py setup` has run: skeleton report, the made-up live model in `live\v1` and `live\v2` (v2 renames
Orders, Orders[Amount], [Total Units], Plan Option and its label), layout.json with three pages, generate.json (trend,
seasonality, a planned measure) and a contract with every flag resolved. It stops at the first approval, which is
yours. The whole chain (both approvals stubbed) was dry-run in a scratch copy: build idempotent, validate 0 errors,
bind check 0, live -> local byte for byte.

In a terminal, in `..\pbik-smoke-batch3` (`pbik` = `python ..\pbip-kit-export\tools\pbik\pbik.py`):

1. `pbik synth approve --by <your name>`: 11 flags listed, then the kept rows Show all / Top ten / Bottom ten. Type
   `Example Live`, then `KEEP 3`.
2. `python make_smoke.py build`: expect verify 0 errors, the third build "No changes", validate 0 errors, bind check
   0 errors. `_pbik-built\` is the report as pbik wrote it.

In Desktop 2.159.883.0:

3. Open `Smoke.pbip`, click **Refresh** (it reads no source). Model view: five calculated tables (Area, Calendar,
   Orders, Plan Option, _Measures) and two relationships from Orders. *(0d: the synthetic TMDL form)*
4. **KPI row**: four equal cards across the content width, the chart lined up below; card 1 shows a "Last year"
   reference label; card 4 shows a percentage (Amount Share, a report-level measure after `bind prepare`). Do label,
   value and change line fill each card? *(item 10)*
5. Card padding question (known-gaps, C-07): on card 2, Format > General > Padding, set top to 40. Note whether the
   content moves. Leave it; the roundtrip records it.
6. The chart's background shape: Format > General > Properties > Advanced options shows **Maintain layer order** on;
   in reading view, clicking the panel doesn't cover the chart. *(C-11)*
7. The line chart: later years higher, December the peak month. *(item 8)*
8. **Option table**: the slicer shows Show all, Top ten, Bottom ten in that order *(item 7)*. The matrix shows regions,
   area level collapsed *(item 11, `active: false`)*; View > Tab order lists it third.
9. **Bind map**: "Top ten" is selected in the slicer. In the Bookmarks pane select both bookmarks and **Group** them
   (any name). *(item 11)*
10. Add any visual to **Bind map** (a card with Total Units). *(item 11, `--name-new`)*
11. Back in a terminal: `pbik desktop screenshot --report Smoke.Report --page "KPI row" --out _snapshots\kpi.png
    --region 0,0,1920,1080` (allowed: restricted, but on the synthetic model), then
    `python ..\pbip-kit-export\design\scripts\card_space.py Smoke.Report --page "KPI row" --png _snapshots\kpi.png`.
12. Save in Desktop, close it.

Then the roundtrip:

```
pbik roundtrip Smoke.Report --before _pbik-built\Smoke.Report --layout design\specs\layout.json --out roundtrip.md
```

It lists what Desktop rewrote and proposes an ID and alt text for the visual from step 10. Then
`pbik roundtrip Smoke.Report --before _pbik-built\Smoke.Report --name-new` names it, and `pbik build Smoke.Report
design\specs\layout.json` should say the two bookmarks sit in your Desktop group and are left alone.

Drift and the bind map (no Desktop needed):

13. `python make_smoke.py drift` (v2 contract; the rules carry every resolution, the renamed option table needs you
    again), `pbik synth approve --by <your name>` (`Example Live`, `KEEP 3`), `python make_smoke.py bindmap`: expect
    Orders -> Order Lines, Plan Option -> Option Picker, Orders[Amount] -> Net Amount, [Total Units] -> Units Sold,
    Option Label -> Label, and bind check 0 errors. Then `pbik bind map approve Smoke.Report --by <your name>`.
14. Optional, only with a published model you can use: connect a new Desktop report to it (Get data > Power BI
    semantic models), save it as PBIP, and compare its `definition.pbir` connection string with
    `bind.connection_string` (bind live's UNVERIFIED part). `bind live --from <that report>` copies Desktop's own.

## Desktop check results (2026-11-13, Desktop 2.159.883.0)

- **Bookmarks: confirmed in Desktop.** The two display bookmarks on "Bind map" hide and show the slicer from the
  bookmark buttons, the pane and Reading view; Desktop saved both bookmark files unchanged (final newline only).
  The first try looked broken only because the page had no buttons and the bookmarks keep the current page
  (`suppressActiveSection`): applied from another page they change nothing visible. No pbik change; test 90 pins
  the form. Not checked: the saved bookmarks.json has no Desktop-made group, so "pbik leaves bookmarks in a Desktop
  group alone" (item 11) is still unconfirmed in Desktop.
- **Drift and bind map:** v2 contract approved, `bind map draft` matched all five renames, `bind map approve` done,
  `bind check` 0 errors. No errors in any step.
- **Roundtrip** (`roundtrip.md` in the smoke folder), proposals for a later pbik fix:
  - `cardVisual.kpi-delta-card`: Desktop drops `layout.verticalAlignment` (4 cards): remove it from the template.
  - Bookmark buttons: Desktop drops the `objects.general` paragraphs pbik writes for button text (P3-V03, P3-V04).
  - Matrix rows: Desktop adds `active: true` on the first row field when a later one is `active: false` (P2-V03).
  - Desktop moved six visuals to visualContainer 2.14.0 (not in Microsoft's published schemas yet).
  - The rest is expected: the slicer selection you changed, the active page, the re-registered theme.
