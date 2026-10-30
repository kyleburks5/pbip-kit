# Third-party content

What in this kit comes from someone else, where it is, and on what terms. Recorded 2026-10-29 (kit v1.0).

## Datasets (test fixtures and regression cases only)

No source data is in the kit: no CSV, Excel or model cache. The fixtures and regression cases hold the report and
model definitions only, and their Power Query source paths point at a generic `C:\pbip-data\...` folder.

| Dataset | Where | Source and terms |
| --- | --- | --- |
| Maven Toys ("Mexico Toy Sales"): a fictitious chain of toy stores | `tools/fixtures/rep4/`, `tools/regression/cases/rep4-parity/` | Maven Analytics free practice dataset (public) |
| HR dataset (`Adjusted_HR_Dataset.csv`) | `tools/fixtures/rep5/`, `tools/fixtures/rep8/`, `tools/regression/cases/rep5-parity/`, `tools/regression/cases/rep8/` | Public HR practice dataset from a YouTube Power BI tutorial (author: Injae), used for regression tests only; contains no real employee data. |

## Code and model content

| Content | Where | Licence |
| --- | --- | --- |
| Bravo for Power BI date template (the `Date` and `DateAutoTemplate` tables, `SQLBI_Template` annotations), made with Bravo in the original HR model | `DateAutoTemplate.tmdl`, `Date.tmdl` and `model.tmdl` in `tools/fixtures/rep5/`, `tools/fixtures/rep8/`, `tools/regression/cases/rep5-parity/`, `tools/regression/cases/rep8/` | MIT License, Copyright (c) SQLBI Corporation (https://github.com/sql-bi/Bravo, LICENSE checked 2026-10-29) |
| DAX Lib packages DaxLib.SVG, DataTides.ColourContrast, DataTides.SignificantChange (vendored, unmodified) | `design/udf/vendor/` | MIT; each package's LICENSE and `design/udf/vendor/NOTICE.md` |
| Power BI base themes as Desktop writes them into every PBIP (`CY24SU10.json`, `Fluent2-CY26SU09.json`) | `StaticResources/SharedResources/BaseThemes/` in the fixtures and regression cases | Microsoft; part of the files Power BI Desktop saves |

## Used, not included

- Data Goblins plugins (power-bi-agentic-development, GPL-3.0): used as installed in Claude Code; the kit copies none
  of their content. `.claude/scripts/pbi-bridge.ps1` frames its messages with code written from the JSON-RPC base
  protocol (Content-Length header, blank line, UTF-8 body), not from the plugins' bridge reference (v1.0).
- Deneb (certified AppSource visual, MIT): installed from AppSource in Desktop, not shipped here.
- Microsoft's PBIR JSON schemas: fetched into `tools/pbik/schemas/` by `pbik schemas fetch`, git-ignored.
- `@microsoft/powerbi-modeling-mcp` and `@daxlib/mcp`: run through npx (VERSIONS.md).
