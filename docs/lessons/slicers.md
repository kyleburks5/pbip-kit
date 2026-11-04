# Slicers and navigation

Read by /plan, /build and /fix. Format and placement: docs/lessons/README.md.

## Index
<!-- lessons:index -->
| ID | Lesson | Enforced by |
| --- | --- | --- |
| S-01 | Short button slicers need Custom padding | `pbik validate` warns (pbikit/validate.py `lesson_checks`) |
| S-02 | Button slicers need a grid sized for their items | `pbik validate` warns (pbikit/slicerfit.py) |
| S-03 | Dropdown slicers with a header need 76px | `pbik validate` warns (pbikit/validate.py `lesson_checks`) |
| S-04 | Page navigator states come from the `navigator` key | pbik build writes the states from `navigator` |
<!-- /lessons:index -->

## S-01 Short button slicers need Custom padding
- **Rule:** Under 40px tall, set `padding` to Custom with 0 top and bottom (`pbik_helpers.button_slicer_padding`).
- **Why:** with the default padding the button text disappears.
- **Enforced by:** `pbik validate` warns (pbikit/validate.py `lesson_checks`)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## S-02 Button slicers need a grid sized for their items
- **Rule:** Set `layout.rowCount` and `columnCount` for the items; check with `pbik validate --port auto`.
- **Why:** with only `orientation`, Desktop picked its own tile width and scrolled the rest (3 of 4 buttons shown).
- **Enforced by:** `pbik validate` warns (pbikit/slicerfit.py)
- **Source:** /smoke 2026-10-18

## S-03 Dropdown slicers with a header need 76px
- **Rule:** Give a dropdown slicer with a header at least 76px of height.
- **Why:** reason not recorded when the lesson was written; check in Desktop before relaxing it.
- **Enforced by:** `pbik validate` warns (pbikit/validate.py `lesson_checks`)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## S-04 Page navigator states come from the `navigator` key
- **Rule:** Style a page navigator's `default`, `hover` and `selected` states with the layout.json `navigator` key, and
  keep page display names short (they are the tile labels).
- **Why:** a navigator's states are not the button slicer's `selection:selected`.
- **Enforced by:** pbik build writes the states from `navigator`
- **Source:** Rep 8
