# Shared panel

`pattern: "panel"` (rail + panel study, 2026-11-15; GENERIC)

**Question it answers:** which numbers and charts belong together?

- **Use when:** a group of cards and a chart read as one unit (one entity's profile, one subject's numbers), so one
  surface holds them instead of each card floating on its own.
- **Avoid when:** the page is a grid of independent tiles (each card is its own container, C-10), or the panel would
  hold one visual only (give that visual its own container).

## Design
- One white shape (`card`) with the container radius and the one soft shadow (`container.pbiShadow`), no border, on
  the page `background`.
- The visuals on it have **no background, border or shadow of their own** and sit at **one inset** from the panel's
  left, right and top edges (the container padding, or a whole number of gutters); rows inside keep equal gaps.
- Titles inside the panel use the visual title and divider (`border`), not a box.

## Build (visual-method ladder)
- 1 native: a shape, layout.json `pattern: "panel"`, `decorative: true`, `container: {"keepLayerOrder": true}` (C-11).
- Template `shape.panel` (clean harvest from the study; confirm in Desktop): radius, shadow, padding and title
  spacing.
- Cards on it: container background off. `pbik validate` accepts them on a panel and warns when one draws its own
  background or the insets differ (pbikit/kpicards.py, lesson C-10).

## layout.json example
```json
{"id": "P1-V05", "type": "shape", "name": "panel", "pattern": "panel", "template": "shape.panel", "decorative": true,
 "x": 659, "y": 128, "w": 1229, "h": 920, "container": {"keepLayerOrder": true}}
```

## Wireframe
The wireframe draws the shape as a card-coloured box with the shadow; the visuals on it draw without their own box.

## Audit
No numbers of its own.
