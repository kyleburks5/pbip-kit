# pbik roadmap batch 4 (2026-11-13)

From tag `pre-batch4-2026-11-13`, one commit per item (`batch4 item <n>: <name>`). Made-up data only.

## Status

| Item | Status | Where |
| --- | --- | --- |
| 1 lean learning system | already there (format, indexes, budgets, placement order, /tidy and /kit-tidy); tests now pin the /tidy safety rules and the placement order | tools/tests/test_kit.py |
| 2 visual headers | done | theme `*` visualHeader off (gen_theme.py); `pbik validate` warns on a visual turning its own on |
| 3 contrast tokens | done | `warningText`, `warningTint`, tokens `badges` (gen_tokens.py, AA-checked); a test over every tag, badge and tint pairing in all presets |
| 4 header band | done | pages align Top by default (`displayArea.verticalAlignment`); validate warns on a header not at 0,0 full width, padding 0; layout `header` |
| 5 clean-export check | done | `python tools/export_check.py` (README "Before you push"), allow-list tools/export_allow.txt |
| 6 pattern stubs | done; every template needs a Desktop-saved sample | docs/patterns: page-header-stack, headline-banner, ranked-bar-table, two-kpi-card, tabs-underline, text-link-button; index.json `status` |
| 7 roundtrip fixes | done | button `text` -> `objects.text.text` on `{id: default}`; matrix first row `active: true`; kpi-delta-card without `layout.verticalAlignment` |
| 8 grouped bookmarks | done | /smoke (and /kit-smoke) step 6 |

Blocked: none.

## Decisions taken (change them if you disagree)

- Item 1 needed no build: everything asked for was already in the kit, so the commit adds tests only.
- `warning` stays the secondary slate (layouts use it); the new amber is `warningText`.
- Pages pbik builds now align Top unless page `props` say otherwise. That changes every page.json pbik writes, so
  the regression goldens were updated (page.json `displayArea` and its owned entry only).
- Header visuals: a layout `header: true`, or a visual named `header-band` / `page-header`.
- Export check: the three made-up test sample folders are allow-listed with their reason; commit author fields
  aren't scanned (your name and email are on every commit by choice); a finding exits 1.
- Pattern stubs have no wireframe renderer yet (the wireframe draws their visual type) and no template file: index.json
  lists each template with `status: needs a Desktop-saved sample` until you harvest it.

## Desktop checklist (pbik-smoke-batch4)

`..\pbik-smoke-batch4\Smoke.pbip` (beside the kit folder): made-up data only, a copy of the batch 3 synthetic model.
`make_smoke.py` built it (0 errors, the second build "No changes"); `_pbik-built\` is the report as pbik wrote it.
Validate's one intended warning: P2-V05's own header is on (item 2).

1. Open `Smoke.pbip` in Desktop 2.159.883.0 and click **Refresh** (it reads no source).
2. **Header and KPIs** *(items 4, 6)*:
   - The dark header band starts at the very top-left and spans the page; page content isn't centred vertically.
   - Inside it: eyebrow, title, description, the page tabs, a thin rule.
   - The KPI row: three KPI cards and a tinted two-value card (this year and last year).
   - The banner reads "Amount is …, +x% on last year".
3. Hover any visual: no header icons *(item 2)*. On **Tables**, the bar chart shows its header (turned on on purpose).
4. **Tables** *(items 6, 7)*:
   - The ranked table shows rank, area, amount with data bars, and a ▲/▼ trend.
   - The matrix shows regions with the area level collapsed.
   - "See the overview →" is a text-only link that goes to the first page.
5. **Bookmarks** *(items 7, 8)*:
   - The two buttons read "Hide options" and "Show options" and work.
   - In the Bookmarks pane, select both bookmarks and choose **Group**.
6. Save, close Desktop, then run the roundtrip below and a rebuild:
   `python ..\pbip-kit-export\tools\pbik\pbik.py build Smoke.Report design\specs\layout.json`. The build should say both
   bookmarks sit in your Desktop group and are left alone, and bookmarks.json should still hold the group.

```
python ..\pbip-kit-export\tools\pbik\pbik.py roundtrip Smoke.Report --before _pbik-built\Smoke.Report --layout design\specs\layout.json --out roundtrip.md
```

Expect no proposals about button `general` paragraphs, matrix `active` or the card's `layout.verticalAlignment`.

## Desktop check results (2026-11-13, Desktop 2.159.883.0)

- **Saved in Desktop, forms confirmed.** After the save, `pbik roundtrip` lists only the final newline (32 files) and
  the re-registered theme (`resourcePackages`, same content): Desktop kept everything else pbik wrote. That confirms
  the batch 4 forms on save: page `displayArea.verticalAlignment` Top, the header band, the theme's visual headers
  off and the one visual turning its own on, button labels as `objects.text.text` (no paragraphs dropped any more),
  the matrix's first row `active: true`, and the kpi-delta-card without `layout.verticalAlignment`.
- **Per-step visual notes:** not recorded (the report back had placeholders for header/KPIs, hover icons, tables and
  buttons).
- **Bookmark group: confirmed in Desktop** (second save, 2026-11-13). Desktop saved both bookmarks in a group
  (`Group 1`, bookmarks.json `children`); the rebuild printed "bookmark … sits in Desktop group 'Group 1': left alone"
  for both, left both bookmark files byte-identical and kept the group (bookmarks.json the same JSON, only pbik's
  final newline back). Item 8 and batch 3 item 11's bookmark-group behaviour are confirmed.
