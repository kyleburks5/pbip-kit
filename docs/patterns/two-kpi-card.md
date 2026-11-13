# Two-KPI tinted card

`pattern: "two-kpi-card"` (stub: batch 4 item 6)

**Question it answers:** how do two related numbers stand against each other (actual and target, this year and last)?

- **Use when:** two numbers read together, one primary and one secondary, on a tinted card in a KPI row.
- **Avoid when:** the numbers are unrelated (two cards), or more than two values (a small table).

## Design
- One new card with two fields (callout and a reference label, or two callouts), background `brandTint` (or a badge
  fill), text from the badge's text colour; the card is its own container (C-10).
- Same size as the other cards in the row; label, both values and the change line fill the card.

## Build (visual-method ladder)
- 1 native: a new card (cardVisual) with two data fields.
- Template `cardVisual.two-kpi-card`: **needs a Desktop-saved sample.** Make it on the Patterns page in Desktop, save,
  and run
  `pbik templates harvest`; until then build from the plain type's template and the layout's own keys.

## Not yet
- Wireframe renderer (the wireframe draws the visual type), measures sketch, layout.json example, audit.
