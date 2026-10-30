# Running the kit in VS Code Copilot Chat

For a laptop with GitHub Copilot instead of Claude Code. The prompts in `.github/prompts/` and the rules in
`.github/copilot-instructions.md` are generated from the Claude files (`python tools/copilot/sync.py`); edit the
Claude files, never the generated ones. Setting up the laptop first (doctor.ps1, VS Code, the MCP servers, the work
catalog): docs/WORK-SETUP.md.

Setup checked on VS Code 1.143.1 (2026-10-29): the /kit- prompts are listed; Copilot read and summarised the kit's workflow, visual-method ladder and data-safety rules correctly; powerbi-authoring-local and daxlib-mcp tools are visible once started. **Copilot end-to-end check: pending.** No /kit- command has been run in Copilot yet; `/kit-brd` and `/kit-plan` run at work on the first day (VERSIONS.md).

## What differs from Claude Code

| Claude Code | Copilot Chat (Agent mode) |
| --- | --- |
| `/brd`, `/plan`, `/fix`, ... | `/kit-brd`, `/kit-plan`, `/kit-fix`, ...: Copilot has its own `/plan`, `/fix` and `/review` |
| `$ARGUMENTS` | The text you type after the command. VS Code doesn't fill variables inside a prompt file, so the prompts say "the text after /kit-plan in my message" |
| CLAUDE.md and .claude/rules | `.github/copilot-instructions.md` (the same text, with a Copilot preamble). `.vscode/settings.json` turns off `chat.useClaudeMdFile` so VS Code doesn't load CLAUDE.md a second time |
| Modeling MCP (powerbi-authoring plugin) | Microsoft's **Power BI Modeling MCP** VS Code extension (`analysis-services.powerbi-modeling-mcp`, listed as "Power BI Authoring MCP Server"); its server is **powerbi-authoring-local** and may need starting (below) |
| daxlib-mcp (.mcp.json) | The same `.mcp.json` (VS Code reads it), or the vendored copy if npm is blocked (design/udf/README.md) |
| reports:svg-reviewer and other agents, Data Goblins skills | Not available: Copilot reviews against .claude/rules/svg.md and runs `pbik validate` |

## Before the first run

1. `powershell -NoProfile -ExecutionPolicy Bypass -File tools\doctor.ps1`: no FAIL lines (docs/IT-REQUEST.md for any).
2. Open the kit folder in VS Code (File > Open Folder) and trust it when asked: prompt files, the instructions
   file and `.mcp.json` load only in a trusted workspace.
3. Open Copilot Chat (Ctrl+Alt+I) and pick **Agent** in the mode list under the chat box. The prompts set
   `agent: agent` themselves; an older VS Code that ignores `agent:` (it used `mode:`) runs them in whatever mode is
   picked, so pick Agent anyway.
4. Type `/kit-` in the chat box: the ten kit prompts are listed with their descriptions. If none show, check
   `chat.promptFilesLocations` includes `.github/prompts` (the default), or run **Chat: Run Prompt...** from the
   Command Palette.
5. Start the Modeling MCP before `/kit-model` (next section). `/kit-brd` and `/kit-plan` don't change the model, but
   `/kit-model` stops without it.

## The Modeling MCP in VS Code

The extension's server appears as **powerbi-authoring-local**, and it can be stopped when VS Code opens.

1. Command Palette (Ctrl+Shift+P) > **MCP: List Servers**. Find `powerbi-authoring-local` and read its state.
2. If it is stopped, select it > **Start Server**. The first time, VS Code asks whether to trust the server: trust it
   (it is Microsoft's extension; it reaches only the model open in your Desktop, docs/IT-REQUEST.md). Select it again
   > **Show Output** to see it start without errors.
3. In Copilot Chat (Agent mode), open the tools picker (the tools icon in the chat box) and tick the
   `powerbi-authoring-local` tools. Unticked tools are invisible to Copilot, which then can't make the model changes.
4. Do the same for `daxlib-mcp` (from `.mcp.json`) if npm is reachable; otherwise use the vendored copy
   (design/udf/README.md "When npm is blocked").
5. Then run `/kit-model`. VS Code asks before each MCP tool call; allow them for the session if you like.

Starting servers automatically: the setting **`chat.mcp.autostart`** (experimental in VS Code 1.143.1) starts MCP
servers when you send a chat message:

| Value | What it does |
| --- | --- |
| `newAndOutdated` (default) | starts new servers and servers whose configuration changed, if they aren't running |
| `onlyNew` | starts only servers that have never run |
| `never` | never starts them: start each one from **MCP: List Servers** |

A server that has run before and was stopped is neither new nor outdated, so it stays stopped even with the
default. That is why `powerbi-authoring-local` can be stopped: check **MCP: List Servers** at the start of each
session. The kit doesn't set `chat.mcp.autostart` in `.vscode/settings.json`; leave it at the default. If
**MCP: List Servers** shows no servers at all, your organisation may restrict MCP (`chat.mcp.access`, or
`chat.mcp.allowManagedServersOnly`, set by policy): ask IT to allow the Power BI Modeling MCP extension.

## Dry run: /kit-brd

1. Put the source files in `data/` (public data only) and any reference images or notes in `design/reference/`.
2. In the chat box: `/kit-brd Sales overview for regional managers: revenue and margin vs last year by region and
   month; data/sales.csv`. The grey hint after the command (`argument-hint`) says what to type.
3. Copilot reads CLAUDE.md, the template and docs/it-security.md, lists `data/` (names and sizes), and writes
   `design/reference/brd.md`. It asks before running any terminal command: allow each one (or allow
   `python` and `git` for the session).
4. Expect: a reply with the "open" and "confirm" items in under 15 lines, and a new `design/reference/brd.md`.
   Check the response's **References** list shows `.github/copilot-instructions.md` (the rules were loaded).
5. Review brd.md and answer the open items in the chat. Nothing is committed: commits happen only at
   `/kit-model approved`, `/kit-build` and `/kit-fix`, or when you say so.

## Then /kit-model (needed before /kit-plan)

`/kit-plan` reads the model and model-check.md, so run `/kit-model` first with the raw tables loaded in Desktop.
First check **MCP: List Servers**: `powerbi-authoring-local` running and its tools ticked ("The Modeling MCP in
VS Code"). Copilot proposes the model and stops; `/kit-model approved` applies it through that server (VS Code asks
to allow each MCP tool call).

## Dry run: /kit-plan

1. Desktop open with the model (for the wireframe numbers). Without it, the plan says so and draws the wireframe with
   sample shapes (`--data none`).
2. `/kit-plan bento preset, brand colour #0B5CAD` (or nothing: the clean preset).
3. Copilot works through the eight steps without asking for approval first: the Design ambition table in
   `design/specs/spec.md`, tokens and theme (`gen_tokens.py`, `gen_theme.py`), `design/specs/layout.json`, the
   wireframe (`wireframe_data.py --port auto`, then `gen_wireframe_hf.py`), the rest of the spec, `audit.json`, and
   the checks (`audit_ids.py`, `check_contrast.py`).
4. Expect: a summary under 15 lines; `design/wireframes/wireframe.html` to open in Edge (B toggles ID badges).
   If design/specs/project.json has `customVisuals: false`, Deneb visuals are planned as their fallbacks.
5. Review the wireframe, then `/kit-build approved` when it's right.

## If something doesn't work

- A long step stops halfway (Copilot's request limit): reply "continue"; the prompts are written so a step can be
  rerun.
- A prompt shows `${input:...}` or an old `/plan` name: the prompts are out of date; run
  `python tools/copilot/sync.py` and reload the window.
- Copilot asks to approve the same command over and over: allow it for the session from the approval box.
- Note what went wrong by step and command name in design/reviews/ and propose a lesson (docs/lessons/README.md).
