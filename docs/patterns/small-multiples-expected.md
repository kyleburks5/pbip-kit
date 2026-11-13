# Small multiples against an expected line

`pattern: "small-multiples-expected"`

**Question it answers:** which members are off their expected path, and since when?

- **Use when:** 4 to 16 members, each with a time series and its own expected path.
- **Avoid when:** over ~16 members (use an exception list of the off-path ones), or when one shared reference is enough
  (one line chart with a reference line).

## When to use
- 4 to 16 members, each with a time series and an expected path (target, forecast, plan, last year, a seasonal
  baseline). Each panel's own expected line, not one shared average.
- The shapes matter: a member that drifts away is visible at a glance.

## Design
- Same y scale in every panel unless the members differ by size (then say "own scale" in the subtitle).
- Expected: thin dashed `slate` line. Actual: `teal` line, 2-3px.
- Panel titles are the member names (direct labels; no legend). Order panels by the gap, not alphabetically, when the
  question is "which are off".
- Optional: colour the panel header `red` when the member is off path (measure on the header background,
  docs/lessons/cards.md small multiples lesson).

## Build (visual-method ladder)
| Step | How | Draws | Status |
| --- | --- | --- | --- |
| 1 native (pick this) | Line chart: X = `Date[Month]`, Y = `[Actual]`, `[Expected]`, small multiples = `Member[Name]` | panels with both lines, per-panel expected line | `dataPoint.fill` and `lineStyles.strokeWidth` per series in the catalog; **small multiples on a line chart** (binding role, grid layout) and the dashed `lineStyle` are *harvest* |
| 1 native, simpler | A y-axis reference line instead of an `[Expected]` series | one constant per panel (the same for all) | only when the expectation is one number for all members |
| 3 Deneb | `facet` (or `row`/`column`) with a `line` layer per series | everything, panel order and header colour by rule | when panel order by gap is required |

The expected path must be a measure series, not a reference line: a reference line is one value for the whole
visual, so every panel would show the same line.

## Measures (sketch)
```dax
Expected = CALCULATE ( [Actual], SAMEPERIODLASTYEAR ( 'Date'[Date] ) ) * ( 1 + [Growth Target] )
Gap %    = DIVIDE ( [Actual] - [Expected], [Expected] )
```

## layout.json example
```json
{"id": "P2-V04", "name": "regions-vs-plan", "page": "P2", "type": "lineChart", "pattern": "small-multiples-expected",
 "cols": [1, 12], "x": 32, "y": 200, "w": 1856, "h": 640, "z": 1,
 "bindings": {"Category": ["'Date'[Month]"], "Y": ["[Actual]", "[Expected]"], "Rows": ["Region[Region]"]},
 "props": {"dataPoint.fill@[Actual]": "teal", "dataPoint.fill@[Expected]": "slate",
           "lineStyles.strokeWidth@[Actual]": 3, "lineStyles.strokeWidth@[Expected]": 1, "legend.show": false},
 "container": {"title": "Each region against its plan", "subtitle": "Dashed: plan; solid: actual",
               "altText": "Monthly actual against plan, one small panel per region"},
 "build": {"method": "native", "step": 1, "reason": "Native small multiples; per-panel expected line as a series"},
 "notes": "Rows (small multiples role) and lineStyles.lineStyle dashed: harvest from the Patterns page before /build"}
```

## Wireframe
A grid of panels (up to 16), each with the expected line dashed and the actual line solid on a shared scale; panel
titles from the small-multiples field. With the data file, rows group by the small-multiples field.

## Audit
`[Actual]` and `[Expected]` for two members in the default state; a member with no rows in the period (empty panel);
the first year (no prior-year basis, `[Expected]` blank).
