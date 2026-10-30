# Partial-period markers (hollow point)

`pattern: "partial-period"`

**Question it answers:** is the last point complete, or still filling up?

## When to use
- Any time series whose latest period is not over yet (month to date, the current week) or whose data arrives late.
  A partial month drawn like a full one reads as a fall.

When not: the report always shows closed periods only (then filter the open period out and say so in the subtitle).

## Design
- Complete periods: solid `teal` line with small dots.
- The partial period: a hollow point (white fill, `teal` outline) joined by a dashed segment, with a label "partial:
  to 14 Oct". Optionally a faint projected value.
- Card values for the current period carry "(to 14 Oct)" in their label or reference label.

## Build (visual-method ladder)
| Step | How | Draws | Status |
| --- | --- | --- | --- |
| 1 native (pick this) | Line chart with two series: `[Value complete]` (blank in the open period) and `[Value partial]` (the last complete period and the open one). Partial series: `slateLight`, markers on; data label on the open point | separate, lighter last segment and point | `dataPoint.fill`, `lineStyles.showMarker` per series in the catalog; dashed `lineStyle` *harvest* |
| 2 SVG measure | Sparkline in a card or table with the last point drawn as a ring | hollow point in small sparklines | a DaxLib.SVG sparkline first (design/udf/packages.json), else new SVG code |
| 3 Deneb | `line` + `point` with `"filled": false` when `partial` is true, `strokeDash` on the last segment | true hollow point and dashed segment | when the chart is the hero and the hollow point is required |

Native markers have no hollow form; the lighter colour plus a "partial" data label carries the meaning at step 1.

## Measures (sketch)
```dax
Last complete date =                                   -- end of the last full month (or week)
VAR _d = CALCULATE ( MAX ( Fact[Date] ), REMOVEFILTERS () )
RETURN IF ( _d = EOMONTH ( _d, 0 ), _d, EOMONTH ( _d, -1 ) )
Is partial period = MAX ( 'Date'[Date] ) > [Last complete date]
Value complete = IF ( [Is partial period], BLANK (), [Value] )
Value partial  = IF ( MAX ( 'Date'[Date] ) > EOMONTH ( [Last complete date], -1 ), [Value] )
```
The partial series covers the last complete month and the open one, so the two lines join; when the latest month is
complete it is a single point under the complete line (hide it with `IF ( [Is any partial], ... )` if that matters).

## layout.json example
```json
{"id": "P1-V05", "name": "monthly-trend", "page": "P1", "type": "lineChart", "pattern": "partial-period",
 "x": 32, "y": 360, "w": 1240, "h": 400, "z": 1,
 "bindings": {"Category": ["'Date'[Month]"], "Y": ["[Value complete]", "[Value partial]"]},
 "props": {"dataPoint.fill@[Value complete]": "teal", "dataPoint.fill@[Value partial]": "slateLight",
           "lineStyles.showMarker@[Value partial]": true, "legend.show": false},
 "container": {"title": "Monthly value", "subtitle": {"measure": "[Partial period note]"},
               "altText": "Monthly value; the current month is partial and drawn lighter"},
 "build": {"method": "native", "step": 1, "reason": "Two series give the open period its own colour and marker"}}
```

## Wireframe
Solid line to the last complete point, dashed segment to a hollow ring for the partial point, with "partial" next to
it. The renderer treats the last category as partial unless the data file marks it.

## Audit
`[Value]` for the last complete period and the partial one; the partial label's date; the case where the latest
period is complete (no partial series drawn).
