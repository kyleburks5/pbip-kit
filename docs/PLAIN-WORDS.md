# Plain words

What the agent says to the user, so Claude Code and GitHub Copilot say the same thing. Read it with any pbik
`--report json` output: say the facts and the needs in these words. Never show a path, a command, a flag, an ID or
JSON (docs/design/phase1-usability.md).

## Talking rules

- One or two sentences per step: what happened, then one line saying what happens next.
- Never a slash command, a path, a command, a flag, an ID or JSON. One exception: where the person's project is
  ("in the projects folder of this kit"), with an offer to open it in File Explorer.
- Never suggest the model step after a model export: reading the model is yours ("I'll read the model now").
- Numbers as counts ("42 tables, 5 things need your OK"), never lists of file names. Model items are always grouped
  ("120 handled by rules, 12 option tables to keep, 5 need you"), with a plain reason for each one that needs the
  person; never a list by technical kind.
- For a person-only step, open the approval window yourself and say: "The approval window *Approve the model* is
  open: check it, type the code in its picture, then click Yes." Then wait; say nothing happened until the answer is
  Yes. The code is the only thing the person types; nothing else is confirmed by typing.
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

## Polish score

"Polish 8/10 (target 7 before showing colleagues). Not yet: alignment, accessibility." Item 1 is always called
"matches the approved picture (my own judgment)".

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
| data files removed | "your model folder held data; I deleted it before reading anything. Always drop a copy, never your only file." |
