# <Project name>: requirements

Copy this file to `brd.md` and fill it in. `/model` and `/plan` read `brd.md`. Delete the guidance in italics as you go. Anything marked "confirm" is checked against the real data before it is built.

## 1. Purpose and audience
*Who reads this, in what setting, and what decisions does it support? Keep it to a short paragraph and a list of decisions.*

## 2. Data source
*Where the data comes from, who owns it, its classification (public, synthetic, internal, restricted), and a table of the tables and what each holds.*

| Table | What it holds | Size |
| --- | --- | --- |
| <name> | <description> | <rows> |

*Data volume: total rows and file size per source, and expected growth. /model measures it and recommends an audit mode (CLAUDE.md "Audit modes").*

*Known quirks to confirm: numbers stored as text, missing date table, missing relationships, no revenue or profit column, and so on.*

## 3. Business questions
*Questions a reader should be able to answer in seconds. Three to six is enough.*

1. <question>

## 4. Measures (definitions)
*One row per measure, in plain words, including what "prior" or "same period last year" means.*

| Measure | Definition |
| --- | --- |
| <name> | <how it is calculated> |

## 5. Pages and content
*For each page: its purpose, the visuals in reading order, and a priority (must have, should have, could have).*

**Page 1: <name> (must have)**
- <visual or block>

## 6. Filters and interactions
*Which filters exist, what clicking a visual does, how pages connect, what shows when a filter empties a visual, and whether there is a reset.*

## 7. Look and feel
*Canvas size, mood, palette (or "use the company theme"), fonts, corner and shadow style, and contrast needs.*

## 8. Data readiness (complete after profiling)

| Need | Where it comes from | Status |
| --- | --- | --- |
| <field or measure> | <table or "new"> | Exists, Needs building or Not available |

## 9. Limits and out of scope
*What the data cannot show, so the design does not imply it. Also anything deliberately left out.*

## 10. Done when
*The checks the report must pass to count as finished.*

- Parts add up to totals
- Every key value matches a recompute from the raw rows (the numbers audit)
- No clipped text, no empty buttons, and no scrollbars where a visual should fit
- Every control on the wireframe works in the report, or is logged as a known gap

## 11. IT and security
*Classification, what the agent may see (aggregates only unless cleared), credentials, external URLs the report loads, refresh, sharing and row-level security. Details in `docs/it-security.md`.*
