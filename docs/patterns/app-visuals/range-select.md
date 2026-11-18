# Range select

**Question:** What happens to the rest of the page in the span I drag?

**Use when** the reader picks a stretch of a timeline or a band of a measure (days open 30-60, values above the
target) and the page should follow; a click clears it.
**Avoid when** a between slicer above the chart does it (native, ladder step 1: [brushed-range](../brushed-range.md)),
or the axis is categorical (use click and Ctrl-click instead).

## Design

- A one-axis brush keeps the other axis whole (timelines); a two-axis brush selects a box (scatter).
- The span shows as a light accent band with an outline; the selected items stay strong, the rest dims
  ([focus-dim](focus-dim.md)); the headline says how many are selected.
- The brush never starts on a mark, so clicking a mark still selects it.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| native | between slicer (date or number) | a slicer above the chart is fine |
| Deneb | an interval selection on the chart that cross-filters ([brushed-range](../brushed-range.md)) | a static chart with brushing |
| **kit custom visual** | a one-axis (`range.ts` `rangeSelect`) or two-axis (`Interaction.enableBrush`) brush | inside an app visual |

Code: `src/kit/patterns/range.ts` `rangeSelect(g, {axis, box, keysIn, onRange})` turns the span into keys; pass them
to `Interaction.select(keys)` to cross-filter. The starter uses the two-axis brush in every view (Interaction > Drag
to select a range).

## Checks

Harness: a `drag` step, then `minSelectCalls` and `text` "selected"; a click on empty space and `clears`.
