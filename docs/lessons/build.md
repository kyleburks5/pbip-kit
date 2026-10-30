# Build method

Moved from CLAUDE.md (v1-simplify, 2026-10-29); placement rules in docs/lessons/README.md. Read by /plan (layout.json keys), /build and /fix.

- Build and style through the kit, not by hand: `design/scripts/gen_theme.py` (theme from tokens), then `pbik build` from `design/specs/layout.json` alone (the theme, the page that opens first, navigator states and every visual setting are layout keys). No per-rep `build.py` (pbik 0.6): anything layout.json can't express, even with `props` and `{"raw": ...}` copied from a Desktop-saved file, is a pbik gap: stop and report it by visual ID instead of writing build code.
- Every build must give the same result when run twice; the old field-parameter patch stacked its fields on every run. *(pbik build is idempotent; /build reruns it and the regression suite checks it.)*
- Build the first card (or any repeated unit) and screenshot it before repeating it.
- When a Desktop setting fixes something pbik can't write, save once, diff that visual.json against an untouched sibling, and copy the exact JSON into layout.json (`props` with `{"raw": ...}`). A setting worth reusing goes on the Patterns page (..\pbip-patterns) and into a template (`pbik templates harvest`).
- Before restyling a visual, look up its object and property names and enum values in a visual.json Desktop saved (the Patterns page, a harvested template in design/templates/, or an earlier rep in examples/) instead of guessing (Rep 7).
- Check a template for reference lines before using it. A template line bound to a field drew at 0 with the template's old label ("Company: 0" over a top-5 chart); since pbik 0.6.1 pbik build drops such a line whole, so give the visual its own `referenceLines` in layout.json (Rep 9). *(pbik build drops a field-bound template line since 0.6.1.)*
- Measure-driven text or numbers (subtitle, title, axis start/end) are an expression, not a literal: in layout.json a `cf` entry with `kind: "value"` (or `container.title: {measure}`). Don't set a literal value after it on the same property; it replaces the measure. On a gauge, put colour measures on the objects without a selector.
- Rename fields per visual with `displayName` on that binding in layout.json (only that visual's projection changes).
- A visual that uses a field parameter must project every underlying field, in parameter order, plus a sibling `fieldParameters` entry. Binding only the display column draws one bar named after the selected field; bind it in layout.json as a `fieldParameter` item (pbik writes both, since 0.3). *(pbik writes both from a `fieldParameter` binding since 0.3.)*

## Native first: recorded and checked
- Every Deneb visual names a native or SVG fallback in layout.json (`fallback`); `pbik build --no-custom-visuals`
  builds the fallbacks instead. *(`pbik validate` errors on a Deneb visual without one.)*
- Record the build method of every visual in layout.json (`build.method`, design/reference/layout-schema.md). *(audit_ids.py flags a visual without one.)*
