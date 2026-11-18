# Live headline

**Question:** What does this view, or my selection, say in one sentence?

**Use when** a visual or a page has one finding the reader should not have to work out: "North holds 33% of open
deals", "3 of 240 selected; South holds most of them". The sentence updates with filters and selection.
**Avoid when** there is no stable finding to state (a sentence that is often wrong is worse than none), or the
number needs a comparison the sentence can't carry (use a KPI card with its reference).

## Design

- One sentence, the number in it formatted like the model's measure, under 90 characters; no colour-only meaning.
- Order of precedence: a selection here, a highlight from another visual, a drill-in, then the whole view.
- On a page: a card (or text box with a value) right under the title, in the headline text style.
- **Lowest / highest X headlines work within the current filter context and are never blank** (Desktop review
  2026-11-17: "Site 10 has the lowest status" picked from all 24 sites while the page showed West, so the card read
  "--"):
  - rank the members the page shows now: `VALUES ( T[Member] )`, filtered to those with a value. A member column's
    `ALLSELECTED` ignores filters on the table's other columns (a region slicer), so it can name a member the page
    doesn't show; use it only for the member column a slicer itself filters (the share headline below);
  - break ties in a fixed order (`TOPN ( 1, ..., [Value], ASC, T[Member], ASC )`) so the sentence doesn't change
    between refreshes;
  - say something sensible in every case: none qualify ("No sites with a status in this view."), one ("Site 05 is
    the only site in this view (status 72)."), several (the ranking, with the count it is out of). Never return
    BLANK: a card shows it as "--".
- **Counts agree with their noun**: "1 region", "1 site", "1 person", never "1 regions" or "site(s)". In DAX,
  `_N & IF ( _N = 1, " site", " sites" )`; in a kit visual, `count(n, "site")` (kit/words.ts: plurals in English,
  people / person, y / ies), and a localised string passes both forms (`forms`). Found 2026-11-17 in every kit
  headline ("1 items", "across 1 regions", "of 1 sites").

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| **native** | a DAX text measure in a new card or a text box value | a page headline (normal pick) |
| kit custom visual | `headline.ts` inside the visual (it knows the visual's own selection) | a headline about one app visual |

Measure (tested on the scratch model, 2026-11-16): the member, its share, and what of. With one member filtered it
compares with all members; otherwise it names the largest.

```dax
Headline Share =
VAR _One = HASONEVALUE ( Sales[Region] ) && ISFILTERED ( Sales[Region] )
VAR _Top = TOPN ( 1, ALLSELECTED ( Sales[Region] ), [Total Amount], DESC )
VAR _Name = IF ( _One, SELECTEDVALUE ( Sales[Region] ), MAXX ( _Top, Sales[Region] ) )
VAR _Part = CALCULATE ( [Total Amount], REMOVEFILTERS ( Sales[Region] ), Sales[Region] = _Name )
VAR _All = IF ( _One, CALCULATE ( [Total Amount], REMOVEFILTERS ( Sales[Region] ) ),
                      CALCULATE ( [Total Amount], ALLSELECTED ( Sales[Region] ) ) )
RETURN
    IF ( NOT ISBLANK ( _All ),
        _Name & " holds " & FORMAT ( DIVIDE ( _Part, _All ), "0%" ) & " of total amount"
            & IF ( _One, "", ", the most of any region" ) & ".",
        "No data in this view." )
```

Lowest (or highest) of the members in view:

```dax
Headline Lowest =
VAR _Rated = FILTER ( ADDCOLUMNS ( VALUES ( Sites[Site] ), "@s", [Avg Status] ), NOT ISBLANK ( [@s] ) )
VAR _N = COUNTROWS ( _Rated )
VAR _Low = TOPN ( 1, _Rated, [@s], ASC, Sites[Site], ASC )
VAR _Site = MAXX ( _Low, Sites[Site] )
VAR _S = MAXX ( _Low, [@s] )
RETURN
    SWITCH ( TRUE (),
        _N = 0, "No sites with a status in this view.",
        _N = 1, _Site & " is the only site in this view (status " & FORMAT ( _S, "0" ) & ").",
        _Site & " has the lowest status (" & FORMAT ( _S, "0" ) & ") of " & _N & " sites." )
```

Tested on the proof model (2026-11-17): all sites "Site 10 has the lowest status (58) of 24 sites."; West "Site 21
has the lowest status (62) of 6 sites." (the 3D visual's own headline says the same); one site and none as above.

Results: "East holds 26% of total amount, the most of any region." (no filter); "East holds 25% of total amount."
(East and the months up to June); "No data in this view." when nothing qualifies. In a kit visual: `headline({keys, selected,
highlighted, drilled, allCount, groupName, groupOf, t})`, every sentence a localisable template.

## Checks

Numbers audit: the share in the sentence against `DIVIDE` of the two totals in each audit state (a text entry).
Harness: `text` checks after each selection, highlight and drill.
Every headline measure: a DAX query in the audit's states, including a filter on another column of the table (a
slicer) and the empty case (a value no row has): the text names a member the page shows, and it is never blank.
