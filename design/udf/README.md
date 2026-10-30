# DAX functions: DAX Lib packages

SVG measures and other reusable DAX come from DAX Lib packages (daxlib.org), not from function files kept in the kit.
`packages.json` lists the packages a rep may install, with their licences. The kit keeps no function files of its
own; `vendor/` holds unmodified copies of the listed packages with their licences (`vendor/NOTICE.md`), only for a
laptop where npm is blocked.

## Order of preference

1. A DAX Lib package listed in `packages.json` (licence checked), installed with the daxlib-mcp server (.mcp.json,
   pinned to `@daxlib/mcp@0.1.0`). DaxLib.SVG covers most SVG measures.
2. New SVG code in the rep's model, written to .claude/rules/svg.md, when no listed package draws it.

Packages are installed into the model, not copied here: `/plan` puts a package a rep needs on the model approval
list, and `/model approved` installs it with daxlib-mcp `install_package`, saves it to the TMDL and records the version
under `installed` in `packages.json`. A package that isn't in `packages.json` needs its licence checked and a row there
first.

## When npm is blocked (the vendored copy)

daxlib-mcp starts through `npx`, so it needs Node.js and the npm registry (`tools/doctor.ps1` checks both). Where
either is blocked, install from the vendored copy through the modeling MCP instead; the result in the model is the
same functions with the same `DAXLIB_PackageId` / `DAXLIB_PackageVersion` annotations:

1. `python design/udf/vendored.py --check` (every listed package vendored and unchanged).
2. `python design/udf/vendored.py <Id> --out <scratch>/<Id>.json` (the function definitions).
3. Raise the compatibility level to 1702 first if it is on the approval list (modeling MCP `database_operations`).
4. Modeling MCP `function_operations` Create with that file's list as `definitions` (`useTransaction` true).
5. Record it under `installed` in packages.json with `"from": "vendored"`; then save, export the TMDL and run
   `pbik model check` as usual.

## Using a package function

- Test the call query-scoped first (`EVALUATE ROW ( "svg", <Package.Function> ( ... ) )` through run-dax.ps1) in every
  audit state, including the empty case and blank inputs, and run audit_svg.py on what it returns.
- Pass colours from tokens.json (hex text), never model column references, as arguments.
- `pbik model check` must see the installed functions in the TMDL (save in Desktop after installing).
