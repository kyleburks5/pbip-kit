# UDF KPI card library (Park.*) — kit copy

33 DAX user-defined functions from the UDF KPI Card Library, used with the author's permission
(design/udf/udf-kpi-library-provenance.md). One `.tmdl` file each; `index.json` lists each function with a plain
description, parameters, style parameters and the tokens they default to, output, what it calls and is called by,
the model tables it needs, an example, Use when / Avoid when, the kit's fingerprint and the original's, the changes
made, and whether it's enabled.

- **Optional toolbelt:** used only when the plan or the person picks a function. Nothing uses them by default.
  Pattern: docs/patterns/svg-kpi-card.md.
- **Changes from the author's code:** CHANGES.md (K-01 to K-07). The author's originals are not in the master kit:
  they stay in the study project, with the script that made this copy from them. `../index_udf.py` rebuilds the
  index after a reviewed change (`--originals <folder>` only where the originals are).
- **Before using a function:** `pbik udf check <Name>` checks the fingerprints (a changed file is noticed), that it's
  turned on, and that the model has the tables it reads (`'Date'` for BasicLineChart and the gradient card's
  Dumbbell2c).
- **Install text:** `pbik udf render <Name>` fills the `{{token}}` placeholders from design/tokens.json and adds what
  the function calls (`--format query` for a query-scoped test). Needs compatibility level 1702. `pbik udf install`
  writes it into the synthetic model; `pbik udf inline` expands a call into plain DAX instead.
- **Turned off:** `Park.Icons.SolidIcon` and `Park.Icons.GradientIcon` until the icon pack's source and licence are
  recorded (provenance note); `pbik udf list` doesn't offer them and every pbik step refuses them. No icon pack and no
  icons table ship with the kit. Every card works without them: leave the icon argument out (Card1 draws its own
  small diamond, Card2 an empty tinted tile, SVGKPICard nothing). `Park.Icons.CleanSVG` is plain text cleaning and
  stays on.
