# Data freshness line

`pattern: "freshness-line"`

**Question it answers:** how current is this, and can I trust it today?

- **Use when:** every page (one line near the title), and time charts whose axis runs past the last data date.
- **Avoid when:** the page already shows a refresh date in a shared header (one line per page is enough).

## When to use
- Every report page: one short line near the title, "Data to 30 Sep 2026 · refreshed 1 Oct 06:10".
- On time charts, a vertical line at the last data date when the axis runs past it (a date table to year end).
- A stale state: when the data is older than its expected refresh, say so in `red` text with a symbol.

## Design
- The text in `textMuted`, caption size, right-aligned under the page title or in the header strip.
- Stale: "⚠ Data is 9 days old (expected daily)" in `red`; a symbol and words, not colour alone.
- On charts: a thin `textMuted` dashed category-axis line labelled "data to 30 Sep".

## Build (visual-method ladder)
| Step | How | Draws | Status |
| --- | --- | --- | --- |
| 1 native (pick this) | New card (cardVisual) with a text measure `[Freshness]`, label off, transparent; colour from `[Freshness colour]` | the line of text, red when stale | card value font colour by measure: `cf` kind colour on `value.fontColor`; text measure recognised by `pbik model check` |
| 1 native, on charts | `referenceLines: [{axis: "category", value: "[Last data date]", label: "data to"}]` | vertical line at the last date | `xAxisReferenceLine` is in the catalog for column charts; on line charts *harvest* |

## Measures (sketch)
```dax
Last data date = MAX ( Fact[Date] )                              -- ignores slicers: CALCULATE ( ..., REMOVEFILTERS () )
Days old      = DATEDIFF ( [Last data date], TODAY (), DAY )
Freshness     = "Data to " & FORMAT ( [Last data date], "d mmm yyyy" ) &
                IF ( [Days old] > [Expected lag days], "  ⚠ " & [Days old] & " days old", "" )
Freshness colour = IF ( [Days old] > [Expected lag days], "#A84545", "#5A6577" )   -- token values from /plan
```
The refresh time itself isn't in the model; if needed, store it in a one-row table at refresh (Power Query
`DateTime.LocalNow()`), which is an aggregate, not row data.

## layout.json example
```json
{"id": "P1-V02", "name": "freshness", "page": "P1", "type": "cardVisual", "pattern": "freshness-line",
 "x": 1306, "y": 40, "w": 582, "h": 40, "z": 2,
 "bindings": {"Data": ["[Freshness]"]},
 "props": {"label.show": false, "value.fontSize@default": "caption", "value.horizontalAlignment@default": "right"},
 "cf": [{"type": "measure", "object": "value", "property": "fontColor", "measure": "[Freshness colour]"}],
 "container": {"background": false, "border": false, "shadow": false,
               "altText": "The date the data runs to, and a warning when it is older than expected"},
 "build": {"method": "native", "step": 1, "reason": "Text measure in a new card"}}
```
Hex in DAX breaks the "never hardcode colours" rule unless /plan writes the colour measures from tokens.json; record
the token names in the measure description.

## Wireframe
The freshness text right-aligned in caption size; a dashed vertical "data to" line on time charts that have a
`freshness-line` reference line. Without data: "Data to dd mmm yyyy".

## Audit
`[Last data date]` against `MAX` of the raw date column; `[Freshness]` text in the default state; the stale case
(a `TODAY` override is not possible in DAX queries, so test `[Days old] > lag` with a query-scoped `DEFINE MEASURE`
of `[Days old]` set to a large number).
