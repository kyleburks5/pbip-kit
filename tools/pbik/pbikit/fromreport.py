"""`pbik layout from-report <X.Report> [--out F]`: an existing report as a draft layout.json (v1.7, A2).

Reads the PBIR pages and visuals (position, size, type, fields; never data: a report folder holds none), turns them
into a boxes file in each page's own pixels and runs the same mapping as a wireframe (design/scripts/ref_layout.py):
scaled to 1920 wide, snapped to the 12-column grid and to 8px, visual types chosen, IDs in reading order. Then the
fields come back on each visual as bindings, by role, as layout.json names them ("Table[Column]", "[Measure]").
Visual groups, and visuals hidden in the report, are left out (listed in the result).
"""
import json, pathlib, sys

KIT = pathlib.Path(__file__).resolve().parents[3]

KINDS = {"card": ("kpi", None), "cardVisual": ("kpi", None), "multiRowCard": ("kpi", None), "kpi": ("kpi", None),
         "gauge": ("kpi", None), "lineChart": ("chart", "line"), "areaChart": ("chart", "area"),
         "stackedAreaChart": ("chart", "area"), "barChart": ("chart", "bar"), "clusteredBarChart": ("chart", "bar"),
         "hundredPercentStackedBarChart": ("chart", "bar"), "columnChart": ("chart", "column"),
         "clusteredColumnChart": ("chart", "column"), "hundredPercentStackedColumnChart": ("chart", "column"),
         "lineClusteredColumnComboChart": ("chart", "column"), "lineStackedColumnComboChart": ("chart", "column"),
         "donutChart": ("chart", "donut"), "pieChart": ("chart", "pie"), "scatterChart": ("chart", "scatter"),
         "map": ("chart", "map"), "filledMap": ("chart", "map"), "azureMap": ("chart", "map"),
         "tableEx": ("table", None), "pivotTable": ("matrix", None), "slicer": ("slicer", None),
         "advancedSlicerVisual": ("buttons", None), "actionButton": ("button", None), "textbox": ("text", None),
         "image": ("image", None), "pageNavigator": ("tabs", None), "bookmarkNavigator": ("buttons", None),
         "shape": ("panel", None), "basicShape": ("panel", None)}


class FromReportError(Exception):
    pass


def field_name(f):
    """A PBIR field reference -> "Table[Column]" or "[Measure]"; None when it isn't a plain column or measure."""
    for kind in ("Column", "Measure", "Aggregation", "HierarchyLevel"):
        x = f.get(kind)
        if not x:
            continue
        if kind == "Aggregation":
            return field_name(x.get("Expression") or {})
        if kind == "HierarchyLevel":
            lvl = x.get("Level")
            ent = (((x.get("Expression") or {}).get("Hierarchy") or {}).get("Expression") or {}).get("SourceRef", {})
            return f"{ent.get('Entity', '')}[{lvl}]" if lvl else None
        ent = ((x.get("Expression") or {}).get("SourceRef") or {}).get("Entity")
        prop = x.get("Property")
        if kind == "Measure":
            return f"[{prop}]"
        return f"{ent}[{prop}]" if ent and prop else None
    return None


def visual_fields(v):
    """{role: [field names]} from a visual.json's query."""
    qs = (((v.get("visual") or {}).get("query") or {}).get("queryState")) or {}
    out = {}
    for role, spec in qs.items():
        names = [field_name(p.get("field") or {}) for p in (spec or {}).get("projections", [])]
        names = [n for n in names if n]
        if names:
            out[role] = names
    return out


def read_report(report):
    """{"width", "height", "pages": [{"name", "boxes"}]} (each box keeps its fields), plus what was left out."""
    report = pathlib.Path(report)
    pages_dir = report / "definition" / "pages"
    if not pages_dir.is_dir():
        raise FromReportError("that folder isn't a Power BI report in the project format (no pages found)")
    meta = {}
    try:
        meta = json.loads((pages_dir / "pages.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    order = meta.get("pageOrder") or sorted(p.name for p in pages_dir.iterdir() if p.is_dir())
    pages, left_out, width, height = [], [], None, None
    for name in order:
        pf = pages_dir / name / "page.json"
        if not pf.exists():
            continue
        page = json.loads(pf.read_text(encoding="utf-8"))
        if page.get("visibility") == "HiddenInViewMode":
            left_out.append(f"page {page.get('displayName', name)} (hidden)")
            continue
        width, height = width or page.get("width", 1280), height or page.get("height", 720)
        boxes = []
        for vf in sorted((pages_dir / name / "visuals").glob("*/visual.json")):
            v = json.loads(vf.read_text(encoding="utf-8"))
            if "visualGroup" in v or "visual" not in v:
                continue
            if v.get("isHidden"):
                left_out.append(f"a hidden {v['visual'].get('visualType')} on {page.get('displayName', name)}")
                continue
            vt = v["visual"].get("visualType", "")
            kind, chart = KINDS.get(vt, ("chart", "other"))
            pos = v.get("position") or {}
            b = {"kind": kind, "x": pos.get("x", 0), "y": pos.get("y", 0), "w": pos.get("width", 100),
                 "h": pos.get("height", 100), "_fields": visual_fields(v), "_type": vt}
            if chart:
                b["chart"] = chart
            if vt not in KINDS:
                b["features"] = [f"{vt} visual (not a core visual)"] if not vt.startswith("deneb") else []
            boxes.append(b)
        pages.append({"name": page.get("displayName", name), "boxes": boxes, "_w": page.get("width", width),
                      "_h": page.get("height", height)})
    if not pages:
        raise FromReportError("the report has no visible pages")
    return {"width": width, "height": height, "pages": pages}, left_out


def from_report(report):
    """(layout, findings, left_out): the report as a draft layout.json with its fields as bindings."""
    sys.path.insert(0, str(KIT / "design" / "scripts"))
    import ref_layout as RL
    ref, left_out = read_report(report)
    layout, findings, _ = RL.map_reference(ref)
    by_box = {}
    for p_i, page in enumerate(ref["pages"], start=1):
        for b in page["boxes"]:
            by_box[(f"P{p_i}", round(b["x"]), round(b["y"]), round(b["w"]), round(b["h"]))] = b
    for v in layout["visuals"]:
        r = v.get("reference") or {}
        b = by_box.get((v["page"], r.get("x"), r.get("y"), r.get("w"), r.get("h")))
        if not b:
            continue
        roles = {"cardVisual": "Data", "tableEx": "Values", "pivotTable": "Rows", "slicer": "Values",
                 "advancedSlicerVisual": "Values"}
        fields = b["_fields"]
        if fields:
            if v["type"] == b["_type"]:
                v["bindings"] = fields
            elif v["type"] in roles:
                v["bindings"] = {roles[v["type"]]: [n for ns in fields.values() for n in ns]}
            else:
                v["bindings"] = fields
        v["reference"]["from"] = b["_type"]
    layout["_note"] = ("Draft from an existing report (pbik layout from-report): positions on the grid, types and "
                       "fields from the report. The plan picture shows it; the person adjusts it in plain words.")
    return layout, findings, left_out
