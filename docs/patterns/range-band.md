# Range band with current-period dots

`pattern: "range-band"`

**Question it answers:** is this period inside its usual range, and where in it?

## When to use
- A measure with a seasonal or historical normal: the band is the range (min to max, or a percentile band) of the
  same period in earlier years, the dots are this year.
- Over time (months on the x axis), or across members (one row per region, band = the region's own history).

When not: fewer than three earlier periods (the band is noise), or when the reader needs the exact history of each
year (use a line per year instead).

## Design
- Band: `slateTint` fill (or two thin `slateLight` lines when the band can't be shaded), no labels.
- Dots: this period's values, `teal` when inside the band, `red` when outside, size 6-8px. The last dot gets a
  data label.
- A legend-free subtitle says what the band is: "Band: lowest to highest of 2019-2025".

## Build (visual-method ladder)
| Step | How | Draws | Status |
| --- | --- | --- | --- |
| 1 native (pick this) | Line chart, X = `Date[Month]`. Series `[Band Low]` and `[Band High]` as thin `slateLight` lines without markers, `[Value]` with line width 0 and markers on | band edges + dots | `lineStyles.strokeWidth` and `lineStyles.showMarker` per series (metadata selector) and `dataPoint.fill` per series are in the catalog |
| 1 native, shaded | Same chart with error bars on `[Value]` (upper `[Band High]`, lower `[Band Low]`, shaded area) | filled band + dots | *harvest*: error-bar settings aren't in the catalog yet |
| 2 SVG measure | Per-row band in a table column (one row per member: grey rect from low to high, a dot at the value) | band + dot per row | for the across-members form; a DaxLib.SVG function first (design/udf/packages.json) |
| 3 Deneb | `rect` (or `area`) layer for the band + `point` layer coloured by inside/outside | everything, including dot colour by rule | needs the Deneb fallback (item 4 of v0.4) |

Dot colour by rule (inside teal, outside red) per data point is not native on a line chart's markers; at step 1 keep
one dot colour and let a data label or the exception list carry "outside". Pick step 3 only if the design needs the
coloured dots.

## Measures (sketch)
```dax
Band Low  = MINX ( VALUES ( 'Date'[Year] ), CALCULATE ( [Value], 'Date'[Year] < MAX ( 'Date'[Year] ) ) )
Band High = MAXX ( VALUES ( 'Date'[Year] ), CALCULATE ( [Value], 'Date'[Year] < MAX ( 'Date'[Year] ) ) )
Outside Band = IF ( ISBLANK ( [Value] ), BLANK (), INT ( [Value] < [Band Low] || [Value] > [Band High] ) )
```
Restrict the band years with the slicer context removed (`REMOVEFILTERS ( 'Date'[Year] )` + a year window), and guard
blanks (docs/lessons/dax.md).

## layout.json example
```json
{"id": "P1-V06", "name": "sales-vs-usual", "page": "P1", "type": "lineChart", "pattern": "range-band",
 "cols": [1, 8], "x": 32, "y": 360, "w": 1240, "h": 400, "z": 1,
 "bindings": {"Category": ["'Date'[Month]"], "Y": ["[Band Low]", "[Band High]", "[Value]"]},
 "sort": {"field": "'Date'[Month Number]", "direction": "Ascending", "default": true},
 "props": {"lineStyles.strokeWidth@[Band Low]": 1, "lineStyles.strokeWidth@[Band High]": 1,
           "lineStyles.strokeWidth@[Value]": 0, "lineStyles.showMarker@[Value]": true,
           "lineStyles.showMarker@[Band Low]": false, "lineStyles.showMarker@[Band High]": false,
           "dataPoint.fill@[Band Low]": "slateLight", "dataPoint.fill@[Band High]": "slateLight",
           "dataPoint.fill@[Value]": "teal", "legend.show": false},
 "container": {"title": "Sales this year against the usual range",
               "subtitle": "Band: lowest to highest of the same month in earlier years",
               "altText": "Monthly sales this year as dots against the lowest-to-highest range of earlier years"},
 "build": {"method": "native", "step": 1,
           "reason": "Band edges as lines and markers-only current series are native; shading needs error bars (harvest)"}}
```

## Wireframe
Shaded band between the low and high series (the first two Y fields), dots for the last Y field, coloured
`red` outside the band. Sample data: a seasonal curve with one dot outside.

## Audit
Key values: `[Band Low]`, `[Band High]` and `[Value]` for the default month and the first year (no earlier years:
band blank, dots still drawn), plus a month with no rows. Check `Outside Band` on one inside and one outside case.
