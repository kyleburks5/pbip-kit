# Batch studies, Part D: three rebuilds against their originals (v1.12, 2026-11-19)

Each test rebuilt one of the maintainer's own reports with `/start` from a plain-words request, on a made-up model
(no data copied). Polish scores are `pbik score` from the files only (checks 1, 3 and 7 are the agent's own and left
unchecked on both sides, so originals and rebuilds compare like for like), run after the Part D fixes below. The test
projects aren't in the kit; three of them are in the separate examples repository.

| Test | Original | Rebuild | Score (original → rebuild) |
| --- | --- | --- | --- |
| 1 Electronic Sales | Rep 4 (two pages, header band, KPI tiles, trend, Top / Bottom 5 tables) | One app-like page in dark glass: rail of pickers, live headline, four KPI tiles with mini bars, focus-dim trend, breakdowns, exception list | 3/10 → 8/10 |
| 2 IT Service Tickets | Rep 9 (header band and four channel panels) | The same page as the panel style layout (`pbik layout panels`), plus a drill-through page from a Top 5 bar | 4/10 → 7/10 |
| 3 Shot breakdown | A web app (not a Power BI report: no score) | Dark-glass explorer page: rail of pickers, the court (kit spatial canvas: Dots, Zones, Ranked), side panel of cards, FG% by quarter, areas table | n/a → 8/10 |

## Better, worse and why

**Test 1.** Better: one page answers the brief (where revenue comes from, the trend against last year, what needs
attention) without page hops; every headline number has a comparison; text and states pass AA on the dark theme;
tab order follows reading order. Worse: Rep 4's inventory page has no counterpart (out of the brief); the made-up
model has no region or channel, so city and store type stand in (said in the plan). Rep 4's low score is mostly
its age: IDs from before pbik (82 check errors), smoothed lines, 9-10 pt axis text, 50 accessibility warnings.

**Test 2.** Same look as Rep 9 (compared side by side on the plan picture and in Desktop). Better: the change chips,
compact quarter labels without collisions, light histogram axes, the Top 5 label above each bar without the
duplicate selector-less colour Rep 9 carried (CH-02), AA everywhere (Rep 9:
16 accessibility warnings), a drill-through page. Still flagged: the page is dense by design (four panels of six
parts each: "crowded page" stays as an accepted property of the style).

**Test 3.** Better than a static court: areas coloured against the league's rate for that area on one diverging
scale shared with the table, small samples faded or hidden, made filled and missed hollow, the Dots ↔ Zones ↔
Ranked morph, a click on an area filters the page. Worse: no shot-by-shot animation like the web app; the court is a
private kit visual (IT review, not AppSource-certified).

## Patterns pbik chose on its own, and where it should have

| Test | Chosen on its own | Should have, didn't (fixed or noted) |
| --- | --- | --- |
| 1 | live-headline, kpi-mini-bars, focus-dim, direct-labels, exception-list, honest-data, the rail of pickers | the year picker moved into the rail kept its old tab place: now `tab_order` |
| 2 | panel-style-layout (house style for 2-6 members), threshold-histogram, label-above-bars, live-headline | none after the Rep 9 brief; the drill-through card comparisons came from `drill_card_comparisons` |
| 3 | rail-panel in dark glass (house style for an explorer page), spatial-canvas, honest-data, live-headline | one accent on the quarter chart needed the sort-by scope (`sort_by_scope`); the pills needed dark-theme colours (`pill_colours`) |

## Problems found and fixed in the kit (general)

- The made-up model: arrow format strings quoted for TMDL; the build says when a changed contract leaves the model
  as it was (a person approves contracts).
- Kit visuals: a column in a value well is summed, as Desktop binds it (the court showed "No data yet"); colours
  in capabilities typed as colours; the readout panel's padding inside its width; the benchmark named from its
  field ("the league").
- Polish: pill colours on dark themes, sort-by scope in planned measures, picker title room from the theme, tab
  order set to reading order.
- Score and validate: layouts from before pbik (pages a list) read in pbik's form; reading order treats a rail, a
  side panel and panel-style panels as columns under the top band; kit visuals need no saved sort; a diverging
  gradient counts as coloured by direction; text measures need no thousands separator; a sentence card isn't a
  KPI; a left-aligned value with its comparison line is the house style; a drill-through page takes its source
  page's year; a left rail counts as the page's frame.
- Panel style: the change chip is 11 pt; no selector-less colour beside the per-series colours. The share bar keeps
  Rep 9's 60 px (at 48 px Desktop drew its empty-chart icon, CH-03); the score lets two visuals without a
  background touch by 12 px or less of padding.
- Catalog: a table's text-colour gradient (fillRule) confirmed in Desktop.
