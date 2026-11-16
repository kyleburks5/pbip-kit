# Provenance: UDF KPI card library (study 2026-11-15)

- **Source:** the "UDF KPI Card Library" report and semantic model, a DAX user-defined function (UDF) KPI card
  library bought and extended by the kit's owner. Function namespace `Park.` (an earlier version used `PBI.`).
- **Permission (confirmed 2026-11-15):** the library's author gave permission to use it in the owner's work. The
  owner confirmed this covers keeping the 33 functions in the kit (decision 1, 2026-11-15). The library is not
  MIT-licensed and is not a DAX Lib package, so it is not listed in `packages.json` (which is for DAX Lib packages)
  and is never installed through daxlib-mcp.
- **Data class:** public (approved in the approval window, 2026-11-15).
- **Where it was read:** the functions were read read-only on 2026-11-15 from the owner's downloaded copy open in
  Power BI Desktop (modeling server export; nothing in the Model folder was opened; the model wasn't changed).
- **Where things are:** the author's 33 originals stay unchanged in the study project (Study 2), never in the
  master kit; the kit holds only its own copy.
- **What came into the kit (2026-11-15, Study 2 import):**
  - the kit copy in design/udf/library/park-kpi (changes K-01 to K-07 in its CHANGES.md, index.json with a
    fingerprint per function);
  - two card templates from a clean harvest (bindings, texts, names, filters and saved selections removed; colours
    mapped to token roles), source label `udf-kpi-study`: `design/templates/cardVisual.svg-kpi-card.json` and
    `design/templates/advancedSlicerVisual.svg-kpi-card-buttons.json`; log design/reviews/harvest-udf-kpi.md.
- **Not copied:** no data values, no icons (neither the embedded images in measures nor the model's icons table),
  no measure texts.

## Icons (decision 2, 2026-11-15): disabled

- The icon functions (`Park.Icons.SolidIcon`, `Park.Icons.GradientIcon`) read a 3,058-row `icons` table that the
  source model loads from a folder of SVG files. **The pack's site wasn't named** in the decision (the text read
  "<site name>"), so its source is unconfirmed.
- The icon names (`thumb-up-fill`, categories such as `Arrows.arrow-down-box-fill`) follow **Remix Icon**'s naming.
  Remix Icon's current licence, read 2026-11-15 at https://github.com/Remix-Design/RemixIcon/blob/master/License,
  is the **Remix Icon License v1.0** (January 2026): commercial and non-commercial use and modification allowed;
  selling the icons as a pack or making a competing icon library, and using an icon as a logo or trademark, are not;
  attribution optional for use in projects (suggested credit "Icons by Remix Icon (https://remixicon.com)"); keeping
  the copyright notices and the licence is required when distributing the library or a large part of it. It is not
  MIT, Apache or CC0. (Older Remix Icon releases were Apache 2.0; which release the pack came from isn't known.)
- **So the icon functions stay turned off** (index.json `status`; `pbik udf list` doesn't offer them, and
  `pbik udf check`, `render`, `install`, `inline` and a `udfCard` refuse them with this reason). The kit ships no icon
  pack and no icons table; every card works without one (the icon argument left out).
- **For later (when someone wants icons):** record the pack's site, release and licence here. If it is Remix Icon:
  the Remix Icon License v1.0 allows use and modification in projects, attribution optional (suggested credit above);
  it forbids selling the icons as a pack, making a competing icon library, and using an icon as a logo or trademark;
  shipping the whole set (or a large part) needs the copyright notice and the licence beside it. So a kit icons table
  holding the full pack would count as distributing a large part: ship only the few icons a report uses, or have
  each project load them itself. Older Apache 2.0 releases need their NOTICE kept. Then turn the two functions on in
  index_udf.py (`STATUS`) and add an icons-table step to `pbik udf install`. To enable: name the pack's site and version here, record its licence, add any required credit to this
  note and the kit docs, then set their status to `enabled` in design/udf/library/index_udf.py (`STATUS`) and
  rebuild the index. `Park.Icons.CleanSVG` is text cleaning only and stays enabled. No icon is stored in the kit.
