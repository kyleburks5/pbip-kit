# Drill zoom

**Question:** What is inside this group, without leaving the page?

**Use when** a group (a region, a team, a stage) is worth opening in place: its items re-pack to fill the visual, a
breadcrumb says where you are, Back returns. Also the camera zoom: fly in on one item and back out.
**Avoid when** the detail needs a different layout or other fields (use a drill-through page), or the hierarchy has
more than three levels (a breadcrumb gets long; use a tree or a matrix).

## Design

- The group label (or card, or bar) is a button: underlined, reachable with Tab, Enter opens it.
- Opening it is a screen: the breadcrumb ("All / North") and Back appear in the top bar; the headline switches to
  "North: 79 items, 33% of all 240."
- Items move to their new places (the same morph as [morph-layouts](morph-layouts.md)); the camera zoom is a separate
  move (double-click an item, double-click empty space to come back), flying through the Motion engine.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| native | drill-down / expand on a hierarchy (matrix, bar chart) with the drill buttons | the native drill is enough |
| Deneb | not really: no screen stack | - |
| **kit custom visual** | screens with a back stack and breadcrumb; camera zoom | the drill should feel like an app |

Code: `src/kit/patterns/drill.ts` (`Drill` on top of `scene.ts` `Screens`; `flyTo`, `frameMark`), used in the starter
(`drawLabels()` opens a group; the `dblclick` handler flies the camera). For real hierarchies (a Category > Product
column hierarchy), read a matrix data view with `data.ts` `hierarchy()`, which gives each node a selection id, and use
`selectionManager.toggleExpandCollapse` to load the next level.

## Screens in HTML (cards, panels, lists)

A drill drawn in HTML (a card that opens a detail screen, like the region panel) goes through `Morpher.run(layer,
render, {screen: true})`: tag the shared parts with `data-share` (the card and the detail chart; each stage's mini
column and its detail bar) and they morph by key while the rest cross-fades. `Morpher.run(layer, render)` without
`screen` is the in-place form for new data. Never empty a screen and replay a staggered entrance: that was a 0.3 s
blank and a 1 s fade on every click (Desktop review 2026-11-18).

## Checks

Harness: `clickText` on a group label, a `frames` step (the re-pack), `text` "North:" in the headline, then
`clickText` "Back". Desktop: Back and the breadcrumb with the keyboard only.
