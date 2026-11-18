# Network and org chart

**Question:** Who belongs where, and how do the same people group another way?

**Use when** the data has parent pointers (a person and their manager, a part and its assembly) and the reader should
see the tidy hierarchy, then the same people regrouped by a field (team, location), with search.
**Avoid when** the hierarchy is very deep or wide (more than about 500 shown nodes: use a decomposition tree or a
matrix), or the links aren't a tree (many-to-many networks need a force graph without the tree view).

## Design

- **Tree**: cards (name, group, how many below) in a tidy top-down layout (d3-flextree on d3-hierarchy), elbow links,
  a +n button to open a branch. Text is never smaller than 11 px on screen (the meta line at the tree's smallest
  scale): the tree fits the visual down to that scale and no further; the first look opens as many levels (three at
  most) as fit at it, and a wider tree pans (centred on the branch just opened) instead of shrinking. Found in
  Desktop 2026-11-17: shrinking to fit put names at 6 px.
- Tree layout (Format pane > Tree): Compact uses d3-flextree (WTFPL), Standard uses d3-hierarchy's tree (ISC); same
  card sizes. The handoff pack names both, for legal teams that don't accept WTFPL.
- **Clusters by Group A / Group B**: the cards blend into their group colour and shrink into circles that cluster per
  group with physics; group names above each cluster. Pills switch Tree / By A / By B.
- **Find a person**: matches stay strong, the rest dims; Enter opens the branch above the first match, flies the
  camera to it, selects it and the headline says who they report to.
- Card text shows at rest only: hidden while the cards move, back when they land (re-drawing 120 fading labels every
  frame was the stutter: 9-30% frozen frames, now 0-1%).
- Zoom and pan (wheel, drag); click to filter the page (Clicks: Filter, the default), Ctrl to add; keyboard: Up the manager, Down the first report,
  Left / Right colleagues, Space opens or closes, "/" goes to search.
- Ties are named together in the headline ("Engineering, Product and Sales are the largest (15 each)").

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| native | decomposition tree; a matrix with a parent-child hierarchy (PATH functions) | exploring a measure down a hierarchy |
| Deneb | Vega's tree transform (static) | a static tree |
| **kit custom visual** | the tree that morphs into clusters, search, expand, zoom | app-like org charts (normal pick) |

Code: the `org-chart` proof visual (scratch project). Roles: Item, Parent (the parent's Item), Label, Group A,
Group B. Cluster layouts are settled once per view and size and reused (a re-render must not re-run the physics from
its last result). Flow and layered layouts (elkjs) aren't in the kit: a possible later add once its EPL-2.0 licence
is approved (docs/design/app-visuals.md).

## Checks

Harness: expand, `tree-to-clusters` and `team-to-location` strips, find-and-fly, a filter coming in, keyboard,
bookmark and reopen, high contrast, phone size, the resize regression, the Standard tree layout; `minTextPx: 11` and
`noOverlap` on the tree; `_perf` measures frozen frames in each morph.
