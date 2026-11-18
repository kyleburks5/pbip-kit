# Focus and dim

**Question:** Which items am I looking at, and how do they sit among the rest?

**Use when** a selection (here or in another visual) should stand out while the rest stays visible for comparison.
**Avoid when** the rest is noise the reader never needs (filter instead of highlighting).

## Design

- Selected or highlighted items keep full colour and get a foreground outline; the rest drop to the pane's Dimmed
  opacity (default 25%). Nothing moves.
- One rule everywhere: a selection in this visual wins; otherwise a highlight from another visual (cross-filter
  coming in as a highlight) decides; with neither, everything is full strength.
- High contrast: no transparency. Unselected items are hollow with a foreground stroke; selected ones are filled with
  the host's selected colour as the stroke.
- Colour is never the only signal: the headline says how many are selected.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| **native** | cross-highlight between native visuals (Edit interactions: Highlight) | native visuals (normal) |
| Deneb | opacity from `__selected__` (simple-mode cross-filter, `deneb.interactivity.crossFilter`) | Deneb charts |
| kit custom visual | `emphasis.ts` `emphasis(theme, base, selected, anySelected, highlightedOff)` | app visuals |

Kit visuals declare `supportsHighlight` so other visuals' highlights arrive as `highlights` on the values; `data.ts`
sets `highlighted` per record.

## Checks

Harness: the `highlight` step (cross-filter in), a `clickMark` (out), and the high-contrast scenario's screenshots.
