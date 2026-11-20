# Threshold histogram

`pattern: "threshold-histogram"` (from Rep 9, v1.12; GENERIC)

**Question it answers:** how is a duration or amount spread out, and how much of it is inside the limit?

- **Use when:** a count spread over a whole-number measure (days to resolve, days to pay, minutes waiting, length of
  stay) that has a threshold (an SLA, a target, a prompt-pay limit), per member or overall.
- **Avoid when:** the values aren't whole numbers or bins (bin them first), or there is no threshold (a plain
  column chart).

## Design
- Column chart on a continuous (Scalar) axis: one bar per whole value, the axis title under it ("Days to resolve"), a
  few value ticks, light gridlines (`divider`).
- Bars up to the threshold in the member's colour, beyond it in `outSla` grey: a per-point colour measure
  (`<Title> Bar Colour`: the threshold from the row's own context, e.g. the channel's SLA days).
- A dashed line at the average on the category axis, labelled "avg: 2.95" (name and value, 2 decimals).
- The subtitle says it in words: "8,246 within SLA (88.1%) · SLA 5 days · avg 2.95 days" (a text measure).
- The value axis ends at 1.3 x the tallest bar (an axis-max measure) so the line label stays clear.

## Build
1 native: `clusteredColumnChart`, `categoryAxis.axisType` Scalar, a `cf` per-point fill measure (layout.json
`perPoint: true`; the kit's `split` hint {at, within, beyond} lets the plan picture colour the bars), a
`referenceLines` entry on the category axis, `xAxisReferenceLine.dataLabelDecimalPoints` 2. `pbik layout panels`
writes it in each panel; on its own, copy the panel's entry.

## Audit
The subtitle's numbers (within, rate, threshold, average) are numbers-audit entries; the bar colours follow the
threshold of the row's own member.
