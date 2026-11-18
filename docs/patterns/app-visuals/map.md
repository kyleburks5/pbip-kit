# Map (choropleth, dots, bubbles)

**Question:** Where are things, and which places stand out?

**Use when** the places are US states (or another bundled shape set) and the reader should see where values sit, open
one place, and filter the page by clicking it, with no map service.
**Avoid when** the places are addresses or points needing a basemap (Azure Maps, which needs network access and IT
approval), or there are only a few places (a bar chart reads better).

## Design

- **Map**: states shaded from the panel colour to the accent by the Colour measure (else the Value); states with no
  data stay quiet.
- **Dots**: one dot per Group member (a site) packed around its state's centre with physics, in the text colour with
  a background edge so they read on any shade.
- **Bubbles**: each state's outline morphs into a circle sized by its Value (flubber `toCircle`), pushed apart with
  physics (a Dorling-style cartogram); the morph runs through the kit's motion engine (reduce motion: it jumps).
- The headline and the Back / breadcrumb / pills row are the visual's header band: the map draws below the header as
  measured (`chromeBottom`) and is clipped there (`Layers.clipTop`), so a zoomed state never slides under the text
  (found in Desktop 2026-11-17: "Texas: ... of all" sat on the zoomed map and the pills).
- Click a state: the page filters to it and the camera zooms into its box; a breadcrumb ("All / Texas") and
  double-click zoom back out. Arrow keys walk the states west to east; Enter selects.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| native | filled map / shape map (Azure Maps and Bing need network; the shape map takes a TopoJSON) | a static shaded map is enough |
| Deneb | a choropleth from a bundled TopoJSON in the spec | static, no morph |
| **kit custom visual** | map, dots and bubbles with the morph, zoom and click to filter | the app-like map (normal pick) |

Code: the `state-map` proof visual (scratch project): `us-atlas/states-albers-10m.json` (pre-projected, ISC, Census
data) read with `topojson-client` (ISC), drawn with `d3-geo` `geoPath()`; flubber (MIT) for the morph; `settle()` for
the cartogram. The map adds about 60 KB to the package (165 KB in all). Other shape sets (world-atlas countries,
us-atlas counties) work the same way; bundle only the one a visual uses.

## Checks

Harness: `map-to-bubbles` and `bubbles-to-dots` frame strips, a state click (`clickSelector`
`path.kit-state[aria-label^='Texas']`) with the zoom frames, a filter coming in, keyboard, high contrast, no data,
the resize regression; `noOverlap` and `minTextPx: 11` on the overview and the zoomed state.
