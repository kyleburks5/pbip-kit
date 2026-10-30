"""pbik templates harvest: turn the visuals on a page named "Patterns" into reusable visual templates.

Each visual.json on that page is copied to design/templates/<visualType>.<name>.json (the visual name without its
P<n>-V<nn>_ ID, e.g. cardVisual.card-reference-labels.json) with its field bindings (query), name and position
removed; objects, visualContainerObjects, filters and conditional formatting are kept as Desktop saved them. The
largest visual of each type (by area, then by ID) is also written as <visualType>.json, the default `pbik build` uses
when layout.json names no template. Pick another in layout.json with "template": "<file stem>".
Formatting bound to fields stays in the template; `pbik build` drops what the target model doesn't have (with a
warning). An index of every template, with its source visual, goes to <out>/index.json.
"""
import copy, pathlib, re

from .objects import load, save
from .report import ID_RE, Report, fail

DROP_TOP = ("name", "position", "parentGroupName", "howCreated")


def strip(d):
    t = copy.deepcopy(d)
    for k in DROP_TOP:
        t.pop(k, None)
    vis = t.get("visual", {})
    q = vis.pop("query", None)
    if q == {"queryState": {}}:                 # no fields: keep Desktop's empty query (pbik build follows it)
        vis["query"] = q
    t["_pbik"] = {"note": "Visual template harvested by pbik templates harvest; bindings, name and position removed."}
    return t


def harvest(report_path, out_dir="design/templates", page_name="Patterns"):
    rep = Report(report_path)
    hit = rep.page_by(page_name)
    if not hit:
        fail(f"no page named {page_name!r} in {rep.path.name} (pages: {[p[1].get('displayName') for p in rep.pages()]})")
    _, _, folder = hit
    out = pathlib.Path(out_dir)
    written, index, best = [], {}, {}
    for d, f in rep.visuals(folder):
        vt = d.get("visual", {}).get("visualType")
        if not vt:
            continue
        vname = d.get("name", f.parent.name)
        short = re.sub(r"[^A-Za-z0-9_-]+", "-", ID_RE.match(vname).group(2) if ID_RE.match(vname) else vname)
        stem = f"{vt}.{short}"
        tpl = strip(d)
        written.append((out / f"{stem}.json", save(out / f"{stem}.json", tpl), f.parent.name))
        index[stem] = {"visualType": vt, "source": f.parent.name}
        pos = d.get("position", {})
        area = pos.get("width", 0) * pos.get("height", 0)
        if vt not in best or area > best[vt][0]:
            best[vt] = (area, tpl, f.parent.name, stem)
    for vt, (_, tpl, src, stem) in sorted(best.items()):
        written.append((out / f"{vt}.json", save(out / f"{vt}.json", tpl), src))
        index[vt] = {"visualType": vt, "source": src, "default": True, "sameAs": stem}
    if written:
        save(out / "index.json", {"_note": f"pbik templates harvest from {rep.path.name}, page {page_name!r}. "
                                           "<type>.json is the default (the largest visual of that type).",
                                  "templates": dict(sorted(index.items()))})
    for target, changed, src in written:
        print(f"{'wrote' if changed else 'same '} {target}  (from {src})")
    if not written:
        print(f"page {page_name!r} has no visuals")
    return written
