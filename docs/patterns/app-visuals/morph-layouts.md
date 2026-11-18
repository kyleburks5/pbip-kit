# Morph between layouts

**Question:** How do the same items look by group, by stage, or by two numbers?

**Use when** one set of records has several honest arrangements (a grid by two categories, columns by stage, a scatter
by two measures, clusters by group) and seeing the same items move between them is the point: the reader follows a
record from one view to the next.
**Avoid when** the views show different things (use pages or bookmarks), the reader needs exact values more than
movement (a table or bar chart), or there are more than about 30,000 records.

## Design

- One mark per record keeps its colour (its group) in every layout; only position and size change.
- The move: every mark travels from where it is to its new place, with the pane's duration, easing and a small
  per-item stagger (capped so the whole move stays under about one second); marks that leave shrink out, new ones
  grow in.
- Labels for the layout (group rows, stage columns, axis ticks) swap at the start of the move; pills say which layout
  is on.
- Reduce motion: the marks jump to the end state; nothing else changes.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| native | separate visuals per layout with bookmarks | no animation is needed |
| Deneb | each layout, switched by a parameter; Vega's transitions are limited | static views are enough |
| **kit custom visual** | the animated morph | the move itself is the story (normal pick) |

Code: `src/kit/patterns/layouts.ts` (`grid`, `columns`, `scatter`, `clusters`, `orderOf`, `pack`) gives each layout
the same keys; `src/kit/motion.ts` (`Motion.to`) moves them on any drawing layer; the starter visual
(`src/visual.ts`, `place()` and `render()`) shows the whole loop. A new layout is one function returning
`{pos, cells}` for the same units.

## Shape morph (flubber)

Positions aren't the only thing that can move: a shape can turn into another (a state outline into a circle, a bar
into a dot, one region's outline into another's). flubber (MIT, `interpolate`, `toCircle`, `fromCircle`, `toRect`)
returns path strings for t from 0 to 1; drive t with the kit's `Motion.tween`, so easing, duration and reduce motion
apply. The map pattern (map.md) uses it for Map <-> Bubbles. Keep `maxSegmentLength` around 6-10 px: smaller is
smoother but slower.

## layout.json

```json
{"id": "P1-V04", "page": "P1", "x": 32, "y": 120, "w": 1200, "h": 640, "type": "custom", "custom": "P1-V04_deal-dots",
 "pattern": "morph-layouts",
 "bindings": {"Item": ["Deals[Deal ID]"], "Group": ["Deals[Region]"], "Stage": ["Deals[Stage]"],
              "X": ["[Days Open]"], "Y": ["[Deal Value]"]},
 "fallback": {"type": "scatterChart", "bindings": {"Details": ["Deals[Deal ID]"], "X": ["[Days Open]"], "Y": ["[Deal Value]"]},
              "build": {"method": "native", "step": 1, "reason": "the same deals as a native scatter, no morph"},
              "container": {"title": "Deals by value and days open"}},
 "container": {"title": "Every open deal", "altText": "One dot per open deal, by region and stage"},
 "build": {"method": "custom-visual", "step": 4, "nativeTried": "scatter chart with bookmarks per view",
           "reason": "the move between views is the point"}}
```

`pbik visual add` writes this entry (with a table as the fallback, to swap for the native visual you tried).

## Checks

Harness: a `frames` step after each pill (mid-move frames and a strip), `marks` equal to the row count, and a
reduce-motion run whose frames are identical.
