# Forecast bullet

**Question:** Will we reach the target at this pace?

**Use when** a year-to-date (or quarter-to-date) actual has a target and a simple run-rate forecast, and the reader
should see how much is done, how much is only projected, and where the target sits, in one bar.
**Avoid when** the forecast comes from a model the reader can't question (say where it comes from in the alt text),
or there is no target (a progress bar with the actual alone).

## Design

- A rounded track (`colors.neutralTint`); the actual as a solid bar (`colors.brand`); from the actual to the forecast
  a hatched segment (diagonal lines in the brand colour on `colors.brandTint`): projected, not done; the target as a
  dark marker (`colors.text`) across the bar.
- The scale runs to 105% of the larger of forecast and target, so the marker never sits on the edge.
- The numbers go next to it (a card, or table columns); the image carries the shape. Alt text says all three numbers
  and "hatched: forecast, not yet done".

## Build

Checked first: DaxLib.SVG `Compound.ProgressBar` draws a track and one fill, with no pattern fill or target marker
(its defs have gradients, not patterns). So this is a new SVG measure (ladder step 2), small enough to keep plain.

```dax
Forecast Bullet SVG =
VAR _Accent = "%23038D96"     // tokens colors.brand
VAR _Track = "%23EEF1F6"      // tokens colors.neutralTint
VAR _Tint = "%23E7F3F5"       // tokens colors.brandTint
VAR _Mark = "%231D2733"       // tokens colors.text
VAR _W = 285        // W:H = the tile's (571 x 48): the card scales images to its width
VAR _H = 24
VAR _A = [Year Actual]
VAR _F = MAX ( [Year Forecast], _A )
VAR _G = [Year Target]
VAR _Scale = DIVIDE ( _W - 4, MAX ( _F, _G ) * 1.05 )
RETURN
    IF ( NOT ISBLANK ( _A ),
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='" & _W & "' height='" & _H & "' viewBox='0 0 " & _W & " " & _H & "'>"
            & "<defs><pattern id='hatch' width='6' height='6' patternUnits='userSpaceOnUse' patternTransform='rotate(45)'>"
            & "<rect width='6' height='6' fill='" & _Tint & "'/><line x1='0' y1='0' x2='0' y2='6' stroke='" & _Accent & "' stroke-width='2.5'/></pattern></defs>"
            & "<rect x='0' y='6' width='" & _W & "' height='12' rx='6' fill='" & _Track & "'/>"
            & "<rect x='0' y='6' width='" & FORMAT ( _F * _Scale, "0.0", "en-US" ) & "' height='12' rx='6' fill='url(%23hatch)'/>"
            & "<rect x='0' y='6' width='" & FORMAT ( _A * _Scale, "0.0", "en-US" ) & "' height='12' rx='6' fill='" & _Accent & "'/>"
            & "<rect x='" & FORMAT ( _G * _Scale - 1.5, "0.0", "en-US" ) & "' y='1' width='3' height='22' rx='1' fill='" & _Mark & "'/>"
            & "</svg>" )
```

`[Year Actual]`, `[Year Forecast]` (actual / periods so far x periods in the year) and `[Year Target]` are the
model's own measures; the pattern only draws them. `url(%23hatch)`: the `#` of the reference is encoded like a colour.

Tested query-scoped on the scratch model (2026-11-16): the bar, the hatched forecast and the target marker drew in
Chromium from the data URI; blank with no data. Review it with the `reports:svg-reviewer` agent before building it.

**Size it to the tile.** A new card scales its image to the tile's width, not to fit inside it, so an SVG whose
width:height is narrower than the tile's is cut top and bottom (Desktop review 2026-11-17: 160x44 bars in a 571x48
tile were drawn 571x156). Keep `_H` for the drawing and set `_W = _H x tile width / tile height`; `pbik validate`
warns when an image would be cut and says the size to draw.

## Checks

`audit_svg.py` in every audit state; the three numbers in the card or table are part of the numbers audit.
