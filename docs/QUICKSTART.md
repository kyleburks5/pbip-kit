# Quickstart

From a copy of the kit to a finished report. Commands in `bat` blocks run in a Command Prompt in the project folder.
Commands that start with `/` are typed in the assistant's chat.

In GitHub Copilot the chat commands start with `/kit-`: `/kit-brd`, `/kit-model`, and so on. Set up VS Code first
([WORK-SETUP.md](WORK-SETUP.md)).

## 1. Copy the kit

Pick a folder name with no spaces, outside OneDrive. Copy the kit without its Git history and start a new one:

```bat
robocopy C:\path\to\pbip-kit C:\reports\sales-dashboard /E /XD .git _snapshots
cd /d C:\reports\sales-dashboard
git init
git add -A
git commit -m "Start from pbip-kit"
```

## 2. Check the machine

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File tools\doctor.ps1
```

Fix every FAIL line before going on (the line says what to ask IT). WARN lines have a fallback and can stay.
Optional, for extra schema checks:

```bat
python -m pip install --user jsonschema
```

## 3. Add the data

1. Copy the raw source files (CSV, Excel, ...) into `data\`. Git never commits this folder.
2. If the data isn't public, stop and fill in `docs\it-security.md` with the data owner first.
3. Optional: put a wireframe (HTML) or reference images of the report in `design\reference\`.

## 4. Write the requirements

Open the project folder in your assistant (Claude Code, or VS Code with Copilot Chat in Agent mode). Then:

```text
/brd Sales overview for regional managers: revenue and margin vs last year, by region and month
```

The assistant writes `design\reference\brd.md` and lists what it guessed ("confirm") and what it doesn't know
("open"). Read the file, answer the items in the chat, and edit it until it is right.

## 5. Make the Power BI project

1. Open Power BI Desktop. In **File > Options and settings > Options > Preview features**, turn on the Power BI
   project (.pbip) save option, the TMDL format for the semantic model and the PBIR format for the report, if your
   Desktop lists them. Turn on the Desktop Bridge preview feature too, if it is there (it lets the assistant reload
   and screenshot the report).
2. **Get data** from the files in `data\`. Load the raw tables as they are: no relationships or measures yet.
3. **File > Save as**, type **Power BI project (.pbip)**, in the project folder, for example `Sales.pbip`. This
   creates `Sales.Report\` and `Sales.SemanticModel\`.
4. Keep Desktop open. Then download the PBIR schemas once:

```bat
python tools\pbik\pbik.py schemas fetch Sales.Report
```

## 6. Build the model

```text
/model
```

The assistant profiles each table (aggregates only), recommends an audit mode and proposes the core model as one
list: cleaning, relationships, a date table and base measures. It changes nothing yet. Read the list, ask for
changes, then approve it:

```text
/model approved
```

It applies the model through the Modeling MCP, checks every new measure returns a value, writes
`design\reviews\model-check.md` and commits. When it says so, save in Desktop (Ctrl+S).

## 7. Plan the report

```text
/plan clean preset, brand colour #0B5CAD
```

The brief is optional. The assistant writes the colour tokens and theme, `design\specs\layout.json` (every visual with
its ID), `design\specs\spec.md` (with a "done when" line per visual) and `design\specs\audit.json`, then draws the
wireframe. Open it in Edge:

```bat
start msedge "%CD%\design\wireframes\wireframe.html"
```

Press **B** to show the visual IDs. Ask for changes by visual ID ("move P1-V04 under P1-V02") until the wireframe is
right. If the plan needs a fallback (an SVG measure or a custom visual), the assistant asks you first.

## 8. Build the report

Save in Desktop and close it. Then:

```text
/build approved
```

The assistant builds the report files with pbik, validates them, runs the audits, commits, and gives you a numbered
list of Desktop steps. Open `Sales.pbip` again from File Explorer.

## 9. Review

With the report open in Desktop:

```text
/review
```

The assistant screenshots each page, compares it with the wireframe and `design\checks.md`, audits the numbers and
writes a ranked list to `design\reviews\review.md`. It fixes nothing yet.

## 10. Fix

```text
/fix
```

It fixes the high and medium items (or the ones you name: `/fix P1-V04 P2-V01`), reloads, re-checks and commits. It
may propose lessons for the kit: approve or decline each one. Repeat `/review` and `/fix` until the review is clean.

Before every reload: if Desktop shows unsaved changes, close it without saving and reopen the `.pbip`. The assistant
stops when Desktop is "dirty".

## Done when

- `design\reviews\review.md` has no high or medium items.
- `pbik validate` passes: `python tools\pbik\pbik.py validate Sales.Report --layout design\specs\layout.json`.
- The numbers audit (`/validate`) shows every key value matching.
- Every visual meets its "done when" line in `design\specs\spec.md`.

Then save in Desktop, commit, and publish from Desktop as you normally would. The kit never publishes.

More detail on each step: [PLAYBOOK.md](PLAYBOOK.md).
