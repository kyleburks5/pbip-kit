# KPI card with mini bars

**Question:** Where does this period sit against the last twelve?

**Use when** a headline number has a monthly (or weekly) history and the reader should see the current period's bar
next to the ones before it, the current one in the accent colour.
**Avoid when** the comparison is one number (prior year, target: a reference label on the card is enough), or the
periods are not in order (the measure needs a sortable period column).

## Design

- A new card: the label, the value, a reference label with the change, and below them the mini bars as the card's
  image (image area 100, fit; .claude/rules/svg.md).
- Twelve bars from the same zero, quiet colour (`colors.secondLight`); the current period in `colors.brand`. No axis:
  the card's own numbers carry the values.
- Alt text names the value, the change and "current month highlighted against the eleven before".

## Native route: KPI tile with a small this-year vs last-year chart

When the comparison is this year against last year by month (not "this period against the last twelve"), build it
natively: one panel shape; a new card (label, value, reference label with the change vs last year) on the top half;
a clustered column chart on the bottom half with Month on the axis and `[Value LY]`, `[Value]` as two series (last
year in `colors.secondLight`, this year in `colors.brand`), axes, gridlines and legend off, data labels off, the card
and the chart with no background of their own ([panel](../panel.md)). A row of 4 to 6 such tiles makes the KPI strip.
Health example: members, claims, cost per member, approval rate; sales: revenue, units, margin, orders. Pick SVG
mini bars (below) when the tile is too small for a chart (under about 120 px high) or the current period must be
highlighted.

## Build

Checked first (svg.md order): DaxLib.SVG `Compound.Bars` / `Viz.Bars` colour one bar only as the minimum or maximum,
and the kit UDF cards (`Park.SVG.SVGKPICard` Bar1-Bar5) colour bars against last year, not the current period. So this
is a new SVG measure (ladder step 2); record that as `build.nativeTried` / `build.reason`.

```dax
KPI Bars SVG =
VAR _Accent = "%23038D96"          // tokens colors.brand
VAR _Quiet = "%23B8C2D6"           // tokens colors.secondLight
VAR _W = 524        // W:H = the tile's (571 x 48): the card scales images to its width
VAR _H = 44
VAR _Cur = MAX ( Sales[Month] )    // the current period: the latest month in the filter context
VAR _Months = TOPN ( 12, FILTER ( ALL ( Sales[Month] ), Sales[Month] <= _Cur ), Sales[Month], DESC )
VAR _T = ADDCOLUMNS ( _Months, "@v", CALCULATE ( [Total Amount], REMOVEFILTERS ( Sales[Date], Sales[Year] ) ) )
VAR _Max = MAXX ( _T, [@v] )
VAR _Bw = DIVIDE ( _W, COUNTROWS ( _T ) )
VAR _Bars =
    CONCATENATEX ( _T,
        VAR _I = RANKX ( _T, Sales[Month], , ASC ) - 1
        VAR _Hh = DIVIDE ( [@v], _Max ) * ( _H - 4 )
        RETURN "<rect x='" & FORMAT ( _I * _Bw + _Bw * 0.15, "0.0", "en-US" ) & "' y='" & FORMAT ( _H - _Hh, "0.0", "en-US" )
            & "' width='" & FORMAT ( _Bw * 0.7, "0.0", "en-US" ) & "' height='" & FORMAT ( _Hh, "0.0", "en-US" )
            & "' rx='1.5' fill='" & IF ( Sales[Month] = _Cur, _Accent, _Quiet ) & "'/>",
        "", Sales[Month], ASC )
RETURN
    IF ( NOT ISBLANK ( _Max ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='" & _W & "' height='" & _H
            & "' viewBox='0 0 " & _W & " " & _H & "'>" & _Bars & "</svg>" )
```

Swap the period column (`Sales[Month]`, text that sorts in order, or a month number) and the measure. Colours are
`%23` + the token's hex (hand-written SVG: `%23`, never a raw `#` or `%`). Data category ImageUrl; as a card image,
wrap it in a report extension measure (`pbik measure ext add ... --data-category ImageUrl`).

Tested query-scoped on the scratch model (2026-11-16): twelve bars to 2026-11, the last in the accent; with Region =
East and months up to 2026-06, twelve bars ending at June; blank with no data. Review it with the
`reports:svg-reviewer` agent before building it.

**Size it to the tile.** A new card scales its image to the tile's width, not to fit inside it, so an SVG whose
width:height is narrower than the tile's is cut top and bottom (Desktop review 2026-11-17: 160x44 bars in a 571x48
tile were drawn 571x156). Keep `_H` for the drawing and set `_W = _H x tile width / tile height`; `pbik validate`
warns when an image would be cut and says the size to draw.

## Checks

`design/scripts/audit_svg.py` in every audit state (well-formed, no raw `%`), the empty state included.
