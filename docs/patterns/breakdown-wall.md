# Breakdown wall

`pattern: "breakdown-wall"`

**Question it answers:** for the measure I pick, how does every way of slicing it compare with last year?

- **Use when:** one page must answer "by what?" for several dimensions at once (department, age band, plan, region,
  channel), for any of a few measures, and readers scan for the row that moved most.
- **Avoid when:** one or two dimensions matter (a chart per dimension reads better), or the measures don't share a
  comparison (a picker that changes meaning between tables confuses).

## Examples
- Health plan: members, claims, cost per member, and approval rate, each by plan type, age band, region, provider
  network and channel; current vs last year with the change.
- Sales: revenue, units, margin by region, channel, category, store type and customer segment.

## Design
- One metric picker (a button slicer, top left of the wall) drives every table; the picked metric's name is in each
  table's title ("Claims by age band"), so a screenshot stays readable.
- Tables on the grid, same columns in the same order: member, Current, Last year, Change (signed, with ▲ / ▼ and a
  colour, never colour alone). Sorted by Change; 5 to 8 rows each, so the wall fits without scrolling.
- The number format follows the metric (whole numbers, currency, %): one dynamic format string, not a format per table.
- Small groups follow [honest data](honest-data.md): a rate under the threshold is faded or blank in every table.

## Build (visual-method ladder)
| Step | How | Pick it when |
| --- | --- | --- |
| 1 native (pick this) | A disconnected Metric table (or a field parameter) on a button slicer; `Current`, `Last year`, `Change` as SWITCH measures with a dynamic format string; one `tableEx` per dimension | always |
| 1 native | A calculation group instead of SWITCH measures | the model already has one, or many measures |
| 2 SVG | A change bar per row (DaxLib.SVG first) | the wall needs the size of the change at a glance |

## Measures (sketch)
```dax
Current   = SWITCH ( SELECTEDVALUE ( Metric[Metric], "Members" ),
               "Members", [Members], "Claims", [Claims], "Cost per member", [Cost per member] )
-- dynamic format string on Current, Last year:
SWITCH ( SELECTEDVALUE ( Metric[Metric], "Members" ), "Cost per member", "$#,0.00", "#,0" )
Last year = CALCULATE ( [Current], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )
Change    = DIVIDE ( [Current] - [Last year], [Last year] )
Table title = SELECTEDVALUE ( Metric[Metric], "Members" ) & " by age band"
```
Test each with the picker on every metric, and a member with no last year (Change blank, not infinite).

## layout.json example
```json
{"id": "P1-V07", "name": "by-age-band", "page": "P1", "type": "tableEx", "pattern": "breakdown-wall",
 "x": 32, "y": 360, "w": 446, "h": 300,
 "bindings": {"Values": ["Members[Age band]", "[Current]", "[Last year]", "[Change]"]},
 "sort": {"field": "[Change]", "direction": "Descending"},
 "container": {"title": {"measure": "[Title by age band]"}, "altText": "The picked metric by age band, this year and last"},
 "build": {"method": "native", "step": 1, "reason": "SWITCH measures with a dynamic format string drive every table"}}
```

## Checks
Audit: Current and Last year for two metrics in two tables against a DAX recompute; the format of each metric
(currency shows $, counts no decimals); a member new this year. Wireframe: the wall with the picker on one metric.
