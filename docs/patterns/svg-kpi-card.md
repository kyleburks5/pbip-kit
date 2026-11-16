# SVG KPI card

`pattern: "svg-kpi-card"` (UDF KPI card study, 2026-11-15; Study 2 import; Desktop checks U-1 to U-6 still open in
design/reviews/pbik-roadmap.md)

**Question it answers:** one headline number with its change and trend, read at a glance in one designed tile.

- **Use when:** the design wants a tile a native card can't draw (value, change pill and a microchart together),
  the same card repeats across metrics, and the card function is installed in the model or inline mode is used.
- **Avoid when:** a native new card with reference labels shows it (`kpi-delta-card`, `two-kpi-card`: ladder step
  1); the number must be selectable, read by a screen reader or exported; the live model lacks the function and it
  isn't inlined; a microchart card has no month order and label columns.

## Design
- The card is the image: the function draws background, border, radius, label, value, change and icon; the visual's
  own fill, border, value and label are off.
- Colours and font come from the report's design tokens (the function's style parameters, BLANK() = token):
  `text`, `textMuted`, `card`, `border`, `good`, `bad`, `goodTint`, `badTint`, `font.family`. The accent colour is an
  argument (a token hex).
- A blank value draws no card; a blank comparison shows a dash in `textMuted`, never +0%.
- Keep the function's aspect ratio when sizing the box from the grid: Card2 280:150, Card1 250:140, SVGKPICard
  240:180.

## Build (visual-method ladder)
- 1 native: a new card with a reference label (try first; record what it can't draw in `build.nativeTried`).
- **2 SVG (normal pick):** a card function from the kit UDF library (design/udf/library/park-kpi, `index.json`):
  - one card: template `cardVisual.svg-kpi-card`; a visual calculation calling the function (`DataType` Text), the
    measures it uses as hidden fields, `image.imageType` imageUrl, `image.imageUrl` = the calculation, size from
    the box, padding 0, value and label off;
  - one card per member, or a model / report measure: template `advancedSlicerVisual.svg-kpi-card-buttons`, the
    measure on `image.image`.
- In layout.json: a `udfCard` (design/reference/layout-schema.md) does all of the above in one `pbik build`.
  Mode `inline` (default) needs no function in the model; `measure` and `calc` need it (`pbik udf install`).
- Before use: `pbik udf check` (fingerprints, turned on, model tables such as `'Date'`); `pbik udf render
  --format query` to test a call query-scoped.
- Icons are turned off (provenance note): leave the icon argument out; never pick an icon function.
- Both templates are a clean harvest: **confirm in Desktop** (U-5).

## Accessibility and numbers
- Alt text states the number and the change in words (A-01).
- The numbers drawn are `svg` entries in the numbers audit.

## Not yet
- A wireframe renderer for the function (the wireframe draws a plain card); Desktop checks U-1 to U-6
  (design/reviews/pbik-roadmap.md), all "verify in Desktop".
