# How to describe a visual

You can ask for any visual in plain words. You don't need the names below: say what you want to see and do, and the
kit picks the pattern and the route. These words help when you want to be exact.

## 1. Say what one mark is

| You say | The kit hears |
| --- | --- |
| "one dot per deal", "every person as a square" | a unit chart: one mark per row (Item = the deal's ID) |
| "a bar per region", "a line over the months" | an aggregated chart (native first) |
| "cards for each team", "a panel with the details" | a free-form layout: cards and panels inside one visual |

## 2. Say how it is arranged, and what changes it

| You say | Pattern |
| --- | --- |
| "grouped by region and stage", "in columns by stage", "plotted by value and age" | layouts: grid, columns, scatter ([morph-layouts](morph-layouts.md)) |
| "they regroup when I click a pill", "switch between views" | [view-pills](view-pills.md) + [morph-layouts](morph-layouts.md) |
| "clusters that pull together", "bubbles that settle" | clusters with physics (`layouts.ts` `clusters`) |
| "click a group to open it, with a back button" | [drill-zoom](drill-zoom.md) |
| "zoom into one item", "fly in" | camera zoom (drill-zoom) |
| "drag across the timeline to pick a period" | [range-select](range-select.md) |
| "a sentence at the top that says what I'm looking at" | [live-headline](live-headline.md) |
| "the rest fades when I pick some" | [focus-dim](focus-dim.md) |

## Asking for the general patterns

| You say | Pattern | What you get |
| --- | --- | --- |
| "use my panel style layout, one panel per channel" (or per line of business, care setting, region) | [panel style layout](../panel-style-layout.md) | a dark header band and one full-height panel per member: share bar, big number with a change chip, quarterly mini columns, a histogram against the threshold, top 5 bars (`pbik layout panels`) |
| "how long it takes, against the SLA", "bars inside the limit in colour" | [threshold histogram](../threshold-histogram.md) | bars within the threshold coloured, beyond it grey, a dashed "avg" line |
| "names above the bars", "top 5 with room for the names" | [label-above bars](../label-above-bars.md) | slim full-width bars, the name above, the value at the end |

| You say | Pattern | What you get |
| --- | --- | --- |
| "show it on a picture of the court / body / clinic floor / route", "where on the floor plan", "which part of the body" | [spatial canvas](../spatial-canvas.md) | the space drawn by the kit (generic shapes, no logos), points on it, areas coloured, ranked row |
| "click an area to filter the page", "pick a room and the rest follows" | clickable areas (spatial canvas, [map](map.md)) | a real page filter on the area's field |
| "use our own areas" (a GeoJSON, a list of rooms with sizes, depot locations) | spatial canvas, custom shapes | your shapes, with the same click and colour rules |
| "a route", "the patient's path through the steps", "a delivery round" | spatial canvas, track | a track from the data's own coordinates, its stages as areas |
| "then line the areas up best to worst", "turn the map into a ranking" | map / spatial canvas ranked row | the shapes slide out of the map into a row and back |
| "hide anything under 11 people", "don't show small groups" | [honest data](../honest-data.md), privacy mode | values under the threshold are not shown anywhere ("fewer than 11") |
| "fade the ones with too little data" | honest data, fade | thin samples fade toward grey with "limited sample" |
| "judge each kind against its own normal", "colour against the benchmark" | honest data, own range | colour = above or below what is usual for that group |
| "not just colour", "show done vs not done" | honest data, shape | filled vs hollow, solid vs dashed, a symbol |
| "which two differ most?", "say how A and B differ" | live headline, [biggest gap](live-headline.md) | "A is 2.3× B on X." |
| "details on the side, not pop-ups" | [focus-dim](focus-dim.md), docked readout | a panel beside the drawing that follows your pointer |
| "show the best one when I'm not pointing at anything" | focus-dim, idle standout | the standout item in the readout and the headline |
| "one picker for the metric and tables for every breakdown" | [breakdown wall](../breakdown-wall.md) | a metric picker driving a wall of tables, formats that follow the metric |
| "small chart of this year against last year in each KPI card" | [KPI tile](kpi-mini-bars.md) (native route) | card + small two-series column chart on one panel |
| "a list of the late ones, and say when there are none" | [exception list](../exception-list.md) | threshold in the title, a plain sentence when empty |

## 3. Say how it should feel

- Speed: "quick", "slow and smooth", "no animation" (Motion: duration, easing, Animate off).
- Look: colours ("our teal", "the brand colours"), corner radius ("rounded"), "a soft shadow", font size.
- Amount: "up to 5,000 deals", "only the top 50".

## 4. Say what it should do to the rest of the page

"Clicking a dot filters the table", "the cards follow the region slicer", "nothing else changes". Cross-filtering in
both directions is on by default for kit visuals and Deneb charts.

## 5. Say where it must work

"It must print to PDF", "it goes to the work tenant", "people use it with a screen reader". This decides the route:
some tenants block custom visuals (the kit then builds the native fallback), some exports don't draw them, and every
kit visual is keyboard and high-contrast ready.

## Examples

- "One dot per open deal, grouped by region and stage, with pills for columns and a scatter of value against days
  open. Clicking dots filters the deal table. A sentence on top says which region holds the most."
  → unit chart + morph-layouts + view-pills + live-headline, kit custom visual, table fallback.
- "Three KPI cards for this month with a small bar chart of the last year under each, current month highlighted."
  → kpi-mini-bars, SVG measure in native cards.
- "A progress bar for the year with the projected rest hatched and a target line."
  → forecast-bullet, SVG measure.
- "A panel of cards per team; click one to see its people as dots, with Back."
  → free-form cards (`scene.ts` `card`) + drill-zoom + unit chart, kit custom visual.

If something can't be built the way you describe it, the plan says so and offers the nearest thing, before anything
is built.
