# Rail + panel layout

`pattern: "rail-panel"` (layout style; rail + panel study, 2026-11-15; GENERIC). Preset: `rail-panel` (optional).

**Question it answers:** which member am I looking at, and what is its whole story?

- **Use when:** a profile or explorer page: the reader picks one member (a store, a product, a person, a site) from a
  list, maybe narrows it with a second list, and reads that member's numbers, picture and chart together; views of the
  same member switch with tabs.
- **Avoid when:** an overview across all members (grid or bento reads faster), more than about 30 members to pick
  from without search (a dropdown or a search slicer instead), or pages that need the full width for a wide table.

## Design
- **Rail:** a full-height `card`-coloured shape on the left. It is the one thing that may touch the page edge (x 0,
  y 0); its inner (right) edge sits on a grid column edge, normally the end of column 3 or 4. In it: the page header
  stack (logo, eyebrow and title) and one or two pickers stacked side by side or top to bottom, with a thin `border`
  rule between them.
- **Panel:** one shared panel (pattern `panel`) over the remaining columns, on the page `background`, holding the
  profile card, the KPI row and the chart; inside it, a 5 + 7 split of the 8 columns works well.
- **Tabs:** pattern `tabs-underline` above the panel's right part; each tab shows one view set (a group per view)
  through a **display-only** bookmark (Data unchecked; .claude/rules/pbik.md).
- **Colour:** the chrome is monochrome (tab accent and selections in `text` / `selected`); data colours mark the data
  and, through a colour measure, the selected member.
- Everything except the rail stays on the 12-column grid and the 32px margin.

## Dense form (the house style, v1.12)
The default layout when a request names no look (design/themes/presets/README.md "Styles"): an overview page keeps
the rail and puts its content in panels.
- **Rail** (columns 1-2, inner edge x 321): the page title at the top (on a drill-through page, the Back button above
  it), then every picker, lined up by `pbik layout polish`: one left edge and width (the rail less 32 px each side),
  40 px pills, 24 px between pickers (pbikit/polish.py `rail_pickers`).
- **Content** (columns 3-12): the headline sentence on the background at the top, a KPI panel (pattern `panel`, the
  cards on it without boxes of their own), then rows of charts and lists, each in its own panel (the container, no
  shared panel for a single visual).
- **Details** open in a side panel (a docked group or a drill-through page), never a pop-up over the content.
- No header band (polish adds none on a rail page).

## Build (visual-method ladder)
- 1 native throughout: shape (rail, `pattern: "rail-panel"`), new card (header title, profile, KPIs), new slicers
  (image list, image cards), bookmark navigator, groups and bookmarks, scatter or any chart.
- Clean templates from the study (confirm each in Desktop): `cardVisual.header-title`, `shape.rule`,
  `advancedSlicerVisual.image-list`, `advancedSlicerVisual.image-cards`, `shape.panel`, `cardVisual.profile-card`,
  `cardVisual.kpi-row-chips`, `cardVisual.two-kpi-card`, `bookmarkNavigator.tabs-underline`, `image.titled`,
  `scatterChart.on-image`.
- Pickers ship with a saved default selection so the page never opens empty: layout.json
  `selection: {field, values}` on the picker (one value for a single-select picker); pbik writes it as Desktop saves a
  clicked value. **Verify in Desktop** on the new slicers (roadmap gap 30, study Desktop check 5).
- `pbik` score: the grid check lets a rail touch one page edge when its inner edge is on the grid (pbikit/score.py).

## layout.json example (positions on the 12-column grid; column 4 ends at x 635, column 5 starts at x 659)
```json
[{"id": "P1-V01", "type": "shape", "name": "rail", "pattern": "rail-panel", "decorative": true,
  "x": 0, "y": 0, "w": 635, "h": 1080, "container": {"keepLayerOrder": true}},
 {"id": "P1-V05", "type": "shape", "name": "panel", "pattern": "panel", "template": "shape.panel", "decorative": true,
  "x": 659, "y": 128, "w": 1229, "h": 920}]
```

## Starter and wireframe
- Starter layout `profile-explorer` (docs/layouts/starters/profile-explorer.json; `pbik start starters` offers it):
  the rail with two pickers (`{category}`, then `{detail}` inside it), tabs, and the panel with the KPI row, the profile
  card and the chart.
- gen_wireframe_hf.py draws the rail (card fill, a rule on its inner edge), the panel (card fill, radius, the soft
  shadow) and the picker tiles (`advancedSlicerVisual.image-list`: a round picture and the name per row;
  `advancedSlicerVisual.image-cards`: a picture over the name per card).

## Desktop checks before a big build (from the study; none confirmed yet; other templates: a /smoke-style check)
1. An image visual bound to a measure renders (then an SVG measure could go there; .claude/rules/svg.md only if yes).
2. The hidden-from-tab-order value Desktop keeps today (the kit writes -9999000; other files show -1, -1001).
3. `bookmarkNavigator.tabs-underline` keeps its accent-bar states and selected-bookmark binding after a save.
4. A display-only tab bookmark (Data unchecked) showing one group and hiding two round-trips.
5. A picker's saved `selection` on a new slicer is kept and opened on (roadmap gap 30).
6. A card fill-image watermark (`fillCustom.image`, transparency) on `cardVisual.profile-card`.
7. `scatterChart.on-image` + `image.titled`: fixed axis start and end keep the points aligned at Fit to page.
8. Two templates saved at visualContainer 2.8.0: check them against project.json `targetDesktop` first.
9. Label transparency on a new card, only if `pbik validate` should flag muting text that way (A-02).

## Audit
The profile card and KPI numbers follow the usual audit entries; the picker's default member is the audit's first
state.
