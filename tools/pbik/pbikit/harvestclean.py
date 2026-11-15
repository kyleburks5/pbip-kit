"""pbik templates harvest --clean: templates from any report page, with nothing of the source left in them.

For studying someone's report (or one's own polished report) without copying it: the visuals on any page (or every
page), or only those a pick file names, become design/templates/<visualType>.<name>.json with
- removed: the name, position, group, filters, howCreated, hidden flag and the query (bindings);
- removed: every text the report wrote (titles, subtitles, alt text, labels, card titles, "show blank as", button
  and tab text, the selected bookmark), every saved selection (slicer `general.filter`), every registered or bound
  image, every property bound to a field or measure (conditional formatting, colour measures, detail values), every
  entry whose selector names a field, a data point or a member (per-field and per-member formatting), and the axis
  start and end values (the source data's range);
- mapped: every colour, literal or theme slot, to a tokens.json role (card, border, text, textMuted, shadow, brand),
  written as that role's colour in design/templates/palette.json, so `pbik build` recolours it to the project's
  palette like any kit template;
- kept: formatting settings as Desktop saved them (numbers, true/false, enum values, font families, state
  selectors such as default, hover, selected).
A leak check then looks for every removed text in the written files; a hit is an error and the file isn't written.
The run never touches the `<visualType>.json` defaults; it adds its templates to index.json (source: the label).
The report (--log, Markdown) lists per template what was removed and how each colour was mapped, by property path and
reason: no values.
"""
import copy, json, pathlib, re

from .objects import load, save
from .recolour import category, load_palette
from .report import ID_RE, Report, fail

KEEP_TOP = ("$schema",)
KEEP_VISUAL = ("visualType", "objects", "visualContainerObjects", "drillFilterOtherVisuals", "autoSelectVisualType")
TEXT_PROPS = {"text", "titletext", "alttext", "showblankas", "selectedbookmark", "imageurl", "url", "name", "tooltip",
              "paragraphs", "webur", "weburl", "bookmark", "pagename", "destination", "drillthroughsection",
              "placeholdertext", "headertext", "customtext", "label", "suffix", "prefix", "description"}
PROJECT_NUMBERS = {("categoryAxis", "start"), ("categoryAxis", "end"), ("valueAxis", "start"), ("valueAxis", "end"),
                   ("y1AxisReferenceLine", "value"), ("referenceLine", "value"), ("xAxisReferenceLine", "value")}
BOUND = ("Measure", "Column", "Aggregation", "HierarchyLevel", "Conditional", "FillRule", "ResourcePackageItem",
         "SelectRef", "SparklineData", "Arithmetic", "Hierarchy")
HEX = re.compile(r"^'?(#[0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?'?$")
ENUM = re.compile(r"^'[A-Za-z0-9:_.\-]{1,40}'$")
FONT_PROPS = re.compile(r"fontfamily$|fontface$", re.I)
NUM = re.compile(r"^-?\d+(\.\d+)?[DLM]?$")


def _lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    sat = (max(r, g, b) - min(r, g, b)) / (max(r, g, b) or 1)
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2], sat


def role_of_hex(h, cat):
    """A literal colour's tokens.json role, from where it sits and how light and saturated it is."""
    if cat == "shadow":
        return "shadow", "shadow"
    lum, sat = _lum(h)
    if lum >= 0.93:
        return ("card" if cat in ("fill", "text") or lum >= 0.99 else "border"), "near white"
    if lum >= 0.7 and sat < 0.25:
        return "border", "light grey"
    if lum < 0.05 and sat < 0.35:
        return "text", "near black"
    if sat < 0.3:
        return ("textMuted" if cat == "text" else "border" if lum > 0.4 else "textMuted"), "muted grey"
    return "brand", "saturated"


def role_of_theme(t, cat):
    """A ThemeDataColor's role: slot 0 is the theme background, 1 the foreground, 2+ the data colours."""
    cid, pct = t.get("ColorId", 0), float(t.get("Percent", 0) or 0)
    if cat == "shadow":
        return "shadow", f"theme slot {cid}"
    if cid == 0:
        if pct <= -0.3:
            return ("text" if cat == "text" else "shadow"), "theme background, much darker"
        if pct < 0:
            return "border", "theme background, darker"
        return "card", "theme background"
    if cid == 1:
        return "text", "theme foreground"
    return ("brandTint" if pct > 0.3 else "brand"), f"theme data colour {cid - 1}"


def palette_hex(palette, role, cat):
    """The clean-palette colour that recolours to `role` where it sits (palette.json), else for any position."""
    alias = {"brand": "teal", "brandTint": "tealTint", "brandText": "tealDark"}
    for name in (role, alias.get(role)):
        if not name:
            continue
        for hx, where in palette.items():
            if where.get(cat) == name:
                return hx
        for hx, where in palette.items():
            if name in where.values():
                return hx
    return None


def _bound(node):
    if isinstance(node, dict):
        if any(k in node for k in BOUND):
            return True
        return any(_bound(v) for v in node.values())
    if isinstance(node, list):
        return any(_bound(v) for v in node)
    return False


def _selector_named(sel):
    if not isinstance(sel, dict):
        return False
    if "data" in sel or "metadata" in sel or "scopeId" in json.dumps(sel):
        return True
    return str(sel.get("id", "")).startswith("field-")


class Cleaner:
    def __init__(self, palette):
        self.palette = palette
        self.removed, self.mapped, self.texts = [], [], set()

    def note_text(self, node):
        """Remember every text literal under node, for the leak check."""
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "Value" and isinstance(v, str) and v.startswith("'") and not HEX.match(v):
                    inner = v[1:-1].replace("''", "'").strip()
                    if len(inner) >= 3 and not ENUM.match(v):
                        self.texts.add(inner)
                else:
                    self.note_text(v)
        elif isinstance(node, list):
            for v in node:
                self.note_text(v)

    def colour(self, node, path, obj, prop):
        """Map colours in node in place; return False when the node holds something that must go."""
        if isinstance(node, dict):
            if "ThemeDataColor" in node:
                cat = category(obj, prop)
                role, why = role_of_theme(node["ThemeDataColor"], cat)
                hx = palette_hex(self.palette, role, cat)
                if not hx:
                    self.removed.append((path, f"colour role {role} not in palette.json"))
                    return False
                node.clear()
                node["Literal"] = {"Value": f"'{hx}'"}
                self.mapped.append((path, why, role))
                return True
            for k, v in list(node.items()):
                if k == "Value" and isinstance(v, str):
                    m = HEX.match(v)
                    if m:
                        cat = category(obj, prop)
                        role, why = role_of_hex(m.group(1).upper(), cat)
                        hx = palette_hex(self.palette, role, cat)
                        if not hx:
                            self.removed.append((path, f"colour role {role} not in palette.json"))
                            return False
                        node[k] = f"'{hx}'"
                        self.mapped.append((path, f"literal, {why}", role))
                    elif v.startswith("'") and not (ENUM.match(v) or FONT_PROPS.search(prop)):
                        self.removed.append((path, "text"))
                        return False
                elif not self.colour(v, path, obj, prop):
                    return False
        elif isinstance(node, list):
            return all(self.colour(v, path, obj, prop) for v in node)
        return True

    def clean_objects(self, objs, where):
        out = {}
        for obj, entries in (objs or {}).items():
            keep = []
            for i, e in enumerate(entries if isinstance(entries, list) else []):
                sel = e.get("selector")
                base = f"{where}.{obj}"
                if _selector_named(sel):
                    self.note_text(e)
                    self.removed.append((f"{base} (entry for one field or member)", "per-field / per-member"))
                    continue
                props = {}
                for prop, v in (e.get("properties") or {}).items():
                    path = f"{base}.{prop}" + (f" @{sel.get('id')}" if isinstance(sel, dict) and sel.get("id") else "")
                    pl = prop.lower()
                    if pl in TEXT_PROPS:
                        self.note_text(v)
                        self.removed.append((path, "text, image or target"))
                        continue
                    if obj == "general" and pl == "filter":
                        self.note_text(v)
                        self.removed.append((path, "saved selection"))
                        continue
                    if (obj, prop) in PROJECT_NUMBERS:
                        self.removed.append((path, "the source data's range"))
                        continue
                    if _bound(v):
                        self.note_text(v)
                        self.removed.append((path, "bound to a field, measure or image"))
                        continue
                    v2 = copy.deepcopy(v)
                    if not self.colour(v2, path, obj, prop):
                        self.note_text(v)
                        continue
                    props[prop] = v2
                if props:
                    e2 = {k: copy.deepcopy(x) for k, x in e.items() if k != "properties"}
                    e2["properties"] = props
                    keep.append(e2)
            if keep:
                out[obj] = keep
        return out

    def clean(self, d):
        self.removed, self.mapped = [], []
        self.note_text(d)
        for k in d:
            if k not in KEEP_TOP and k != "visual":
                self.removed.append((k, "name, position, group, filters or flags"))
        vis = d.get("visual", {})
        t = {k: d[k] for k in KEEP_TOP if k in d}
        v2 = {k: copy.deepcopy(vis[k]) for k in KEEP_VISUAL if k in vis and k not in ("objects", "visualContainerObjects")}
        q = vis.get("query")
        if q:
            if any((r.get("projections") for r in (q.get("queryState") or {}).values())):
                self.removed.append(("visual.query", "bindings"))
            v2["query"] = {"queryState": {}}
        for k in vis:
            if k not in KEEP_VISUAL and k != "query":
                self.removed.append((f"visual.{k}", "not formatting"))
        for where in ("objects", "visualContainerObjects"):
            got = self.clean_objects(vis.get(where), where)
            if got:
                v2[where] = got
        t["visual"] = v2
        t["_pbik"] = {"note": "Clean template (pbik templates harvest --clean): bindings, text, selections, images, "
                              "names and per-member formatting removed; colours mapped to tokens via palette.json."}
        return t

    def leaks(self, t):
        s = json.dumps(t, ensure_ascii=False)
        return sorted(x for x in self.texts if x in s)


def harvest_clean(report_path, out_dir="design/templates", page=None, pick=None, log=None, label="study"):
    rep = Report(report_path)
    if page:
        hit = rep.page_by(page)
        if not hit:
            fail(f"no page {page!r} in the report (pages: {[p[1].get('displayName') for p in rep.pages()]})")
        visuals = rep.visuals(hit[2])
    else:
        visuals = rep.visuals()
    picks = load(pathlib.Path(pick)).get("templates", {}) if pick else None
    out = pathlib.Path(out_dir)
    palette = load_palette(out)
    if not palette:
        fail(f"no palette.json in {out}: the colour mapping needs it")
    cl = Cleaner(palette)
    lines = [f"# Clean harvest: {label}", "",
             "Made by `pbik templates harvest --clean`. What was removed and how colours were mapped, per template "
             "(property paths and reasons only; no values from the source).", ""]
    written, index_add, errors = [], {}, []
    found = set()
    for d, f in visuals:
        vt = (d.get("visual") or {}).get("visualType")
        folder = f.parent.name
        if not vt or (picks is not None and folder not in picks):
            continue
        found.add(folder)
        if picks is not None:
            name = picks[folder]
        else:
            m = ID_RE.match(folder)
            name = m.group(2) if m else folder
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", name)
        stem = f"{vt}.{name}"
        t = cl.clean(d)
        leaks = cl.leaks(t)
        if leaks:
            errors.append(f"{stem}: {len(leaks)} removed text(s) still in the template; not written")
            continue
        changed = save(out / f"{stem}.json", t)
        written.append((out / f"{stem}.json", changed))
        index_add[stem] = {"visualType": vt, "source": label, "clean": True}
        lines += [f"## {stem}", "", f"Removed ({len(cl.removed)}):", ""]
        groups = {}
        for path, why in cl.removed:
            groups.setdefault(why, []).append(path)
        for why, paths in sorted(groups.items()):
            uniq = sorted(set(paths))
            lines.append(f"- {why} ({len(paths)}): " + ", ".join(f"`{p}`" for p in uniq[:12])
                         + (f" and {len(uniq) - 12} more" if len(uniq) > 12 else ""))
        lines += ["", f"Colours mapped ({len(cl.mapped)}):", ""]
        cg = {}
        for path, why, role in cl.mapped:
            cg.setdefault((why, role), []).append(path)
        for (why, role), paths in sorted(cg.items()):
            lines.append(f"- {why} -> `{role}` ({len(paths)}): " + ", ".join(f"`{p}`" for p in sorted(set(paths))[:8]))
        lines.append("")
    if picks is not None:
        for missing in sorted(set(picks) - found):
            errors.append(f"pick {missing!r} ({picks[missing]}): no visual with that folder name")
    if index_add:
        idx_f = out / "index.json"
        idx = load(idx_f) if idx_f.exists() else {"templates": {}}
        tpls = idx.setdefault("templates", {})
        for stem, entry in index_add.items():
            old = tpls.get(stem) or {}
            if old.get("status") == "needs a Desktop-saved sample":       # a pattern stub's placeholder: keep its link
                entry["status"] = f"clean harvest ({label}): confirm in Desktop"
            tpls[stem] = {**old, **entry}
        idx["templates"] = dict(sorted(idx["templates"].items()))
        save(idx_f, idx)
    if errors:
        lines += ["## Errors", ""] + [f"- {e}" for e in errors] + [""]
    if log:
        lf = pathlib.Path(log)
        lf.parent.mkdir(parents=True, exist_ok=True)
        lf.write_text("\n".join(lines), encoding="utf-8")
    for target, changed in written:
        print(f"{'wrote' if changed else 'same '} {target}")
    for e in errors:
        print(f"error: {e}")
    if errors:
        raise SystemExit(1)
    return written
