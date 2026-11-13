# Direct labels instead of legends

`pattern: "direct-labels"`

**Question it answers:** which line or bar is which, without looking it up in a legend?

- **Use when:** a chart with 2-5 series or labelled bars, so each mark carries its own name.
- **Avoid when:** more than ~5 series (labels collide; highlight one or two and grey the rest, or use small multiples).

## When to use
- Any chart with 2-5 series. The label sits on or at the end of its mark, in the series colour (or in `text` next to
  a coloured mark when the colour fails 4.5:1).
- Bar charts: the category name above each bar (docs/lessons/charts.md, Rep 6) rather than an axis far away.

## Design
- Legend off. Line charts: series name at the right end of each line. Bar charts: category above the bar, value at
  the bar end. Stacked bars: segment labels only where the segment is wide enough.
- A subtitle can carry what the colours mean when one series is highlighted: "This year in teal".

## Build (visual-method ladder)
| Step | How | Draws | Status |
| --- | --- | --- | --- |
| 1 native, bars (pick for bars) | Labels above bars: zero spacer series + detail label (`pbik_helpers.label_above_bars`, docs/lessons/charts.md) | category above each bar | in the catalog (clusteredBarChart `labels.*` on metadata, Rep 6) |
| 1 native, lines (pick for lines) | Legend off + line chart series labels at the line ends | series name at the end of each line | *harvest*: series labels aren't in the catalog yet |
| 1 native, lines, simpler | Legend off + subtitle naming the colours, or a text box per series | names near the chart, not on the lines | always available; text boxes don't follow the data |
| 3 Deneb | `text` layer on the last point per series (`argmax` of the date) | labels at line ends that follow the data | when series labels can't be harvested |

## layout.json example
```json
{"id": "P1-V07", "name": "trend-by-channel", "page": "P1", "type": "lineChart", "pattern": "direct-labels",
 "x": 32, "y": 360, "w": 1240, "h": 400, "z": 1,
 "bindings": {"Category": ["'Date'[Month]"], "Y": ["[Online]", "[Stores]"]},
 "props": {"legend.show": false, "dataPoint.fill@[Online]": "teal", "dataPoint.fill@[Stores]": "slate"},
 "container": {"title": "Sales by channel", "subtitle": "Online in teal, stores in slate",
               "altText": "Monthly sales online and in stores"},
 "build": {"method": "native", "step": 1, "reason": "Legend off; subtitle names the colours until series labels are harvested"}}
```

## Wireframe
Legend off; each line labelled at its right end in its colour (bar charts: category above the bar, as the
`aboveLabels` renderer already does).

## Audit
Nothing extra: the labels are names, not numbers. Check in /review that no label overlaps another at the default
state and at the narrowest filter.
