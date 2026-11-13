# Page header stack

`pattern: "page-header-stack"` (stub: batch 4 item 6)

**Question it answers:** where am I, what is this page for, and what should I read first?

- **Use when:** every report page: eyebrow, title, one-line description, an optional banner, tabs and a thin rule
  above the content.
- **Avoid when:** a single-visual page or a tooltip page (a title is enough), or when the report already has a shared
  header band.

## Design
- Order, top to bottom: eyebrow (`textMuted`, small caps), title (`text`, title size), description (`textMuted`, one
  line), an optional headline banner, tabs, a thin rule (`border`), then the content.
- The stack sits in the header container at x 0, y 0, full page width, padding 0 (lesson and `pbik validate` header
  check, batch 4 item 4); the content starts below the rule.

## Build (visual-method ladder)
- 1 native: text boxes, a shape for the rule, a page navigator for the tabs.
- Template `textbox.page-header-stack`: **needs a Desktop-saved sample.** Make it on the Patterns page in Desktop,
  save, and run
  `pbik templates harvest`; until then build from the plain type's template and the layout's own keys.

## Not yet
- Wireframe renderer (the wireframe draws the visual type), measures sketch, layout.json example, audit.
