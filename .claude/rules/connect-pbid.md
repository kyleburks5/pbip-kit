Learnings from Claude about connecting to semantic models via the connect-pbid skill

- Desktop Bridge params must be wrapped: `params = { client, args: { ... } }`. Flat params (as in references/desktop-bridge.md) fail; `args` is required even when empty.
- `file.reload/v1` defaults `reloadModelDefinition` to true; always pass false for report-only reloads.
- `report.snapshot.capture/v2` exists and accepts an optional `region` {x,y,width,height} in PBIR page units; useful for per-visual comparison.
- `report.snapshot.capture/v1` returns the visible canvas viewport (incl. collapsed Filters pane strip and scrollbar), not a clean page-only render.
- Client script for this project: `.claude/scripts/pbi-bridge.ps1` (manifest | state | reload | screenshot).
