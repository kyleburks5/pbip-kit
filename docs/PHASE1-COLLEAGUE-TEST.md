# Phase 1 colleague test

For someone who has never used the kit. They try it alone; you watch and write down where they get stuck. About an
hour. Made-up data only (the `pbik-walkthrough-inputs` folder); never real data.

## Setup (you, before they arrive)

- A laptop with VS Code, the agent (Claude Code or GitHub Copilot), Power BI Desktop and the kit.
- The made-up inputs and the stand-in team pack folder beside the kit.
- Close any terminal. Don't explain the kit. Give them only the task list below.
- Have a timer and this page to fill in.

## Their task list (hand this over)

You're building a small Power BI report by chatting with the assistant in VS Code. You never need a terminal. If
you're unsure, ask the assistant, not me.

1. Start a new report project called *Colleague Test*. Its data is restricted.
2. Give it the model in the folder *1 made-up model* (a copy, as the assistant asks).
3. Approve the model when the assistant asks you to (it will tell you how).
4. Ask for one page: a few KPI cards and a monthly trend, with a slicer.
5. Look at the report in Power BI Desktop.
6. Connect the report to the live model. The live pick is in *2 made-up live pick*, standing in for Desktop.
7. Put it back on the made-up model.

## What to observe (you)

| # | Step | Time | Where they hesitated (more than ~10 s) | What they asked | Needed a terminal or a path? | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | New project | | | | | |
| 2 | Drop the model | | | | | |
| 3 | Approve (task + dialog) | | | | | |
| 4 | Plan and build | | | | | |
| 5 | Open in Desktop | | | | | |
| 6 | Connect live (pick + task) | | | | | |
| 7 | Back to synthetic | | | | | |

Also note:

- Did they find **Tasks: Run Task** on their own after the assistant named the task? How long did it take?
- Did they read the dialog before clicking? Did they understand what *Yes* would do?
- Did the assistant ever show a path, command, ID or JSON? Quote it.
- Did they drop their only copy, or a copy? Did the "data deleted" warning worry or confuse them?
- Words they didn't understand, such as "synthetic", "contract", "bind" or "pack".
- Anything they expected to happen that didn't.

## Afterwards

- Total time, against the target of 30-45 minutes for a first setup.
- Their own words: the hardest moment, and what would have helped.
- Copy the table into design/reviews/ (no names: "colleague 1").
