# Work setup: VS Code with GitHub Copilot

For a work laptop that has VS Code and GitHub Copilot instead of Claude Code. The kit, the workflow and pbik are the
same. What changes: the assistant, how the MCP servers start, and often an older, IT-managed Power BI Desktop.

Once set up, follow [QUICKSTART.md](QUICKSTART.md) with `/kit-` in front of each command. For your first run in Copilot
Chat, with what to expect at each step, see [COPILOT.md](COPILOT.md).

## 1. Get the kit onto the laptop

Clone or copy the kit to a folder with no spaces, outside OneDrive (sync can lock files while Desktop saves). Then
copy it once per report, as in QUICKSTART step 1.

## 2. Run the go/no-go check

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File tools\doctor.ps1
```

It changes nothing. Each line is one of:

- **PASS**: ready as is.
- **WARN**: works, with the fallback printed under it.
- **FAIL**: the kit can't run that step. The line under it says what to ask IT.

It checks Python, pip (or an offline install), jsonschema, pbik, the PowerShell execution policy, Node.js, npx and
npm registry access, the Modeling MCP and daxlib-mcp, Power BI Desktop against VERSIONS.md, compatibility level 1702,
the Desktop Bridge, Deneb, Git, the proxy, the kit folder and the Copilot files. It exits 1 on any FAIL (NO-GO).

Behind a proxy that hangs, skip the network checks with `-Offline`:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File tools\doctor.ps1 -Offline
```

For any FAIL, send IT [IT-REQUEST.md](IT-REQUEST.md) with the FAIL lines. It lists every tool, its licence, what it
accesses and the network hosts it needs.

Common WARN fallbacks:

| WARN | Fallback |
| --- | --- |
| pip can't reach its index | pbik needs no packages. For jsonschema, download the wheels on another machine into `tools\wheels\` and install with `python -m pip install --user --no-index --find-links tools\wheels jsonschema` |
| npm registry blocked | DAX Lib from the vendored copy (`design\udf\vendor\`, below) |
| No Desktop Bridge | Reload and screenshot by hand (the build gives you the steps) |
| Custom visuals blocked | Set `"customVisuals": false` in `design\specs\project.json`: every Deneb visual is built as its fallback |
| Git user not set | `git config --global user.name "<name>"` and `git config --global user.email "<work email>"` |

## 3. Set up VS Code

1. Install the **GitHub Copilot Chat** extension, signed in with your work account.
2. Install Microsoft's **Power BI Modeling MCP** extension (listed as "Power BI Authoring MCP Server"):

   ```bat
   code --install-extension analysis-services.powerbi-modeling-mcp
   ```

3. **File > Open Folder** on the project folder, and trust it when asked. Prompt files, the instructions file and
   `.mcp.json` load only in a trusted workspace.
4. Open Copilot Chat (Ctrl+Alt+I) and pick **Agent** in the mode list under the chat box.

## 4. The Copilot files

| File | What it is |
| --- | --- |
| `.github/copilot-instructions.md` | The kit's rules (CLAUDE.md and `.claude/rules/`), with a short Copilot preamble. Copilot loads it on every chat |
| `.github/prompts/kit-<name>.prompt.md` | One prompt per command: `/kit-brd`, `/kit-model`, `/kit-plan`, `/kit-theme`, `/kit-build`, `/kit-review`, `/kit-fix`, `/kit-validate`, `/kit-smoke`, `/kit-update` |
| `.vscode/settings.json` | Turns off `chat.useClaudeMdFile`, so Copilot doesn't load CLAUDE.md a second time |
| `.mcp.json` | The daxlib-mcp server (pinned to `@daxlib/mcp@0.1.0`) |

The `.github` files are generated. Never edit them. Edit `CLAUDE.md`, `.claude/rules/` or `.claude/commands/`, then:

```bat
python tools\copilot\sync.py
```

`python tools\copilot\sync.py --check` tells you if they are out of step (doctor.ps1 and the tests run it too).

Type `/kit-` in the chat box to see the prompts. The grey hint after a command says what to type. The commands have
the `kit-` prefix because Copilot has its own `/plan`, `/fix` and `/review`.

## 5. Start the MCP servers

The Modeling MCP is the only way the kit changes the model. Its server is **powerbi-authoring-local**, and it can be
stopped when VS Code opens. Check it at the start of each session:

1. Command Palette (Ctrl+Shift+P) > **MCP: List Servers**.
2. Select `powerbi-authoring-local` > **Start Server**. The first time, trust it. **Show Output** shows it starting.
3. In Copilot Chat, open the tools picker (the tools icon in the chat box) and tick the `powerbi-authoring-local`
   tools. Copilot can't see unticked tools.
4. Do the same for `daxlib-mcp` (from `.mcp.json`) if npm is reachable.

`/kit-brd` and `/kit-plan` don't change the model, but `/kit-model` stops without these tools. If **MCP: List Servers**
shows no servers at all, your organisation may restrict MCP: ask IT to allow the Power BI Modeling MCP extension.

### DAX Lib when npm is blocked

daxlib-mcp starts through npx. Where npm is blocked, the same packages are kept in `design\udf\vendor\` with their
licences. `/kit-model approved` installs them through the Modeling MCP instead:

```bat
python design\udf\vendored.py --check
python design\udf\vendored.py DaxLib.SVG --out %TEMP%\DaxLib.SVG.json
```

Details: [design/udf/README.md](../design/udf/README.md), "When npm is blocked".

## 6. Match the work Desktop

A work laptop often runs an older Desktop than the one the kit was tested on. Two settings in
`design\specs\project.json` handle it:

```json
{"targetDesktop": "<work Desktop version>", "catalog": "work"}
```

- **`targetDesktop`**: the work Desktop's version (Help > About). `pbik build` then writes only the file schema
  versions that Desktop can open, and `pbik validate` errors on newer ones. `pbik project show` prints what the
  target resolves to.
- **`catalog`**: the settings catalog `pbik validate` warns from. The **work catalog** (`tools\pbik\catalogs\work.json`)
  lists the settings the work Desktop has saved, so validate warns on settings it has never saved.

Agree a target change before making it. Then make the work catalog once:

1. On a machine with the Patterns project, copy it, set its target to the work version and lower its schemas
   (`pbik schemas lower`), as in [UPDATE-ROUTINE.md](UPDATE-ROUTINE.md), "A catalog for another machine".
2. On the work laptop, open the copy in Desktop, check the Patterns page, and save.
3. Build the catalog from the saved files, and check it:

   ```bat
   python tools\pbik\pbik.py catalog refresh --name work <folder of the saved Patterns copy>
   python tools\pbik\pbik.py catalog list
   ```

4. Commit `tools\pbik\catalogs\work.json`. It holds setting names, value types and the Desktop version: no data.

Until it exists, doctor.ps1 warns and `pbik validate` skips the catalog check.

## 7. Work-safe settings

- **Data.** Aggregates only, unless the data owner clears row-level access in writing. Record each data set in
  [it-security.md](it-security.md).
- **Wireframe offline.** Set `"vega": "offline"` at the top of layout.json, so the wireframe loads nothing from the
  internet when you open it.
- **Custom visuals.** If the tenant blocks them, set `"customVisuals": false` in project.json.
- **Commits.** Copilot commits only at `/kit-model approved`, `/kit-build` and `/kit-fix`, or when you say so.

## 8. If something doesn't work

- A long step stops halfway: reply "continue". Each step can be rerun.
- A prompt shows `${input:...}` or an old name: run `python tools\copilot\sync.py` and reload the window.
- Copilot asks to approve the same command again and again: allow it for the session.
- Copilot can't change the model: check **MCP: List Servers** and the ticked tools (step 5).
- More: [PLAYBOOK.md](PLAYBOOK.md#troubleshooting).
