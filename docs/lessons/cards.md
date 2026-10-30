# Shapes, containers and new cards

Moved from CLAUDE.md (v1-simplify, 2026-10-29); placement rules in docs/lessons/README.md. Read by /plan, /build and /fix.

## Shapes and containers
- Shapes ignore the theme fill: set fill, outline and corners explicitly from the tokens, and put fill colour, transparency and line colour on `selector: {id: default}` (keep `show` selector-less), or Desktop draws the theme's first data colour (Rep 7; layout.json `style`, or `pbik_helpers.shape_objects`).
- A card that shows a text measure on a coloured background needs every background layer off (container background, `fillCustom`, `cardCalloutArea`, `layout` background, `outline`, `shadowCustom`), or a white box shows (`pbik_helpers.card_layers_off`).

## New card (cardVisual)
- Corner radius renders only when `shapeCustomRectangle.tileShape` is `rectangleRoundedByPixel`; set it with `rectangleRoundedCurve`. *(gen_theme.py writes it in the theme.)*
- A reference label with no detail shows "--"; add a `referenceLabelDetail` entry with `show: false`.
- Reference-label settings on metadata-only selectors are ignored once the label has an `id`'d entry: merge them into it (the layout.json `referenceLabels` key writes one or several labels per value this way, `objects.ref_labels`).
- Reference labels: use the "sentence" style, centred, below the value, with `referenceLabel.backgroundShow` for a tinted strip. "Tabular" splits each row into fixed columns that clip titles and deltas in narrow tiles (Rep 7).
- A new card ignores its own padding: Desktop draws its content from the top. To place card content, make the card transparent, size and centre the visual itself, and put the glass on a shape behind it (Rep 7).
- Small multiples: `smallMultiplesLayout.orientation` 0 = Grid (2 = one horizontal row, 1 = vertical) and `style` "Cards" for one tile per cell ("Table" shares one grid). Only then do `rowCount` / `columnCount` apply (Rep 7; `pbik_helpers.small_multiples_grid`).
- `smallMultiplesAccentBar` coloured by a measure doesn't render. To colour each small multiple, set `smallMultiplesHeader.backgroundColor` to the measure on the `{data: [{roles: ["Rows"]}]}` selector (Rep 7; `pbik_helpers.small_multiples_header_colour`).
- To show an image from a measure, use a new card filtered to one value, with the value and label hidden and the image scaled to fill (layout.json `cf` type `image`): an image visual can't take a measure.
