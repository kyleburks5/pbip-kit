# Build method

Read by /plan (layout.json keys), /build and /fix. Format and placement: docs/lessons/README.md.

## Index
<!-- lessons:index -->
| ID | Lesson | Enforced by |
| --- | --- | --- |
| B-01 | Build through the kit, never by hand | – |
| B-02 | Every build gives the same result twice | pbik build (idempotent writes); /build reruns it; the regression suite |
| B-03 | Build the first repeated unit first | – |
| B-04 | Copy a setting Desktop saved instead of guessing | `pbik validate` warns on settings outside the catalog (`pbik catalog show`) |
| B-05 | A template's reference lines are dropped, so give the visual its own | pbik build drops a field-bound template line (since 0.6.1) |
| B-06 | Measure-driven text is an expression, not a literal | – |
| B-07 | Rename fields per visual with displayName | pbik build writes it per projection |
| B-08 | Field parameters bind every underlying field | pbik build writes every field in parameter order plus `fieldParameters` (since 0.3) |
| B-09 | Every Deneb visual names a fallback | `pbik validate` errors on a Deneb visual without one |
| B-10 | Record the build method of every visual | design/scripts/audit_ids.py flags a visual without one |
| B-11 | Filter on a measure only at visual level | pbik build stops with an error on a page measure filter |
| B-12 | HTML Content visuals use legacy rendering and room to draw | pbik build sets `compatibility.legacyRendering` and warns under 43px; `pbik validate` warns too |
<!-- /lessons:index -->

## B-01 Build through the kit, never by hand
- **Rule:** Run `design/scripts/gen_theme.py`, then `pbik build` from `design/specs/layout.json` alone (theme, opening
  page, navigator states and every visual setting are layout keys). Anything layout.json can't express, even with
  `props` and `{"raw": ...}` copied from a Desktop-saved file, is a pbik gap: stop and report it by visual ID.
- **Why:** per-rep build.py scripts and patches drifted from layout.json and couldn't be rerun safely.
- **Enforced by:** not enforced (read at /build, which forbids build code)
- **Source:** pbik 0.6 (kit v0.3)

## B-02 Every build gives the same result twice
- **Rule:** Run `pbik build` twice; the second run must print "No changes".
- **Why:** the old field-parameter patch stacked its fields again on every run.
- **Enforced by:** pbik build (idempotent writes); /build reruns it; the regression suite
- **Source:** pre-pbik builds (kit v0.3)

## B-03 Build the first repeated unit first
- **Rule:** Build the first card (or any repeated unit), screenshot it, and only then repeat it.
- **Why:** a mistake in a repeated unit is repeated in every copy before anyone sees it.
- **Enforced by:** not enforced (read at /build)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## B-04 Copy a setting Desktop saved instead of guessing
- **Rule:** Before restyling, look up object and property names and enum values in a Desktop-saved visual.json (the
  Patterns page, design/templates/, an earlier rep). When a Desktop setting fixes what pbik can't write, save once,
  diff that visual.json against an untouched sibling and copy the exact JSON into layout.json `props` (`{"raw": ...}`).
  A setting worth reusing goes on the Patterns page and into a template (`pbik templates harvest`).
- **Why:** guessed names validate but Desktop ignores them.
- **Enforced by:** `pbik validate` warns on settings outside the catalog (`pbik catalog show`)
- **Source:** Rep 7

## B-05 A template's reference lines are dropped, so give the visual its own
- **Rule:** Put reference lines in the visual's own `referenceLines` in layout.json.
- **Why:** a template line bound to a field drew at 0 with the template's old label ("Company: 0").
- **Enforced by:** pbik build drops a field-bound template line (since 0.6.1)
- **Source:** Rep 9

## B-06 Measure-driven text is an expression, not a literal
- **Rule:** Bind measure-driven titles, subtitles and axis ends with a `cf` entry (`kind: "value"`) or
  `container.title: {measure}`, and set no literal on the same property after it. On a gauge, put colour measures on
  the objects without a selector.
- **Why:** a literal set after the measure replaces it.
- **Enforced by:** not enforced (read at /build)
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## B-07 Rename fields per visual with displayName
- **Rule:** Rename a field on one visual with `displayName` on that binding in layout.json.
- **Why:** only that visual's projection changes; the model keeps its name.
- **Enforced by:** pbik build writes it per projection
- **Source:** CLAUDE.md before v0.5 (rep not recorded)

## B-08 Field parameters bind every underlying field
- **Rule:** Bind a field parameter as a `fieldParameter` item in layout.json.
- **Why:** binding only the display column drew one bar named after the selected field.
- **Enforced by:** pbik build writes every field in parameter order plus `fieldParameters` (since 0.3)
- **Source:** Rep 5

## B-09 Every Deneb visual names a fallback
- **Rule:** Give each Deneb visual a native or SVG `fallback` in layout.json.
- **Why:** where custom visuals are blocked, `--no-custom-visuals` (or project.json `customVisuals: false`) builds it.
- **Enforced by:** `pbik validate` errors on a Deneb visual without one
- **Source:** kit v0.4

## B-10 Record the build method of every visual
- **Rule:** Set `build.method`, `build.step` and `build.reason` per visual ID (design/reference/layout-schema.md).
- **Why:** the visual-method ladder can only be checked against what was recorded.
- **Enforced by:** design/scripts/audit_ids.py flags a visual without one
- **Source:** kit v0.4

## B-11 Filter on a measure only at visual level
- **Rule:** Put measure filters (`{field: "[M]", op: ">", value: 0}`) in a visual's `filters`, never a page's.
- **Why:** Power BI filters on a measure only per visual; a page filter on one does nothing useful.
- **Enforced by:** pbik build stops with an error on a page measure filter
- **Source:** kit v1.2

## B-12 HTML Content visuals use legacy rendering and room to draw
- **Rule:** Keep HTML Content visuals (any `htmlContent<GUID>` type) at least 43px tall.
- **Why:** shorter, the visual has no room to draw its content.
- **Enforced by:** pbik build sets `compatibility.legacyRendering` and warns under 43px; `pbik validate` warns too
- **Source:** kit v1.2 (not Desktop-tested yet)
