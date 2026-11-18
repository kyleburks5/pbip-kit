# 3D scene (blocks, floors, fly-in)

**Question:** How big is each place, how is it doing, and what is inside it?

**Use when** the items have a physical sense of size and parts (sites and floors, warehouses and racks) and the 3D
form adds meaning: footprint by size, height by parts, colour by status, and flying into one to see its parts.
**Avoid when** exact comparison matters more than the overview (a bar chart is more accurate than 3D heights), the
report will be exported to PDF or PowerPoint (private visuals don't export; see the design note), or the readers'
machines are very weak (software WebGL, no GPU: about 30 frames a second while flying, 50-60 orbiting).

## Design

- Blocks on a ground plane with soft shadows (one directional light, PCF soft shadow map, lights tinted by the theme);
  footprint by Size, height by the number of Items (floors), colour from the theme's sentiment colours (negative,
  neutral, positive) by the Status measure. Labels are HTML placed over the scene.
- Orbit and zoom camera (Three's OrbitControls); hover picks a block or floor (raycaster) for the tooltip; the canvas
  draws only when something moves.
- Click a block: the page filters to it (a real filter on the site column, so cards and tables follow), the camera
  flies in on an arc (the kit's motion engine), the floors pull apart and take their own status colours, the other
  sites sink into flat light outlines on the ground, and a detail panel lists the floors, top floor first like the
  stack. Click a floor (in the scene or the panel): the page filters to that site and floor (a two-column filter:
  "Floor 2" alone is in every site). Back, the breadcrumb or Escape fly back out and clear the filter.
- New rows (a slicer, another visual): sites that leave sink into the ground, then new ones rise out of it; the
  camera stays where it is. Its own click filter going out and coming back redraws nothing; the filter is sent when
  the flight has landed, so Power BI's re-draw of the page never lands mid-flight.
- Hover: a site's tooltip shows the site's own fields only (site, size, status); a floor's shows site, floor, size,
  status. The panel row of the floor under the pointer lights up, matched by the floor's key, never by its position
  (the panel lists floors top first, the data bottom first: matching by position lit the mirror-image row).
- Smooth motion: all floors are one InstancedMesh (one draw call); nothing is see-through, ever (dimming mixes the
  colour toward the background; transparent blocks looked like grey fog and cost a sort every frame); while the
  camera moves there is no shadow pass, no labels and a lower pixel ratio, and all three come back at rest; the
  first frame of a move is drawn before it starts (no blank flash).
- Reduce motion: no flights, the camera jumps. High contrast: background-coloured blocks with foreground outlines.
  Keyboard: arrows cycle the blocks (the label lights up, the headline reads it out), Enter flies in. No WebGL: a flat
  SVG layout with the same clicks.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| native | bar chart, treemap, matrix | almost always: 3D is a choice, not a need |
| **kit custom visual** | the 3D scene with Three.js (MIT) | the 3D form is the point and the export rule is accepted |

deck.gl isn't used: it brings its own WebGL engine (luma.gl) aimed at geospatial layers, and Three covers blocks,
floors, picking and shadows. Code: the `site-blocks` proof visual (scratch project); Three is imported class by class
so only what is used is bundled: a 261 KB package. Frame rate in the harness (software WebGL, SwiftShader; before /
after the Desktop review of 2026-11-17): orbit 20 -> 47-61 a second; flying in 9 -> 19-30 a second with frozen frames
(over 50 ms) 32% -> 3-15%; flying out 8 -> 34 a second, 23% -> 0-1%. A GPU in Desktop is faster; one longer frame
can remain at the click (the filter's own update), so Desktop stays the final check.

## Checks

Harness (WebGL on): blocks, `fly-in` and `fly-out` frame strips, a floor click, hover, keyboard, a filter coming in,
reduce motion; every floor hovered in turn with its own panel row checked (`selectorText`), site tooltip fields
(`tooltipFields`), the site and the site-and-floor filters (`filterValues`), nothing see-through and no shadow pass
while moving (`state`); `nowebgl` runs with WebGL off (the fallback); `_perf` measures frames a second and frozen
frames in real time (`perf`, `measure`). `click3d`
and `hover3d` steps aim at a block by name (the visual reports where it is on screen).
