# Plain words

What the agent says to the user, so Claude Code and GitHub Copilot say the same thing. Read it with any pbik
`--report json` output: say the facts and the needs in these words. Never show a path, a command, a flag, an ID or
JSON (docs/design/phase1-usability.md).

## Talking rules

- One or two sentences per step: what happened, then one line saying what happens next.
- Never a slash command, a path, a command, a flag, an ID or JSON. The project is the folder the person opened (one
  folder = one project); its two folders are named plainly: the Model folder and the Reference folder. Never open
  File Explorer windows: say which folder a file goes in, and after "done" say what arrived and where ("Reference:
  Orders overview.html, a wireframe page").
- Never tell the person to run anything, and never pass on a raw error: say what went wrong in plain words and what
  you'll do about it.
- Never suggest the model step after a model export: reading the model is yours ("I'll read the model now").
- Numbers as counts ("42 tables, 5 things need your OK"), never lists of file names. Model items are always grouped
  ("120 handled by rules, 12 option tables to keep, 5 need you"), with a plain reason for each one that needs the
  person; never a list by technical kind.
- For a person-only step, open the approval window yourself and say: "The approval window *Approve the model* is
  open in front of your other windows: check it, then click Yes or No." Then wait; say nothing happened until the
  answer is Yes. Only when screen control is on does it also ask for the code in its picture; say so then. Nothing
  is ever confirmed by typing in the chat.
- Errors: what's wrong in the report's own terms ("the Sales card uses a field the live model doesn't have"), and
  what you'll do about it.
- At the start of every chat, say where the project is: "Sales Overview: you're past the plan picture; next is the
  colours."

## Questions

- Ask only what only the person knows (what the report should help people decide, what a KPI means when the model
  can't say, the hand-polish minutes) or what an approval needs. Everything else is a default shown in the plan
  picture, changeable in one reply.
- Batch questions in one message. Target: 5 or fewer interactions per quick build, 3-4 with a model pack (a reply or
  an approval window counts as one).

## Build options

| Option | Say |
| --- | --- |
| guided build | "We build it together, one step at a time": I stop after the page purpose, the plan, the colours, the build, the checks and the polish for you to look. |
| quick build | "Tell me what you want, approve the plan, and I'll build it": I stop only at the plan picture and the approvals. |
| switching | "Say *switch to guided* or *finish the rest quickly* at any time." |
| suggestion | "Quick builds of this kind of report have scored lower (5.7 vs 8.0); I suggest a guided build." |

## Stages (the progress list and the status line)

start (what the report is for, and what you have), the model, the page purpose, the plan picture, the colours, the
build, the checks, the polish, the result, switching to the live model, the wrap-up.

## App-like visuals (v1.11)

| Thing | Say |
| --- | --- |
| kit custom visual | "an animated visual the kit builds for this report (it needs your IT team's OK at work)" |
| route | "how a visual is made": built-in, built-in with formatting, a picture made from a measure, Deneb, or an animated kit visual |
| route switched off | "Your organisation blocks animated visuals, so I built the plain version of that one" |
| exported page | "a page that goes out as PDF or PowerPoint or by subscription: I keep it to built-in and Deneb visuals, which export" |
| click filter | "Clicking in the visual filters the whole page; the Clear button in its corner undoes it" |
| frame meter | "a hidden speed check I can turn on to measure smoothness; it's off in what you share" |
| harness | "my offline test of the visual, before it reaches Power BI" |

## Polish score

"Polish 6/10 (15 of 15 checks applied; 9 passed; target 7 before showing colleagues). Not yet: KPI cards read well,
text sized for the canvas." A check that can't apply is "N/A" with its reason and left out ("10 of 15 checks applied,
5 N/A"); more than a third N/A adds "Limited score: many checks didn't apply". Check 1 is always called "matches the approved picture (my own judgment)". After the build, the real Desktop
screenshot is put beside the approved picture: "The built page matches the approved picture" or "2 differences from
the approved picture: ...". The picture's numbers are examples; never compare them with the report's.

## Flags in a model (gate summaries use the same words)

| Kind | Say | Resolutions, in plain words |
| --- | --- | --- |
| `enter-data` | "a small table someone typed into the model" | synthesize: made-up rows; keep rows: option labels: its exact labels and order (a person confirms); drop: left out |
| `m-code` | "a table loaded by a query" | synthesize: made-up rows in the same shape; drop: left out |
| `connection` | "a link to a data source; it isn't copied" | synthesize: replaced by made-up data; drop: left out |
| `rls` | "a row-level security role; it isn't copied" | not reproduced: the synthetic model has no roles |
| `entity` | "a table about accounts, members or other people or organisations" | synthesize: made-up values only (never its real rows); drop: left out |

## Gates (the approval window; the Command Palette tasks of the same names are an optional extra)

| Gate | Window title | What Yes does |
| --- | --- | --- |
| `synth-approve` | Approve the model | accepts the model's description and how each flag is handled |
| `map-approve` | Approve the name map | accepts which report names match which live-model names |
| `model-approve` | Approve model changes | accepts what changed in the live model since the last approval |
| `bind-live` | Connect to the live model | points the report at the published model (a backup is kept) |
| `bind-local` | Back to the synthetic model | points the report back at the made-up model, exactly as it was |
| `class-lower` | Loosen the data class | allows more (live queries, screenshots) for this project |
| `pack-register` | Share the model pack | puts this model's approved setup in the team folder |

## Check results

| Result | Say |
| --- | --- |
| stale reference | "a leftover field nothing in the model has any more; I'll remove it" |
| map error | "a name in the map doesn't exist in the live model; I'll fix the map" |
| filter value type | "a filter uses text where the column holds numbers (or the other way round)" |
| planned measure | "a measure we planned that the live model doesn't have; I'll keep it inside the report" |
| KPI card rule | "the KPI cards aren't evenly sized or aligned; I'll fix the layout" |
| data files removed | "your Model folder held data; I deleted it before reading anything. Always drop a copy, never your only file." |
