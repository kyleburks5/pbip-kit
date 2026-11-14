# Phase 1: usability (design, for review)

Goal: someone who has never opened a terminal builds a report by chatting, and moving from the synthetic model to the
published one feels like three clicks. The agent (Claude Code or GitHub Copilot) does everything except the
person-only approvals, which become buttons. Status: design only, nothing built. Builds on
docs/design/synth-to-live.md (batch 3) and the model packs (batch 3 item 15).

**Verify at work** marks what this machine can't prove: a real published model, GitHub Copilot, Power BI Desktop
2.155 (the work version), the team share and IT policy. Those parts are built against made-up connection files and
stubs here, and checked at work from the list at the end.

## 1. Chat-only flow

**What the user sees:** plain sentences: "Your project is set up. The model has 42 tables; 5 things need your OK:
click *Approve the model* (Ctrl+Shift+P, then type *approve*)." No paths, commands, flags, IDs or JSON.

**How:**
- Every pbik command gets `--report json`: a machine summary (`{"ok", "facts", "needs", "next"}`). The agent reads
  that, not the human text, and the command files tell it to answer in plain words from `facts` and `needs`.
  New `docs/PLAIN-WORDS.md`: one plain sentence per message kind (flag kinds, check results, gate names), so both
  agents say the same thing.
- New `pbik project init <name> [--class internal|restricted|public] [--from-pack <pack>]`: copies the kit into a new
  folder beside it (git-tracked kit files only), `git init`, first commit, data class, `.vscode/tasks.json`. Raising
  the class is an agent step; lowering it is a gate (section 2).
- The agent runs on its own: copying references into design/reference/, `model intake` (section 3), synth slice /
  generate / verify, `bind check` / `prepare`, build, validate, roundtrip, tests (fast mode), commits (CLAUDE.md's
  existing commit rules), pack reuse and drift.
- CLAUDE.md and the Copilot instructions get one rule (one in, one out): "run pbik yourself; never show the user a path
  or a command; for a gate, say which button to press and why." The command files (/brd, /model, /plan, /build,
  /review, /fix) end with a plain "what happened / what's next" section built from `--report json`.

## 2. Person-only gates as buttons

Six gates: approve the model (synth approve), approve the name map (bind map approve), approve model drift
(model approve), connect to the live model (bind live), back to the synthetic model (bind local), loosen the data
class (project class, lowering).

**Flow:**
1. The agent prepares: `pbik gate prepare <gate>` writes `.pbik/gates/<gate>.json` (git-ignored) with the plain
   summary (counts, the items that need a person, what happens on Yes) and a hash of what is being approved.
2. The agent tells the user which button to press. It can't press it.
3. The user runs the VS Code task (Command Palette: *Tasks: Run Task* > *Approve the model*, or a key binding).
   The task runs `pbik gate run <gate>`, which shows the summary in a **Windows dialog** (PowerShell
   `System.Windows.Forms`: summary text, *Yes, approve* / *No*) and, on Yes, applies the step with the approver from
   `git config user.name` and the Windows user, the date and the hash. On No, nothing changes.
4. The agent sees the result in `.pbik/gates/<gate>.result.json` and carries on.

**Why a dialog:** both agents run their commands in a terminal; a terminal prompt can be answered by an agent (Copilot
types into terminals), a desktop dialog can't, unless the agent has computer use, which these setups don't grant.
`gate run` also keeps today's refusals (no TTY, `CLAUDECODE` set), and refuses when the prepared hash no longer
matches (the content changed after preparing). Honest limit: this stops an agent approving by accident or on its own
initiative; it isn't proof against a person who scripts around it. Every approval is logged in
`design/reviews/approvals.md` (committed): gate, summary, who, when, hash.

**Status bar:** VS Code has no built-in task buttons. Options: (a) Command Palette and key bindings only (works today,
nothing to install); (b) a tiny local extension in `tools/vscode-gates/` adding status-bar buttons that run the tasks
(needs IT's OK to side-load). Recommended: (a) now, (b) if IT agrees. **Verify at work:** both agents with
`.vscode/tasks.json` (Copilot agent mode can't answer task inputs or the dialog; Claude Code in VS Code the same),
the dialog under the work laptop's PowerShell policy, side-loading if (b).

## 3. Model drop folder

The user drops one of these into `design\reference\model\` (git-ignored): a TMDL folder, a single TMDL script
(`createOrReplace`), a `.SemanticModel` folder, or a TMSL / JSON export (`.bim`, `.json`).

`pbik model intake` (the agent runs it first, before anything else reads the folder):
1. **Data files out first:** deletes `cache.abf`, any `*.abf`, `.pbi\` (local settings and cache), `data\` and any
   `*.pbix` / `*.pbit` (refused: they hold data; ask for a TMDL or PBIP export instead), before any parsing. Deletion
   is permanent (no recycle bin). Lists what it removed in a warning: "Your model folder held a data cache; I removed
   it before reading anything."
2. Detects the format (definition.pbism / `*.tmdl` / `createOrReplace` / JSON with `model.tables`), converts what it
   needs (TMSL to the contract directly; a `.SemanticModel` to its `definition\`), and runs `synth contract`
   (no values, no M code, no connection strings, as today).
3. Writes `design\reference\model\.gitignore` (`*`), and the export check lists the folder as data.

The agent rule (CLAUDE.md and Copilot instructions): never open, list or read `design\reference\model\`; only run
intake. A hook (Claude Code `PreToolUse` on Read/Grep/Glob for that path) enforces it there; Copilot relies on the
rule. **Verify at work:** the Copilot side, and a TMSL export from the work tenant.

## 4. Model packs done right

- **Rule library** `rules/library.json` in the kit (versioned with it): generic rules matched by flag kind and simple
  facts (table name pattern, row count, column names), e.g. "M code: synthesize", "connection: not copied", "RLS: not
  reproduced", "Enter-data table of ≤ 50 rows with a label and an order column: keep rows (a person confirms)",
  "tables named like account / member / customer: entity, synthesize". `synth contract` applies the library first,
  then the pack's own rules.
- **Grouped approval:** the gate summary groups flags: "120 handled by rules, 12 option tables to keep (rows shown),
  5 need you". Only the last group needs a decision per item; the first group is approved as a group (listed in the
  log).
- **Plain explanations:** every flag kind has a one-line explanation and what each resolution means
  (docs/PLAIN-WORDS.md), shown in the dialog and by the agent.
- **Reuse:** "start a new dashboard on model X": the agent finds pack X in the pack folders, runs
  `project init --from-pack`, and if the user dropped a newer TMDL, runs drift; only changes reach the drift gate.
- **Team folder:** `project.json` `packFolders` (a team share first, then personal). Registering to the team folder is
  a gate; the pack records approver, date, kit version and data class (as today). Read access is enough to reuse.
  **Verify at work:** the share path, permissions, and that the export check never sees it (outside every repo).
- **Learning:** after an approval, resolutions a person made that look generic (same kind, no table-specific reason)
  are proposed as library rules; adding them is part of the next kit update (a lesson-like review, never automatic).

## 5. Desktop as the model picker

`bind live` stops taking typed names: the agent prepares `design\reference\live\Pick a model.pbip` (an empty report),
the user opens it in Desktop, picks the published model (Get data > Power BI semantic models), saves and closes;
the *Connect to the live model* gate reads the Desktop-saved `definition.pbir` (`bind live --from`, batch 3) and shows
workspace, model and model ID in plain words before Yes. Typed IDs stay as an expert fallback. Here: tested with
made-up Desktop-shaped connection files. **Verify at work:** a real published model, Desktop 2.155's saved form.

## 6. Token tracking

- `pbik step start|end <step>` (the agent runs them around each workflow step) appends to `.pbik/steps.jsonl`:
  step, start, end, outcome.
- Claude Code: `tools/usage.py` joins the steps with the session transcript's per-message `usage` (input, output,
  cache read/write tokens) by time window and writes `design/reviews/usage.md` (one row per step, totals per build).
- Copilot: premium requests aren't exposed locally; usage.py records the step times and a column for the count from
  GitHub's usage page, filled in by hand. **Verify at work.**
- Targets go in the same file so Phase 2 has a baseline.

## Test plan

**Made-up large model** (`tools/fixtures/big_model.py` writes it, nothing committed but the script): 60 tables, 400
measures (layered: base, ratios, time intelligence, SVG), 20 option tables (Enter data, 2-40 rows), 6 account /
member-like tables, 3 RLS roles, M partitions with invented servers, 2 calculated tables, a field parameter; written
as a TMDL folder, a `createOrReplace` script, a `.SemanticModel` with a fake `cache.abf` and `.pbi\`, and a TMSL
export.

| Area | Test (here) |
| --- | --- |
| Intake | each format detected; fake data files deleted before any parse (a spy on file reads); warning lists them; folder git-ignored; `.pbix` refused |
| Rule library | ≥ 90% of the big model's flags resolved by library rules; option tables and entity tables grouped right; no entity table ever offered keep-rows |
| Grouped gate | summary counts match; the dialog is a stub function in tests (never an environment switch); refusals: agent shell, no TTY, changed hash, No |
| Approval log | one entry per gate with who, when, hash; plain-words text from PLAIN-WORDS.md |
| Chat-only | every command's `--report json` has `facts` / `needs` / `next`; a check that command files never tell the agent to show a path or command |
| Reuse | `project init --from-pack` + drift on a changed big model: only changed tables regenerated; reuse path under 10 minutes of agent time (timed) |
| Picker | bind live from made-up Desktop-shaped `definition.pbir` files (byConnection variants) |
| Usage | usage.py on a made-up transcript and steps file gives the right per-step totals |
| Regression | all suites with `--regression`; export check clean |

**Timing targets** (measured with `pbik step` logs on the big model, a person answering the gates): first setup
(drop model to first build) 30-45 minutes; reuse of a pack (new dashboard to first build) about 10 minutes.

**Verify at work** (one checklist, run on the work laptop): Copilot agent mode end to end (chat-only flow, gates as
tasks, no answer to the dialog); Desktop 2.155 opens the synthetic model and saves the picker report; a real
published model through the picker and `bind live`, then `bind local`; the team pack folder (register, reuse,
permissions); PowerShell dialog policy; Copilot usage numbers; IT's view on the optional status-bar extension.

## Build order (after review)

1. `--report json` and PLAIN-WORDS.md; 2. gates (prepare / run, dialog, tasks.json, approval log); 3. `model
intake`; 4. rule library and grouped approval; 5. `project init` and pack folders; 6. the Desktop picker;
7. `pbik step` and usage.py; 8. big-model fixture and the timing runs; then the work checklist.

## Decisions (review, 2026-11-13)

1. Three data classes stay in pbik; it-security.md drops "synthetic" and calls it "restricted with a synthetic model".
2. Command Palette tasks only; the agent names the exact task to pick. The status-bar extension is a later IT request.
3. Intake deletes data files permanently, logs what it removed, and tells users to drop a copy, never their only file.
4. Team pack folder: a local stub folder here; its location and permissions (only people approved for the model's
   data class may register) are verify at work.
