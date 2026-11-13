# Ranked bar table

`pattern: "ranked-bar-table"` (stub: batch 4 item 6)

**Question it answers:** who ranks where, by how much, which way are they moving, and are they OK?

- **Use when:** 10 to 30 members ranked by one measure, with the trend and a status for each row.
- **Avoid when:** fewer than 6 members (a bar chart reads faster) or no ranking measure the reader cares about.

## Design
- Columns: rank, member, value with **native data bars** (conditional formatting), a trend arrow (▲ ▼ ► with `good` /
  `bad` / `textMuted`) and a status chip (tokens `badges`: text on its fill, 4.5:1).
- Sorted by the value; the rank is a measure (RANKX over ALLSELECTED), so it follows the filters.

## Build (visual-method ladder)
- 1 native (table, data bars, icon or text CF); 2 SVG measure only when the bars need a target tick the data bars
  can't draw (fallback register first).
- Template `tableEx.ranked-bar-table`: **needs a Desktop-saved sample.** Make it on the Patterns page in Desktop,
  save, and run
  `pbik templates harvest`; until then build from the plain type's template and the layout's own keys.

## Not yet
- Wireframe renderer (the wireframe draws the visual type), measures sketch, layout.json example, audit.
