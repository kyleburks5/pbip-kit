# Charts and tables

Moved from CLAUDE.md (v1-simplify, 2026-10-29); placement rules in docs/lessons/README.md. Read by /plan, /build and /fix.

## Charts
- Bar chart with each category label above its bar (Rep 6): Y axis = the category, with axis values and title off. X axis = a zero measure (`_ Blank = 0`) first, then the real measure. In Data labels, pick the zero-measure series and set Title off, Value off, Detail on, with the category field as the detail. The real measure keeps its value at the bar end. In PBIR that is a `labels` entry for the zero series (selector `metadata`) with `labelPosition` OutsideEnd, `labelOverflow` and the `enable*DataLabel` flags, plus a per-data-point entry (selector `data` dataViewWildcard matchingOption 1, the same `metadata`, `highlightMatching` 1) holding `dynamicLabelDetail` = the category column (Aggregation, Function 3). A series-level `dynamicLabelValue` or `dynamicLabelDetail` alone validates but draws nothing. Template: `pbik_helpers.label_above_bars`.
- A selector-less `dataPoint.fill` is ignored once a chart has more than one series. Colour each series by `selector.metadata` (layout.json `props` `dataPoint.fill@[Measure]`).
- A chart that draws an empty-chart icon in Desktop usually has too little room to plot. Remove its title and axis titles, put any text in its own card, and give it at least ~48px (Rep 6).
- Give column and bar charts a Y-axis max measure so the tallest bar and its labels don't run into the top of the plot (Rep 6): `MAXX ( VALUES ( <axis column> ), [Measure] ) * 1.3`, bound to `valueAxis.end` with a `cf` entry (`type: "measure", kind: "value"`). Set no literal `valueAxis.end` after it.
- Set display units on money KPIs and data labels explicitly; Auto shows "$0.1M" for values under $100K and full numbers on cards.
- On a labels-above-bars chart, `layout.clusteredGapSize` doesn't move the label away from its bar. Space the bars with `categoryAxis.innerPadding` (and the label size) and check in Desktop (Rep 9).
- Heatmaps: use dark text in every cell and pick a colour scale whose darkest colour still gives 4.5:1 with that text. Don't switch text colour per cell with a measure in a matrix; it rendered white in every cell.

## Tables
- Turn off word wrap in table cells. *(gen_theme.py writes `wordWrap: false` in the theme.)*
- Size table and matrix columns with layout.json `columnWidths: "fit"` (pbik 0.6); hand-set widths only where one column needs a fixed size.
