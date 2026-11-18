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
