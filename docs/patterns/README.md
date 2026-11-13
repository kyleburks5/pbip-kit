# Pattern library

Patterns for reports that answer "compared with what?" and "is anything wrong?" rather than only "how much?".
`/plan` records the design ambition first (spec.md: baseline, normal, exceptions, partial or stale data per key
number), then picks patterns from here and names them on each visual in layout.json (`pattern`).

| Pattern (`pattern` key) | Question it answers | Native build | Lowest step that draws it all |
| --- | --- | --- | --- |
| [Range band with current-period dots](range-band.md) (`range-band`) | Is this period inside its usual range? | Line chart: min / max lines + current as dots | 1 native (band shading: error bars, to harvest) |
| [Dumbbell rows with change labels](dumbbell.md) (`dumbbell`) | How far did each member move between two points, and which way? | none (two marker-only series have no connector) | 2 SVG measure in a table |
| [Small multiples against an expected line](small-multiples-expected.md) (`small-multiples-expected`) | Which members are off their expected path? | Line chart with small multiples + an expected series | 1 native |
| [Brushed range selection](brushed-range.md) (`brushed-range`) | What happens in the period I pick? | Between slicer on the date above the chart | 1 native (brushing on the chart itself: 3 Deneb) |
| [Partial-period markers](partial-period.md) (`partial-period`) | Is the last point complete, or still filling up? | Separate "partial" series, lighter, marker only | 1 native (a true hollow point: 3 Deneb) |
| [Data freshness line](freshness-line.md) (`freshness-line`) | How current is this, and can I trust it today? | Text measure in a card + category-axis reference line | 1 native |
| [Exception list](exception-list.md) (`exception-list`) | Which members need attention, worst first? | Table whose measures are blank for normal rows | 1 native |
| [Direct labels instead of legends](direct-labels.md) (`direct-labels`) | Which line or bar is which, without a lookup? | Legend off; series / category labels on the marks | 1 native (line-end labels: series labels, to harvest) |
| [Page header stack](page-header-stack.md) (`page-header-stack`) | Where am I, what is this page for, and what should I read first? | stub: see the page | 1 native (template needs a Desktop-saved sample) |
| [Headline banner](headline-banner.md) (`headline-banner`) | What is the one thing to know on this page right now? | stub: see the page | 1 native (template needs a Desktop-saved sample) |
| [Ranked bar table](ranked-bar-table.md) (`ranked-bar-table`) | Who ranks where, by how much, which way are they moving, and are they OK? | stub: see the page | 1 native (template needs a Desktop-saved sample) |
| [Two-KPI tinted card](two-kpi-card.md) (`two-kpi-card`) | How do two related numbers stand against each other (actual and target, this year and last)? | stub: see the page | 1 native (template needs a Desktop-saved sample) |
| [Tabs with underline](tabs-underline.md) (`tabs-underline`) | Which view am I on, and what else is there? | stub: see the page | 1 native (template needs a Desktop-saved sample) |
| [Text link button](text-link-button.md) (`text-link-button`) | Where do I go for more? | stub: see the page | 1 native (template needs a Desktop-saved sample) |

## How a pattern page is laid out

- **The question it answers** (one sentence a reader would ask), then a **Use when** and an **Avoid when** line
  (/plan quotes them as the reason for each pattern it picks), then **When to use** in more detail.
- **Design**: what is drawn and what each mark means, with the colours as token names.
- **Build**: the visual-method ladder for this pattern (CLAUDE.md "Visual-method ladder"): what each step draws, and
  the step `/plan` should normally pick. Record the step and reason in layout.json `build`.
- **Measures**: the DAX the pattern needs, as a sketch to adapt (test it query-scoped first, docs/lessons/dax.md).
- **layout.json example**: pbik keys only (tools/pbik/README.md). Properties marked *harvest* are not yet in the
  settings catalog (`pbik catalog show`): set them once on the Patterns page in Desktop, save, and copy the saved
  JSON (docs/lessons/build.md), or pick the lower-fidelity native form until then. `pbik validate` warns on any
  property outside the catalog.
- **Wireframe**: what `gen_wireframe_hf.py` draws for `pattern` (one renderer per pattern).
- **Audit**: what goes into design/specs/audit.json for the pattern's numbers.

## Rules shared by every pattern

- Every headline number has a comparison (a baseline: prior period, target, expected or peer), drawn next to it.
- Normal is drawn quietly (light tokens: `border`, `slateLight`, `neutralTint`); exceptions take the accent colour.
- Partial or stale data is marked where the number is, not only in a footnote.
- Colour is never the only signal: pair it with a label, a symbol or position (CLAUDE.md "Accessibility").
- Measures a pattern adds as report extension measures are self-contained: one extension measure never references
  another (docs/lessons/dax.md; the visuals failed in Desktop). Repeat shared logic in VARs, or ask for the
  measures in the model.
- Aggregates only (docs/it-security.md): no pattern needs row-level data; Deneb datasets are the visual's own
  aggregated query, like any other visual.
