# Theme presets

Starting colour schemes for `/theme` (design/scripts/gen_tokens.py), used only when the brief gives no brand colours
and design/reference/ has no reference. Default: **clean**.

| Preset | Look | Corners, edges |
| --- | --- | --- |
| `clean` | Neutral slate-teal on a cool grey canvas, white cards (the palette tokens.json shipped with, Rep 5) | 16px, soft shadow, no border |
| `bento` | Warm off-white canvas, white tiles, indigo brand with coral and mint | 24px, near-flat shadow, no border |
| `corporate` | Navy header, corporate blue, grey neutrals | 4px, 1px border, no shadow |
| `rail-panel` | Light neutral canvas, white rail and one floating white panel, monochrome chrome, weight-led type (study 2026-11-15) | 12px, one soft shadow on the panel, no border |
| `dark-glass` | Navy canvas, glass panels with thin edges, one warm amber accent, muted data, DIN titles and numbers (study 2026-11-18) | 14px, 1px edge, one deep soft shadow |

A preset file holds `mode`, `brand` (colours by role: `primary=`, `brand=`, `bad=`, `good=`, `second=`, others are
extra series colours), optional `colors` (names it pins; the clean preset pins its whole palette) and `container`,
`control` or `font` values for tokens.json. Pinned colours are still checked: one that fails WCAG 2.1 AA moves and is
listed in design/reviews/theme.md.

Layout style is separate from the palette: a bento *layout* (tiles of mixed spans and heights) comes from /plan
(docs/layouts/bento.html is a reference of one); the bento preset is the look that suits it.

## Styles

**House styles (the default when a request doesn't name a look), where they fit:** the panel style layout for
comparing a few members (2 to 6) side by side; rail + panel, or dark glass, for explorer pages (pick one member, read
its story); side panels or drill-through pages instead of pop-ups for details. /plan uses them instead of the plain
grid, and names the alternative style in one line of the plan (an assumption the person can change: "say grid style
for the plain grid instead"). A project can name another default in design/specs/project.json `houseStyle`.

A style is a layout and a look that go together; presets are named by style, never by a person or a report. /plan
picks one per page from these lines and names the preset in the spec's Pattern choices row (any preset may still be
used with any layout). Each study of another report (a project's design/reviews/WRAPUP-study-*.md, brought into the kit) can add one.

| Style (preset) | Layout | Use when | Avoid when |
| --- | --- | --- | --- |
| grid (`clean`) | rows of cards and charts on the 12-column grid (docs/layouts/grid.html) | an overview across all members: KPIs, the main trend, a breakdown | one member's story, or many small mixed tiles |
| bento (`bento`) | tiles of mixed spans and heights (docs/layouts/bento.html) | a showcase page with a few strong numbers and charts of different weight | dense comparison or long tables |
| corporate (`corporate`) | grid under a dark header band | formal reporting that must look like the organisation's other reports | exploration pages, where the band takes too much room |
| rail + panel (`rail-panel`) | a rail at the left edge with pickers, one shared panel, tabs (docs/patterns/rail-panel.md) | a profile or explorer page: pick one member, read its numbers, picture and chart together, switch views with tabs | an overview across all members, more than about 30 members without search, or a full-width table |
| panel style layout (`panel-style`; a house style) | a dark header band with the title, a definition line and the year; one full-height panel per member with its identity colour and icon, share bar, big number with a change chip, quarterly mini columns, threshold histogram and top N (docs/patterns/panel-style-layout.md; `pbik layout panels`) | comparing 2 to 6 members of one dimension side by side (channels, lines of business, care settings, regions): the default house style for that | more than 6 members, one member's deep story, or a wide table on the same page |
| rail + panels, dense (any light preset) | the rail with the title and every picker, the content in panels: a KPI panel, then charts and lists each in their own panel (docs/patterns/rail-panel.md "Dense form") | the default when a request names no look (house style): overview and drill-through pages, dense pages included; details in a side panel, never a pop-up | a page that needs the full width for one wide table or map, or a look the request names |
| dark glass (`dark-glass`) | a left rail with pickers, the main visual large, details in a docked side panel (docs/patterns/rail-panel.md, app-visuals/focus-dim.md); 1920x1080 grid | an app-like explorer or showcase page read on screen: one space, map or chart to explore, a few numbers beside it, one thing highlighted at a time | printed or exported pages (dark pages print badly), dense comparison tables, or reports that must match a light house look |
