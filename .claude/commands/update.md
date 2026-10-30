After a Power BI Desktop update: $ARGUMENTS
Follow docs/UPDATE-ROUTINE.md. Don't update anything mid-rep (VERSIONS.md "Update policy").
1. Record the version: Desktop (`python tools/pbik/pbik.py project record` in the rep, or Help → About), plugins and pbik as /smoke step 1. Compare with VERSIONS.md and add a changelog row (date, Power BI Desktop, old, new). Refresh what Microsoft publishes: `python tools/pbik/pbik.py schemas support --refresh`, then `pbik project show`; note any new schema version (git diff tools/pbik/schema-support.json).
2. Check Desktop has no unsaved changes (`python tools/pbik/pbik.py desktop state --fail-if-dirty`); stop if it does.
3. Run the regression suite: `python tools/run_tests.py --regression`. A changed golden build is a finding: list the files and JSON paths, don't accept them (`regress.py --update`) without asking me.
4. Run /smoke (one card, one button slicer, one table) and record its result.
5. If the update brings a new visual or setting the kit should use (from the release notes, or $ARGUMENTS): propose the patterns.json entries and ask me. Then rebuild the Patterns page (`python tools/patterns/build_patterns.py --page-only --force`), ask me to set the new setting in Desktop by hand and save, and run `pbik roundtrip` on it.
6. Harvest: `python tools/pbik/pbik.py templates harvest "<pbip-patterns>\<Name>.Report"`, then `python tools/pbik/pbik.py catalog refresh --name <this machine's catalog> <pbip-patterns>` (project.json `catalog`; "home" here). Show me the new templates and catalog lines.
7. Run `python tools/run_tests.py` again, then propose the release (patch, minor or major, VERSIONS.md "Releases") with the Desktop version it was tested on. Don't commit unless I say so.
