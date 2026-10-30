# Slicers and navigation

Moved from CLAUDE.md (v1-simplify, 2026-10-29); placement rules in docs/lessons/README.md. Read by /plan, /build and /fix.

- Button slicers under ~40px tall need `padding.default` set to Custom with 0 top and bottom, or the button text disappears (`pbik_helpers.button_slicer_padding`).
- Button slicers need `layout.rowCount` and `columnCount` sized for their items. With only `orientation`, Desktop picks its own tile width and scrolls the rest. Check with `pbik validate --port auto` (Smoke 2026-10-18). *(`pbik validate` warns, pbikit/slicerfit.py.)*
- Dropdown slicers with a header need at least 76px of height.
- A page navigator's states are `default` / `hover` / `selected`, not the button slicer's `selection:selected`. Write them with the layout.json `navigator` key (fill, outline, radius, font, size, colors and transparency per state). The tile labels are the page display names, so keep page names short.
