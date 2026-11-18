# Context strip

**Question:** What is the page showing right now?

**Use when** slicers, cross-filters or a selection in an app visual change what every number means, and the reader
should not have to open the filter pane to know: a quiet line under the title, "Showing East · all categories · up to
2026-11".
**Avoid when** the page has no slicers (the title says it), or the filters are long lists (say "3 regions", not
all of them).

## Design

- One line in `colors.textMuted`, caption size, directly under the page title (the [page header
  stack](../page-header-stack.md) description line).
- Each filtered field in reading order, "All <things>" when it isn't filtered, joined with " · ".
- Optional: the selected item from an app visual ("Deal D-0042") goes first, set by cross-filter like any filter.

## Build

| Route | What it draws | Pick it when |
| --- | --- | --- |
| **native** | a DAX text measure in a new card (label off, left-aligned) or a text box value | always (normal pick) |

```dax
Context Strip =
VAR _R = IF ( ISFILTERED ( Sales[Region] ),
    CONCATENATEX ( VALUES ( Sales[Region] ), Sales[Region], ", ", Sales[Region], ASC ), "All regions" )
VAR _C = IF ( ISFILTERED ( Sales[Category] ),
    CONCATENATEX ( VALUES ( Sales[Category] ), Sales[Category], ", ", Sales[Category], ASC ), "all categories" )
VAR _M = MAX ( Sales[Month] )
RETURN "Showing " & _R & " · " & _C & " · up to " & _M
```

Past three values, swap the list for a count: `COUNTROWS ( VALUES ( ... ) ) & " regions"`. Tested on the scratch
model (2026-11-16): "Showing All regions · all categories · up to 2026-11"; with East and months to June, "Showing
East · all categories · up to 2026-06".

## Checks

The audit states in design/specs/audit.json each give the expected line (a text entry); `pbik validate` checks the
card's contrast and size like any text.
