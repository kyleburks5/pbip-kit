# Plain words

What the agent says to the user, so Claude Code and GitHub Copilot say the same thing. Read it with any pbik
`--report json` output: say the facts and the needs in these words. Never show a path, a command, a flag, an ID or
JSON (docs/design/phase1-usability.md).

## Talking rules

- One or two sentences per step: what happened, then what's next.
- Numbers as counts ("42 tables, 5 things need your OK"), never lists of file names.
- For a person-only step, name the task exactly: "Press Ctrl+Shift+P, type *Run Task*, and pick **Approve the
  model**." Then wait; say nothing happened until the result says Yes.
- Errors: what's wrong in the report's own terms ("the Sales card uses a field the live model doesn't have"), and
  what you'll do about it.

## Flags in a model (gate summaries use the same words)

| Kind | Say | Resolutions, in plain words |
| --- | --- | --- |
| `enter-data` | "a small table someone typed into the model" | synthesize: made-up rows; keep rows: option labels: its exact labels and order (a person confirms); drop: left out |
| `m-code` | "a table loaded by a query" | synthesize: made-up rows in the same shape; drop: left out |
| `connection` | "a link to a data source; it isn't copied" | synthesize: replaced by made-up data; drop: left out |
| `rls` | "a row-level security role; it isn't copied" | not reproduced: the synthetic model has no roles |
| `entity` | "a table about accounts, members or other people or organisations" | synthesize: made-up values only (never its real rows); drop: left out |

## Gates (Command Palette: Tasks: Run Task)

| Gate | Task to pick | What Yes does |
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
