"""pbik info: pages and visuals by ID, type, position and fields (read-only)."""
import json

from .objects import qref
from .report import ID_RE, Report
from .validate import walk_fields


def info(report_path, as_json=False):
    rep = Report(report_path)
    out = []
    for name, pd, folder in rep.pages():
        page = {"name": name, "displayName": pd.get("displayName"), "width": pd.get("width"),
                "height": pd.get("height"), "displayOption": pd.get("displayOption"), "visuals": []}
        for d, f in rep.visuals(folder):
            m = ID_RE.match(f.parent.name)
            pos = d.get("position", {})
            roles = {}
            for role, st in d.get("visual", {}).get("query", {}).get("queryState", {}).items():
                roles[role] = [p.get("queryRef") or qref(p["field"]) for p in st.get("projections", [])]
            other = sorted({f"{e}.{p}" for k, e, s, p, path in walk_fields(d) if "/query/" not in path})
            page["visuals"].append({"id": m.group(1) if m else None, "folder": f.parent.name,
                                    "type": d.get("visual", {}).get("visualType"),
                                    "x": pos.get("x"), "y": pos.get("y"), "w": pos.get("width"),
                                    "h": pos.get("height"), "z": pos.get("z"), "fields": roles, "otherFields": other})
        out.append(page)
    if as_json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return out
    ext = rep.extensions()
    mf = rep.model_folder()
    print(f"{rep.path.name}  (model: {mf.name if mf else 'not found'}; extension measures: {len(ext)})")
    for p in out:
        print(f"\nPage {p['displayName']!r}  [{p['name']}]  {p['width']}x{p['height']} {p['displayOption']}")
        for v in sorted(p["visuals"], key=lambda x: (x["id"] is None, x["id"] or x["folder"])):
            box = f"{v['x']},{v['y']} {v['w']}x{v['h']} z{v['z']}"
            print(f"  {v['id'] or '(no ID)':9} {v['type'] or '?':28} {box:26} {v['folder']}")
            for role, fl in v["fields"].items():
                print(f"            {role}: {', '.join(fl)}")
            if v["otherFields"]:
                print(f"            (filters/formatting): {', '.join(v['otherFields'])}")
    return out
