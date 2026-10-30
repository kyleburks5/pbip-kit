# Accessibility

Moved from CLAUDE.md (v1-simplify, 2026-10-29); placement rules in docs/lessons/README.md. Read by /plan (layout.json alt text, colours), /build and /fix.

- Every data visual and image has alt text (layout.json `container.altText`: what it shows, in one sentence).
- Text meets WCAG 2.1 AA contrast against what is behind it: 4.5:1, or 3:1 for large text (18pt and up, or 14pt bold or
  semibold). That includes button, navigator and slicer text in each state against that state's fill.
- No text below 10pt (tokens `a11y.minFontPt`).
- Tab order follows reading order: top to bottom in rows, left to right in a row (decorative shapes and hidden
  visuals don't count).
- Colours come from /theme (design/scripts/gen_tokens.py): every text pair 4.5:1 and every selected state 3:1 against
  the card with its text 4.5:1, by moving lightness only (design/reviews/theme.md lists what moved). Use colour names in
  their role: text in `text`, `textMuted`, `primaryText`, `brandText` (`tealDark`), `good`, `bad`, `warning`; text on
  primary bands in `onDark` / `onDarkMuted`; selected tiles `selected` with `onSelected` text. `--layout --fix-layout`
  renames the rest (v1-design: Rep 8 had `teal` + white in its selected tiles, 4.0:1).
- design/scripts/check_contrast.py measures every text on the drawn wireframe against what is behind it (hidden
  groups too); /plan and /theme run it.
- `pbik validate` checks all four as warnings (pbikit/a11y.py). Fix them in layout.json, or note why one is accepted in
  the spec by visual ID.
