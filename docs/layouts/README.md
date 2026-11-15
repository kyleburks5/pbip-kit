# Layout styles

Small HTML references, one per layout style, that `/plan` maps to layout.json with design/scripts/ref_layout.py
(test_design.py runs each). Open one in a browser to see the style; copy one to design/reference/ as a starting point.

| File | Style | What it shows | Maps to |
| --- | --- | --- | --- |
| `grid.html` | grid | title and filter, a row of four KPIs, two charts, a table | text box, slicer, 4 cards, line and bar charts, table |
| `bento.html` | bento | tiles of mixed spans (5/3/4/7/3/5/4 columns) and three heights | charts, cards and a table at their own spans |
| `rail.html` | rail | a navigation rail on the left, content to its right | a vertical page navigator on a band shape |
| `tabs.html` | tabs | a tab bar under the title, and tabs inside a card | a page navigator (one page per tab); in-card tabs listed as a gap (buttons and bookmarks) |
| `dense.html` | dense table | three dropdowns and a full-width table of 27 short rows with a sparkline column | slicers and a dense table (row padding 2); the sparkline listed as a gap (SVG measure, ladder step 2) |

ref_layout.py reads any HTML page this way (cards, tables, charts and their kind, KPI numbers, titles, slicers,
buttons, button groups, tab bars, rails). For an image the agent writes a boxes file (ref_layout.py docstring) and the
same mapping runs. design/specs/reference-map.md lists, by visual ID, what Power BI can't reproduce and the native
option used instead.

## Starter layouts (v1.7)

For a person with no wireframe or report: `starters/` holds four page layouts built only from the styles above and
the patterns in docs/patterns/, with slots for the title, up to four KPIs, a date, a category and a detail field inside it
(`pbik start starters` fills them from the model and the kit draws each as a picture; the person picks one and
changes it in plain words).

| Starter | Style | What it shows |
| --- | --- | --- |
| `executive-summary.json` | grid | title, four KPI cards, the main trend (direct labels), a ranked bar |
| `trend-dashboard.json` | grid | title, a KPI strip, the main trend against its usual range (range band), small multiples by category |
| `detail-table.json` | rail | title, two filters on the left, an exception list, a ranked bar |
| `profile-explorer.json` | rail + panel (docs/patterns/rail-panel.md) | a rail at the page edge with two pickers (category, then detail), tabs over display-only bookmarks, one shared panel with four KPIs, a profile card and the chart (trend or breakdown) |
