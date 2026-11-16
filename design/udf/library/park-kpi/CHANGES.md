# Kit changes to the author's functions

The author's originals stay unchanged in the study project (Study 2), not in the master kit; their fingerprints
are in index.json `originalSha256`. The kit copy here was made from them by the study's make_kit_copy.py, which
makes each change below as an exact, counted replacement and stops if the original text isn't found. Each changed
place in a file carries its K-id; index.json `changes` lists them per function.

All changes tested 2026-11-15 query-scoped (renamed `KitTest.`) against the owner's copy of the source model in
Power BI Desktop, with one metric and one year picked; results in the study's wrap-up (§5), aggregates only.

| ID | Change | Functions | Why |
| --- | --- | --- | --- |
| K-01 | The author's `DAXLIB_PackageId = PBI.SVG` / `DAXLIB_PackageVersion` annotations removed | the 12 that had them | They are not DAX Lib packages; the versions were mixed (0.4.1–0.6.0). The kit fingerprints each file instead (index.json `sha256`), so any change is noticed (`pbik udf check`) |
| K-02 | Style parameters added after the author's parameters: font, text, muted, surface, border, good, bad (Card2 also good and bad tints); BLANK() gives the report's design token; every colour and font literal inside the card replaced by these | Card1, Card2, SVGKPICard (font was already a parameter: now with a token default), SVGKPICardGradient | Cards follow the report's style preset (CLAUDE.md: never hardcode colours or fonts) |
| K-03 | Default colours and fonts inside microcharts, helpers and the line chart replaced by `{{token}}` placeholders: up `good`, down `bad`, current marks `text`, comparison marks `secondLight`, axis text `textMuted`, font `font.family` | microcharts, axis helpers, BasicLineChart | Same reason; their own colour and font parameters still win when given |
| K-04 | The gradient card's chart calls rewritten for the microcharts' current signatures (8 arguments, 9 for Bar1); Dumbbell2c keeps the older 12-argument dumbbell, which matches | SVGKPICardGradient | The original passed 11 arguments to 8-argument functions and didn't compile |
| K-05 | A blank current value returns BLANK (no card; replaced by K-09); a blank comparison shows "–" in the muted colour instead of +0% (Card2's pill uses the border colour) | the four cards | The original drew a card showing 0 and +0% for missing data |
| K-06 | Bar3: colours passed in the microchart's order (up, past bar = neutral, down) | SVGKPICard | The original passed (up, down, neutral) to (up, past bar, down), so past bars took the down colour |
| K-07 | An unknown chart style stops with an error naming the allowed styles | SVGKPICard, SVGKPICardGradient | The original drew the card with no chart and no warning. DAX `ERROR` takes a constant message, so it can't name the wrong style; `IFERROR` doesn't catch it (a query with a wrong style fails, which is the point) |
| K-08 | Card2's icon: no icon now draws no tile (the empty tinted square is gone, so the label and value have the card to themselves); the icon argument also takes the name of one of the kit's own glyphs, drawn from scratch for the kit in the accent colour: `trend-up`, `trend-down`, `currency`, `cart`, `people`. Default: no icon | Card2 | The UDF card gallery (2026-11-16) showed an empty tinted square on every Card2; the icon pack stays off (licence), so the kit offers a few simple glyphs of its own (no licence question) |
| K-09 | A blank current value draws the card with its label and a muted "No data" in place of the value (no change, no chart), instead of nothing; supersedes K-05's "no card" | the four cards | The gallery's blank-value card left a hole in the layout; a card that keeps its shape reads as "no data yet", not as a broken visual |
| K-10 | Card1's change text keeps its sign: a fall reads "-11%" (it was "11%" in the bad colour), a rise "+11%" | Card1 | The original formatted the absolute value after choosing the sign, so a fall lost its minus; colour alone isn't enough (WCAG 1.4.1, use of colour) |
| K-11 | The change arrow is a solid triangle (▲ up, ▼ down) in the change colour, as on the kit's native KPI cards; a trailing argument `_ArrowShape` picks it: "triangle" (default, BLANK()) or "chevron" (the author's thin chevron). Card1, which drew no arrow, gets one left of its change text. A blank comparison draws no arrow (the dash says it). The colour follows good and bad, so "lower is better" (the kit swaps them) colours a fall green | the four cards | One look across the kit's cards, native and UDF; the chevron read as a decoration at card sizes. **The signature changes:** DAX functions have no optional arguments (Desktop: "the minimum argument count ... is 15"), so a call written before K-11 needs one more argument (BLANK() for the triangle); pbik writes every argument, so its cards rebuild cleanly |

K-08 to K-11 (2026-11-16) were made in the kit copy directly, after the UDF card gallery Desktop test; they are
not in the study's make_kit_copy.py.

**Kept as the author wrote it:** English text inside the cards ("From last year", "From Last Year"), `$` and `K` in
Card1, the "K" in the gradient card's value, the fixed sizes, and the icon functions (disabled: licence).
