"""Settings catalog: every formatting property, value type and selector shape found in files Power BI Desktop saved.

    pbik catalog refresh <project or report folder> ...     scan Desktop-saved files and merge them into the catalog
    pbik catalog refresh --name work <folder>              the same into a named catalog (tools/pbik/catalogs/work.json)
    pbik catalog show [--type cardVisual] [--object title]  print what is known
    pbik catalog list                                       the catalogs and the Desktop version each came from

Named catalogs hold what one machine's Desktop saved ("home", "work"): settings an older Desktop never saved are
warnings when a report validates against its catalog. project.json `catalog` names the one `pbik validate` uses;
without a name it is "home" (tools/pbik/catalogs/home.json, this machine's).

`pbik validate` warns when pbik wrote a property, value type or selector the catalog has never seen in a
Desktop-saved file: a setting Desktop may ignore or rewrite (docs/lessons/build.md, "Before restyling a visual, look up ...").

A file counts as Desktop-saved when it has no final newline: Desktop writes none, pbik always writes one (seen in the
Patterns page save, 2026-10-19). `--all` scans every file anyway.

Catalog (tools/pbik/catalogs/<name>.json):
  visuals.<visualType>.objects.<object>.<property>   {types: [...], selectors: [...]}
  container.<object>.<property>                      visualContainerObjects, the same for every visual type
  page.<object>.<property>                           page.json objects
  sources: [{folder, files}]
Value types: bool, number (12D), int (12L), text ('x'), datetime, color:literal / color:theme / color:measure /
color:aggregation / color:conditional / color:fillRule, measure, column, aggregation, resource, paragraphs, filter, ...
Selector shapes: none, id:default / id:hover / id:selected / id:<n> / id:field-*, metadata, data:dataViewWildcard,
data:scopeId, and combinations joined with '+' (data:dataViewWildcard+metadata).
"""
import json, pathlib, re

from .objects import load, save

HERE = pathlib.Path(__file__).resolve().parent
CATALOGS = HERE.parent / "catalogs"
DEFAULT_NAME = "home"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
NAMED_IDS = {"default", "hover", "selected", "disabled", "press"}


def desktop_saved(f):
    with open(f, "rb") as fh:
        fh.seek(0, 2)
        if fh.tell() == 0:
            return False
        fh.seek(-1, 2)
        return fh.read(1) != b"\n"


# ---------------------------------------------------------------- value types and selector shapes
def expr_type(e):
    if not isinstance(e, dict):
        return "other"
    if "Literal" in e:
        v = str(e["Literal"].get("Value", ""))
        if v in ("true", "false"):
            return "bool"
        if v.startswith("'"):
            return "text"
        if v.startswith("datetime"):
            return "datetime"
        if re.fullmatch(r"-?\d+L", v):
            return "int"
        if re.fullmatch(r"-?[\d.]+(E-?\d+)?D|-?[\d.]+M", v):
            return "number"
        return "literal"
    for k, name in (("ThemeDataColor", "theme"), ("Measure", "measure"), ("Column", "column"),
                    ("Aggregation", "aggregation"), ("ResourcePackageItem", "resource"),
                    ("Conditional", "conditional"), ("FillRule", "fillRule"), ("SelectRef", "selectRef")):
        if k in e:
            return name
    return "expr:" + next(iter(e), "?")


def value_type(v):
    if isinstance(v, list):
        return "paragraphs" if v and isinstance(v[0], dict) and "textRuns" in v[0] else "list"
    if not isinstance(v, dict):
        return type(v).__name__
    if "expr" in v:
        return expr_type(v["expr"])
    if "solid" in v:
        t = expr_type(v["solid"].get("color", {}).get("expr"))
        return "color:" + ("literal" if t == "text" else t)
    if "filter" in v:
        return "filter"
    return "object:" + next(iter(v), "?")


def selector_shape(sel):
    if not sel:
        return "none"
    parts = []
    for k in sorted(sel):
        x = sel[k]
        if k == "id":
            x = str(x)
            parts.append("id:" + (x if x in NAMED_IDS else "field-*" if x.startswith("field-") else
                                  "<n>" if x.isdigit() else "<other>"))
        elif k == "data":
            kinds = sorted({next(iter(d), "?") for d in x if isinstance(d, dict)}) if isinstance(x, list) else ["?"]
            parts.append("data:" + "+".join(kinds))
        else:
            parts.append(k)
    return "+".join(parts)


# ---------------------------------------------------------------- scanning
def entries(objs):
    """(object, property, value type, selector shape) for every property in a PBIR objects dict."""
    for obj, lst in (objs or {}).items():
        for e in lst if isinstance(lst, list) else []:
            shape = selector_shape(e.get("selector"))
            props = e.get("properties", {})
            if not props:
                yield obj, None, None, shape
            for prop, val in props.items():
                yield obj, prop, value_type(val), shape


def _add(node, obj, prop, vt, shape):
    o = node.setdefault(obj, {})
    p = o.setdefault(prop or "_entry", {"types": [], "selectors": []})
    if vt and vt not in p["types"]:
        p["types"].append(vt)
        p["types"].sort()
    if shape not in p["selectors"]:
        p["selectors"].append(shape)
        p["selectors"].sort()


def report_folders(folder):
    p = pathlib.Path(folder)
    if (p / "definition").is_dir():
        return [p]
    return sorted(x for x in p.glob("*.Report") if (x / "definition").is_dir())


def scan(folders, cat=None, include_all=False):
    """Merge every Desktop-saved visual.json and page.json under the folders into cat. Returns (cat, added) with
    added = ["visualType.object.property: type @ selector", ...] new to the catalog."""
    cat = cat or {"visuals": {}, "container": {}, "page": {}, "sources": []}
    before = set(flatten(cat))
    for folder in folders:
        reps = report_folders(folder)
        if not reps:
            raise SystemExit(f"{folder}: no *.Report folder with a definition/ inside")
        for rep in reps:
            n = 0
            for f in sorted(rep.glob("definition/pages/*/visuals/*/visual.json")):
                if not include_all and not desktop_saved(f):
                    continue
                d = load(f)
                vis = d.get("visual") or {}
                vt = vis.get("visualType")
                if vt:
                    node = cat["visuals"].setdefault(vt, {})
                    for obj, prop, t, sh in entries(vis.get("objects")):
                        _add(node, obj, prop, t, sh)
                for obj, prop, t, sh in entries(vis.get("visualContainerObjects")):
                    _add(cat["container"], obj, prop, t, sh)
                n += 1
            for f in sorted(rep.glob("definition/pages/*/page.json")):
                if include_all or desktop_saved(f):
                    for obj, prop, t, sh in entries(load(f).get("objects")):
                        _add(cat["page"], obj, prop, t, sh)
                    n += 1
            name = str(rep).replace("\\", "/")
            src = next((s for s in cat["sources"] if s["folder"] == name), None)
            if src:
                src["files"] = n
            else:
                cat["sources"].append({"folder": name, "files": n})
    cat["sources"].sort(key=lambda s: s["folder"])
    for key in ("visuals",):
        cat[key] = {k: _sorted(v) for k, v in sorted(cat[key].items())}
    cat["container"], cat["page"] = _sorted(cat["container"]), _sorted(cat["page"])
    added = sorted(set(flatten(cat)) - before)
    return cat, added


def _sorted(node):
    return {o: dict(sorted(p.items())) for o, p in sorted(node.items())}


def flatten(cat):
    for vt, objs in cat.get("visuals", {}).items():
        for obj, props in objs.items():
            for prop, info in props.items():
                for t in info["types"] or ["-"]:
                    for sh in info["selectors"]:
                        yield f"{vt}.{obj}.{prop}: {t} @ {sh}"
    for where in ("container", "page"):
        for obj, props in cat.get(where, {}).items():
            for prop, info in props.items():
                for t in info["types"] or ["-"]:
                    for sh in info["selectors"]:
                        yield f"{where}.{obj}.{prop}: {t} @ {sh}"


def catalog_path(name=None, path=None):
    """--catalog <file> wins; then a catalog name (none: "home")."""
    if path:
        return pathlib.Path(path)
    name = name or DEFAULT_NAME
    if not NAME_RE.match(name):
        raise SystemExit(f"pbik: catalog name {name!r}: letters, digits, - or _ (e.g. home, work)")
    return CATALOGS / f"{name}.json"


def list_catalogs():
    rows = [(f.stem, f) for f in sorted(CATALOGS.glob("*.json"))]
    for name, f in rows:
        if not f.exists():
            continue
        cat = load(f)
        desk = cat.get("desktop") or {}
        print(f"{name:12} {sum(1 for _ in flatten(cat)):5} setting(s)  {len(cat.get('sources', []))} report(s)  "
              f"Desktop {desk.get('version', '?')}" + (f" ({desk['refreshed']})" if desk.get("refreshed") else ""))


def load_catalog(path=None):
    p = pathlib.Path(path) if path else catalog_path()
    return load(p) if p.exists() else None


def refresh(folders, path=None, include_all=False, name=None, desktop=None, today=None):
    """desktop: the Desktop version that saved the files (recorded in the catalog; detected when not given)."""
    import datetime
    from . import versions
    p = catalog_path(name, path)
    cat = load_catalog(p)
    if cat is not None:
        cat.pop("_note", None)
    cat, added = scan(folders, cat, include_all)
    v = desktop or (versions.detect_desktop() if not path else None)      # a named catalog is this machine's
    if v and v != (cat.get("desktop") or {}).get("version"):      # the date moves only with the version
        cat["desktop"] = {"version": v, "refreshed": today or datetime.date.today().isoformat()}
    out = {"_note": "Settings Power BI Desktop saved, by visual type / container / page, object and property: value "
                    "types and selector shapes. Written by `pbik catalog refresh` (pbikit/catalog.py); don't edit.",
           **cat}
    changed = save(p, out)
    for a in added:
        print(f"new  {a}")
    print(f"{p}: {sum(1 for _ in flatten(cat))} setting(s) from {len(cat['sources'])} report(s); {len(added)} new"
          + ("" if changed else " (unchanged)"))
    return added


# ---------------------------------------------------------------- checks (pbik validate)
def check_entry(cat, visual_type, where, obj, prop, val, sel):
    """None if Desktop has saved this (object, property, value type, selector); else the reason."""
    if where == "visualContainerObjects":
        node, label = cat.get("container", {}), "container"
    elif where == "page":
        node, label = cat.get("page", {}), "page"
    else:
        node, label = cat.get("visuals", {}).get(visual_type), visual_type
        if node is None:
            return f"no Desktop-saved {visual_type} in the catalog"
    info = node.get(obj, {}).get(prop or "_entry")
    if info is None:
        return (f"{label} object {obj!r} never seen in a Desktop-saved file" if obj not in node else
                f"{label} {obj}.{prop} never seen in a Desktop-saved file")
    if prop is not None:
        vt = value_type(val)
        if vt not in info["types"]:
            return f"{label} {obj}.{prop} as {vt}: Desktop saved it only as {', '.join(info['types'])}"
    shape = selector_shape(sel)
    if shape not in info["selectors"]:
        return f"{label} {obj}.{prop or ''} on selector {shape}: Desktop saved it only on {', '.join(info['selectors'])}"
    return None


def show(path=None, visual_type=None, obj=None):
    cat = load_catalog(path)
    if cat is None:
        raise SystemExit(f"no catalog at {path or catalog_path()}: run pbik catalog refresh --name <name> <folders>")
    for line in flatten(cat):
        head = line.split(":", 1)[0].split(".")
        if visual_type and head[0] != visual_type:
            continue
        if obj and (len(head) < 2 or head[1] != obj):
            continue
        print(line)
