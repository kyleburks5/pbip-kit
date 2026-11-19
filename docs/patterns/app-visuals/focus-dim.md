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

## Docked readout (details beside, never over)

- Hovering or focusing an item shows its details in a readout docked at the visual's right edge (or a panel beside a
  native visual), not a pop-up over the marks: the data stays visible and the reader can compare. The readout lists
  the item, its count, its rate and what it is judged against ("Usual for Outpatient 61-86%", "+10 points vs
  benchmark"), with the small-sample note from [honest data](../honest-data.md).
- The drawing is framed in what the readout leaves (`Layers.insets`, `Interaction.fit`): nothing sits under it.
- **Idle standout**: while nothing is hovered or picked, the readout (and the headline) shows the standout: the item
  with the best score among those with enough rows (`standout()` in honest.ts; none qualify: none is shown). Native:
  a card bound to a "standout" text measure, and the matching item's colour by a `cf` measure. Example: a clinic
  floor's best room on time; the region with the largest gain this month.
- Native route: a card or table in a panel beside the chart, filtered by the chart's selection (Edit interactions:
  Filter), with its empty state showing the standout measure.

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
