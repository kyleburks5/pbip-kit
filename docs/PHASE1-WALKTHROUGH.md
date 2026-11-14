# Walkthrough (v1.7): guided build, quick build, and no wireframe

Try the kit the way a new user would: everything through the chat, nothing typed in a terminal. Made-up data only.
Design: docs/design/phase1-usability.md (Part A).

## What you need, and where the made-up inputs are

- One of: the **Claude desktop app** (Code tab), **Claude Code in VS Code**, or **GitHub Copilot in VS Code** (the main
  work environment: verify at work).
- Power BI Desktop.
- The made-up inputs in the folder **pbik-walkthrough-inputs**, beside the kit folder (same parent folder):

  | Folder | What | Used in |
  | --- | --- | --- |
  | `1 made-up model` | **Example Big.SemanticModel**, a made-up model with a fake data cache in it on purpose | Part 1 |
  | `2 made-up live pick` | **Pick.Report**, standing in for a report Desktop saved connected to a published model | Part 5 |
  | `3 made-up wireframe` | **Orders overview.html**, one wireframe page on the made-up model's names | Runs A and B |
  | `4 made-up requirements` | **Requirements.md**, a short brief with no layout | Run C |

- A stand-in team pack folder, **pbik-team-packs**, beside the kit too.

**How to read this:** *You say* is what you type in the chat; *You do* is a click; *Expect* is what should happen.
If the agent ever shows you a path, a command, a slash command or JSON, or asks you to open a terminal, note it: that's
a bug. Count your interactions (each message you send and each approval window) for the table at the end.

## The three apps

| | Claude desktop app | Claude Code in VS Code | Copilot in VS Code (verify at work) |
| --- | --- | --- | --- |
| Open the kit | pick the kit folder for the session | File > Open Folder: the kit | File > Open Folder: the kit; Copilot Chat in agent mode |
| Pictures (plan, screenshots) | shown in the chat | opened beside the chat as editor tabs | opened beside the chat as editor tabs |
| Approval windows | the agent opens them | the agent opens them | the agent opens them |
| Command Palette tasks | none (not needed) | optional extra | optional extra |

## How-tos

**Guided build.** "We build it together, one step at a time." The agent stops after the page purpose, the plan
picture, the colours, the build, the checks and the polish, shows what changed, and waits for your OK or your changes.
It's the default until a quick build of that kind of report has reached 7/10.

**Quick build.** "Tell me what you want, approve the plan, and I'll build it." The agent stops only at the plan
picture and the approval windows, then does the colours, build, checks and polish on its own and shows the result:
before and after screenshots, the polish score and anything it couldn't fix. Say "switch to guided" at any time to get
the stops back, or "finish the rest quickly" to drop them.

## Part 1. A project and the model (about 10 minutes)

1. *You do:* open the kit (see the three apps).
2. *You say:* "I want an orders dashboard. I have a model export and a wireframe."
3. *Expect:*
   - "Your project ... is ready in the projects folder of this kit (data class restricted). I can open it in File
     Explorer." You keep working in the same chat.
   - the agent opens the inputs folder and the model folder in File Explorer and asks for a **copy** of each.
4. *You do:* copy **Example Big.SemanticModel** (from `1 made-up model`) into the model folder, and
   **Orders overview.html** (from `3 made-up wireframe`) into the inputs folder. Say "done".
5. *Expect:*
   - a warning that the model folder held a data cache, deleted before anything read it;
   - the model in counts and one grouped line ("... handled by rules, ... option tables to keep, 5 need you"), with
     a plain reason for each of the 5. No slash command, and no list by technical kind;
   - "You gave me 1 thing: Orders overview.html (a wireframe page). Path: a wireframe page."
6. *You say:* "Make up values for those five."
7. *Expect:* the **Approve the model** window opens by itself: counts, the option tables' rows, a code drawn as a
   picture, a box, and *Yes, approve* / *No*.
   - Try **No** first: "Not approved: nothing changed." Ask again.
   - Type the code, click **Yes**. The agent sees it and carries on.
   - Type a wrong code three times once (optional): "Not approved" and nothing changes.

## Run A. Guided build from the wireframe (about 20-30 minutes)

8. *Expect:* "Guided build or quick build?" with one line each (asked once; guided is the default). *You say:*
   "Guided."
9. *Expect:* the page purpose as one sentence. *You say:* "OK" (or change it).
10. *Expect:* **the plan picture**: the page drawn as it will be built, and the short list (each KPI and its measure
    and comparison, the assumptions, any fallback, guided build, restricted, the model). *You say:* one change, for
    example "Make the bar chart rank stores, not regions." *Expect:* the picture again. *You say:* "OK".
11. *Expect:* a stop after the colours, the build, the checks and the polish, each with what changed. Say "OK" each
    time. Desktop opens the report by itself; if the agent can't prove Desktop holds only its own reload marks, it
    asks you to close Desktop without saving.
12. *Expect:* the result: before and after screenshots, "Polish n/10 (target 7 ...)", what's not done yet and what it
    couldn't fix with click steps. Note the score and your interaction count.
13. *You say:* "Share this model with the team." *Expect:* the **Share the model pack** window (code, Yes).

## Run B. Quick build of the same page (about 10-15 minutes)

14. *You say:* "Start another project called Orders Quick on the same model, from the same wireframe, quick build."
15. *Expect:* the model is recognised ("the model you approved before: no model approval needed"); the inputs folder
    opens: copy **Orders overview.html** again. Then the plan picture. *You say:* "OK".
16. *Expect:* no more stops until the result (unless the agent is unsure, then one plain question with its default).
    Then the result as in step 12, and "Switch to live?". *You say:* "Not now."
17. Note the score and the interactions. Target: 3-4 with the model pack.

## Run C. No wireframe: starter layouts (about 10-15 minutes)

18. *You say:* "Start a project called Returns Check on the same model. I only have requirements." Copy
    **Requirements.md** (from `4 made-up requirements`) into the inputs folder when asked.
19. *Expect:* no question about what the report is for (the requirements say it), then **2-3 starter layouts as
    pictures** (executive summary, trend dashboard, detail table) filled with the model's names.
20. *You say:* "The third one, but put the returns share in the first column." *Expect:* the plan picture and list.
    *You say:* "OK, quick build."
21. *Expect:* the result as in step 12. Note the score and the interactions.

## Part 5. Switch to live, dry run, and back (about 5 minutes)

22. *You say:* "Switch the first project to live."
23. *Expect:* the agent asks you to pick the model in Desktop. There is no published model here, so copy **Pick.Report**
    (from `2 made-up live pick`) into the live folder it opens, and say "saved".
24. *Expect:* the **Connect to the live model** window: "You picked Example Big in workspace Sample Workspace". Code,
    Yes. Don't open the report in Desktop now: the model is made up.
25. *You say:* "Back to the synthetic model." Window, code, Yes.

## Part 6. A new chat knows where you are

26. Start a new chat in the same folder. *You say:* "Where am I?"
27. *Expect:* each project with its stage and what's next ("Orders Quick: every step is done (quick build, polish
    8/10)"), the last one used first.

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
   - The plan picture and screenshots open beside the chat.
   - The approval window opens from Copilot's terminal; Copilot doesn't (and can't) answer it.
   - A new chat says where the project is.
2. **The approval window under work policy:** opened by the agent from the Claude desktop app, Claude Code in VS Code
   and Copilot; the code picture shows; PowerShell policy allows Windows Forms (note any message).
3. **The model-folder guard in both Claude apps** with a project in the projects folder: reading the model folder is
   blocked from the kit and from inside a project.
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
