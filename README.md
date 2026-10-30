# pbip-kit

**Status: v1.0** (2026-10-29). Tests, the regression suite and the setup check pass; the Copilot end-to-end check
is pending and runs at work on the first day ([VERSIONS.md](VERSIONS.md)).

A starting folder for building polished Power BI reports with an AI coding assistant.

You write down what the report must show. The assistant builds the semantic model, plans the pages, draws a
wireframe, builds the report files and checks them against the wireframe and the numbers. You approve each step and
look at the result in Power BI Desktop.

The report is a Power BI Project (PBIP): the report in PBIR format and the model in TMDL, as plain files under Git.
The kit builds and checks those files with its own tool, **pbik** (`tools/pbik/`).

The kit works with **Claude Code** (commands in `.claude/commands/`) or with **GitHub Copilot in VS Code** (the same
commands as prompts in `.github/prompts/`).

## What you need

| Tool | Version | Why |
| --- | --- | --- |
| Windows with PowerShell 5.1 | | the Desktop scripts and the setup check |
| Power BI Desktop | the version in [VERSIONS.md](VERSIONS.md), or newer | building and viewing the report |
| Python | 3.9 or newer | pbik and the design scripts (standard library only) |
| Git | any recent | the kit commits after each step |
| Node.js with npm / npx | 18 or newer | starts the MCP servers (model changes, DAX Lib) |
| Claude Code, **or** VS Code with GitHub Copilot Chat | see VERSIONS.md | the assistant |
| Microsoft Edge | already on Windows | draws wireframes and previews (headless) |
| jsonschema (Python package) | optional | extra schema checks in `pbik validate` |

Check a machine with one command. It prints PASS, WARN (with the fallback) or FAIL (with what to ask IT):

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File tools\doctor.ps1
```

Use public data only, unless your data owner has cleared it ([docs/it-security.md](docs/it-security.md)).

## Where to go next

| Read | When |
| --- | --- |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | You want to build a report now: every command, in order, on one page. |
| [docs/PLAYBOOK.md](docs/PLAYBOOK.md) | You want to know how it works: each command, the visual-method ladder, pbik, themes, patterns, DAX Lib, lessons, Git, updates, troubleshooting and a glossary. |
| [docs/WORK-SETUP.md](docs/WORK-SETUP.md) | You are on a work laptop with VS Code and GitHub Copilot. |
| [docs/COPILOT.md](docs/COPILOT.md) | Your first run in Copilot Chat, step by step. |
| [docs/IT-REQUEST.md](docs/IT-REQUEST.md) | You need IT to allow a tool or a network host. |
| [docs/UPDATE-ROUTINE.md](docs/UPDATE-ROUTINE.md) | Power BI Desktop has updated. |
| [tools/pbik/README.md](tools/pbik/README.md) | You need the full list of pbik commands and layout keys. |
| [VERSIONS.md](VERSIONS.md) | You want the tested versions, releases and changelog. |
| [THIRD-PARTY.md](THIRD-PARTY.md) | You need to know what came from someone else: the test datasets, the Bravo date template, DAX Lib. |
| [CLAUDE.md](CLAUDE.md) | The rules the assistant follows in every session. |

## Folder map

| Path | Holds |
| --- | --- |
| `CLAUDE.md`, `.claude/` | The assistant's rules, commands (`/brd`, `/model`, ...), rule files and Desktop scripts |
| `.github/`, `.vscode/`, `.mcp.json` | The Copilot prompts and instructions (generated), VS Code settings, the DAX Lib MCP server |
| `data/` | Your raw source files (never committed) |
| `design/reference/` | The requirements (`brd.md`), its template, the layout schema, and any wireframe or reference images |
| `design/specs/` | The plan: `layout.json`, `spec.md`, `audit.json`, `project.json` |
| `design/wireframes/`, `design/reviews/` | The wireframe, and the model checks, reviews and audits |
| `design/tokens.json`, `design/themes/` | Colours, fonts and spacing; the Power BI theme and the theme presets |
| `design/templates/`, `design/scripts/`, `design/udf/` | Visual templates, the design and audit scripts, the DAX Lib packages |
| `design/checks.md`, `design/known-gaps.md` | The defect checklist used on every review; what Desktop or pbik can't do, with workarounds |
| `docs/` | These guides, plus lessons, patterns, layout styles, custom visuals and IT notes |
| `tools/` | pbik, the setup check (`doctor.ps1`), the Copilot sync, the Patterns builder, tests, their fixtures (`tools/fixtures/`) and the regression suite |
| `examples/` | Reference material and history; the kit doesn't use it |

## Tests

```bat
python tools\run_tests.py --regression
```

Run it after any change to pbik or the scripts, and after a Power BI Desktop update.
