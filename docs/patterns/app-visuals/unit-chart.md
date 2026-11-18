# Unit chart (one mark per record)

**Question:** How many are there, and which ones, counted one mark at a time?

**Use when** the count is small enough to see (tens to a few thousand), each record matters (a deal, a person, a
case), and the reader should be able to point at one and ask about it.
**Avoid when** the records are not people-sized things (transactions by the million), when the total is the only
point (a card), or when the data may only be shown as aggregates (docs/it-security.md: a unit chart shows rows; check
the audit mode first).

## Design

- Marks packed in a grid inside each cell or column: the spacing fills the space, the radius is capped by Mark size.
- Colour by group (theme data colours) or one accent; selection and highlights follow [focus-dim](focus-dim.md).
- Each mark has a tooltip with the record's fields, and is reachable with the arrow keys.
- When there are more records than the visual draws (Most items drawn), a banner says how many are shown.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| native | none (a native scatter overlaps; a waffle is not native) | - |
| Deneb | a static unit chart (`mark: circle` with `window` row numbers); click to cross-filter | no animation or drill |
| **kit custom visual** | packed units, animated, drill and zoom, thousands of items (Canvas / WebGL) | normal pick for app pages |

Code: `layouts.ts` `pack()`, `grid()`, `columns()`; the renderer is picked by count in `layers.ts` (`MarkLayer`).
Data: the Item role holds one row per record (window of 30,000, `fetchMoreData` past it; `data.ts`).

## Checks

Harness: `marks` equals the row count; the fetch-more scenario (rows in segments) ends with every row drawn.
Numbers audit: the count in the headline against `COUNTROWS` of the visual's filter context.
