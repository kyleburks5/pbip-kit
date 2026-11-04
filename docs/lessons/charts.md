# Charts and tables

Read by /plan, /build and /fix. Format and placement: docs/lessons/README.md.

## Index
<!-- lessons:index -->
| ID | Lesson | Enforced by |
| --- | --- | --- |
| CH-01 | Category labels above bars use a zero spacer series | – |
| CH-02 | Colour each series by its metadata selector | `pbik validate` warns (pbikit/validate.py `lesson_checks`) |
| CH-03 | An empty-chart icon means too little room | – |
| CH-04 | Column and bar charts get a Y-axis max measure | – |
| CH-05 | Money values get explicit display units | – |
| CH-06 | Space labels-above-bars with innerPadding | – |
| CH-07 | Heatmaps keep one dark text colour | `pbik validate` contrast warnings (pbikit/a11y.py) on the colours it can read |
| CH-08 | No word wrap in table cells | design/scripts/gen_theme.py writes `wordWrap: false` in the theme |
| CH-09 | Size table columns to fit | pbik build (`columnWidths: "fit"`, since 0.6) |
<!-- /lessons:index -->

## CH-01 Category labels above bars use a zero spacer series
- **Rule:** For a label above each bar: Y axis = the category (axis values and title off); X axis = a zero measure
  (`_ Blank = 0`) first, then the real measure; the zero series' data labels show only the detail, the category field
  (`pbik_helpers.label_above_bars`; the PBIR form is under Reference).
- **Why:** a series-level `dynamicLabelValue` or `dynamicLabelDetail` alone validates but draws nothing.
- **Enforced by:** not enforced (read at /build)
- **Source:** Rep 6

## CH-02 Colour each series by its metadata selector
- **Rule:** Colour series with `props` `dataPoint.fill@[Measure]` (selector `metadata`).
- **Why:** a selector-less `dataPoint.fill` is ignored once a chart has more than one series.
- **Enforced by:** `pbik validate` warns (pbikit/validate.py `lesson_checks`)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## CH-03 An empty-chart icon means too little room
- **Rule:** Remove the chart's title and axis titles, put text in its own card, and give the plot at least ~48px.
- **Why:** Desktop draws the empty-chart icon when there is too little room to plot.
- **Enforced by:** not enforced (seen only in Desktop)
- **Source:** Rep 6

## CH-04 Column and bar charts get a Y-axis max measure
- **Rule:** Bind `valueAxis.end` to `MAXX ( VALUES ( <axis column> ), [Measure] ) * 1.3` with a `cf` entry
  (`type: "measure", kind: "value"`) and set no literal `valueAxis.end` after it.
- **Why:** the tallest bar and its labels ran into the top of the plot.
- **Enforced by:** not enforced (read at /plan)
- **Source:** Rep 6

## CH-05 Money values get explicit display units
- **Rule:** Set display units on money KPIs and data labels.
- **Why:** Auto shows "$0.1M" for values under $100K and full numbers on cards.
- **Enforced by:** not enforced (read at /plan)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## CH-06 Space labels-above-bars with innerPadding
- **Rule:** Space the bars with `categoryAxis.innerPadding` (and the label size) and check in Desktop.
- **Why:** `layout.clusteredGapSize` doesn't move the label away from its bar.
- **Enforced by:** not enforced (seen only in Desktop)
- **Source:** Rep 9

## CH-07 Heatmaps keep one dark text colour
- **Rule:** Use dark text in every heatmap cell and a colour scale whose darkest colour still gives 4.5:1 with it.
- **Why:** text colour switched per cell by a measure rendered white in every cell of a matrix.
- **Enforced by:** `pbik validate` contrast warnings (pbikit/a11y.py) on the colours it can read
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## CH-08 No word wrap in table cells
- **Rule:** Keep word wrap off in table cells.
- **Why:** not recorded when the lesson was written.
- **Enforced by:** design/scripts/gen_theme.py writes `wordWrap: false` in the theme
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## CH-09 Size table columns to fit
- **Rule:** Use layout.json `columnWidths: "fit"`; hand-set widths only where one column needs a fixed size.
- **Why:** not recorded when the lesson was written (fit sizes every column from its text).
- **Enforced by:** pbik build (`columnWidths: "fit"`, since 0.6)
- **Source:** kit v0.3

## Reference

CH-01 in PBIR: a `labels` entry for the zero series (selector `metadata`) with `labelPosition` OutsideEnd,
`labelOverflow` and the `enable*DataLabel` flags (Title off, Value off, Detail on), plus a per-data-point entry
(selector `data` dataViewWildcard matchingOption 1, the same `metadata`, `highlightMatching` 1) holding
`dynamicLabelDetail` = the category column (Aggregation, Function 3). The real measure keeps its value at the bar end.
