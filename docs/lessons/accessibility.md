# Accessibility

Read by /plan (alt text, colours), /build and /fix. Format and placement: docs/lessons/README.md. Fix a warning in
layout.json, or note why it is accepted in the spec by visual ID.

## Index
<!-- lessons:index -->
| ID | Lesson | Enforced by |
| --- | --- | --- |
| A-01 | Every data visual and image has alt text | `pbik validate` warns (pbikit/a11y.py); gen_wireframe_hf.py lists the missing ones |
| A-02 | Text meets WCAG 2.1 AA contrast in every state | `pbik validate` warns (pbikit/a11y.py); design/scripts/check_contrast.py on the wireframe |
| A-03 | No text below 10pt | `pbik validate` warns (pbikit/a11y.py) |
| A-04 | Tab order follows reading order | `pbik validate` warns (pbikit/a11y.py); pbik writes tab order as the visual number x 100 |
| A-05 | Colours come from /theme and are used in their role | gen_tokens.py `--layout --fix-layout` renames colours out of role; check_contrast.py |
<!-- /lessons:index -->

## A-01 Every data visual and image has alt text
- **Rule:** Write `container.altText` for every data visual and image: what it shows, for which period or filter, in
  one sentence.
- **Why:** screen readers announce a visual by its alt text.
- **Enforced by:** `pbik validate` warns (pbikit/a11y.py); gen_wireframe_hf.py lists the missing ones
- **Source:** kit v0.3

## A-02 Text meets WCAG 2.1 AA contrast in every state
- **Rule:** 4.5:1 against what is behind the text, 3:1 for large text (18pt and up, or 14pt bold or semibold),
  including button, navigator and slicer text in each state against that state's fill.
- **Why:** WCAG 2.1 AA.
- **Enforced by:** `pbik validate` warns (pbikit/a11y.py); design/scripts/check_contrast.py on the wireframe
- **Source:** kit v0.3

## A-03 No text below 10pt
- **Rule:** Keep every text at or above tokens `a11y.minFontPt` (10).
- **Why:** smaller text isn't readable at normal zoom.
- **Enforced by:** `pbik validate` warns (pbikit/a11y.py)
- **Source:** kit v0.3

## A-04 Tab order follows reading order
- **Rule:** Number visual IDs top to bottom, left to right; set `tabOrder` only where that can't follow.
- **Why:** keyboard users move through visuals in tab order.
- **Enforced by:** `pbik validate` warns (pbikit/a11y.py); pbik writes tab order as the visual number x 100
- **Source:** Rep 9

## A-05 Colours come from /theme and are used in their role
- **Rule:** Make colours with /theme (gen_tokens.py moves lightness only until every pair passes) and use each name in
  its role: text in `text`, `textMuted`, `primaryText`, `brandText`, `good`, `bad`, `warning`; text on primary bands
  in `onDark` / `onDarkMuted`; selected tiles `selected` with `onSelected` text.
- **Why:** Rep 8 had `teal` with white text in its selected tiles: 4.0:1.
- **Enforced by:** gen_tokens.py `--layout --fix-layout` renames colours out of role; check_contrast.py
- **Source:** Rep 8 (v1-design)
