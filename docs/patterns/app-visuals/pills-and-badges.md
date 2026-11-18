# Pills and badges

**Question:** Which view am I on, which filters are on, and is this real data?

Three small native parts that make a page read like an app. None needs a custom visual.

## Pill tabs (`pill-tabs`)

**Use when** two to six pages or views sit side by side and the reader switches often.
**Avoid when** the switch is inside one visual ([view-pills](view-pills.md)) or there are more than six.

Build (native): a page navigator (or a bookmark navigator over display bookmarks) with pill styling: fully rounded
shape, the selected state filled with `colors.brand` and `colors.onSelected` text, the rest `colors.card` with
`colors.textMuted` text and no border. The form to start from is `bookmarkNavigator.tabs-underline`
([tabs-underline](../tabs-underline.md)) with the pill shape; every state keeps WCAG AA contrast (`pbik validate`).

## Filter pills (`filter-pills`)

**Use when** a filter has a handful of values the reader toggles (regions, stages): pills read faster than a dropdown.
**Avoid when** there are more than about eight values (use a dropdown or a list slicer).

Build (native): the button slicer (`advancedSlicerVisual.button-slicer`, single or multi select) with fully rounded
buttons, the selected state in `colors.brand`, `layout.rowCount` / `columnCount` set so the tiles don't scroll
(lessons: slicers). Multi-select with Ctrl, as every slicer.

## Sample-data badge (`sample-badge`)

**Use when** the page runs on synthetic or sample data (the kit's synthetic model, a demo) and a screenshot could
travel without that context.
**Avoid when** the data is live and complete (remove the badge at switching to live: `pbik bind live` lists it).

Build (native): a button (`actionButton.pill-button`) with no action, text "Sample data", `colors.warningTint` fill and
`colors.warningText` text (AA), placed at the right of the title row, `decorative: false` with alt text "This page
shows sample data". A text-only badge, never colour alone.

## Checks

`pbik validate`: contrast in every state, text not below 10pt, tab order (the badge sits in the title row's order).
