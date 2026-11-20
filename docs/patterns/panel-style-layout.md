# Panel style layout

`pattern: "panel-style-layout"` (a layout style and a house style; learned from the maintainer's Rep 9 report, v1.12;
GENERIC). Preset: `panel-style` (design/themes/presets/panel-style.json). Built by `pbik layout panels`.

**Question it answers:** how do these few members compare, each telling the same story side by side?

- **Use when:** 2 to 6 members of one small dimension are compared side by side: channels, lines of business, care
  settings, regions, product lines. Each member's panel answers the same questions in the same places, so the eye
  moves across the page. It is the default house style for comparing a few members (design/themes/presets/README.md
  "Styles").
- **Avoid when:** more than 6 members (use the grid or rail + panel, pickers instead), one member's deep story (rail +
  panel), or a page that must also hold a wide table (put it on a drill-through page).

## Design (Rep 9's sizes, 1920 x 1080)
- **Header band:** full width, 200 px, near-black (`header`); a kit-drawn icon (56 px), the title (`title`, white),
  a definition line under it (`subtitle`, `onDarkMuted`: what is counted and how), the Year dropdown at the right
  (single select, opens on a set year, `headerControl` fill).
- **Panels:** one per member, equal width across the content (3 columns each for 4 members), from y 136 to the bottom
  margin (912 px), overlapping the band by 64 px; white, radius 20, one soft shadow, no border. In each, 24 px in:
  1. the member's name in its identity text colour (`cardTitle`) and its icon on a tinted circle (52 px), top right;
  2. its share of the whole: a line ("49.1% of all interactions", `subtitle`, muted) and a progress bar (a 100%
     stacked bar, 60 px tall: the share in the member's colour on a `track` grey rest);
  3. the big number (`kpi`, semibold) with a **change chip** under it ("▲ +252 · +2.8% vs 2022" on a good / bad /
     neutral tint, by the member's polarity: for a lower-is-better member a rise is red), beside **quarterly mini
     columns** with compact labels (display units Auto: 2.3K; `pbik validate` flags labels that would overlap);
  4. a 1 px rule;
  5. the **threshold histogram** ([threshold-histogram](threshold-histogram.md));
  6. the **top N** of a category as [label-above bars](label-above-bars.md): the name above each slim bar, the value
     at its end. Right-clicking a bar drills through to the detail page.
- **Identity colours:** the preset's `memberPalette` in order (Rep 9: blue, green, teal, red; then purple, amber), each
  checked by the kit: the mark 3:1 on white (bars), the text shade 4.5:1 on white and on its tint (AA). Red and green
  carry meaning: put a member that means trouble (escalations, readmissions) where its colour says so, or give it its
  own `color` in the spec.
- **Interactions:** a click inside one panel filters that panel only (the others are set to no filter).
- Nothing else on the page: details are a drill-through page reached from the top N bars.

## Build (visual-method ladder)
1 native throughout: shapes (band, panels, rules), text boxes, new cards (share line, big number with the chip as a
reference-label detail on its own font and fill measures, last year's value hidden), a 100% stacked bar, column
charts, a bar chart, a dropdown slicer. The icons are image visuals showing kit-drawn PNGs (step 2: a glyph can't
sit on a tinted circle at a steady size); pbikit/icons.py draws them, no outside icon pack.

The spec (design/specs/panels.json) names the fields; `pbik layout panels` writes everything else:

```json
{"page": "P1", "dimension": "Channel[Interaction Type]", "members": ["Calls", "Chats", "Emails", "Escalations"],
 "memberMeta": {"Escalations": {"lowerIsBetter": true}},
 "header": {"title": "IT Service Ticket Overview", "definition": "…", "icon": "headset", "year": "Date[Year]",
            "yearDefault": 2023},
 "count": "[Interactions]", "countLabel": "Interactions", "countNoun": "interactions", "countLY": "[Interactions PY]",
 "share": "[Share of Interactions %]", "measureTable": "DataTable", "period": "Date[Quarter]",
 "distribution": {"column": "DataTable[Resolution Time (Days)]", "threshold": "[SLA Days]",
                  "average": "[Avg Resolution Days]", "within": "[Interactions Within SLA]", "rate": "[SLA Compliance %]",
                  "title": "Resolution time", "axis": "Days to resolve", "unit": "days", "thresholdName": "SLA"},
 "top": {"field": "DataTable[Category]", "n": 5, "title": "Top 5 categories"}, "date": "'Date'[Date]"}
```

It writes the visuals (stable IDs by name; a rerun keeps them, and retires the page's other visuals unless `keep`
lists them), the planned measures (share rest and title, the chip's text, font and fill, the histogram's bar colour
and subtitle, the axis maxima, the top N's label and spacer), the preset's colours and sizes and each member's
identity colours in tokens.json, and the icons in design/images/. Any measure the spec names that the model lacks
(last year, the share) is planned too. Light or dark: the panels follow `card` and the text tokens, so a dark preset
works (check the chips' tints for AA).

**Healthcare example:** one panel per line of business (Medicare, Medicaid, Commercial, Exchange): members enrolled,
their share, the change vs last year, monthly or quarterly mini columns, a histogram of days to claim payment against
the prompt-pay limit, and the top 5 diagnosis groups. Or one panel per care setting (Inpatient, Outpatient,
Emergency, Home health): visits, share, change, length of stay against its target, top 5 conditions. The icons
guess from the names (bed, clinic, cross, home) or take `memberMeta.<member>.icon`.

## Wireframe
gen_wireframe_hf.py draws it as Desktop does: the chip on its tint, compact quarter labels, the histogram's bars in
colour up to the threshold and grey beyond, a few value ticks, "Days to resolve" under the axis and "avg: 2.95" on the
dashed line, the names above slim bars. The regression case `panel-style` builds it, so the look can't drift.

## Desktop checks
Confirmed on test 2 of the batch studies (2026-11-19, Desktop 2.159.1231.0, made-up model): band, panels, icons,
chips, compact labels, threshold histogram with its "avg" label, label-above bars, drill-through from a top N bar.
