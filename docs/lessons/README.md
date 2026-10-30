# Lessons: where a new one goes

A lesson is something a rep learned the hard way (a Desktop quirk, a DAX trap, a build step that failed). CLAUDE.md is
read in every session, so it stays small: `tools/tests/test_kit.py` fails when it passes 150 lines.

Topic files: dax.md, build.md, cards.md, slicers.md, charts.md, accessibility.md, audit-modes.md. Helpers named
`pbik_helpers.<name>` are in design/scripts/pbik_helpers.py (the pure builders live in tools/pbik/pbikit/objects.py).
A rule that a check now enforces keeps its background here, marked with the check in *(italics)*.

## Placement order

Put each new lesson in the first place that fits:

1. **A check**: a `pbik validate` rule (tools/pbik/pbikit/) or a test, if a script can tell right from wrong. A check
   runs every time; a rule only works if it is read.
2. **A template or token**, if it is about how a visual looks: a harvested template in design/templates/, a theme
   default from design/tokens.json (gen_theme.py), or a pbik default.
3. **The command file** (.claude/commands/<step>.md), if it applies to one step only (/model, /plan, /build, ...).
4. **docs/lessons/<topic>.md**, if it is background: why something is done, a Desktop quirk with its click steps, a
   pattern to copy. One file per topic (desktop, dax, cards, charts, slicers, svg, ...). Rules files in .claude/rules/
   count here for topics they already hold (pbik, svg, connect-pbid).
5. **CLAUDE.md**, only if it applies to every session. **One in, one out:** a lesson added to CLAUDE.md retires or
   moves another, so the file never grows.

Each lesson names the rep it came from (`(Rep 9)`). A lesson placed lower down still gets a one-line pointer only if
the agent would otherwise miss it; most don't need one.

## Proposing a lesson

Every lesson proposed (by /fix or the rep wrap-up) says:

| Lesson | Rep | Where it goes (1-5 above) | Why not higher |
| --- | --- | --- | --- |

"Why not higher" is one line: for example "needs Desktop to see it, no file check can tell" for a lesson that isn't a
check.

## Retiring rules

When a check or a template now enforces a rule in CLAUDE.md (or a command file), propose retiring the rule: name the
rule, the check that enforces it (`pbik validate` rule, test name or template) and where the background moves, if
anywhere. Wait for approval, then remove it.

## Rep wrap-up

At the end of a rep (after the last /fix is approved), `/wrapup` runs these steps and shows the diff before
anything is committed:

1. List the lessons the rep produced that aren't placed yet, in the table above.
2. List CLAUDE.md rules that a check added during the rep now enforces, and propose retiring them.
3. Check the CLAUDE.md line count (`python tools/tests/test_kit.py`) and that a new CLAUDE.md lesson retires one.
4. After approval: apply, run `python tools/copilot/sync.py`, run `python tools/run_tests.py --regression`, commit.
