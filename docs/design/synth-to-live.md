# Synthetic to live (design, batch 3)

Build a report on a synthetic copy of a model, then point it at the published model. The agent sees the synthetic
data only; a person approves each step that reaches the real model.

## Files

| File | Holds | Written by |
| --- | --- | --- |
| design/specs/project.json `dataClass` | public, internal or restricted | `pbik project class` |
| design/specs/contract.json | tables, columns (type), measures (DAX), relationships, flags with resolutions and the rules behind them, approval | `pbik synth contract`, `synth resolve`, `synth approve` (person) |
| design/specs/generate.json | seed, slice, planned measures, hints (rows, fact, trend, seasonality, month-end), deviations | `synth slice`, the agent (hints), `bind prepare` |
| `<Name>.SemanticModel` | the synthetic model: every table a calculated DATATABLE, annotation `PBIK_Synthetic` | `synth generate` |
| design/specs/bind-map.json | synthetic name -> live name (tables, fields), accepted DAX changes, approval | `bind map draft`, `bind map approve` (person) |
| `.pbik/bind/` (git-ignored) | backup of the report before `bind live`, file hashes after it | `bind live`, read by `bind local` |

The contract never holds M code, connection strings, RLS expressions or row values, except option-table rows a
person kept (`keep rows: option labels`). Flags name the table and the kind of source only.

## Data classes

- **public**: no limits. **internal**: the default; live DAX allowed. **restricted**: the report must sit on the
  synthetic model (`PBIK_Synthetic`); while it is bound live (`.pbik/bind/state.json`) `pbik desktop screenshot` and
  run-dax.ps1 refuse (`pbik project class --guard`).

## Commands

| Step | Command | Person-only |
| --- | --- | --- |
| 0a | `pbik project class [public|internal|restricted] [--guard dax|screenshot]` | |
| 0b | `pbik synth contract <TMDL folder or createOrReplace script> [--out]` | |
| | `pbik synth resolve <flag> <resolution> [--why]` (records the rule) | |
| 0c | `pbik synth approve --by <name>` (types the model name) | yes |
| 0d | `pbik synth slice <layout.json>`, `synth generate <Name>`, `synth verify <SemanticModel>` | |
| 0e | `pbik bind check <Report>` | |
| 0f | `pbik bind prepare <Report> [--port]` | |
| 0g | `pbik bind live <Report> --workspace W --model M --id <url or id>` or `--from <Desktop-saved Report>` | yes |
| 0h | `pbik bind local <Report>` (refuses while Desktop is open) | |

Person-only commands refuse when stdin isn't a terminal or the `CLAUDECODE` environment variable is set (an agent's
shell): the person runs them. Approval records `by`, the date and a hash of what was approved; any later change to
the approved content voids it.

## Generation

Deterministic: every value comes from `random.Random(sha1(seed/table/column))`. Dimension keys are unique; fact
foreign keys draw from the dimension's keys (relationships); date keys cover `dateRange`. Planned measures (in
generate.json, not in the contract) are written to the synthetic model with annotation `PBIK_Planned`; `bind prepare`
moves them into report-level measures before `bind live`, inlining planned dependencies as `CALCULATE ( ... )` (a
measure reference is an implicit CALCULATE, so this keeps the meaning inside iterators too). Type changes the
generator had to make are `deviations`; `synth verify` and `bind check` note them, never fail on them.

## Live binding

`bind live` backs the report up, rewrites every field reference per bind-map.json, then writes definition.pbir
`byConnection` (workspace, model name, semantic model ID; Desktop's form, UNVERIFIED until a Desktop save confirms it).
`bind local` restores files unchanged since `bind live` byte for byte and reverse-maps only files changed while live.
