# App-visual patterns

Moves that make a page feel like an app (docs/design/app-visuals.md), and the page polish around them. Each page is a
library entry: the question, **Use when** / **Avoid when** (/plan quotes them), the route pbik picks (the first that
delivers it: native, native + formatting, SVG measure, HTML, Deneb, kit custom visual), the reusable code, and how
the harness or the numbers audit checks it. Not rules: the rules stay in CLAUDE.md and .claude/rules.

The code modules live in the app-visual template (`tools/appvisuals/template/src/kit/patterns/`), so every kit custom
visual made with `pbik visual new` has them; `pbik visual refresh` brings an older visual up to date.

## Moves inside a visual

| Pattern (`pattern`) | Question it answers | Lowest route that does it all | Module |
| --- | --- | --- | --- |
| [Morph between layouts](morph-layouts.md) (`morph-layouts`) | How do the same items look by group, by stage, by two numbers? | kit custom visual | `layouts.ts` + `motion.ts` |
| [Unit chart](unit-chart.md) (`unit-chart`) | How many, and which ones, one mark per record? | Deneb (static); kit custom visual (animated, drill) | `layouts.ts` (`pack`, `grid`, `columns`) |
| [Drill zoom](drill-zoom.md) (`drill-zoom`) | What is inside this group, without leaving the page? | kit custom visual (native: drill-down on a hierarchy) | `drill.ts` + `scene.ts` Screens |
| [View pills](view-pills.md) (`view-pills`) | Which view of the same data am I on? | kit custom visual (native: field parameter + button slicer) | `scene.ts` `pills()` |
| [Range select](range-select.md) (`range-select`) | What happens in the span I drag? | Deneb (`brushed-range`); kit custom visual | `range.ts`, `Interaction.enableBrush` |
| [Live headline](live-headline.md) (`live-headline`) | What does this view, or my selection, say in one sentence? | native (a DAX measure in a card); in a kit visual `headline.ts` | `headline.ts`; the Headline Share measure |
| [Focus and dim](focus-dim.md) (`focus-dim`) | Which items am I looking at, and how do they compare with the rest? | native (cross-highlight); kit visual `emphasis.ts` | `emphasis.ts` |
| [Map](map.md) (`map`) | Where are things, and which places stand out? | kit custom visual (native: filled / shape map) | the `state-map` visual: us-atlas + topojson-client + flubber |
| [Network and org chart](network-org.md) (`network-org`) | Who belongs where, and how do they group another way? | kit custom visual (native: decomposition tree) | the `org-chart` visual: d3-flextree + d3-force |
| [3D scene](3d-scene.md) (`3d-blocks`) | How big is each place, how is it doing, what is inside? | kit custom visual (Three.js) | the `site-blocks` visual |

## Page polish (no custom visual needed)

| Pattern (`pattern`) | Question it answers | Lowest route | Where |
| --- | --- | --- | --- |
| [KPI card with mini bars](kpi-mini-bars.md) (`kpi-mini-bars`) | Where does this period sit against the last twelve? | SVG measure in a new card | KPI Bars SVG |
| [Forecast bullet](forecast-bullet.md) (`forecast-bullet`) | Will we reach the target at this pace? | SVG measure | Forecast Bullet SVG |
| [Context strip](context-strip.md) (`context-strip`) | What is the page showing right now? | native (text measure in a card) | Context Strip |
| [Pills and badges](pills-and-badges.md) (`pill-tabs`, `filter-pills`, `sample-badge`) | Which view, which filter, and is this real data? | native (navigator, button slicer, button) | templates |

[How to describe a visual](describe-a-visual.md) turns plain words ("dots that regroup when I click a pill") into
these patterns and routes.

## Shared rules for this library

- The first frame is the final frame: the first draw and every resize show the end state at once. A page that isn't
  in front gets no animation frames, and an export captures what is drawn now (found in Desktop, 2026-11-17).
- The route is the first one that delivers both the look and the interaction; record `build.step`, `build.reason`
  and `build.nativeTried` (CLAUDE.md "Native first"). Every Deneb or kit custom visual names a native fallback.
- Clicks filter the page by default (Interaction > Clicks: Filter): a real filter through `sendPicks` (filter.ts), so
  cards, tables and every other visual follow; Cross-highlight is the option. Found in Desktop 2026-11-17: selections
  alone left cards and tables unchanged.
- Clicks stay smooth through Power BI's round trip (Desktop review 2026-11-17, second recording): the visual shows
  the click at once (highlight, dim, zoom, fly) and sends its filter only after the move lands (`Later`, scene.ts);
  saved views go 1.5 s after a move (StateStore). Power BI re-draws the rest of the page when either arrives, on the
  same thread as the animation, so sending mid-move froze it for 300-400 ms.
- Updates are sorted before any work (`UpdateGate`, updates.ts): the visual's own filter or saved view coming back
  ("same") draws nothing again; new rows ("data") morph by key (stay = glide, leave = shrink or sink, new = grow or
  rise), physics carries on from where marks are (`resume`), layouts already settled are reused (`settle` keeps the
  last few), and the camera is never restarted. A canvas is only resized on a real resize (a resize wipes it).
- New rows from a slicer or another visual drop the visual's own click filter; a "Clear" chip in the header row
  clears it by hand. pbik build gives every kit visual a NoFilter interaction toward each slicer on its page, so a
  click never shrinks the slicer's pills; validate warns when one is missing.
- A group keeps one colour in every kit visual: its place in the sorted group names (`ColorScale.seed`).
- Measuring: the hidden frame meter (perf.ts; layout props `debug.meter@none` / `debug.selfTest@none`) lists each
  move's frozen share, longest frame and the updates Power BI sent, in a corner panel a Desktop screenshot carries;
  self-test plays the visual's own moves once its page is in front (make the page the opening page). Target: no frame
  over 100 ms after a click and under 5% frozen frames in any move. The harness simulates the round trip (`roundTrip`,
  400 ms) and checks it (`measure`, `smooth`).
- Match by key, never by position: a list, a panel row or a label finds its item by the item's key (a sorted or
  reversed list lights the wrong row otherwise). The harness checks it (`selectorText`).
- The header is a band: the drawing starts below the header as measured (`chromeBottom`) and is clipped there
  (`Layers.clipTop`); labels never overlap the header or each other (harness `noOverlap`); no text under 11 px on
  screen after zoom (`minTextPx`).
- Labels and text at rest: while things move, hide text that would be redrawn every frame (3D labels, card text) and
  show it when they land; the harness `measure` / `perf` steps report frozen frames (over 50 ms) per move.
- Motion always has an off switch (the visual's Reduce motion, and the system setting) and never carries meaning by
  itself: the end state says everything.
- Colours come from the theme or tokens (an SVG measure names the token in a comment); nothing is a fixed colour.
- Numbers drawn in an image or written in a headline are part of the numbers audit (`svg` and text entries).
