# Vendored DAX Lib packages: notices

Unmodified copies of the DAX Lib packages listed in design/udf/packages.json, kept for a laptop where npm or npx
is blocked (daxlib-mcp can't start). Each folder holds the package's `functions.tmdl`, `manifest.daxlib`,
`README.md` and its `LICENSE`, copied on 2026-10-29 from the DAX Lib catalog repository at commit
`daxlib/daxlib@0e65ac4137e73edfcb1cef4ac880b9cd31bb5389` (`packages/<letter>/<id>/<version>/`). Package icons are
left out. `python design/udf/vendored.py --check` confirms each file is unchanged (SHA-256 in packages.json).

| Package | Version | Authors | Licence | Licence text (LICENSE in the folder) |
| --- | --- | --- | --- | --- |
| DaxLib.SVG | 2.0.0 | Kurt Buhler, Jake Duddy, Tom Shanley | MIT | "Copyright (c) 2025 DAX Lib", from github.com/daxlib/dev-daxlib-svg (the manifest's repositoryUrl), commit d73d34b7e74e5f327d54ac8f6adb1d25db35a5cb |
| DataTides.ColourContrast | 0.1.0 | Juls-BI | MIT | "Copyright (c) 2025 SQLBI", the github.com/daxlib/daxlib repository's LICENSE (the package has no repository of its own) |
| DataTides.SignificantChange | 0.1.0 | Juls-BI | MIT | as above |

The MIT licence lets the kit copy and redistribute these files as long as the copyright and permission notice stay
with them: keep each `LICENSE` beside its package, and keep the functions' `DAXLIB_PackageId` /
`DAXLIB_PackageVersion` annotations when installing (vendored.py writes them).

To update a package: change its version in packages.json, copy the new folder from the DAX Lib repository (same four
files), record the commit, the SHA-256 and the function count under `vendored`, and run `vendored.py --check`.
