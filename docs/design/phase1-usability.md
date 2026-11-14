# Phase 1: usability (design)

Goal: someone who has never opened a terminal builds a report by chatting, without asking the maintainer anything,
and moving from the synthetic model to the published one is one approval window. The agent (Claude Code in the
Claude desktop app or VS Code, or GitHub Copilot) does everything except the person-only approvals.

Status: **Part A (v1.7 revision) approved 2026-11-13 (decisions in A14); built in stages (A13).** Part B is Phase 1 as built (stages a-f,
commits 8291638 to 0d5937e); where v1.7 changes it, Part B says so. Templates, patterns, style and checks don't change
in v1.7: it changes how a person moves through the steps.

**Verify at work** marks what this machine can't prove: a real published model, GitHub Copilot, Power BI Desktop
2.155 (the work version), the team share and IT policy. Those parts are built against made-up files and stubs here,
and checked at work from the list at the end.

---

# Part A: v1.7 revision

## A1. The main flow in one picture

```
 Start                      Plan as a picture             Build                         Result
 "I want a dashboard"  -->  wireframe preview +      -->  theme, build, checks,    -->  before/after screenshots,
 + whatever they have       KPI/measure list +            polish (guided: pause         polish score, what it
 (kit picks the path)       assumptions; OK or            after each stage;             couldn't fix,
                            "change X"                    quick: no pauses)             "Switch to live?" window
```

A person answers at most: what the report is for (only with no wireframe or report), the plan picture (OK or
changes), the model approval window (first use of a model only), and "Switch to live?". Everything else is a default
shown in the plan picture.

## A2. Start: the kit picks the path (item 1)

**What the user sees:** "I want a dashboard for X" plus anything they have. The agent opens the project's
**inputs folder** in File Explorer if they have files ("drop a copy here"); a picture attached in the chat works too
(the agent reads it and asks for a copy in the folder only if it must keep it).

**How:** new `pbik start detect` reads the inputs folder (never the model folder) and returns one path:

| Given | Path | Uses (exists today) |
| --- | --- | --- |
| HTML wireframe | from wireframe | ref_layout.py reads it into layout.json |
| Image: wireframe or a screenshot of any report | from picture | the agent writes a boxes file, ref_layout.py maps it |
| Existing report: a `.Report` folder | from report | **new** `pbik layout from-report`: PBIR pages and visuals to layout.json (positions snapped to the grid, IDs given in reading order, fields kept as names) |
| Existing report: screenshots only | from picture | as above, one page per screenshot |
| Requirements only (text, Markdown, Word) | starter layouts, pre-filled from the requirements | below |
| Nothing | starter layouts | below |

Several inputs: a wireframe or report wins over requirements (the requirements fill the KPI list and assumptions).

**Model:** the agent looks for a model in the model drop folder by running `model intake` (Part B3, unchanged). Intake
now also computes a **model fingerprint** (table and column names, no values) and matches it against the pack folders
(Part B4): a match loads that pack, so the model approval window doesn't appear again (only drift reaches it).
**Data class:** from the pack; otherwise restricted. The plan picture shows it; lowering it stays a gate.

**No wireframe or report (starter layouts):** one open question, "What should this report help people decide?",
then 2-3 starter layouts shown as pictures, each a combination of the kit's existing page layouts
(docs/layouts/) and patterns (docs/patterns/), no new patterns:

- **Executive summary:** headline banner, 4 two-KPI cards with comparisons, one trend, one ranked bar.
- **Trend dashboard:** KPI strip, a large trend with a range band, small multiples by one category.
- **Detail table:** filters rail, an exception list, a ranked bar table.

They live as three layout.json fragments in `docs/layouts/starters/` with a slot per KPI; the agent fills the slots
from the answer, the requirements and the model's measures, and draws each with gen_wireframe_hf.py as a PNG. The
user picks one ("the second") and adjusts in plain words ("swap the trend for a table", "add a region slicer").
Fully generated wireframes from detailed requirements stay in v1.8 (A12).

## A3. Plan as a picture (item 2)

Replaces the separate BRD document and the CONFIRM questions in the main flow (the BRD template and `/brd` stay for
anyone who wants them, so no workflow step is removed and v1.7 stays a minor release).

**What the user sees:** the rendered wireframe (high-fidelity, from gen_wireframe_hf.py as a PNG: shown in the chat
where the app shows pictures, otherwise opened beside the chat) and a short list:

```
Page: Sales overview: "Are we on track this month, and where are we behind?"
KPIs                         Measure            Compared with
  Revenue                    [Total Revenue]    same month last year
  Orders                     [Order Count]      target
Assumptions (say "change ..." to change any)
  - "Total" means [Total Revenue], not [Gross Revenue]  (2 candidates found)
  - red/green only for vs target; trend line in the brand colour
  - default date: latest full month; slicers start cleared
  - fallback: status pills in the table as an SVG (a native table can't draw chips)
Build: quick build   Data: restricted   Model: Example Big (pack, approved 2026-11-10)
```

The user replies OK or asks for changes in plain words; the agent updates layout.json, redraws, and shows it again
until OK. On OK the kit stores the picture's hash in the project status file (A7): the build compares against that
picture.

**Fallbacks:** CLAUDE.md requires asking before a fallback. The plan list names each one with the native option
tried, so OK on the plan is that approval; a fallback found later during the build is a stop (A5).

**Page purpose:** a short "Page purpose" section (the sentence per page, who it's for, the decision) is still
written into design/specs/spec.md for the wrap-up and the numbers audit.

## A4. Two build options (item 4)

Same steps, same approvals, templates, plain words, progress list and files; only the pauses differ.

- **Guided build:** "We build it together, one step at a time." Pauses after each stage for a look: page purpose,
  plan, theme, build, checks, polish. Today's step-by-step approach, in plain words, without the terminal.
- **Quick build:** "Tell me what you want, approve the plan, and I'll build it." Pauses only at the plan picture
  (and the gates); then theme, build, checks and polish on its own, and the result.

**Asking:** once, at the start, in plain words, batched with any other question ("Guided build or quick build?"
with the one-line description of each). Not asked when a default exists; then the default is shown in the plan
picture and changeable there.

**Default:** guided build until quick build has reached 7/10 on that report type (A6), then the user's last choice,
or the team default if a team pack folder has `team.json` `defaultMode` (full team presets are v1.8).
Report type = the start path plus the starter layout (from wireframe, from picture, from report, executive summary,
trend, detail table).

**Switching anytime:** "switch to guided" pauses from the next stage; "finish the rest quickly" drops the remaining
pauses. The status file records the switch.

**Learning:** every build records its mode, report type, polish score, interactions and hand-polish minutes
(A6) in a personal history, `%USERPROFILE%\.pbik\builds.jsonl` (no data, no names of tables or measures). If the last
3 quick builds of a type average below 7 or below the guided builds of that type, the start says: "Quick builds of
detail tables have scored lower (5.7 vs 8.0); I suggest a guided build." The user's choice still wins.

## A5. Build, checks and polish (item 3)

1. **Theme** (tokens and theme, as /theme), **build** (`pbik build`), **checks** (`pbik validate`, audit_layout.py,
   audit_ids.py), each followed by its check; a failed check gets one fix and one recheck.
2. **Before screenshot:** the agent opens the report in Desktop on the synthetic model and screenshots each page
   through the Desktop Bridge.
3. **Polish:** up to two rounds of review and fix (today's /review and /fix): compare the screenshot with the approved
   picture and design/checks.md, fix, rescreenshot.
4. **Stop only if unsure:** a check still failing after its fix, a fallback not in the plan, a measure the plan
   didn't name, two measures that fit one KPI, a gate, a Desktop or bridge failure. The stop is one plain question,
   with the default it would take.
5. **Result:** before/after screenshots, the polish score (A6), and anything it couldn't fix, each with the click
   steps in Desktop (design/known-gaps.md). Then the **Switch to live?** window (the bind-live gate, A8): with a
   pack that knows its published model, the window shows it; otherwise the agent first asks the person to pick it in
   Desktop (Part B5).

**Model approval** appears only the first time a model is used, as one grouped window (Part B4, unchanged).

**Desktop housekeeping:** the rules stay (never reload with unsaved changes; close without saving and reopen after
the agent edits report files). Who closes Desktop is decision D1. Without the Desktop Bridge (exit 3), screenshots
are by hand and the fidelity item of the score is "not checked" (counts as 0, said plainly).

## A6. Polish score (item 9)

Shown on every build's final screen and in the wrap-up. Ten pass/fail items, one point each:

| # | Item | How it's checked |
| --- | --- | --- |
| 1 | Layout matches the approved picture | page positions vs the approved layout.json, and the screenshot vs the picture (agent-judged, named as such) |
| 2 | Alignment and spacing | audit_layout.py (grid, margins, gutters) |
| 3 | KPI cards filled | a DAX query: every card's measure returns a value in the default state |
| 4 | Right visual types | built types vs the approved plan |
| 5 | Right measures | bound fields vs the plan's KPI list |
| 6 | Fonts and colours | theme and tokens only (validate's hardcoded-colour and font checks) |
| 7 | Interactions working | slicers filter their visuals (DAX with and without the filter), buttons and bookmarks target real pages |
| 8 | No overlaps or clutter | audit_layout.py overlaps, visuals per page within the pattern's budget |
| 9 | Accessibility | A-01 to A-05 without warnings, or excepted by ID |
| 10 | No validate errors | `pbik validate` |

**v1.7 walkthrough revision (2026-11-14):** five more checks, the polish a person notices, so the score is honest:
11 KPI cards read well (they fill their space; the change line readable, ▲ / ▼, green / red by direction), 12 numbers
read well (thousands separators, number headers over their numbers, "vs" columns coloured), 13 charts read well
(months in month order, straight lines), 14 text sized for the 1920 canvas, 15 a finished look (a header band with
the filter in it). Fifteen checks, shown out of 10: the walkthrough's page scores 6/10 (9 of 15) where the ten gave 8;
rebuilt with the polish defaults (`pbik layout polish`, the theme) it scores 9/10 on the files.

Plus **hand-polish minutes**: at wrap-up, one optional question, "How many minutes did you spend tidying it in
Desktop?" (0 if none). Target: 7/10 before showing colleagues; below that, the final screen says so and lists the
failing items. `pbik score` computes items 2-10 from the files and queries; the agent records item 1.

## A7. Same chat, project status (item 6)

**No forced chat or app switch:** `project init` creates the project inside the open folder, in `projects\<name>\`
(git-ignored by the kit, its own git repository), so the agent keeps working in the same chat, inside its permitted
folder, and VS Code shows it in the Explorer. pbik takes `--in <name>` before the command (the agent passes it;
the person never sees it). Where the project sits is decision D2. Pack folders can be the person's own settings
(`model packs --add-folder`), so every new project finds them and no machine path is committed.

**Project status file:** `design/status.json` (committed, no data): path taken, mode, report type, model pack, data
class, approved plan hash, stage done and stage next, last polish score. `pbik status` gives the plain line. Rule for
both agents: at the start of any chat, run `pbik status` and say "You're at *build*; next is *checks*." With several
projects, it lists them with their stage and asks which (or takes the last one used).

The only place a path appears: telling the user where their project is, with an offer to open it in File Explorer.

## A8. Gates launched by the agent (item 5)

Works the same in the Claude desktop app, Claude Code in VS Code and Copilot. Command Palette tasks stay as an
optional extra.

**Flow:**
1. The agent prepares the gate (`pbik gate prepare`, as today: summary and hash).
2. The agent opens the window itself: `pbik gate open <gate>` starts the Windows dialog as a separate process and
   returns at once; `pbik gate wait <gate>` waits (up to 30 minutes) for the result file.
3. The window shows the summary, a **4-character code drawn as a picture** (not text: screen readers of other
   programs and UI Automation can't read it), a box to type it, and *Yes, approve* / *No*. Yes needs the code;
   three wrong tries close the window with nothing changed. The code is made in the dialog process and never written
   to a file, stdout or the log.
4. On Yes the step is applied as today (approver, date, hash, approval log). The agent reads the result and says what
   happened and what's next.

**Refusals:** the content changed after preparing (hash); screen control active (below); another gate window open.
The old refusal "in an agent's shell (CLAUDECODE)" goes: launching is now the agent's job, and the safety is that
only a person at the screen can read the code and click.

**Screen control (computer use):** there is no reliable system-wide signal. What the kit can do:
- Claude Code: a `PreToolUse` hook on the computer-use tools writes a session marker; `gate open` refuses while
  the marker is fresh: "Screen control is on in this chat. Turn it off, then ask me again."
- Copilot in VS Code has no screen-control tool today; nothing to detect.
- Anything else (another screen-control app): not detectable; the window says so plainly and the typed code is the
  only protection.

**Honest limit:** the code stops an agent approving by accident, on its own initiative, or by sending a key press;
an agent with screen control can read the picture, which is why it refuses when it can tell. It isn't proof against a
person who scripts around it. The Claude Code hook also blocks shell commands that drive windows (SendKeys, UI
Automation) while a gate window is open; Copilot relies on the rule. **Verify at work:** the window from the Claude
desktop app's shell, VS Code's terminal and Copilot's terminal under the work PowerShell policy.

## A9. Plain words and few questions (items 7, 8)

- PLAIN-WORDS.md and grouped summaries by default. No slash commands, paths or commands in replies (exception in A7).
  Never suggest "/model" after a model export: intake's `next` says "I'll read the model now". After every step,
  one line: what happens next.
- Ask only what only the user knows (the decision the report serves, what a KPI means when the model can't say, the
  hand-polish minutes) or what a gate needs; batch questions in one message; everything else is a default in the
  plan picture, changeable in one reply.
- **Interaction target:** 5 or fewer per quick build, 3-4 with a model pack. An interaction is a reply from the person
  or a gate window. Counted by the agent (`pbik step note --interaction`; Claude Code: checked against the
  transcript by usage.py).

  | Quick build, new model | | Quick build, with a pack | |
  | --- | --- | --- | --- |
  | 1 | request and inputs | 1 | request and inputs |
  | 2 | batched answers (mode, anything only they know) | 2 | plan OK |
  | 3 | model approval window | 3 | Switch to live? |
  | 4 | plan OK | (4) | one change to the plan |
  | 5 | Switch to live? | | |

  Desktop closing (D1) and hand screenshots without the bridge add to this; the count says so.
- A test checks command files and PLAIN-WORDS.md: no slash command, path or command in any user-facing sentence,
  no "/model" suggestion after intake.

## A10. The model-folder guard when the working folder changes (item 10)

**Bug:** the hook runs `python tools/hooks/guard_model_folder.py` by a relative path. When the agent's working folder
changes (a project in `projects\`, a `cd`), Python can't find the script, the hook errors, and Claude Code treats a
hook error as non-blocking: the guard silently stops guarding.

**Fix:** the hook command uses the project folder (`$CLAUDE_PROJECT_DIR`) and the script fails closed (any error on a
tool call that names a model folder blocks it). The path match already covers any `design\reference\model` in any
project; relative paths are resolved against the event's `cwd`, so `..\model\x` from `design\reference` is caught.
Tests: run the hook from three working folders (kit, a project, a temp folder) on Read, Glob and a shell command.
**Verify:** `$CLAUDE_PROJECT_DIR` expansion on Windows in the desktop app and in VS Code; if it fails there,
`project init` writes the absolute path into `.claude/settings.local.json`.

## A11. Walkthrough and how-tos (item 11)

docs/PHASE1-WALKTHROUGH.md is rewritten for the Claude desktop app, Claude Code in VS Code and Copilot (one column of
differences, Copilot marked verify at work):

1. One project, one made-up model, one made-up wireframe (HTML) of one page.
2. **Run A, guided build** from the wireframe; **Run B, quick build** of the same page in a second project. A table
   compares polish score, interactions, minutes, and hand-polish minutes.
3. **Run C, no wireframe:** "What should this report help people decide?", the starter pictures, pick and adjust,
   quick build.
4. Switch to live (dry run, as today) and back.

Where the made-up inputs are: `pbik-walkthrough-inputs` beside the kit gets `3 made-up wireframe` and
`4 made-up requirements` next to the existing model and live pick; the doc names each. **How-tos** (a short section
in QUICKSTART.md and the walkthrough): one paragraph for guided build, one for quick build, in the words of A4.
The colleague test (docs/PHASE1-COLLEAGUE-TEST.md) switches to quick build with a model pack and records the
interaction count.

## A12. Later (v1.8, design only)

- **"Where am I?":** any time, a picture of the progress list with the current stage marked (builds on A7).
- **Undo:** "undo the last change": each stage is a commit, so undo is a revert of the last stage's commit after a
  plain summary of what goes back (never across a gate).
- **Richer progress list with time estimates:** per stage, from the personal history's median times.
- **Team presets:** in the team pack folder: theme, chosen patterns, starter layouts, default mode, model packs;
  never data. Registering a preset is a gate.
- **Generated wireframes from detailed requirements:** requirements to a full layout, beyond the starters.

## A13. Release v1.7: stages

One commit per stage; tests on the large made-up model (tools/fixtures/big_model.py); related suites after each stage;
a short report after each stage, continuing unless something needs a decision.

| Stage | Items | What | Tests |
| --- | --- | --- | --- |
| a | 10, 6 | guard fix; `projects\` inside the open folder, `--in`; `design/status.json`, `pbik status` | hook from 3 working folders; status after each stage; a new chat's first line |
| b | 5 | `gate open` / `gate wait`, code as picture, refusals, screen-control marker hook | dialog stub; wrong code x3; changed hash; marker; no file holds the code |
| c | 7, 8 | PLAIN-WORDS updates, question rules, interaction counting | user-facing text check; interaction counts on a scripted run |
| d | 1 | `start detect`, `layout from-report`, fingerprint and pack match, starter layouts | each input kind detected; big-model report round trip; pack matched by fingerprint |
| e | 2 | plan picture (PNG + list), plan hash, fallbacks in the plan, page purpose | picture redrawn after a change; hash recorded; fallback listed |
| f | 3, 4, 9 | guided/quick modes, stops, `pbik score`, build history and suggestion | both modes on the big model; score items on seeded faults; suggestion rule |
| g | 11 | walkthrough, how-tos, colleague test, CLAUDE.md and Copilot sync | doc checks; sync |

At the end: full suite with `--regression`, export check, the updated walkthrough, the verify-at-work checklist.
Not pushed. CLAUDE.md changes (one in, one out): the Workflow section describes the main flow and the two build
options, the approval gates line names the plan picture instead of brd.md and /build approved; Copilot files synced.

## A14. Decisions (review, 2026-11-13)

- **D1. Closing Desktop.** The agent may close the Desktop window for this report only when a check proves the only
  unsaved changes are Desktop's own reload marks (the report files on disk match what the agent last built, and the
  Bridge's state shows no change since the agent's last reload). Any doubt, or any change by the person: it never
  closes it, and asks the person instead.
- **D2. Projects folder** `projects\<name>\` inside the open folder: the kit git-ignores `projects/`, each project
  keeps its own git repository, and the export check fails if any file under `projects/` is ever tracked by the kit.
- **D3. Polish item 1** stays the agent's own judgment, labelled "agent-judged".
- **D4. Copilot in VS Code is the main work environment** (A15).

## A15. GitHub Copilot in VS Code (the main work environment)

The whole flow works there, not only the gates: start, plan picture, guided and quick build, progress, approvals,
switch to live. Copilot follows the same rules through its instruction and prompt files (.github/copilot-instructions.md
and .github/prompts/, generated from CLAUDE.md, .claude/rules and .claude/commands by tools/copilot/sync.py), so it
uses the same plain words, status line and question rules.

- **Prompts:** new `.github/prompts/kit-start.prompt.md` (the main flow: detect, plan picture, guided or quick build)
  and `kit-status.prompt.md` ("where am I"), mirrored from `.claude/commands/start.md` and `status.md`. A person never needs to
  type one: the instructions tell Copilot to follow the start flow when someone asks for a dashboard.
- **Pictures:** the plan picture and the result screenshots are PNG files. Copilot chat shows an image only when it is
  attached, so the agent opens each PNG beside the chat in a VS Code editor tab (`code <png>` from its terminal, the
  same in Claude Code in VS Code), and says in one line what it shows. In the Claude desktop app the agent shows it in
  the chat.
- **Approvals:** `gate open` runs from Copilot's terminal like any command (A8).
- **Progress:** `pbik status` in every new chat (A7); the progress list is the status file's stages.
- **Verify at work:** every Copilot part (no Copilot here): the prompts listed, a quick build end to end, images
  opened beside the chat, the approval window from Copilot's terminal, the status line in a new chat.

## A16. The 14 walkthrough notes, mapped

| # | Note | Fixed by |
| --- | --- | --- |
| 1 | Walkthrough written for VS Code only; the desktop app has no tasks | A11 (three apps), A8 (window opened by the agent, no tasks needed) |
| 2 | Next step says "say what the report is for (/brd)", walkthrough skips it | A2, A3 (no BRD in the main flow; init's next line names the start flow in plain words) |
| 3 | "/brd" is a slash command a new user won't understand | A9 (no slash commands in replies; a test checks init and every `next`) |
| 4 | The new project is a separate folder, so the rest is another chat | A7 (projects inside the open folder, same chat) |
| 5 | "Ready" doesn't say where; the agent couldn't open the folder outside its own | A7 (location stated with an offer to open; inside the agent's folder) |
| 6 | Had to ask for the folder's location twice | A7 (the ready message states it once, unasked) |
| 7 | Walkthrough doesn't say where the made-up model folder is | A11 (each made-up input named with its place) |
| 8 | Model reply listed 112 items by kind; the 5 unexplained | A9 (grouped summaries by default: intake's facts lead with the grouped line and the plain reasons) |
| 9 | Serious: told to run /model after a model export | A9 (intake's next line; a test forbids "/model" in intake output and PLAIN-WORDS) |
| 10 | Said option tables are confirmed by typing a row count; walkthrough says click Yes | A8 (the window's typed code is the only typing; plain words fixed) |
| 11 | Model-folder guard breaks when the working folder moves | A10 |
| 12 | /model mentioned again, unasked | A9 (as 9; the rule covers every reply) |
| 13 | Serious: no way to run approvals in the desktop app without a terminal | A8 |
| 14 | A new chat in VS Code doesn't know what happened | A7 (status file and `pbik status` in every new chat) |

## A17. Walkthrough revision (2026-11-14): one folder = one project, two drop folders, plain approvals

Replaces the projects-folder approach of A7 and D2. The person copies or clones the master kit into a new folder and
opens it; that folder is the project (no projects subfolder, no second folder, no chat switch). On first run
`pbik project setup` turns the copy into the project: its own git, data class, status file, the master-only files
removed, and two plainly named drop folders, **Model** (the semantic model export, git-ignored, data files deleted
before reading) and **Reference** (wireframe, screenshot, requirements or an existing report, git-ignored).
`pbik start check` says at the start of every build, one line per folder, what it holds and what is missing; the agent
never opens File Explorer and asks for a missing file by folder name; an empty Reference folder means the one open
question and the starter layouts. Approval windows are a plain Yes / No, in front of other windows; the typed code
appears only when screen control is active. The export check fails if a project or a filled drop folder sits inside
the master kit. The walkthrough, how-tos and QUICKSTART say "copy the kit, open the folder, put your model in Model".
The plan picture is the fast preview (example values, never data); after the build a real Desktop screenshot is
compared with the approved preview.

---

# Part B: Phase 1 as built (stages a-f)

## B1. Chat-only flow (stage a)

- Every pbik command takes `--report json`: `{"ok", "facts", "needs", "next"}`. The agent answers in plain words
  from it (docs/PLAIN-WORDS.md: one plain sentence per message kind).
- `pbik project init <name> [--class ...] [--from-pack <pack>]`: a new project from the kit (git-tracked kit files),
  `git init`, first commit, data class, `.vscode/tasks.json`. **v1.7:** created in `projects\<name>\` (A7, D2).
- The agent runs intake, synth, bind checks, build, validate, roundtrip, tests and commits itself.

## B2. Person-only gates (stage b)

Six gates: approve the model, approve the name map, approve model drift, connect to the live model, back to the
synthetic model, loosen the data class. `gate prepare` writes the summary and hash; the person runs the Command
Palette task; `gate run` shows a Windows Yes/No dialog and applies the step; the approval log
(design/reviews/approvals.md) records gate, summary, who, when, hash. **v1.7:** the agent opens the window and a
typed code is needed (A8); the tasks stay as an extra.

## B3. Model drop folder (stage c)

`pbik model intake` deletes data files first (`*.abf`, `.pbi\`, `data\`; `.pbix`/`.pbit` refused), detects the format
(TMDL folder, `createOrReplace` script, `.SemanticModel`, TMSL/JSON), writes the contract, git-ignores the folder. The
agent never opens the folder; a Claude Code hook enforces it. **v1.7:** intake also fingerprints the model (A2); the
hook fix (A10).

## B4. Model packs (stage d)

Rule library (`rules/library.json`) applied before the pack's rules; grouped approval ("120 handled by rules,
12 option tables to keep, 5 need you"); plain explanations per flag kind; reuse with automatic drift; pack folders
(`project.json` `packFolders`, team share first); registering to the team folder is a gate; generic resolutions
proposed as library rules at the next kit update. **v1.7:** a pack is found by fingerprint (A2).

## B5. Desktop as the model picker (stage e)

The person picks the published model in Desktop in an empty "Pick a model" report; the *Connect to the live model*
gate reads the saved `definition.pbir` and shows workspace, model and model ID before Yes. Typed IDs stay an expert
fallback.

## B6. Token tracking (stage f)

`pbik step start|end <step>` logs to `.pbik/steps.jsonl`; `tools/usage.py` joins it with the Claude Code transcript
into design/reviews/usage.md; Copilot's premium requests are entered by hand. **v1.7:** steps also carry the
interaction count (A9).

## Test plan (Phase 1, kept)

The made-up large model (`tools/fixtures/big_model.py`: 60 tables, 400 measures, 20 option tables, 6 entity tables,
3 RLS roles, invented M sources, calculated tables, a field parameter; four export formats with fake data files)
backs every suite. Timing targets: first setup 30-45 minutes; reuse of a pack about 10 minutes.

## Verify at work (one checklist, on the work laptop)

Phase 1: Copilot agent mode end to end; Desktop 2.155 opens the synthetic model and saves the picker report; a real
published model through the picker, then back; the team pack folder (register, reuse, permissions); PowerShell
dialog policy; Copilot usage numbers.
v1.7 adds: the gate window opened by the agent from the Claude desktop app, Claude Code in VS Code and Copilot; the
typed code under the work PowerShell policy; the guard hook's project-folder path on Windows in both Claude apps;
a project in `projects\` opened in the same chat in all three; a quick build with a team pack in 3-4 interactions.

## Decisions (review, 2026-11-13, Phase 1)

1. Three data classes stay in pbik; it-security.md calls the synthetic case "restricted with a synthetic model".
2. Command Palette tasks; the status-bar extension is a later IT request. (v1.7: the agent opens the window; tasks
   stay as an extra.)
3. Intake deletes data files permanently, logs what it removed, and tells users to drop a copy.
4. Team pack folder: a local stub here; its location and permissions are verify at work.
