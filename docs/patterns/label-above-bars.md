# Label-above bars

`pattern: "label-above-bars"` (from Rep 6 and Rep 9, v1.12; GENERIC)

**Question it answers:** which few items are biggest, with room for their full names?

- **Use when:** a top N (5 to 8) in a narrow panel, where names on the left would squeeze the bars.
- **Avoid when:** more than about 8 items (a table or a ranked bar table), or long names that wrap twice.

## Design
- A slim bar per item across the full width, the item's name above it (body size, text colour), its value at the bar's
  end; no axes, no gridlines; about 40 px per item.

## Build
1 native: a clustered bar chart with two series: a zero spacer measure (`Top Bar Spacer`, painted `card`) whose data
label shows the item's name as its detail (`labels.dynamicLabelDetail` from a text measure `<Field> Bar Label`, label
position OutsideEnd, overflow on, left aligned), then the count. `categoryAxis.innerPadding` 45 and
`layout.clusteredGapSize` 8 give the slim bar with its label above; the template's reference line is turned off
(`y1AxisReferenceLine.show` false on id 1). A Top N filter keeps N items. `pbik layout panels` writes it.

## Audit
The values at the bar ends are the measure's; the names are the field's.
