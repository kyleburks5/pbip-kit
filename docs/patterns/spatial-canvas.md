# Spatial canvas

`pattern: "spatial-canvas"`

**Question it answers:** where in a space do things happen, and which areas run hot or cold?

- **Use when:** each row has a place in one known space (a court or pitch, a body outline, a floor plan, a route or
  care pathway, service areas), and the reader asks "where" as much as "how much". Clicking an area filters the page.
- **Avoid when:** the places are addresses or regions on a real map (the [map](app-visuals/map.md) pattern), or there
  are fewer than about 5 areas (a bar chart reads better).

## Examples
- Health insurance: claim lines on a body outline by region, approval rate per region judged against its claim
  type's usual range; a clinic floor plan with visits seen on time per room against a 75% benchmark.
- Care pathway: referral, triage, diagnosis, treatment, follow-up as a track drawn from the data's own coordinates.
- Sport: shots on a generic half court, made (filled) or missed (hollow), hot and cold areas by shot type.
- Operations: service areas split by nearest depot; a warehouse floor with picks per aisle.

## Design
- **One geometry, three jobs.** The space is defined once (`kit/patterns/spatial.ts`): from rules (court areas by
  distance and angle, service areas by nearest centre), from shapes (rooms, body regions, a pasted GeoJSON) or from the
  data's own coordinates (a track). The same definition draws the picture, places each point and decides its area.
  The model's Zone column must come from the same rule; the visual counts disagreements and shows a banner.
- Background lines in the text colour at 45%; areas tinted by [honest data](honest-data.md) (own range, small samples,
  shape as well as colour); points quiet under the areas, full strength in the Points view.
- Views (pills): Points, Zones, Ranked (the areas slide out of the space into a ranked row, best first; any map can do
  this). Click an area: the page filters to it; Ctrl-click a second: the headline states the [biggest gap](app-visuals/live-headline.md).
- Details sit in a [docked readout](app-visuals/focus-dim.md) beside the space, never over it; idle, it shows the standout.

## Build (visual-method ladder)
| Step | How | Draws | Pick it when |
| --- | --- | --- | --- |
| 1 native | Scatter chart (transparent, axes fixed to the space's range, axes hidden) over an image of the space drawn by `design/scripts/space_svg.py`; areas as a table or bar | points on the space, no clickable areas | points only, or an exported page |
| 1 native | Shape map (preview) with the areas as TopoJSON | clickable areas, no points | areas only; check the shape map is allowed |
| 3 Deneb | `geoshape` areas + `point` layer from the same coordinates, simple-mode cross-filter | both, static | no kit visuals allowed (routes) |
| 4 kit custom visual (pick for the app-like page) | `pbik visual new <name> --from spatial-canvas` | areas that filter the page, views, ranked morph, readout, honest rules | the normal pick |

The kit visual's fallback is the step 1 scatter-on-image (layout `fallback`), used on exported pages.

## Measures and model
- The Zone column: computed in Power Query or the data load from the same rule (court: `space_svg.court_zone`).
  Never a second, hand-made rule: the harness and the visual both check agreement (`mismatch` 0).
- Visual fields: Item (one row per point), X, Y, Zone, Group (judged against its own range), Outcome (1 or 0),
  Benchmark (optional rate), Order (tracks).
- Native areas table: `Rate = DIVIDE ( [Made], [Attempts] )`, blanked below the small-sample threshold (honest-data).

## layout.json example
```json
{"id": "P1-V05", "name": "shot-map", "page": "P1", "type": "custom", "custom": "shot-map", "pattern": "spatial-canvas",
 "x": 32, "y": 152, "w": 1200, "h": 896,
 "bindings": {"Item": "Shots[Shot ID]", "Zone": "Shots[Zone]", "Group": "Shots[Shot Type]", "X": "Shots[X]",
              "Y": "Shots[Y]", "Outcome": "Shots[Made]"},
 "props": {"space.shape@none": "court", "space.start@none": "zones"},
 "fallback": {"type": "scatterChart", "bindings": {"X": "Shots[X]", "Y": "Shots[Y]", "Category": "Shots[Shot ID]"}},
 "build": {"method": "custom-visual", "step": 4, "nativeTried": "scatter over a court image: no clickable areas",
           "reason": "areas that filter the page and a ranked morph"}}
```

## Checks
Harness (starter scenarios): areas on the court, a body map and a clinic floor (made-up rows), filter on click,
Ctrl-click gap headline, ranked morph with no blank frame and no overlapping labels, loading placeholder, privacy
mode, high contrast, a real-time click (no frame over 100 ms) and the quality step-down on a slow CPU. Audit: one
area's count and rate against a DAX recompute; a suppressed area shows no number anywhere (label, readout, headline).
