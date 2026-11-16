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
  installed at `/model approved` through daxlib-mcp (design/udf/README.md). Next, a kit UDF library function
  (design/udf/library/, today `park-kpi`: 33 KPI card functions used with the author's permission,
  design/udf/udf-kpi-library-provenance.md); only then new SVG code.

## Kit UDF libraries (the optional toolbelt; `pbik udf`, docs/patterns/svg-kpi-card.md)
- Used only when the plan or the person picks a function: `pbik udf list --role card` and its **Use when** lines.
  Never through daxlib-mcp and never in packages.json (they aren't DAX Lib packages).
- Check before use (`pbik udf check`: fingerprint, turned on, the model tables it reads such as `'Date'`); a changed
  file is refused until the maintainer reviews it and rebuilds the index (design/udf/library/index_udf.py).
- Colours and fonts are `{{token}}` placeholders and BLANK()-means-token style arguments: `pbik udf render` fills them
  from tokens.json, and a card's colour arguments are `token:<name>` in `udfCard`, never a typed hex.
- The icon functions (`Park.Icons.SolidIcon`, `Park.Icons.GradientIcon`) are turned off until the icon pack's source
  and licence are recorded; the kit ships no icon pack and no icons table. Leave a card's icon argument out: Card1
  draws its own small diamond, Card2 no icon and no tile, SVGKPICard nothing. Card2 also takes one of the kit's own
  glyphs by name (`trend-up`, `trend-down`, `currency`, `cart`, `people`; K-08).
- Lower is better swaps a UDF card's good and bad colours automatically (layout `lowerIsBetter`); a function reading
  `'Date'` reads the model's own date table (install and inline map it). Card image settings are the ones Desktop
  saved on a working SVG card (image Left, area 100, fit, one tile, no padding): `pbik build` writes them.
- Three ways to use one (`udfCard.mode`): `inline` (default; the function's DAX expanded into a report-level measure,
  so it works on any live model), `measure` (a report-level measure calling the model's function), `calc` (a visual
  calculation with `DataType` Text and the measures it uses as hidden fields; not for functions that take columns).
  `measure` and `calc` need the function in the model: `pbik udf install` (synthetic model always; the person's own
  model only when they ask; level 1702). `pbik bind check` errors on a call the live model lacks and offers inline.
- The library's output keeps a raw `%` (the change text), like DaxLib.SVG: raw `#` colours render. The `%25` rule
  below is for SVG text you write yourself.
- A UDF card is an image: alt text says the number and the change in words (A-01), and the numbers it draws are
  `svg` entries in the numbers audit. Image cards get no saved sort. The six Desktop checks for UDF cards are still
  "verify in Desktop" (design/reviews/pbik-roadmap.md, U-1 to U-6).
- DaxLib.SVG takes colours as raw `"#RRGGBB"`, unlike hand-written SVG. Its output keeps a raw `%` (`width='100%'`),
  so Power BI doesn't decode the URI: raw `#` colours render, `%23` colours draw nothing. Checked in Desktop on a card
  image and table images (v0.4.1, Rep 10 scratch). `pbik validate` flags a `%23` passed to DaxLib.SVG; the `%25` rule
  below is for SVG text you write yourself.
- Review SVG measures with the `reports:svg-reviewer` agent before building them.
