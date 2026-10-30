"""pbik model check: read a semantic model's TMDL and fail on

- a measure without a description (/// line), every measure;
- a measure without a format string (formatString or formatStringDefinition), except text measures: declared
  (dataType: string, dataCategory: ImageUrl) or inferred from the DAX (pbikit/daxtype.py: a string, a & concatenation,
  FORMAT and other text functions, IF / SWITCH / COALESCE with a text branch, a text VAR or measure), so text
  measures need no `formatString: @`;
- a DAX reference (measures, calculated columns, calculated tables) to a table, column or measure that doesn't exist;
- a relationship or sort-by column that points to a missing table or column;
- a call to a user-defined function whose first name part (DaxLib in DaxLib.SVG.Viz.Line) is an installed
  package's (functions.tmdl) but which the model doesn't define (a typo, or a function from another package
  version). The summary counts the functions.
Read-only. Exit 1 on any failure.
"""
import pathlib, re

from . import daxtype, tmdl
from .report import fail


CALL = re.compile(r"(?<![\w.'\[])([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)\s*\(")


def unknown_functions(m, expr):
    """Calls like DaxLib.SVG.Viz.Nope( whose first name part (DaxLib) is an installed package's, but which the model
    doesn't define. Built-ins with dots (NORM.DIST) don't share a package's first part, so they never match."""
    roots = {f.split(".")[0] for f in m.functions if "." in f}
    if not roots or not expr:
        return []
    text = re.sub(r'"[^"]*"', '""', expr)                     # not inside string literals
    out = []
    for name in CALL.findall(text):
        if name.split(".")[0] in roots and name not in m.functions and name not in out:
            out.append(name)
    return out


def check(model_path, only_folder=None):
    p = pathlib.Path(model_path)
    if p.suffix.lower() == ".pbip":
        p = p.with_suffix(".SemanticModel")
    if not ((p / "definition").is_dir() or list(p.glob("*.tmdl"))):
        fail(f"{model_path}: no TMDL definition folder (save the model as TMDL in Desktop)")
    m = tmdl.load(p)
    errors = []
    texts = daxtype.text_measures(m)

    def where(obj):
        return f"{obj.file}:{obj.line}"

    for mm in m.all_measures():
        if only_folder and (mm.display_folder or "") != only_folder:
            continue
        name = f"{mm.table}[{mm.name}]"
        if not mm.description:
            errors.append(f"{where(mm)}  {name}: no description (add a /// line above the measure)")
        if not (mm.format_string or mm.format_string_definition) and (mm.table, mm.name) not in texts:
            errors.append(f"{where(mm)}  {name}: no format string (a number measure needs one; text measures are "
                          "recognised from their DAX)")
        for bad in tmdl.check_references(m, mm.expression):
            errors.append(f"{where(mm)}  {name}: reference {bad} doesn't exist")
        for bad in unknown_functions(m, mm.expression):
            errors.append(f"{where(mm)}  {name}: function {bad} isn't in the model (functions.tmdl)")
    for t in m.tables.values():
        for c in t.columns.values():
            if c.expression:
                for bad in tmdl.check_references(m, c.expression):
                    errors.append(f"{where(c)}  {t.name}[{c.name}] (calculated column): reference {bad} doesn't exist")
            if c.sort_by and c.sort_by not in t.columns:
                errors.append(f"{where(c)}  {t.name}[{c.name}]: sort-by column {c.sort_by!r} doesn't exist")
        for kind, expr, line in t.partitions:
            if kind == "calculated" and expr:
                for bad in tmdl.check_references(m, expr):
                    errors.append(f"{t.file}:{line}  {t.name} (calculated table): reference {bad} doesn't exist")
    for r in m.relationships:
        for side, ref in (("from", r.from_column), ("to", r.to_column)):
            if not ref or not ref[0]:
                errors.append(f"{r.file}:{r.line}  relationship {r.name}: no {side}Column")
                continue
            tbl, col = ref
            if tbl not in m.tables:
                errors.append(f"{r.file}:{r.line}  relationship {r.name}: {side} table {tbl!r} doesn't exist")
            elif col not in m.tables[tbl].columns:
                errors.append(f"{r.file}:{r.line}  relationship {r.name}: {side} column {tbl}[{col}] doesn't exist")
    nm = sum(1 for _ in m.all_measures())
    for e in errors:
        print(f"error  {e}")
    print(f"\n{p.name}: {len(m.tables)} tables, {nm} measures, {len(m.functions)} functions, "
          f"{len(m.relationships)} relationships: "
          f"{len(errors)} error(s)" + (f" (measures in display folder {only_folder!r} only)" if only_folder else ""))
    return errors
