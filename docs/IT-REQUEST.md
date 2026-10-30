# Request to IT: tools for building Power BI reports with pbip-kit

**What it is.** pbip-kit is a folder of scripts and instructions I use to build Power BI reports as project files
(PBIP) on my laptop, with an AI coding assistant (GitHub Copilot in VS Code, or Claude Code) doing the file edits.
Everything runs locally. Reports are published the usual way, by me, from Power BI Desktop.

**What the assistant sees.** Aggregates only: counts, sums and other totals computed by DAX queries in Power BI
Desktop. It does not export or read row-level data unless the data owner clears it in writing (recorded in
docs/it-security.md). The kit itself is built and tested on public data only. No credentials, keys or connection
strings are kept in the project.

**What I'm asking for.** The tools below, and network access to the hosts listed. `tools\doctor.ps1` checks each one
and prints PASS, WARN (works with a fallback) or FAIL; I'll attach its output. Items marked *optional* have a
fallback and can be refused.

| Tool | Source | Licence | What it accesses | Needed for |
| --- | --- | --- | --- | --- |
| Power BI Desktop (current release) | Microsoft Store or Company Portal | Microsoft | Local files; the data sources I already use | Building and checking reports |
| Desktop Bridge (Desktop preview feature) | Built into Power BI Desktop | Microsoft | A local named pipe only (`\\.\pipe\pbi-desktop-bridge-<pid>`): reloads the open report and takes page screenshots | *Optional*: without it I reload by hand |
| Python 3.9+ | python.org or Company Portal | PSF License | Project files only. pbik, the kit's own tool, uses the standard library and never goes online except `pbik schemas fetch` (public JSON schemas from developer.microsoft.com) | Building and validating report files |
| jsonschema (Python package) | PyPI (pypi.org, files.pythonhosted.org), or wheel files copied in | MIT | Nothing: validates files locally | *Optional*: extra checks |
| Windows PowerShell 5.1 running local scripts (execution policy RemoteSigned for my user, or `-ExecutionPolicy Bypass` for `powershell -File`) | Windows | Microsoft | Two scripts in the project: the Desktop Bridge client and a DAX query runner that talks to Desktop's local Analysis Services port | Reload, screenshots, aggregate DAX queries |
| Node.js 18+ LTS with npm / npx | nodejs.org or Company Portal | MIT | Downloads the two MCP servers below from the npm registry | Starting the MCP servers |
| Power BI Modeling MCP server (`@microsoft/powerbi-modeling-mcp`) | npm registry (Microsoft, github.com/microsoft/powerbi-modeling-mcp); in VS Code, Microsoft's extension "Power BI Authoring MCP Server" (`analysis-services.powerbi-modeling-mcp`, server `powerbi-authoring-local`) | MIT (npm package); Microsoft Software License Terms (VS Code extension) | The semantic model open in my Power BI Desktop, over its local port. Changes are made only after I approve them | Model changes (measures, relationships) |
| DAX Lib MCP server (`@daxlib/mcp` 0.1.0, pinned) | npm registry (daxlib.org) | MIT | Reads the public DAX Lib package catalog (daxlib.org, github.com); writes DAX functions into my local Desktop model. Sends no model data | *Optional*: the same packages are kept in the project (below) |
| DAX Lib packages: DaxLib.SVG 2.0.0, DataTides.ColourContrast 0.1.0, DataTides.SignificantChange 0.1.0 | Copies kept in the project (design/udf/vendor), from github.com/daxlib | MIT (notices in design/udf/vendor/NOTICE.md) | Nothing: DAX functions inside the model | Small charts drawn in DAX, colour contrast, outlier tests |
| Deneb custom visual | Microsoft AppSource, **certified** | MIT | Nothing outside the report: certified visuals are reviewed by Microsoft for not calling external services, and the kit's specs load no URLs | *Optional*: every Deneb chart has a native fallback (the build switches with one setting) |
| Git for Windows | git-scm.com or Company Portal | GPL-2.0 | The project folder | Version history of the project |
| VS Code with GitHub Copilot Chat (Agent mode), **or** Claude Code | Company-approved channel | Microsoft / GitHub, or Anthropic commercial terms | Sends my prompts, project files it opens, and aggregate query results to that assistant's service | The assistant |
| Microsoft Edge (already installed) | Windows | Microsoft | Local files; runs headless to draw icons and wireframe previews | Wireframes |

**Network hosts** (HTTPS GET only, unless noted):

- `registry.npmjs.org`, or a company npm mirror: the two MCP servers, at session start.
- `pypi.org` and `files.pythonhosted.org`, or a company PyPI mirror: jsonschema, once (optional).
- `developer.microsoft.com/json-schemas`, `raw.githubusercontent.com`, `learn.microsoft.com`: public Power BI file
  schemas and Desktop release notes, when I refresh them (rare; optional).
- `daxlib.org`, `github.com`: the public DAX Lib catalog (optional).
- AppSource (via Power BI Desktop): the Deneb visual (optional).
- The assistant's own service (GitHub Copilot, or `api.anthropic.com` for Claude Code).
- Wireframe previews can load charting scripts from `cdn.jsdelivr.net`; at work I set them to offline mode, so they
  contact nothing.

**Not requested.** No admin rights, no service accounts, no gateway, no tenant setting changes beyond allowing the
certified Deneb visual (already allowed in our tenant as of 2026-10-24). No uncertified custom visuals: those would
come back to you as a separate request (docs/it-security.md).

**If something is refused**, the kit falls back as follows: no npm registry: DAX Lib from the project copy, but model
changes then need the Modeling MCP from a mirror or the VS Code extension; no Deneb: native charts; no Desktop Bridge:
manual reload; no pip: the kit runs without packages. No Python, PowerShell scripts, Power BI Desktop or Git: the
kit can't run.

Contact: Kyle Burks.
