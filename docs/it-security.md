# IT and security notes

Placeholders. Fill in per project with IT or the data owner before any non-public data goes into `data/`. The kit's
rule today: public data only (CLAUDE.md).

## What the agent may see

Aggregates only unless cleared. Profiling, audits and wireframe numbers use counts, sums and other aggregates from DAX;
row-level data is not exported or read by the agent unless the data owner has cleared it, and the clearance is
recorded here.

Wireframe numbers (`design/scripts/wireframe_data.py`): one aggregate query per visual at its own grain, with the
privacy count from layout.json `privacy`. Groups under `minGroup` (5) are hidden, and one more when exactly one would
be hidden (so it can't be worked out from a total). The file is not saved when a visual groups by an identifier
column, a query returns more than `maxRows` rows, or a small group remains. Not covered: differencing across two
visuals with different filters, and identification from a combination of categories that each pass on their own
(keep visuals' groupings coarse, and add the columns concerned to `identifiers`).

| Data set | Classification | Row-level access cleared? | By whom, when |
| --- | --- | --- | --- |
| *(fill in)* | public / synthetic / internal / restricted | no | |

## Data classification and location

- *Classification of each source, and its owner.*
- *Where the files live (`data/` is git-ignored; nothing in `data/` is committed).*
- *Retention: when local copies are deleted.*

## Credentials

- *No credentials, keys or connection strings in the repo, the TMDL or the scripts.*
- *How data source credentials are held (Desktop's credential store, a gateway).*

## External calls

- *URLs the report loads at view time (image URLs leak the viewer's IP to that host; Rep 7 loaded team logos from a
  public site).*
- *Services the agent and tools contact.* Known: `pbik schemas fetch` downloads public JSON schemas from
  `https://developer.microsoft.com/json-schemas/` (GET only, nothing sent but the URL); no other pbik command goes
  online. The wireframe drawn with `gen_wireframe_hf.py` loads vega, vega-lite and vega-embed (pinned versions)
  from cdn.jsdelivr.net when opened (GET only; the page's numbers stay in the page), and draws Deneb specs with its
  subset renderer when they don't load. **At work, set `"vega": "offline"` in layout.json** (design/reference/
  layout-schema.md): the wireframe then loads nothing from the internet, so opening it contacts no outside host,
  and Deneb visuals are drawn by the subset renderer (marks it can't draw are listed under the visual). `edge_page.py` (wireframe
  tests, `fidelity_check.py`) serves pages to headless Edge from 127.0.0.1 only. The daxlib-mcp server (.mcp.json) downloads
  from npm when it starts and reads the public DAX Lib catalog (see "Agent setup").
  Plugins and the modeling MCP download from GitHub and npm.

## Custom visuals

The visual-method ladder (CLAUDE.md "Native first") allows custom visuals at steps 3 and 4 only.

| Visual | Status | Recorded |
| --- | --- | --- |
| Deneb (Vega / Vega-Lite), AppSource | Certified AppSource visual; confirmed working in the work tenant (as reported by the maintainer) | 2026-10-24 |
| Any other custom visual (.pbiviz from AppSource uncertified, from GitHub, or built in-house; HTML Content) | Uncertified: needs a separate check with IT before use (tenant admin setting for uncertified / organisational visuals, the visual's network calls, its licence) | none cleared |

- Deneb is step 3. Every Deneb visual names a native or SVG fallback in layout.json (`fallback`), so the report can be
  built without custom visuals (`pbik build --no-custom-visuals`) if a tenant blocks them.
- Deneb's data is the visual's own aggregated query, as for any other visual (aggregates only). A Vega-Lite spec can
  load external data or images by URL; the kit's specs use only the `dataset` Deneb provides and no `url` data
  (`pbik validate` rejects a `url` in a spec).
- Certified visuals are reviewed by Microsoft for not accessing external services; uncertified ones are not. A step-4
  visual needs `build.itCheck` in layout.json (who cleared it, when), and a row in the table above.
- Developing a .pbiviz: documented only (docs/custom-visuals.md); the kit has no tooling for it.

## Refresh and gateway

- *Scheduled refresh, gateway, and who owns it.*

## Workspace and sharing

- *Workspace, who can view or build, export settings, sensitivity label.*

## Row-level security

- *Roles, who maps users to them, and how RLS is tested.*

## Agent setup

- *MCP servers enabled and their permissions (`.claude/settings.local.json`).* The project's `.mcp.json` adds
  **daxlib-mcp** (`npx -y @daxlib/mcp --start`, @daxlib/mcp 0.1.0, MIT): npx downloads the server from the npm registry
  when it starts, its catalog tools (`search_packages`, `get_package`, `get_package_readme`) read the public DAX Lib
  catalog (daxlib.org), and `install_package` writes DAX functions into the local Desktop model. The kit uses it only
  at `/model approved`, for packages listed in design/udf/packages.json. No model data is sent: it reads package
  metadata and writes functions. Where npm is blocked, the same packages install from the vendored copy in
  design/udf/vendor (unmodified, with each package's LICENSE; design/udf/vendor/NOTICE.md) through the modeling MCP.
- The request to IT for every tool, its source, licence and access is docs/IT-REQUEST.md; `tools/doctor.ps1` checks
  each one (PASS, WARN with the fallback, FAIL with what to ask IT).
- DAX Lib packages (design/udf/packages.json, licences checked 2026-10-24):

  | Package | Version | Licence | Licence source |
  | --- | --- | --- | --- |
  | DaxLib.SVG | 2.0.0 | MIT | LICENSE in github.com/daxlib/dev-daxlib-svg |
  | DataTides.ColourContrast | 0.1.0 | MIT | no repository of its own; the github.com/daxlib/daxlib catalog repository's LICENSE (MIT, SQLBI) |
  | DataTides.SignificantChange | 0.1.0 | MIT | as above |
  | DaxLib.FormatString | 0.1.2 | unconfirmed | not listed: its repository returned 404 |
- *Plugin sources and pinned versions (VERSIONS.md). The Data Goblins plugins are GPL-3.0, used as installed; the kit
  copies none of their content.*
- *pbik (tools/pbik) runs locally with the Python standard library (jsonschema optional); `pbik desktop` runs
  `.claude/scripts/pbi-bridge.ps1`, which talks to Desktop over a local named pipe.*
