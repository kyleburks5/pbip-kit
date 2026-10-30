# Theme presets

Starting colour schemes for `/theme` (design/scripts/gen_tokens.py), used only when the brief gives no brand colours
and design/reference/ has no reference. Default: **clean**.

| Preset | Look | Corners, edges |
| --- | --- | --- |
| `clean` | Neutral slate-teal on a cool grey canvas, white cards (the palette tokens.json shipped with, Rep 5) | 16px, soft shadow, no border |
| `bento` | Warm off-white canvas, white tiles, indigo brand with coral and mint | 24px, near-flat shadow, no border |
| `corporate` | Navy header, corporate blue, grey neutrals | 4px, 1px border, no shadow |

A preset file holds `mode`, `brand` (colours by role: `primary=`, `brand=`, `bad=`, `good=`, `second=`, others are
extra series colours), optional `colors` (names it pins; the clean preset pins its whole palette) and `container`,
`control` or `font` values for tokens.json. Pinned colours are still checked: one that fails WCAG 2.1 AA moves and is
listed in design/reviews/theme.md.

Layout style is separate from the palette: a bento *layout* (tiles of mixed spans and heights) comes from /plan
(docs/layouts/bento.html is a reference of one); the bento preset is the look that suits it.
