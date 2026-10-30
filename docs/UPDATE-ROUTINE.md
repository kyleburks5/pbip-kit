# Update routine

What to do when Power BI Desktop updates (the Store version updates itself), and how to make the kit work with an
older Desktop on another machine. `/update` runs the first part; the commands are pbik's (tools/pbik/README.md).

Freeze versions during a rep (VERSIONS.md "Update policy"): run this between reps.

## Target Desktop (design/specs/project.json)

```json
{
  "targetDesktop": "latest",
  "catalog": "home",
  "desktop": {"version": "2.159.883.0", "recorded": "2026-10-29"}
}
```

- `targetDesktop`: the oldest Desktop that must open the report: a version (`2.152.882.0`, Help → About) or
  `"latest"`. pbik writes, and validate checks, the PBIR schema versions that Desktop supports:
  - Microsoft publishes when each schema version was released (the CHANGELOG.md beside each schema in
    github.com/microsoft/json-schemas) and which Desktop version each month's release was (the Desktop update archive
    on Microsoft Learn). `pbik schemas support --refresh` reads both into `tools/pbik/schema-support.json`.
  - `pbik build` writes each file's `$schema` at the newest version the target supports, and lowers report.json's.
    `pbik validate` errors on any file declaring a newer version (that Desktop may refuse to open it) and
    schema-checks the files against the older schemas.
  - A Desktop month Microsoft doesn't list counts as the release before it (fewer schema versions, never more). A
    target newer than every listed release isn't pinned: Desktop writes versions Microsoft hasn't published yet
    (visualContainer 2.14.0 from Desktop 2.159, October 2026).
  - Not covered: a visual type or setting the target's schema allows but its Desktop doesn't render. The named catalog
    (below) warns on settings that Desktop never saved.
- `catalog`: the settings catalog `pbik validate` warns from: tools/pbik/catalogs/<name>.json, `home` (this
  machine's, also used without a name) or another machine's (`work`).
- `desktop`: the Desktop version on this machine, written by `pbik project record` at /model. Recording never changes
  the target.

`pbik project show` prints the target, the release it resolves to and the schema version for each kind.

## After a Desktop update (`/update`)

1. **Record the version.** `pbik project record` in the rep (or Help → About), and a changelog row in VERSIONS.md.
   `pbik schemas support --refresh` picks up new schema versions and Desktop releases; `git diff
   tools/pbik/schema-support.json` shows them.
2. **Regression suite.** Check Desktop has no unsaved changes, then `python tools/run_tests.py --regression`. A
   changed golden build means pbik's output changed: review the listed files and JSON paths before accepting them.
3. **`/smoke`.** One card, one button slicer, one table on a `_smoke` page, checked in Desktop against
   design/checks.md.
4. **New visuals or settings, through the Patterns page.** Add the visual or setting to
   `tools/patterns/patterns.json`, rebuild the page (`python tools/patterns/build_patterns.py --page-only --force`),
   open ..\pbip-patterns (beside the kit folder; run the commands here from the kit root) in Desktop, set what pbik can't write by hand, and save. `pbik roundtrip` lists
   what Desktop rewrote.
5. **Harvest.** `pbik templates harvest "..\pbip-patterns\<Name>.Report"` (design/templates/), then
   `pbik catalog refresh --name home ..\pbip-patterns` (and any rep saved since).
6. **Release.** `python tools/run_tests.py`, then a VERSIONS.md "Releases" row: the version (patch, minor or major)
   and the Desktop version it was tested on.

## A catalog for another machine ("work")

A work laptop often runs an older, IT-managed Desktop. Its catalog records what that Desktop saves, so a report
validated against it warns on settings it has never saved.

1. On the home machine, copy the Patterns project for work and set its target to the work Desktop (Help → About on
   the work machine):

   ```bat
   robocopy ..\pbip-patterns ..\pbip-patterns-work /E /XD .git
   rem design\specs\project.json in the copy: {"targetDesktop": "<work version>", "catalog": "work"}
   python tools\pbik\pbik.py schemas lower "..\pbip-patterns-work\<Name>.Report"
   python tools\pbik\pbik.py schemas fetch "..\pbip-patterns-work\<Name>.Report"
   python tools\pbik\pbik.py validate "..\pbip-patterns-work\<Name>.Report" --no-catalog
   ```

   `schemas lower` lowers every file's `$schema` to the work target; validate then checks them against the older
   schemas. Remove or rebuild any visual that fails there: the work Desktop can't open it.
2. Take the copy to the work machine (public data only: the Patterns report holds the Rep 8 public data model), open
   the .pbip in the work Desktop, check the Patterns page, and **save**.
3. On the work machine, with the kit checked out:

   ```bat
   python tools\pbik\pbik.py catalog refresh --name work ..\pbip-patterns-work
   python tools\pbik\pbik.py catalog list
   ```

   The catalog records the work Desktop's version (detected, or `--desktop <version>`). Only files that Desktop
   rewrote count (no final newline): `schemas lower` left pbik's final newline on every file, so a file the work
   Desktop didn't rewrite is skipped rather than counted as its own. If the file count is far below the page's
   visual count, Desktop saved only what changed (not yet checked): note it in design/known-gaps.md.
4. Commit `tools/pbik/catalogs/work.json` (setting names, value types, selector shapes, the folder paths it read and
   the Desktop version: no data) and bring it home. A rep that must open at work sets
   `{"targetDesktop": "<work version>", "catalog": "work"}`.

GitHub Copilot on the work laptop runs the same steps through `.github/prompts/kit-update.prompt.md` (`/kit-update`, docs/COPILOT.md).
