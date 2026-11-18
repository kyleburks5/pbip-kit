# View pills

**Question:** Which view of the same data am I on, and what else is there?

**Use when** two to five views of the same items sit in one visual (Grid / Columns / Scatter / Clusters), and the
switch should be one click with the change happening in place.
**Avoid when** the views are pages of their own (page navigator with pill styling, [pills-and-badges](pills-and-badges.md)),
or there are more than five (a dropdown reads better).

## Design

- A pill group inside the visual's top bar: the current pill filled with the accent, the others quiet; an icon from
  the kit's icon set and a short label (localised strings).
- It is a tab list: arrow keys move between pills, the current one is the tab stop; the live region says "scatter
  view".
- Switching resets the camera and runs the morph; the headline follows.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| native | a field parameter in a button slicer (pill-shaped buttons) switching a native visual's field | the views are one visual's field swaps |
| native + bookmarks | a bookmark navigator over visuals stacked in place | different native visuals |
| **kit custom visual** | pills inside the visual, animated switch | the views are the same items moving |

Code: `src/kit/scene.ts` `pills(parent, options, current, onPick, label)`; the starter's `drawChrome()` and
`setView()`. Settings: Views > View pills (on / off), Start view.

## Checks

Harness: `pill` steps by name; `text` checks that the headline still reads right after each switch.
