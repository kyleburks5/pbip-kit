# Shapes, containers and new cards

Read by /plan, /build and /fix. Format and placement: docs/lessons/README.md. Showing an image from a measure:
.claude/rules/svg.md.

## Index
<!-- lessons:index -->
| ID | Lesson | Enforced by |
| --- | --- | --- |
| C-01 | Shapes need their fill set explicitly | – |
| C-02 | A text card on a coloured background turns every layer off | – |
| C-03 | Rounded new cards need tileShape rectangleRoundedByPixel | design/scripts/gen_theme.py writes it in the theme |
| C-04 | A reference label without detail needs its detail hidden | – |
| C-05 | Reference-label settings go on the label's own entry | pbik build merges them into the `id`'d entry (`objects.ref_labels`) |
| C-06 | Reference labels in the sentence style | – |
| C-07 | A new card ignores its own padding | – |
| C-08 | Small multiples grid settings | – |
| C-09 | Colour small multiples through the header, not the accent bar | – |
<!-- /lessons:index -->

## C-01 Shapes need their fill set explicitly
- **Rule:** Set a shape's fill, outline and corners from the tokens, with fill colour, transparency and line colour on
  `selector: {id: default}` and `show` selector-less (layout.json `style`, or `pbik_helpers.shape_objects`).
- **Why:** shapes ignore the theme fill; Desktop drew the theme's first data colour.
- **Enforced by:** not enforced (layout.json `style` writes it this way)
- **Source:** Rep 7

## C-02 A text card on a coloured background turns every layer off
- **Rule:** Turn off the container background, `fillCustom`, `cardCalloutArea`, the `layout` background, `outline` and
  `shadowCustom` (`pbik_helpers.card_layers_off`).
- **Why:** any layer left on shows as a white box.
- **Enforced by:** not enforced (read at /build)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## C-03 Rounded new cards need tileShape rectangleRoundedByPixel
- **Rule:** Set the corner radius with `rectangleRoundedCurve` and `shapeCustomRectangle.tileShape`
  `rectangleRoundedByPixel`.
- **Why:** with any other tile shape the radius doesn't render.
- **Enforced by:** design/scripts/gen_theme.py writes it in the theme
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## C-04 A reference label without detail needs its detail hidden
- **Rule:** Add a `referenceLabelDetail` entry with `show: false` to every reference label that has no detail.
- **Why:** an empty detail shows "--".
- **Enforced by:** not enforced (read at /build)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## C-05 Reference-label settings go on the label's own entry
- **Rule:** Write reference labels with the layout.json `referenceLabels` key (one or several labels per value).
- **Why:** settings on metadata-only selectors are ignored once the label has an `id`'d entry.
- **Enforced by:** pbik build merges them into the `id`'d entry (`objects.ref_labels`)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## C-06 Reference labels in the sentence style
- **Rule:** Use the "sentence" style, centred, below the value, with `referenceLabel.backgroundShow` for a tinted strip.
- **Why:** "Tabular" splits each row into fixed columns that clip titles and deltas in narrow tiles.
- **Enforced by:** not enforced (card templates use it)
- **Source:** Rep 7

## C-07 A new card ignores its own padding
- **Rule:** To place card content, make the card transparent, size and centre the visual itself, and put the glass on
  a shape behind it.
- **Why:** Desktop draws a new card's content from the top whatever its padding.
- **Enforced by:** not enforced (read at /plan and /build)
- **Source:** Rep 7

## C-08 Small multiples grid settings
- **Rule:** Set `smallMultiplesLayout.orientation` 0 (Grid; 2 is one row, 1 vertical) and `style` "Cards" (one tile per
  cell) before `rowCount` / `columnCount` (`pbik_helpers.small_multiples_grid`).
- **Why:** row and column counts apply only to a Grid of Cards.
- **Enforced by:** not enforced (read at /build)
- **Source:** Rep 7

## C-09 Colour small multiples through the header, not the accent bar
- **Rule:** Set `smallMultiplesHeader.backgroundColor` to the measure on the `{data: [{roles: ["Rows"]}]}` selector
  (`pbik_helpers.small_multiples_header_colour`).
- **Why:** `smallMultiplesAccentBar` coloured by a measure doesn't render.
- **Enforced by:** not enforced (read at /build)
- **Source:** Rep 7
