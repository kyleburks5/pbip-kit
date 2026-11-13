# Exception list

`pattern: "exception-list"`

**Question it answers:** which members need attention, worst first?

- **Use when:** many members, mostly normal, with a written rule for which ones need attention.
- **Avoid when:** every member matters equally (a full ranked table), or there are no rules for "normal" yet (write
  them in the spec's design ambition first).

## When to use
- Many members (stores, products, cases) where most are normal and a few are not. The list shows only the ones
  outside the normal rule (below target, outside the band, late), with how far out they are.
- Next to a summary chart: the chart shows normal, the list names the exceptions.

## Design
- Title from a measure with the count: "4 stores below target".
- Columns: member, the gap (signed, coloured by severity), the value, the baseline, and why ("Below target 3 months").
- Sorted by severity. A small `red` / `slate` status chip or symbol per row; never colour alone.
- Empty state: "No exceptions" (a card shown when the count is 0, or the title measure says it).

## Build (visual-method ladder)
| Step | How | Draws | Status |
| --- | --- | --- | --- |
| 1 native (pick this) | Table whose value measures return BLANK for normal members, so those rows drop out; title bound to `[Exception title]`; gap coloured with `cf` rules or a colour measure | the list, worst first | table cf rules and `values.fontColor` measures are in the catalog; `columnWidths: "fit"` |
| 2 SVG measure | Status chips in a column (pill with text) | chip per row | CLAUDE.md "Native first" names this as the typical SVG fallback |

Rows drop out because a table row shows only when at least one value is non-blank: put the exception rule into every
value measure in the list (or a `[Is exception]` visual filter when pbik supports measure filters; today it writes
categorical and Top N filters only).

## Measures (sketch)
```dax
Is exception   = IF ( ISBLANK ( [Value] ), BLANK (), INT ( [Value] < [Target] ) )
Gap (exc)      = IF ( [Is exception] = 1, [Value] - [Target] )
Value (exc)    = IF ( [Is exception] = 1, [Value] )
Exception count = SUMX ( VALUES ( Store[Store] ), [Is exception] ) + 0
Exception title = IF ( [Exception count] = 0, "No stores below target",
                       [Exception count] & IF ( [Exception count] = 1, " store", " stores" ) & " below target" )
```

## layout.json example
```json
{"id": "P1-V09", "name": "below-target", "page": "P1", "type": "tableEx", "pattern": "exception-list",
 "x": 1306, "y": 360, "w": 582, "h": 400, "z": 1,
 "bindings": {"Values": [{"field": "Store[Store]", "displayName": "Store"},
                         {"field": "[Gap (exc)]", "displayName": "Gap"},
                         {"field": "[Value (exc)]", "displayName": "Sales"}]},
 "sort": {"field": "[Gap (exc)]", "direction": "Ascending"},
 "cf": [{"type": "rules", "object": "values", "property": "fontColor", "field": "[Gap (exc)]", "target": "[Gap (exc)]",
         "rules": [{"op": "<", "value": 0, "color": "red"}]}],
 "columnWidths": "fit",
 "container": {"title": {"measure": "[Exception title]"},
               "altText": "Stores below target this month, largest gap first"},
 "build": {"method": "native", "step": 1, "reason": "Blank-for-normal measures leave only the exceptions"}}
```

## Wireframe
A table of the exception rows only (sample data: 4 of 12 members), the gap in `red`, the title with the count; with
no exceptions the "No …" empty state.

## Audit
`[Exception count]` against a raw recompute of the rule; one exception row's gap; the empty case (count 0, title
text); a member with no rows (not an exception: `ISBLANK` guard).
