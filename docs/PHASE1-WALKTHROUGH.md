# Walkthrough (v1.7): one folder per project, guided build, quick build, and no wireframe

Try the kit the way a new user would: everything through the chat, nothing typed in a terminal. Made-up data only.
Design: docs/design/phase1-usability.md (Part A). One folder = one project: you copy the kit to a new folder and open
that folder; it becomes the project.

## What you need, and where the made-up inputs are

- One of: the **Claude desktop app** (Code tab), **Claude Code in VS Code**, or **GitHub Copilot in VS Code** (the main
  work environment: verify at work).
- Power BI Desktop.
- The made-up inputs in the folder **pbik-walkthrough-inputs**, beside the kit folder (same parent folder). The kit
  makes them with `tools/walkthrough/make_inputs.py`, so they always fit together (the maintainer runs it once):

  | Folder | What | Goes in | Used in |
  | --- | --- | --- | --- |
  | `1 made-up model` | **Example Big.SemanticModel**, a made-up model with a fake data cache in it on purpose | the project's **Model** folder | Runs A, B, C |
  | `2 made-up live pick` | **Pick.Report**, standing in for a report Desktop saved connected to a published model | where the assistant asks | Part 5 |
  | `3 made-up wireframe` | **Orders overview.html**, one page on the made-up model's names (four KPIs, orders by month, orders by region, a regions table) | the project's **Reference** folder | Runs A and B |
  | `4 made-up requirements` | **Requirements.md**, a short brief with no layout | the project's **Reference** folder | Run C |

  They match: orders link to regions and channels in the model, so the example change in step 10 works.
- A stand-in team pack folder, **pbik-team-packs**, beside the kit too.

**How to read this:** *You say* is what you type in the chat; *You do* is a click or a copy in File Explorer;
*Expect* is what should happen. If the assistant ever shows you a path, a command, a slash command or JSON, asks you
to run anything, opens File Explorer windows by itself, or passes on a raw error, note it: that's a bug. If it goes
quiet for more than a minute on a long step, note that too. Count your interactions (each message you send and each
approval window) for the table at the end.

## The three apps

| | Claude desktop app | Claude Code in VS Code | Copilot in VS Code (verify at work) |
| --- | --- | --- | --- |
| Open the project | pick the project folder for the session | File > Open Folder: the project folder | File > Open Folder: the project folder; Copilot Chat in agent mode |
| Pictures (plan, screenshots) | shown in the chat | opened beside the chat as editor tabs | opened beside the chat as editor tabs |
| Approval windows | the agent opens them: plain Yes / No (a code only while computer use is on in that chat) | the agent opens them: plain Yes / No | the agent opens them: plain Yes / No |
| Command Palette tasks | none (not needed) | optional extra | optional extra |

## How-tos

**Start a project.** Copy the kit folder to a new folder (File Explorer: copy, paste, rename it for the report), or
clone it. Open that folder in your app and ask for what you want. On the first run the assistant makes the folder your
project: its own save history, the data class, and two folders for your files, **Model** (a copy of the semantic model
export) and **Reference** (a wireframe, screenshots, requirements or an existing report). It never opens File Explorer
windows: it tells you which folder a file goes in, and after "done" it says what arrived and where.

**Guided build.** "We build it together, one step at a time." The agent stops after the page purpose, the plan
picture, the colours, the build, the checks and the polish, shows what changed, and waits for your OK or your changes.
It's the default until a quick build of that kind of report has reached 7/10.

**Quick build.** "Tell me what you want, approve the plan, and I'll build it." The agent stops only at the plan
picture and the approval windows, then does the colours, build, checks and polish on its own and shows the result:
before and after screenshots, the polish score and anything it couldn't fix. Its own fixes after your OK (a taller
filter, number formats, a legend) don't need another OK. Say "switch to guided" at any time to get the stops back, or
"finish the rest quickly" to drop them.

**Which one am I asked?** The assistant asks "Guided build or quick build?" only when there is no default yet (no
earlier build of this kind of report, no team default). When it doesn't ask, its plan list says which one it will use
and why; say "switch to guided" or "quick build" to change it. This walkthrough says at each run which you'll see.

## Part 1. A project and the model (about 10 minutes)

1. *You do:* copy the kit folder and rename the copy **Orders Guided** (beside the kit). Open **Orders Guided** (see
   the three apps).
2. *You do:* copy **Example Big.SemanticModel** (from `1 made-up model`) into the **Model** folder and **Orders
   overview.html** (from `3 made-up wireframe`) into the **Reference** folder. The two folders appear on the first
   run; if you open the project before they exist, the assistant makes them and asks you for the files.
3. *You say:* "I want an orders dashboard."
4. *Expect:*
   - one line that this folder is now your project Orders Guided (data class restricted), with its Model and Reference
     folders;
   - one line per folder: "Model: Example Big.SemanticModel ..." and "Reference: Orders overview.html (a wireframe
     page), kept in the Reference folder";
   - a warning that the Model folder held a data cache, deleted before anything read it;
   - the model in counts and one grouped line ("... handled by rules, 20 option tables to keep, 5 need you"), with the
     five typed-in target tables as one group and one question for all five;
   - "Guided build or quick build?" in the same message (no default yet: this is the first build of this kind).
   No File Explorer window opens.
5. *You say:* "Make up values for those five. Guided."
6. *Expect:* the **Approve the model** window opens by itself, in front: counts, the option tables' rows, *Yes,
   approve* / *No*. No code to type (unless computer use is on in this chat).
   - Click **No** first: "Not approved: nothing changed." Ask again ("approve the model").
   - Click **Yes**. The agent sees it and carries on.

## Run A. Guided build from the wireframe (about 20-30 minutes)

7. *Expect:* the page purpose as one sentence. *You say:* "OK" (or change it).
8. *Expect:* **the plan picture**: the page drawn with example values (not your data), every table column, and the
   short list: each KPI with its measure and "Compared with: last year", the assumptions, any text too faint to read
   (fixed before you're asked), guided build, restricted, the model. *You say:* one change: "Make the bar chart rank
   channels, not regions." *Expect:* the picture again, the old assumptions replaced, not piled up. *You say:* "OK".
9. *Expect:* a stop after the colours, the build, the checks and the polish, each with what changed. Say "OK" each
   time. Desktop opens the report by itself ("Still opening ..." once a minute while it does); if the agent can't
   prove Desktop holds only its own reload marks, it asks you to close Desktop without saving.
10. *Expect:* the result: before and after screenshots, "Polish n/10 (target 7 ...)", what's not done yet and what it
    couldn't fix with click steps. Note the score and your interaction count.
11. *You say:* "Share this model with the team." *Expect:* the **Share the model pack** window (Yes / No).

## Run B. Quick build of the same page (about 10-15 minutes)

12. *You do:* copy the kit again as **Orders Quick**, open it, put **Example Big.SemanticModel** in Model and
    **Orders overview.html** in Reference.
13. *You say:* "I want an orders dashboard, quick build."
14. *Expect:* the setup line, the two folder lines, the data-cache warning, and "the model you approved before: no
    model approval needed". No build-option question (you said quick). Then the plan picture. *You say:* "OK".
15. *Expect:* no more stops until the result (unless the agent is unsure: then one plain question with its default),
    no silent wait over a minute. Then the result as in step 10, and "Switch to live?". *You say:* "Not now."
16. Note the score and the interactions. Target: 3-4 with the model pack, 5 or fewer without.

## Run C. No wireframe: starter layouts (about 10-15 minutes)

17. *You do:* copy the kit as **Returns Check**, open it, put **Example Big.SemanticModel** in Model and
    **Requirements.md** (from `4 made-up requirements`) in Reference.
18. *You say:* "I want a returns check. Quick build."
19. *Expect:* no question about what the report is for (the requirements say it), then **2-3 starter layouts as
    pictures** (executive summary, trend dashboard, detail table) filled with the model's names.
20. *You say:* "The third one, but put the returns share in the first column." *Expect:* the plan picture and list.
    *You say:* "OK".
21. *Expect:* the result as in step 10. Note the score and the interactions.

## Part 5. Switch to live, dry run, and back (about 5 minutes)

22. In **Orders Guided**, *you say:* "Switch to live."
23. *Expect:* the agent asks you to pick the model in Desktop. There is no published model here, so copy **Pick.Report**
    (from `2 made-up live pick`) where it asks, and say "saved".
24. *Expect:* the **Connect to the live model** window: "You picked Example Big in workspace Sample Workspace". Yes.
    Don't open the report in Desktop now: the model is made up.
25. *You say:* "Back to the synthetic model." Window, Yes.

## Part 6. A new chat knows where you are

26. Start a new chat in the same project folder. *You say:* "Where am I?"
27. *Expect:* the project's stage and what's next ("Orders Guided: you're past the result; next is ..."). In the
    master kit folder itself it says to copy the kit for a project instead.

## Compare

| Run | Build option | Polish score | Interactions | Minutes | Hand-polish minutes |
| --- | --- | --- | --- | --- | --- |
| A | guided, from the wireframe | | | | |
| B | quick, same wireframe, model pack | | | | |
| C | quick, starter layout | | | | |

Targets: 7/10 before showing colleagues; 5 or fewer interactions per quick build, 3-4 with a model pack. If quick
builds score lower, the next start suggests a guided build for that kind of report.

## Verify at work

One checklist for the work laptop. Each item names what can't be proved here.

1. **GitHub Copilot end to end:** Parts 1-6 in Copilot agent mode, nothing typed in a terminal.
   - Copilot reads the kit's instructions and prompts (Chat > Configure: the kit-start and kit-status prompts listed);
     it follows the main flow when asked for a dashboard, in plain words (PLAIN-WORDS.md).
   - A fresh copy of the kit becomes the project on the first run (Model and Reference folders, its own git).
   - The plan picture and screenshots open beside the chat.
   - The approval window opens from Copilot's terminal, in front, as a plain Yes / No; Copilot doesn't (and can't)
     answer it.
   - A new chat says where the project is.
2. **The approval window under work policy:** opened by the agent from the Claude desktop app, Claude Code in VS Code
   and Copilot; it comes up in front; PowerShell policy allows Windows Forms (note any message); with computer use on
   in a Claude chat, the code picture shows and a wrong code three times declines.
3. **The Model-folder guard in both Claude apps:** reading the Model folder is blocked in a project.
4. **Model intake with a real export:** a TMSL export or a TMDL folder from the work tenant; the data files it
   deletes are listed; the rule library's coverage (target: 90% handled by rules or option tables).
5. **Desktop 2.155:** opens the synthetic model and builds; saves a picker report (compare its `definition.pbir` with
   both forms pbik reads); the Desktop bridge state after a reload, and whether closing Desktop is proven safe there.
6. **A real published model:** pick it in Desktop, Connect to the live model, open the report, check the visuals, back
   to the synthetic model.
7. **Team pack folder:** its location; who may share per data class (team.json `registrars`); read access for
   reuse; a team `defaultMode`; that the folder is in no git repository.
8. **A quick build with a team pack in 3-4 interactions**, with the score and minutes.
9. **Copilot usage:** premium requests per step from GitHub's usage page in design/reviews/usage.md.
