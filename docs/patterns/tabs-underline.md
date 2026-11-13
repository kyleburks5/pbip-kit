# Tabs with underline

`pattern: "tabs-underline"` (stub: batch 4 item 6)

**Question it answers:** which view am I on, and what else is there?

- **Use when:** 2 to 6 pages or views of the same subject, switched in place.
- **Avoid when:** more than 6 targets (use a navigation pane) or targets that aren't peers.

## Design
- Text tabs, no boxes: the selected one in `text` with an accent bar under it (`accentBar`, `brand`), the others in
  `textMuted`; a thin `border` rule under the row.
- Keyboard order follows the tabs left to right.

## Build (visual-method ladder)
- 1 native: a page navigator (or bookmark navigator) with the selected state's accent bar.
- Template `pageNavigator.tabs-underline`: **needs a Desktop-saved sample.** Make it on the Patterns page in Desktop,
  save, and run
  `pbik templates harvest`; until then build from the plain type's template and the layout's own keys.

## Not yet
- Wireframe renderer (the wireframe draws the visual type), measures sketch, layout.json example, audit.
