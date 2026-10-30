"""pbik measure ext: report-level extension measures in definition/reportExtensions.json.

Shape as Desktop saves it: {"$schema", "name": "extension", "entities": [{"name": <table>, "measures": [{name,
expression, dataType, dataCategory?, formatString?, description?}]}]}. Visuals bind them with SourceRef Schema
"extension". Typical use: a Text / ImageUrl wrapper around a model SVG measure, so a card's image can show it.
"""
from .objects import load
from .report import Report, fail

DATA_TYPES = ("Text", "Double", "Integer", "Decimal", "Boolean", "DateTime")


def add(report_path, name, expression, data_category=None, data_type=None, table=None, format_string=None,
        description=None):
    rep = Report(report_path)
    model = rep.model()
    if table is None:
        homes = sorted({m.table for m in model.all_measures()}) if model else []
        table = "_Measures" if model and "_Measures" in model.tables else (homes[0] if homes else None)
        if not table:
            fail("no --table given and no measure table found in the model")
    if model and table not in model.tables:
        fail(f"table {table!r} is not in the model")
    if model and model.measure_home(name):
        fail(f"{name!r} is already a model measure ({model.measure_home(name)}); pick another name")
    data_type = data_type or ("Text" if data_category == "ImageUrl" else "Text")
    if data_type not in DATA_TYPES:
        fail(f"--data-type must be one of {DATA_TYPES}")
    f = rep.ext_file()
    d = load(f) if f.exists() else {"$schema": rep.schema_version("reportExtension"), "name": "extension", "entities": []}
    ent = next((e for e in d["entities"] if e["name"] == table), None)
    if ent is None:
        ent = {"name": table, "measures": []}
        d["entities"].append(ent)
    for e in d["entities"]:                  # one name per report
        if e is not ent:
            e["measures"] = [m for m in e.get("measures", []) if m["name"] != name]
    m = {"name": name, "expression": expression, "dataType": data_type}
    if data_category:
        m["dataCategory"] = data_category
    if format_string:
        m["formatString"] = format_string
    if description:
        m["description"] = description
    lst = ent.setdefault("measures", [])
    pos = next((k for k, x in enumerate(lst) if x["name"] == name), None)
    if pos is None:
        lst.append(m)
    else:
        lst[pos] = m
    d["entities"] = [e for e in d["entities"] if e.get("measures")]
    changed = rep.write(f, d)
    print(f"{'wrote' if changed else 'same '} {table}[{name}] in {f.relative_to(rep.path.parent)}")
    return changed


def list_(report_path):
    rep = Report(report_path)
    ext = rep.extensions()
    if not ext:
        print("no report extension measures")
    for (t, n), m in ext.items():
        print(f"{t}[{n}]  {m.get('dataType', '')} {m.get('dataCategory', '')}  = {m.get('expression', '')[:80]}")


def remove(report_path, name):
    rep = Report(report_path)
    f = rep.ext_file()
    if not f.exists():
        fail("no reportExtensions.json")
    d = load(f)
    before = sum(len(e.get("measures", [])) for e in d["entities"])
    for e in d["entities"]:
        e["measures"] = [m for m in e.get("measures", []) if m["name"] != name]
    d["entities"] = [e for e in d["entities"] if e.get("measures")]
    if sum(len(e.get("measures", [])) for e in d["entities"]) == before:
        fail(f"{name!r} not found")
    rep.write(f, d)
    print(f"removed {name}")
