"""Visuals Desktop added without a pbik ID (batch 3 item 11): propose an ID, a folder name and alt text, and with
`pbik roundtrip --name-new` apply them, so the visual can join layout.json.

An ID is the next free number on the page (`P<page>-V<nn>`; IDs in layout.json `retired` are skipped); the folder
becomes `<ID>_<type>`; data visuals without alt text get one from their fields ("Line chart of Total Amount by
Month"), to be reworded by the author. Every place the old visual name appears (page interactions, bookmarks,
group members, mobile layout) is renamed with it.
"""
import json, re

from .objects import load, save
from .report import ID_RE

TYPE_LABEL = {"cardVisual": "Card", "card": "Card", "lineChart": "Line chart", "barChart": "Bar chart",
              "clusteredBarChart": "Bar chart", "columnChart": "Column chart", "clusteredColumnChart": "Column chart",
              "tableEx": "Table", "pivotTable": "Matrix", "donutChart": "Donut chart", "pieChart": "Pie chart",
              "areaChart": "Area chart", "scatterChart": "Scatter chart", "gauge": "Gauge", "kpi": "KPI",
              "map": "Map", "filledMap": "Map", "waterfallChart": "Waterfall chart", "funnel": "Funnel"}
NO_ALT = {"shape", "basicShape", "textbox", "actionButton", "pageNavigator", "bookmarkNavigator", "slicer",
          "advancedSlicerVisual", "listSlicer", "textSlicer", "image"}


def kebab(text):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"([a-z])([A-Z])", r"\1-\2", text or "visual").lower()).strip("-")


def alt_for(d):
    vis = d.get("visual") or {}
    vtype = vis.get("visualType", "")
    if vtype in NO_ALT:
        return None
    measures, columns = [], []
    for role in (vis.get("query") or {}).get("queryState", {}).values():
        for p in role.get("projections", []):
            name = p.get("displayName") or p.get("nativeQueryRef") or p.get("queryRef", "").split(".")[-1]
            (measures if "Measure" in p.get("field", {}) or "Aggregation" in p.get("field", {}) else columns).append(name)
    if not measures and not columns:
        return None
    label = TYPE_LABEL.get(vtype, vtype)
    text = f"{label} of {', '.join(measures or columns)}"
    if measures and columns:
        text += f" by {', '.join(columns)}"
    return text


def has_alt(d):
    for e in ((d.get("visual") or {}).get("visualContainerObjects") or {}).get("general", []):
        if (e.get("properties") or {}).get("altText"):
            return True
    return False


def proposals(rep, layout=None):
    """[{page, folder, id, newFolder, alt, entry}] for every visual whose folder has no ID."""
    retired = set((layout or {}).get("retired", []))
    out = []
    for k, (name, pd, pfolder) in enumerate(rep.pages(), 1):
        visuals = rep.visuals(pfolder)
        ids = [ID_RE.match(f.parent.name).group(1) for _, f in visuals if ID_RE.match(f.parent.name)]
        nums = [int(i.split("V")[1]) for i in ids]
        pages = {i.split("-")[0] for i in ids}
        page = sorted(pages)[0] if len(pages) == 1 else f"P{k}"
        used = set(nums) | {int(r.split("V")[1]) for r in retired if r.startswith(page + "-V")}
        nxt = max(used or {0}) + 1
        for d, f in visuals:
            if ID_RE.match(f.parent.name):
                continue
            vid = f"{page}-V{nxt:02d}"
            nxt += 1
            vtype = (d.get("visual") or {}).get("visualType", "visual")
            alt = None if has_alt(d) else alt_for(d)
            pos = d.get("position", {})
            entry = {"id": vid, "name": kebab(vtype), "page": page, "type": vtype,
                     "desktopPosition": {k_: pos[k_] for k_ in ("x", "y", "z", "width", "height", "tabOrder") if k_ in pos}}
            if alt:
                entry["container"] = {"altText": alt}
            out.append({"page": pd.get("displayName", name), "folder": f.parent.name, "id": vid,
                        "newFolder": f"{vid}_{kebab(vtype)}", "alt": alt, "entry": entry, "file": f})
    return out


def _rename(node, old, new):
    """Replace a visual name used as a string value or a dict key, in place. Returns the count."""
    n = 0
    if isinstance(node, dict):
        for k in list(node):
            v = node[k]
            if k == old:
                node[new] = node.pop(k)
                n += 1
            if v == old and isinstance(v, str):
                node[k if k != old else new] = new
                n += 1
            else:
                n += _rename(v, old, new)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if v == old:
                node[i] = new
                n += 1
            else:
                n += _rename(v, old, new)
    return n


def apply(rep, props):
    """Rename folders, set names and alt text, and rename every reference. Returns the files changed."""
    changed = []
    for p in props:
        f = p["file"]
        d = load(f)
        old = d.get("name", p["folder"])
        d["name"] = p["newFolder"]
        if p["alt"]:
            vco = d.setdefault("visual", {}).setdefault("visualContainerObjects", {})
            vco.setdefault("general", [{"properties": {}}])[0].setdefault("properties", {})["altText"] = {
                "expr": {"Literal": {"Value": "'" + p["alt"].replace("'", "''") + "'"}}}
        save(f, d)
        target = f.parent.with_name(p["newFolder"])
        f.parent.rename(target)
        changed.append(str(target.relative_to(rep.path)))
        for g in list(rep.defn.rglob("*.json")):
            if g.parent == target:
                continue
            try:
                doc = load(g)
            except json.JSONDecodeError:
                continue
            if old in json.dumps(doc) and _rename(doc, old, p["newFolder"]):
                save(g, doc)
                changed.append(str(g.relative_to(rep.path)))
    return changed


def text(props):
    if not props:
        return ""
    lines = ["", "## Visuals without an ID (Desktop added them)", "",
             "| Page | Folder | Proposed ID | Alt text |", "| --- | --- | --- | --- |"]
    for p in props:
        lines.append(f"| {p['page']} | {p['folder']} | {p['id']} ({p['newFolder']}) | {p['alt'] or '(has one, or none needed)'} |")
    lines += ["", "`pbik roundtrip <Report> --name-new` renames them and writes the alt text; then add these to "
              "layout.json (desktopPosition keeps Desktop's exact box):", "", "```json"]
    lines += [json.dumps(p["entry"]) for p in props] + ["```"]
    return "\n".join(lines)
