# Honest data

`pattern: "honest-data"`

**Question it answers:** can I trust this number, and is it good for its kind?

- **Use when:** values are rates or averages over groups of very different sizes, or groups whose normal ranges
  differ (a good rate for one kind is a poor rate for another), or the data is about people (small groups can
  identify someone).
- **Avoid when:** every group is large and judged on one scale (a plain ranked bar is honest already).

## Four rules
1. **Small samples.** Below `minSample` rows a value either fades toward neutral with a "limited sample" note
   (`fade`), or is not shown at all, anywhere (`suppress`, the privacy mode: small-cell suppression, "fewer than 11").
   Set in design/specs/project.json `honestData` `{"minSample": 11, "mode": "fade"}`; without it the mode is
   `suppress` on the work catalog and `fade` elsewhere. pbik build passes both to kit visuals; validate checks them.
2. **Own range.** Each group is coloured against its own normal range or a benchmark, not one scale for all: claim
   approval by claim type, waiting time by clinic size, shooting by shot type. The colour says "above or below what
   is usual for this kind"; the readout says the range ("Usual for Outpatient 61-86%").
3. **Shape as well as colour.** Filled vs hollow (done vs not), solid vs dashed (actual vs forecast), a symbol in
   the label. Text on a member's colour is the theme's text or background colour, whichever contrasts more.
4. **Say the rule.** An [exception list](exception-list.md) states its threshold in its title ("Over 3 days late")
   and says a plain sentence when empty ("No claims over 3 days late."). A suppressed number says so.

## Examples
- Health plan: approval rate by provider, faded under 11 claims, suppressed in privacy mode; readmission rates by
  hospital against each hospital's expected rate; member counts under 11 shown as "<11".
- Sales: margin by product judged within its category; a new store's first weeks marked "limited sample".

## Build (visual-method ladder)
| Step | How |
| --- | --- |
| 1 native (pick this) | Measures: `Shown = IF ( [Rows] < [Min sample], BLANK (), [Rate] )`; a colour measure on the position within the group's band (`cf` measure); a note column or label "fewer than 11"; marker shapes per series |
| 2 SVG | a measure drawing hollow vs filled marks where a native visual has one shape only |
| 4 kit custom visual | `kit/patterns/honest.ts`: `readSampleRule`, `sample`, `countText`, `bandsFrom` / `onBand`, `readableOn`, `standout` |

## Measures (sketch)
```dax
Min sample  = 11                                  -- the project's honestData.minSample
Rate shown  = IF ( [Rows] < [Min sample], BLANK (), [Rate] )                   -- suppress
Rate note   = IF ( [Rows] > 0 && [Rows] < [Min sample], "fewer than " & [Min sample] )
Band low    = CALCULATE ( [Rate], ALLEXCEPT ( Fact, Fact[Group] ) ) - [Band half width]
Band pos    = DIVIDE ( [Rate shown] - [Band low], 2 * [Band half width] )     -- 0 cold .. 1 hot, for a cf gradient
```
In suppress mode every visual on the page uses `Rate shown` (a total that lets a suppressed cell be worked out by
subtraction is suppressed too: blank the next-smallest cell, or show the total rounded).

## Checks
Audit: one group just under and one just over the threshold (shown, faded or blank as the mode says); `<11` text,
never the number, in labels, tooltips, readouts and headlines; the band of two groups recomputed. Accessibility (A-02):
no meaning by colour alone.
