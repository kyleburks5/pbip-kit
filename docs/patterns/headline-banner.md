# Headline banner

`pattern: "headline-banner"` (stub: batch 4 item 6)

**Question it answers:** what is the one thing to know on this page right now?

- **Use when:** a page whose key number has a story that changes with the filters ("Sales are 4% above plan, driven by
  the North").
- **Avoid when:** the sentence would repeat a card next to it, or the narrative can't be computed (write a static
  subtitle instead).

## Design
- A tinted shape (`brandTint`, or `warningTint` / `badTint` for an alert) with a title and a subtitle bound to a
  narrative measure (text built in DAX, `FORMAT` for numbers), text in the badge's own text colour (tokens `badges`).
- One banner per page, under the description, full content width.

## Build (visual-method ladder)
- 1 native: a shape, and a new card or text box whose subtitle is a measure (field-value text).
- Template `shape.headline-banner`: **needs a Desktop-saved sample.** Make it on the Patterns page in Desktop, save,
  and run
  `pbik templates harvest`; until then build from the plain type's template and the layout's own keys.

## Not yet
- Wireframe renderer (the wireframe draws the visual type), measures sketch, layout.json example, audit.
