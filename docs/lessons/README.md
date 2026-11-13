# Lessons: format, placement and upkeep

A lesson is something a rep learned the hard way (a Desktop quirk, a DAX trap, a build step that failed). The kit keeps
lessons few and short, and turns them into checks wherever it can. `python tools/lessons.py check` (run by the tests)
enforces everything below.

## The lessons

<!-- lessons:all -->
| ID | Lesson | File | Enforced |
| --- | --- | --- | --- |
| B-01 | Build through the kit, never by hand | [build.md](build.md) | – |
| B-02 | Every build gives the same result twice | [build.md](build.md) | yes |
| B-03 | Build the first repeated unit first | [build.md](build.md) | – |
| B-04 | Copy a setting Desktop saved instead of guessing | [build.md](build.md) | yes |
| B-05 | A template's reference lines are dropped, so give the visual its own | [build.md](build.md) | yes |
| B-06 | Measure-driven text is an expression, not a literal | [build.md](build.md) | – |
| B-07 | Rename fields per visual with displayName | [build.md](build.md) | yes |
| B-08 | Field parameters bind every underlying field | [build.md](build.md) | yes |
| B-09 | Every Deneb visual names a fallback | [build.md](build.md) | yes |
| B-10 | Record the build method of every visual | [build.md](build.md) | yes |
| B-11 | Filter on a measure only at visual level | [build.md](build.md) | yes |
| B-12 | HTML Content visuals use legacy rendering and room to draw | [build.md](build.md) | yes |
| B-13 | Roundtrip after every hand polish, then update layout.json | [build.md](build.md) | – |
| C-01 | Shapes need their fill set explicitly | [cards.md](cards.md) | – |
| C-02 | A text card on a coloured background turns every layer off | [cards.md](cards.md) | – |
| C-03 | Rounded new cards need tileShape rectangleRoundedByPixel | [cards.md](cards.md) | yes |
| C-04 | A reference label without detail needs its detail hidden | [cards.md](cards.md) | – |
| C-05 | Reference-label settings go on the label's own entry | [cards.md](cards.md) | yes |
| C-06 | Reference labels in the sentence style | [cards.md](cards.md) | – |
| C-07 | Card padding may be ignored: move content with the callout area | [cards.md](cards.md) | – |
| C-08 | Small multiples grid settings | [cards.md](cards.md) | – |
| C-09 | Colour small multiples through the header, not the accent bar | [cards.md](cards.md) | – |
| C-10 | The KPI card is its own container | [cards.md](cards.md) | yes |
| C-11 | Background shapes keep their layer order | [cards.md](cards.md) | yes |
| S-01 | Short button slicers need Custom padding | [slicers.md](slicers.md) | yes |
| S-02 | Button slicers need a grid sized for their items | [slicers.md](slicers.md) | yes |
| S-03 | Dropdown slicers with a header need 76px | [slicers.md](slicers.md) | yes |
| S-04 | Page navigator states come from the `navigator` key | [slicers.md](slicers.md) | yes |
| CH-01 | Category labels above bars use a zero spacer series | [charts.md](charts.md) | – |
| CH-02 | Colour each series by its metadata selector | [charts.md](charts.md) | yes |
| CH-03 | An empty-chart icon means too little room | [charts.md](charts.md) | – |
| CH-04 | Column and bar charts get a Y-axis max measure | [charts.md](charts.md) | – |
| CH-05 | Money values get explicit display units | [charts.md](charts.md) | – |
| CH-06 | Space labels-above-bars with innerPadding | [charts.md](charts.md) | – |
| CH-07 | Heatmaps keep one dark text colour | [charts.md](charts.md) | yes |
| CH-08 | No word wrap in table cells | [charts.md](charts.md) | yes |
| CH-09 | Size table columns to fit | [charts.md](charts.md) | yes |
| D-01 | Test new DAX query-scoped first | [dax.md](dax.md) | – |
| D-02 | Redefine every measure in the chain | [dax.md](dax.md) | – |
| D-03 | Guard comparisons with ISBLANK | [dax.md](dax.md) | – |
| D-04 | Test ranked measures in a sparse state | [dax.md](dax.md) | yes |
| D-05 | A sort-by column never references the column it sorts | [dax.md](dax.md) | – |
| D-06 | Save Desktop-made measures before building | [dax.md](dax.md) | yes |
| D-07 | A new audit check must fail on the old definition | [dax.md](dax.md) | – |
| D-08 | Extension measures reference model measures only | [dax.md](dax.md) | yes |
| D-09 | Conditional counts return 0, not blank | [dax.md](dax.md) | – |
| A-01 | Every data visual and image has alt text | [accessibility.md](accessibility.md) | yes |
| A-02 | Text meets WCAG 2.1 AA contrast in every state | [accessibility.md](accessibility.md) | yes |
| A-03 | No text below 10pt | [accessibility.md](accessibility.md) | yes |
| A-04 | Tab order follows reading order | [accessibility.md](accessibility.md) | yes |
| A-05 | Colours come from /theme and are used in their role | [accessibility.md](accessibility.md) | yes |
| AM-01 | Pick the audit mode from the profile | [audit-modes.md](audit-modes.md) | – |
| AM-02 | Always record the timings | [audit-modes.md](audit-modes.md) | – |
| AM-03 | What every mode keeps | [audit-modes.md](audit-modes.md) | yes |
<!-- /lessons:all -->

Rules files in .claude/rules/ (pbik, svg, connect-pbid) hold the Desktop and tool facts; design/known-gaps.md every gap
with its Desktop click steps. Helpers named `pbik_helpers.<name>` are in design/scripts/pbik_helpers.py.

## Format

Each lesson is a `## <ID> <name>` section with four one-line fields (a field may wrap onto indented lines):

```
## S-01 Short button slicers need Custom padding
- **Rule:** what to do, in one or two sentences.
- **Why:** what went wrong without it ("not recorded" when nobody wrote it down).
- **Enforced by:** the check, test, token or template that enforces it, or "not enforced (<when it is read>)".
- **Source:** the rep, smoke or check it came from (Rep 9; /smoke 2026-10-18; kit v1.2).
```

IDs are the file's prefix and a number (B build, C cards, S slicers, CH charts, D dax, A accessibility, AM audit-modes)
and are never reused. Each file starts with an `## Index` (`python tools/lessons.py index` writes it and the table
above); tables and worked examples go under `## Reference` at the end.

## Placement order

Put each new lesson in the first place that fits:

1. **A check**: a `pbik validate` rule (tools/pbik/pbikit/) or a test, if a script can tell right from wrong. A check
   runs every time; a rule only works if it is read.
2. **A template or token**, if it is about how a visual looks: a harvested template in design/templates/, a theme
   default from design/tokens.json (gen_theme.py), or a pbik default.
3. **The command file** (.claude/commands/<step>.md), if it applies to one step only (/model, /plan, /build, ...).
4. **docs/lessons/<topic>.md**, if it is background. Rules files count here for the topics they hold.
5. **CLAUDE.md**, only if it applies to every session. **One in, one out.**

A lesson placed at 1 or 2 still gets a lesson entry, shrunk to a pointer: the rule in one line, the reason, and the check
in **Enforced by**. Before adding a lesson, look for one that covers it (`python tools/lessons.py find <words>`) and
update that one instead.

## Budgets

| File | Budget (lines) |
| --- | --- |
| CLAUDE.md | 150 |
| each docs/lessons/<topic>.md | 120 |
| each pattern entry (docs/patterns/<name>.md) | 80 |

At the budget the tests warn; more than 25% over, they fail. Two lessons with the same rule fail too. `python
tools/lessons.py status` shows where each file stands.

## Proposing a lesson

Every lesson proposed (by /fix or /wrapup) says:

| Lesson | Rep | New or updates (ID) | Where it goes (1-5 above) | Why not higher |
| --- | --- | --- | --- | --- |

"Why not higher" is one line, for example "needs Desktop to see it, no file check can tell".

**PROJECT-ONLY**: a lesson that only holds for one report (its data, its client, its model) is marked PROJECT-ONLY and
stays in that project's own notes. It never goes into the kit (the master): `tools/lessons.py check` fails on one here.

## Contradictions and retiring

- A new lesson that says the opposite of an existing one is a contradiction: show both with their sources and let me
  decide; never overwrite one silently. `python tools/lessons.py similar` lists lessons that share most of their words.
- When a check or template now enforces a rule in CLAUDE.md or a command file, propose retiring the rule there (name
  the check) and keep the lesson as a pointer.
- Nothing is deleted: a retired lesson moves to docs/lessons/_retired.md with the date and why; an unused file moves
  to _archive/.

## Upkeep: /wrapup and /tidy

- **/wrapup** (Copilot /kit-wrapup) after each rep's last /fix: places the rep's lessons, updates existing ones instead
  of adding duplicates, flags contradictions, shows the diff, and ends with `python tools/lessons.py status`, which
  suggests /tidy when a budget is near (within 10%) or 3+ reports were wrapped up since the last tidy.
- **/tidy** (Copilot /kit-tidy) every few reps: merges duplicates, retires enforced lessons, shows contradictions,
  flags stale lessons and unused files (never removes them), condenses old changelog rows. Tags `pre-tidy-<date>`
  first, asks item by item, runs every test after.
