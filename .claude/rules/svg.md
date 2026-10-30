SVG and images: rules from Reps 2-7. SVG is a fallback (CLAUDE.md "Native first"): record the native option tried, the
reason, and a fallback register row before building one.

## Static SVG images (icons, court lines, wallpaper)
- Render each SVG to a transparent PNG at 4x its size with `design/scripts/svg_to_png.py` (headless Edge); full-canvas
  images at 1x (`--scale 1`). PNG is the route tested in Desktop; `pbik resource add` also takes an .svg, but that is
  not yet confirmed in Desktop.
- Register each PNG once with `pbik resource add <Report> <png>`; it reuses the
  same name instead of adding `<stem>_<digits>.png` copies.
- Bind it as `general.imageUrl` = `ResourcePackageItem` (PackageName RegisteredResources, PackageType 1, ItemName),
  `pbik_helpers.image_objects()`.

## SVG measures (DAX returning `data:image/svg+xml;utf8,...`, dataCategory ImageUrl)
- Write `%` inside the SVG as `%25` (`pbik validate` flags a raw one). A raw `%` (text such as "24%") stops Power BI decoding the data URI: every `%23`
  colour draws black while the text still shows (Rep 5).
- Show an SVG measure in a new card (filtered to one value, value and label hidden, image area 100, fit) or a table
  or matrix column (layout.json `cf` type `image`). An image visual can't take a measure.
- An extension measure references model measures only, never another extension measure (docs/lessons/dax.md).
- The card image needs a measure with a declared Text type: wrap the model measure in a report extension measure
  (`pbik measure ext add <Report> "img X" --expression "[Model Measure]" --data-category ImageUrl`).
- Test new SVG measures query-scoped first (`DEFINE MEASURE`), then write them to the TMDL.
- Every SVG measure must pass `design/scripts/audit_svg.py` (well-formed XML, no raw `%`) in every state of
  `design/specs/audit.json`, including the empty case and the first year.
- The numbers drawn in the SVG text are part of the numbers audit: `design/scripts/audit_numbers.py` (`svg` entries)
  compares them with `FORMAT ( [measure], "<format>" )`.
- Use a DAX Lib package listed in `design/udf/packages.json` (DaxLib.SVG) before writing a new SVG measure; it is
  installed at `/model approved` through daxlib-mcp (design/udf/README.md).
- DaxLib.SVG takes colours as raw `"#RRGGBB"`, unlike hand-written SVG. Its output keeps a raw `%` (`width='100%'`),
  so Power BI doesn't decode the URI: raw `#` colours render, `%23` colours draw nothing. Checked in Desktop on a card
  image and table images (v0.4.1, Rep 10 scratch). `pbik validate` flags a `%23` passed to DaxLib.SVG; the `%25` rule
  below is for SVG text you write yourself.
- Review SVG measures with the `reports:svg-reviewer` agent before building them.
