# Custom visuals (ladder steps 3 and 4)

CLAUDE.md "Native first" sets the visual-method ladder: 1 native, 2 SVG, 3 Deneb, 4 any other custom visual. This page
covers steps 3 and 4. IT status for each visual is in docs/it-security.md ("Custom visuals").

## Step 3: Deneb

- Certified AppSource visual, MIT licence (VERSIONS.md). Draws a Vega or Vega-Lite spec over the visual's own
  aggregated dataset.
- Built by pbik from layout.json (`type: "deneb"`, the spec and a `fallback`; tools/pbik/README.md). The PBIR form
  is learned from a Deneb visual Desktop saved on the Patterns page (..\pbip-patterns), not from Deneb's
  or Desktop's program code.
- Every Deneb visual names a native or SVG fallback; `pbik build --no-custom-visuals` builds the fallbacks, for a
  tenant that blocks custom visuals or as the accessible variant.
- Review each spec with the `reports:deneb-reviewer` agent before building it, and draw it in the wireframe first.
- Specs use the `dataset` only: no `url` data and no external images (`pbik validate` checks).

## Step 4: other custom visuals (.pbiviz)

Documented only: the kit has no tooling for building, packaging or registering a .pbiviz.

- What it is: a visual packaged as a `.pbiviz` file (a zip of the compiled JavaScript, `capabilities.json` and
  metadata), built with Microsoft's `powerbi-visuals-tools` (`pbiviz new`, `pbiviz package`). In a report it is either
  imported into the report (stored in the report's custom-visual resources) or deployed by the tenant admin as an
  organisational visual (report.json `organizationCustomVisuals`); AppSource visuals are listed in
  `publicCustomVisuals`.
- Before use: an IT check (docs/it-security.md): the tenant settings for uncertified and organisational visuals,
  what the visual sends over the network, its licence, and who maintains it. Record it as `build.itCheck` in
  layout.json and a row in the it-security table.
- Certified (AppSource) means Microsoft reviewed the code for not calling external services and for its build; an
  uncertified visual from AppSource or GitHub has had no such review.
- HTML Content (`html-measure`) counts as step 4 until it has its own row in docs/it-security.md.
- Export and printing: some custom visuals don't render in PDF / PowerPoint export or email subscriptions; check the
  report's distribution before choosing one.
- Rather than building a .pbiviz, check that steps 1-3 really can't draw the design: Deneb covers most bespoke charts
  with a certified visual.
