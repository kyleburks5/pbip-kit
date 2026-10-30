# Dumbbell rows with change labels

`pattern: "dumbbell"`

**Question it answers:** how far did each member move between two points in time (or two scenarios), and which way?

## When to use
- One row per member (region, product, team), two values of the same measure: before and after, plan and actual,
  last year and this year.
- The change matters more than the level, and members should be compared on the change.

When not: more than two points per member (use small multiples), or members whose values differ by orders of
magnitude (use % change bars).

## Design
- One row per member, sorted by the change (largest rise first, or worst first for an exception view).
- A thin `border` line from the earlier value to the later value; earlier dot hollow or `slateLight`, later dot
  `teal` (rise) or `red` (fall). Colour follows polarity (tokens `polarity`): a fall in cost is good.
- A change label at the end of the row: "+4.2 pts" or "-$12K", same colour as the later dot, plus an arrow or sign so
  colour isn't the only signal.

## Build (visual-method ladder)
| Step | How | Draws | Status |
| --- | --- | --- | --- |
| 1 native (tried) | Line chart or clustered bar chart, two series with line width 0 and markers on | two dots per member, **no connector** | fails the design: the connector is the pattern (error bars could join them, not in the catalog) |
| 2 SVG measure (pick this) | Table: member, `[Dumbbell SVG]` (ImageUrl), `[Change label]`, sorted by `[Change]` | everything, one row per member, shared scale | SVG rules (.claude/rules/svg.md); one scale for all rows via `ALLSELECTED` |
| 3 Deneb | `rule` from x=before to x2=after + two `point` layers + `text` for the change | everything, plus axis and tooltips | for a chart with an axis rather than table rows |

The SVG step is a fallback (CLAUDE.md "Native first"): record `nativeTried` and `reason`, add the fallback register
row, and ask before building.

## Measures (sketch)
```dax
Change = [Value] - [Value Before]
Change label = IF ( ISBLANK ( [Change] ), BLANK (),
                    IF ( [Change] >= 0, "▲ +", "▼ " ) & FORMAT ( [Change], "#,0.0" ) )
Dumbbell SVG =
VAR _min = MINX ( ALLSELECTED ( Member[Name] ), MIN ( [Value], [Value Before] ) )
VAR _max = MAXX ( ALLSELECTED ( Member[Name] ), MAX ( [Value], [Value Before] ) )
VAR _x0 = 8 + 184 * DIVIDE ( [Value Before] - _min, _max - _min )   -- or a DaxLib.SVG function (design/udf/packages.json)
VAR _x1 = 8 + 184 * DIVIDE ( [Value] - _min, _max - _min )
VAR _c  = IF ( [Change] >= 0, "%23038D96", "%23A84545" )             -- teal / red from tokens.json
RETURN IF ( ISBLANK ( [Value] ) || ISBLANK ( [Value Before] ), BLANK (),
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='20'>"
  & "<line x1='" & _x0 & "' y1='10' x2='" & _x1 & "' y2='10' stroke='%23DCE2EA' stroke-width='2'/>"
  & "<circle cx='" & _x0 & "' cy='10' r='4' fill='white' stroke='%23B8C2D6' stroke-width='2'/>"
  & "<circle cx='" & _x1 & "' cy='10' r='5' fill='" & _c & "'/></svg>" )
```
Colours come from tokens.json when /plan writes the measure (record the token names in the measure description).
Write `%` as `%25` inside the SVG, test in every audit state (audit_svg.py), and put the change number drawn in the
SVG (if any) in the numbers audit (`svg` entries).

## layout.json example
```json
{"id": "P1-V08", "name": "region-change", "page": "P1", "type": "tableEx", "pattern": "dumbbell",
 "cols": [9, 12], "x": 1306, "y": 360, "w": 582, "h": 400, "z": 1,
 "bindings": {"Values": [{"field": "Region[Region]", "displayName": "Region"},
                         {"field": "[Dumbbell SVG]", "displayName": "Last year → this year"},
                         {"field": "[Change label]", "displayName": "Change"}]},
 "sort": {"field": "[Change]", "direction": "Descending"},
 "cf": [{"type": "measure", "object": "values", "property": "fontColor", "measure": "[Change colour]",
         "target": "[Change label]"}],
 "columnWidths": "fit",
 "props": {"grid.imageHeight": 20, "grid.imageWidth": 200, "grid.rowPadding": 4},
 "container": {"title": "Change by region",
               "altText": "Each region's value last year and this year as two dots joined by a line, with the change"},
 "build": {"method": "svg-measure", "step": 2,
           "nativeTried": "Line chart, two marker-only series", "reason": "No connector between the dots natively",
           "register": "F1"}}
```

Set the table's image size to the SVG's own size (`grid.imageHeight` / `imageWidth`, as Desktop saved them in Rep 5)
and a small `grid.rowPadding`: without them Desktop draws each image row about 75px tall with a small dumbbell in it
(v0.4 Desktop check).

## Wireframe
Rows with a connector and two dots on a shared scale, the change label coloured by direction. Uses the first
category binding for the row labels; with the data file, the two values come from `[Value Before]` / `[Value]` if
bound, else sample values.

## Audit
`[Value]`, `[Value Before]` and `[Change]` per member (sampled mode: top 5, bottom 5, 5 random), the member with no
earlier value (label blank, no dot), and the numbers drawn in the SVG.
