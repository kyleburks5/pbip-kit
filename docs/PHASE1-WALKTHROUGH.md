# Phase 1 walkthrough (chat and Command Palette only)

Try Phase 1 the way a new user would: everything through the chat and the Command Palette, nothing typed in a
terminal. Made-up data only. Design: docs/design/phase1-usability.md.

**What you need:** VS Code with Claude Code (or GitHub Copilot, verify at work), Power BI Desktop, and the made-up
inputs in `pbik-walkthrough-inputs` beside the kit: a model export with a fake data cache in it, and a made-up
"live pick" standing in for a report Desktop saved connected to a published model. A stand-in team pack folder,
`pbik-team-packs`, sits beside the kit too.

**How to read this:** *You say* is what you type in the chat; *You do* is a click; *Expect* is what should happen.
If the agent ever shows you a path, a command or JSON, or asks you to open a terminal, note it: that's a Phase 1 bug.

## 1. A new project (about 2 minutes)

1. *You do:* in VS Code, File > Open Folder: the kit folder.
2. *You say:* "Start a new report project called Walkthrough Sales. The data is restricted."
3. *Expect:* "Your project Walkthrough Sales is ready (restricted)" and a next step. No paths.
4. *You do:* File > Open Folder: the new **Walkthrough Sales** folder beside the kit. Start a new chat there.

## 2. The model (about 5 minutes)

5. *You say:* "I have a model export to start from. Where do I put it?"
6. *Expect:* the agent opens the model folder in File Explorer and asks you to drop a **copy**.
7. *You do:* copy **Example Big.SemanticModel** from `1 made-up model` into that folder. Tell the agent "done".
8. *Expect:*
   - a warning that the folder held a data cache (2 files) that was deleted before anything read it;
   - the model in counts (66 tables, 400 measures);
   - "87 handled by rules, 20 option tables to keep, 5 need you", with the 5 explained in plain words (small
     typed tables of targets).
9. *You say:* "Make up values for those five." *Expect:* the agent records it and names the next task.
10. *You do:* Ctrl+Shift+P > **Tasks: Run Task** > **Approve the model**.
11. *Expect:* a window titled *Approve the model*: counts, the option tables' rows (Choice 1, Choice 2, ...), and
    *Yes, approve* / *No*.
    - Try **No** first: "Not approved: nothing changed." Run the task again and click **Yes**.
    - Tell the agent "approved". *Expect:* it confirms and moves on.

## 3. A synthetic report (about 15-25 minutes)

12. *You say:* "Plan one page: four KPI cards (Fact Orders Amount, Fact Orders Qty, Fact Orders Avg, Fact Returns
    Amount) and a monthly line of Fact Orders Amount, with a slicer on Option 01."
13. *Expect:*
    - it plans (and shows the wireframe if you ask);
    - it makes the synthetic model and builds the report;
    - it tells you to open the report in Power BI Desktop and click Refresh.
14. *You do:* open the report from File Explorer (the agent can open the folder), click **Refresh**, look, close
    without saving.
15. *Expect:* four even KPI cards, the line chart, and the option slicer in the right order (Choice 1, 2, ...).

## 4. Bind live, dry run (about 5 minutes)

16. *You say:* "Connect the report to the live model."
17. *Expect:* the agent asks you to pick the model in Desktop and opens the live folder. For this dry run there is no
    published model, so:
18. *You do:* copy **Pick.Report** from `2 made-up live pick` into that folder. Tell the agent "saved".
19. *Expect:* "You picked Example Big in workspace Sample Workspace. Run **Connect to the live model**."
20. *You do:* close Desktop, then Tasks: Run Task > **Connect to the live model** > **Yes**.
21. *Expect:* "Connected (a backup is kept)." Don't open the report in Desktop now: the model is made up, so it can't
    connect.
22. *You do:* Tasks: Run Task > **Back to the synthetic model** > **Yes**.
23. *Expect:* "Back on the synthetic model, exactly as before." The report opens in Desktop again.

## 5. Share and reuse (optional, about 10 minutes)

24. *You say:* "Use the team pack folder pbik-team-packs beside the kit, and share this model there."
    *Expect:* the agent names the task.
25. *You do:* Tasks: Run Task > **Share the model pack** > **Yes**.
26. *You say*, back in the kit folder: "Start a new dashboard on model Example Big, called Walkthrough Returns."
27. *Expect:* a new project that starts at the plan step, with no model approval needed. Target: about 10 minutes from
    here to a first build.

**Times to note:** first setup (steps 1-15), target 30-45 minutes; reuse (steps 26 onwards), target about 10.
`tools/usage.py` gives the tokens per step if the agent marked them.

## Verify at work

One checklist for the work laptop. Each item names what can't be proved here.

1. **GitHub Copilot end to end:** the walkthrough above with Copilot agent mode.
   - Copilot answers in plain words (PLAIN-WORDS.md) and never shows a path or command.
   - It can't answer the dialog (record what it does if it tries).
   - The `.vscode/tasks.json` tasks appear under Tasks: Run Task.
2. **The dialog under work policy:** the PowerShell window shows (execution policy, Windows Forms allowed).
   - If PowerShell is locked down, note the message.
3. **Model intake with a real export:**
   - a TMSL export or a TMDL folder from the work tenant;
   - the data files it deletes are listed;
   - the rule library's coverage on a real model (target: 90% handled by rules or option tables).
4. **Desktop 2.155:**
   - opens the synthetic model (calculated DATATABLE tables) and builds;
   - saves a picker report: compare its `definition.pbir` with both forms pbik reads.
5. **A real published model:** pick it in Desktop.
   - **Connect to the live model**, open the report, check the visuals.
   - **Back to the synthetic model**.
6. **Team pack folder:**
   - the shared folder's location;
   - who may share per data class (team.json `registrars`);
   - read access for reuse;
   - that the folder is in no git repository.
7. **Copilot usage:** record premium requests per step from GitHub's usage page in design/reviews/usage.md.
8. **IT, later:** the optional status-bar buttons (a small local VS Code extension) instead of the Command Palette.
