"""pbik build: create or update pages and visuals from design/specs/layout.json, by visual ID, idempotently.

What layout.json drives (tools/pbik/README.md has the full key list):
- pages: display name, size, display option, background, page filters, visual interactions (NoFilter ...);
- visuals: folder '<ID>_<name>' from a template (design/templates/<type>.json), position and z-order, field bindings
  by role, sort, reference lines, visual filters (categorical, Top N), slicer default selection, button actions
  (page navigation by page id, clear all slicers, back, bookmark, web URL), container background / border / shadow /
  padding / title / subtitle, text box paragraphs, shape style, conditional formatting (measure colour, rules, data
  bars, gradient, image from measure) and raw properties.

Idempotent: every value is set in place, files are written only when their content changes, and properties pbik
wrote on an earlier run but no longer in layout.json are removed (tracked in the ID map). Visuals that left
layout.json are removed only with --prune.
"""
import copy, json, pathlib, re, shutil

from . import bookmarks as BM
from . import deneb as DN
from . import fields as F
from . import fieldrefs as FR
from . import htmlcontent as HC
from . import deprecations as DEP
from . import schemaprops as SP
from . import unverified as UV
from . import versions
from .objects import (b, chrome_off, colour_expr, drop_shadow, ex, i, load, n, native_ref, navigator_states, qref,
                      ref_labels, s, save, shape_objects, solid, solid_ex, theme_colour)
from .report import ID_RE, Report, fail, stable_name

TEXT_FIT = {"textbox": (-6, 12)}       # text boxes get 6px headroom and 12px extra height (audit_layout.py matches)
AXES = {"x": "xAxisReferenceLine", "category": "xAxisReferenceLine", "y": "y1AxisReferenceLine",
        "y1": "y1AxisReferenceLine", "value": "y1AxisReferenceLine", "y2": "y2AxisReferenceLine",
        "value2": "y2AxisReferenceLine"}
# Horizontal bar charts: the value axis is drawn along the bottom but is still y1 in PBIR (Rep 3 drivers-bars, saved by
# Desktop); xAxisReferenceLine is the category axis and draws nothing useful there.
HORIZONTAL = {"barChart", "clusteredBarChart", "hundredPercentStackedBarChart"}
TABLES = {"tableEx", "pivotTable"}
NO_QUERY = {"shape", "textbox", "actionButton", "image", "basicShape", "pageNavigator", "bookmarkNavigator"}
# Objects whose formatting Desktop keeps on selector {id: default} (counted in the Rep 4-7 files Desktop saved):
# per visual type, the objects, and whether `show` sits on that selector too (cards, button slicers) or stays
# selector-less (buttons, shapes).
STATEFUL = {
    "actionButton": ({"text", "fill", "outline", "icon", "shape", "glow"}, False),
    "shape": ({"fill", "outline"}, False),
    "cardVisual": ({"value", "label", "fillCustom", "outline", "shapeCustomRectangle", "accentBar", "image",
                    "cardCalloutArea", "divider", "shadowCustom", "glowCustom", "padding", "referenceLabelLayout"}, True),
    "advancedSlicerVisual": ({"value", "label", "fillCustom", "outline", "shapeCustomRectangle", "padding", "image"},
                             True),
}
SIZE_PROPS = re.compile(r"(size|fontsize)$", re.I)
LENGTH_PROPS = re.compile(r"(radius|curve|margin|padding|width|weight|top|bottom|left|right)$", re.I)
SLICER_MODES = {"list": "Basic", "basic": "Basic", "dropdown": "Dropdown", "between": "Between", "before": "Before",
                "after": "After"}
OPS = {"=": 0, "==": 0, ">": 1, ">=": 2, "<": 3, "<=": 4}
COLOUR_PROPS = re.compile(r"(color|colour|fill|fillcolor)$", re.I)
THEME_RE = re.compile(r"theme:(\d+)(?::(-?\d+(?:\.\d+)?))?")


class BuildError(Exception):
    pass


class Ctx:
    def __init__(self, report, layout, tokens):
        self.report, self.layout, self.tokens = report, layout, tokens or {}
        self.res = F.Resolver(report, layout.get("measureTable"))
        self.owned_new = {}        # vid -> [[where, key, selector, prop]]
        self.strict = False        # --strict: a property outside Microsoft's schema is an error, not a warning
        self.unverified = set()    # roadmap batch 2 features this build writes (pbikit/unverified.py)

    # tokens
    def colour(self, v):
        """'#hex', a tokens.json colour name, or a theme colour ({"theme": 0, "percent": -0.6} or "theme:0:-0.6",
        Desktop's ColorId: 0 background, 1 foreground, 2.. dataColors[0..]; and a shade) -> hex text or theme_colour()."""
        if v is None:
            return None
        if isinstance(v, dict) and "theme" in v:
            return theme_colour(v["theme"], v.get("percent", 0))
        if isinstance(v, str) and v.startswith("#"):
            return v
        if isinstance(v, str) and v.startswith("theme:"):
            m = THEME_RE.fullmatch(v)
            if not m:
                raise BuildError(f"colour {v!r}: write a theme colour as theme:<index> or theme:<index>:<percent>")
            return theme_colour(m.group(1), m.group(2) or 0)
        for path in (f"colors.{v}", str(v)):
            cur = self.tokens
            for part in path.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
            if isinstance(cur, str) and (cur.startswith("#") or cur.startswith("theme:")):
                return self.colour(cur)
        raise BuildError(f"colour {v!r} is not a hex value, a theme colour or a tokens.json colour")

    def number(self, v, group="fontPt"):
        if isinstance(v, (int, float)):
            return v
        cur = self.tokens.get(group, {}).get(v) if isinstance(v, str) else None
        if cur is None:
            cur = self.tokens
            for part in str(v).split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
        if not isinstance(cur, (int, float)):
            raise BuildError(f"{v!r} is not a number or a tokens.json {group} value")
        return cur

    def font(self, v=None):
        fam = self.tokens.get("font", {}).get("family", "Segoe UI")
        if v in (None, "regular"):
            return fam
        if v in ("semibold", "bold", "light"):
            return f"{fam} {v.capitalize()}"
        return v

    def field(self, text):
        try:
            return self.res.field(text)
        except F.FieldError as e:
            raise BuildError(str(e))


# ---------------------------------------------------------------- object lists with ownership
def _sel_key(sel):
    return json.dumps(sel, sort_keys=True) if sel is not None else None


def set_prop(ctx, vid, d, where, key, selector, prop, value):
    """Set one property on the entry of <where>[key] with exactly this selector (created if missing), in place."""
    objs = d.setdefault("visual", {}).setdefault(where, {}) if where != "page" else d.setdefault("objects", {})
    lst = objs.setdefault(key, [])
    entry = next((e for e in lst if e.get("selector") == selector), None)
    if entry is None:
        entry = {"properties": {}}
        if selector is not None:
            entry["selector"] = selector
        lst.append(entry)
    entry.setdefault("properties", {})[prop] = value
    ctx.owned_new.setdefault(vid, []).append([where, key, _sel_key(selector), prop])


def ensure_entry(ctx, vid, d, where, key, selector):
    """An object entry with this selector and no properties (Desktop keeps some, e.g. columnFormatting: [{}])."""
    lst = d.setdefault("visual", {}).setdefault(where, {}).setdefault(key, [])
    if not any(e.get("selector") == selector for e in lst):
        e = {"properties": {}}
        if selector is not None:
            e["selector"] = selector
        lst.append(e)
    ctx.owned_new.setdefault(vid, []).append([where, key, _sel_key(selector), None])


def release(d, where, key, sel_key, prop):
    if where == "top":                          # a top-level key pbik owns (parentGroupName)
        d.pop(key, None)
        return
    if where == "annotations":                  # an annotation pbik wrote (roadmap gap 13)
        lst = d.get("annotations") or []
        lst[:] = [a for a in lst if a.get("name") != key]
        if "annotations" in d and not lst:
            del d["annotations"]
        return
    if where == "visual":                       # a visual-level key pbik owns (syncGroup)
        d.get("visual", {}).pop(key, None)
        return
    objs = d.get("visual", {}).get(where, {}) if where != "page" else d.get("objects", {})
    if prop is None:                            # an empty entry pbik added
        lst = objs.get(key, [])
        lst[:] = [e for e in lst if not (_sel_key(e.get("selector")) == sel_key and not e.get("properties"))]
        if key in objs and not objs[key]:
            del objs[key]
        return
    lst = objs.get(key, [])
    for e in list(lst):
        if _sel_key(e.get("selector")) == sel_key and prop in e.get("properties", {}):
            del e["properties"][prop]
            if not e["properties"]:
                lst.remove(e)
    if key in objs and not objs[key]:
        del objs[key]


def set_entries(ctx, vid, d, where, key, entries):
    """Write a whole list of entries (selector + properties) through set_prop."""
    for e in entries:
        for prop, val in e["properties"].items():
            set_prop(ctx, vid, d, where, key, e.get("selector"), prop, val)


# ---------------------------------------------------------------- value helpers
def prop_value(ctx, prop, v):
    """Raw layout value -> PBIR property value."""
    if isinstance(v, dict):
        if "fx" in v:
            return solid_ex(fmt_field(ctx, v["fx"], prop))
        if "expr" in v:
            return ex(ctx.field(v["expr"]))
        if "int" in v:
            return i(v["int"])
        if "color" in v:
            return solid(ctx.colour(v["color"]))
        if "theme" in v:
            return solid(ctx.colour(v))
        if "raw" in v:
            return v["raw"]
        raise BuildError(f"{prop}: unknown value {v}")
    if isinstance(v, bool):
        return b(v)
    if isinstance(v, (int, float)):
        return n(v)
    if isinstance(v, str) and (v.startswith("#") or v.startswith("theme:") or COLOUR_PROPS.search(prop)):
        try:
            return solid(ctx.colour(v))
        except BuildError:
            if v.startswith(("#", "theme:")):
                raise
    if isinstance(v, str) and SIZE_PROPS.search(prop):        # a token name ("kpi") is a size, never text
        return n(ctx.number(v, "fontPt"))
    if isinstance(v, str) and LENGTH_PROPS.search(prop):
        try:
            return n(ctx.number(v, "container"))
        except BuildError:
            pass
    return s(v)


def fmt_field(ctx, text, what):
    """A formatting value bound to data: a measure, or an aggregated column (Min(T[C]) / First(T[C]), which Desktop
    saves as Aggregation Function 3, Rep 6 and 7). A bare column can't drive formatting."""
    fld = ctx.field(text)
    if "Column" in fld:
        raise BuildError(f"{what}: {text!r} is a column; formatting needs a measure or an aggregation such as "
                         f"First({text}) or Min({text})")
    return fld


def selector_of(ctx, text):
    """Selector shorthand: default / hover / selected / disabled, * (data points), [Field] or Table[Column]
    (metadata), a JSON object for any other selector exactly as Desktop saves it ('@{"metadata": ..., "id": ...}'),
    or any other text as an id."""
    if text is None:
        return None
    if text.lstrip().startswith("{"):
        try:
            sel = json.loads(text)
        except json.JSONDecodeError as e:
            raise BuildError(f"selector {text[:60]!r} is not valid JSON: {e}")
        if not isinstance(sel, dict):
            raise BuildError(f"selector {text[:60]!r} must be a JSON object")
        return sel
    if text in ("default", "hover", "selected", "disabled"):
        return {"id": text}
    if text in ("*", "points"):
        return {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}
    if text.startswith("["):
        return {"metadata": qref(ctx.field(text))}
    if "[" in text:
        return {"metadata": qref(ctx.field(text))}
    return {"id": text}


# ---------------------------------------------------------------- per-visual parts
def apply_empty_query(v, d, tpl, existing=False):
    """Visuals without fields: Desktop saves `query: {queryState: {}}` on shapes, text boxes, buttons and navigators,
    but not always (Rep 5's auto title had none). layout `emptyQuery` true/false decides; otherwise a new visual
    follows its template (harvest keeps an empty query), and without a template the visual type."""
    if "bindings" in v:
        return
    if "emptyQuery" in v:
        want = bool(v["emptyQuery"])
    elif tpl is not None:
        want = "query" in tpl.get("visual", {})
    elif existing:
        return                                   # existing visual: leave what is there
    else:
        want = v["type"] in NO_QUERY
    if want:
        d["visual"].setdefault("query", {"queryState": {}})
    elif d["visual"].get("query") == {"queryState": {}}:
        del d["visual"]["query"]


# one field-parameter row: ("Label", NAMEOF('Table'[Field]), order)
FP_ITEM = re.compile(r"""\(\s*"((?:[^"]|"")*)"\s*,\s*NAMEOF\s*\(\s*('(?:[^']|'')+'|[^\[\s(]+)\s*\[([^\]]+)\]\s*\)"""
                     r"""\s*,\s*(-?\d+)""")


def field_parameter(ctx, spec):
    """A field parameter binding -> (projections, fieldParameters entry without index).
    The fields come from the parameter's calculated table in the TMDL ({("Label", NAMEOF('T'[C]), order), ...}),
    in parameter order. project "all" (default): every field, the first active, as the Rep 3 helper did (Desktop
    confirmed); "selected": only the selected field (spec `selected`: its label, default the first), with its label as
    displayName, the form Desktop saved in Rep 5."""
    par = ctx.field(spec["fieldParameter"])
    if "Column" not in par:
        raise BuildError(f"fieldParameter {spec['fieldParameter']!r} must be the parameter's column")
    table = par["Column"]["Expression"]["SourceRef"]["Entity"]
    model = ctx.res.model
    t = model.tables.get(table) if model else None
    src = next((p[1] for p in (t.partitions if t else []) if p[0] == "calculated" and p[1]), None)
    if not src:
        raise BuildError(f"{table}: no calculated-table definition in the TMDL, so its fields are unknown")
    items = re.findall(FP_ITEM, src)
    if not items:
        raise BuildError(f"{table}: no NAMEOF fields found in its definition")
    fields = []
    for label, tbl, name, order in sorted(items, key=lambda x: int(x[3])):
        tbl = tbl.strip("'").replace("''", "'")
        notation = f"'{tbl}'[{name}]"
        fields.append((label.replace('""', '"'), ctx.field(notation)))
    mode = spec.get("project", "all")
    if mode == "selected":
        want = spec.get("selected") or fields[0][0]
        hit = [f for f in fields if f[0] == want]
        if not hit:
            raise BuildError(f"{table}: no field labelled {want!r} ({[f[0] for f in fields]})")
        fields = hit
    elif mode != "all":
        raise BuildError(f"fieldParameter project {mode!r} (all, selected)")
    projs = []
    for k, (label, f) in enumerate(fields):
        p = {"field": f, "queryRef": qref(f), "nativeQueryRef": native_ref(f)}
        if k == 0:
            p["active"] = True
        if mode == "selected":
            p["displayName"] = spec.get("displayName", label)
        projs.append(p)
    return projs, {"parameterExpr": par, "length": len(projs)}


def apply_query(ctx, v, d):
    if "bindings" not in v and "sort" not in v:
        return
    vis = d.setdefault("visual", {})
    if "bindings" in v:
        qs = {}
        for role, items in v["bindings"].items():
            projs = []
            fparams = []
            for it in (items if isinstance(items, list) else [items]):
                spec = it if isinstance(it, dict) else {"field": it}
                if "fieldParameter" in spec:
                    fp_projs, fp = field_parameter(ctx, spec)
                    fparams.append({**fp, "index": len(projs)})
                    projs.extend(fp_projs)
                    continue
                f = ctx.field(spec["field"])
                q = qref(f)
                p = {"field": f, "queryRef": q, "nativeQueryRef": native_ref(f)}   # the field's name, not displayName
                if spec.get("displayName"):
                    p["displayName"] = spec["displayName"]
                if spec.get("active") or (not projs and (role == "Category" or (role == "Values" and v["type"] == "slicer"))):
                    p["active"] = True          # Desktop marks the first category (and classic slicer) field active
                projs.append(p)
            qs[role] = {"projections": projs}
            if fparams:
                qs[role]["fieldParameters"] = [{"parameterExpr": f["parameterExpr"], "index": f["index"],
                                                "length": f["length"]} for f in fparams]
        vis.setdefault("query", {})["queryState"] = qs
    if "sort" in v:
        srt = v["sort"] if isinstance(v["sort"], list) else [v["sort"]]
        sd = {"sort": [{"field": ctx.field(x["field"]), "direction": x.get("direction", "Descending")} for x in srt]}
        # Desktop drops isDefaultSort: false on save (Desktop test round 1) and keeps true: "default": true writes it
        if any(x.get("default") for x in srt):
            sd["isDefaultSort"] = True
        vis.setdefault("query", {})["sortDefinition"] = sd


def build_filter(ctx, owner, k, spec):
    name = "pbik_" + stable_name(owner, k, spec.get("field"), length=16)
    fld = ctx.field(spec["field"])
    if "Measure" in fld:
        if owner.startswith("page:"):
            raise BuildError(f"{owner}: {spec['field']} is a measure: Power BI filters on a measure only at visual "
                             "level; move the filter to each visual's `filters`")
        if spec.get("op") not in OPS or "value" not in spec:
            raise BuildError(f"{owner}: measure filter {spec['field']} needs `op` ({', '.join(OPS)}) and `value`")
        f = F.measure_filter(name, fld, OPS[spec["op"]], spec["value"])
    elif "Column" not in fld:
        raise BuildError(f"{owner}: filter field {spec['field']!r} must be a column or a measure")
    elif spec.get("type", "Categorical").lower() == "topn":
        f = F.topn_filter(name, fld, ctx.field(spec["by"]), spec.get("n", 5),
                          bottom=spec.get("direction", "Top").lower() == "bottom")
    elif spec.get("type", "Categorical").lower() == "categorical":
        f = F.categorical_filter(name, fld, ctx.res.column_type(fld), spec.get("values", []), spec.get("invert", False))
    else:
        raise BuildError(f"{owner}: filter type {spec['type']!r} not supported (Categorical, TopN; a measure: op, value)")
    if spec.get("hidden"):
        f["isHiddenInViewMode"] = True
    if spec.get("locked"):
        f["isLockedInViewMode"] = True
    return f


def apply_filters(ctx, owner, d, specs):
    """Replace pbik's own filters (name pbik_*) in place; keep filters made in Desktop."""
    fc = d.setdefault("filterConfig", {}).setdefault("filters", [])
    new = [build_filter(ctx, owner, k, sp) for k, sp in enumerate(specs or [])]
    names = {f["name"] for f in new}
    for f in new:
        pos = next((k for k, x in enumerate(fc) if x.get("name") == f["name"]), None)
        if pos is None:
            fc.append(f)
        else:
            fc[pos] = f
    fc[:] = [x for x in fc if not (x.get("name", "").startswith("pbik_") and x["name"] not in names)]
    if not fc:
        del d["filterConfig"]["filters"]
        if not d["filterConfig"]:
            del d["filterConfig"]


def apply_reference_lines(ctx, vid, v, d):
    for k, rl in enumerate(v.get("referenceLines", [])):
        axis = str(rl.get("axis", "value"))
        key = AXES.get(axis)
        if not key:
            raise BuildError(f"{vid}: reference line axis {axis!r} (value, value2, category; or x, y1, y2)")
        if axis == "x" and v["type"] in HORIZONTAL:
            raise BuildError(f"{vid}: on a {v['type']} the value axis is y1 even though it runs along the bottom; "
                             "use axis \"value\" (x is the category axis)")
        val = rl["value"]
        props = {"show": b(True),
                 "value": ex(ctx.field(val)) if isinstance(val, str) else n(val),
                 "lineColor": solid(ctx.colour(rl.get("color", "text"))),
                 "transparency": n(rl.get("transparency", 0)),
                 "style": s(rl.get("style", "dashed")),
                 "width": n(rl.get("width", 1)),
                 "position": s(rl.get("position", "front"))}
        if rl.get("label"):
            props["displayName"] = s(rl["label"])
        if rl.get("dataLabel", bool(rl.get("label"))):
            props.update({"dataLabelShow": b(True),
                          "dataLabelColor": solid(ctx.colour(rl.get("labelColor", rl.get("color", "text")))),
                          "dataLabelText": s(rl.get("labelText", "ValueAndName")),
                          "dataLabelHorizontalPosition": s(rl.get("labelHorizontal", "left")),
                          "dataLabelVerticalPosition": s(rl.get("labelVertical", "above"))})
        for prop, val in props.items():
            set_prop(ctx, vid, d, "objects", key, {"id": str(k + 1)}, prop, val)


def shadow_props(ctx, spec):
    pbi = ctx.tokens.get("container", {}).get("pbiShadow", {})
    colour = "#000000"
    m = re.search(r"rgba?\(([^)]+)\)", ctx.tokens.get("container", {}).get("shadow", ""))
    if m:
        r_, g_, b_ = (int(float(x)) for x in m.group(1).split(",")[:3])
        colour = f"#{r_:02X}{g_:02X}{b_:02X}"
    spec = spec if isinstance(spec, dict) else {}
    return drop_shadow(ctx.colour(spec["color"]) if "color" in spec else colour, spec.get("blur", pbi.get("blur", 10)),
                       spec.get("distance", pbi.get("distance", 3)), spec.get("angle", 90),
                       spec.get("transparency", pbi.get("transparency", 90)))[0]["properties"]


def apply_container(ctx, vid, v, d):
    c = v.get("container")
    if c is None:
        return
    if c == "off":
        tmp = {"visual": {}}
        chrome_off(tmp)
        for key, entries in tmp["visual"]["visualContainerObjects"].items():
            set_entries(ctx, vid, d, "visualContainerObjects", key, entries)
        return

    def put(key, props):
        for prop, val in props.items():
            set_prop(ctx, vid, d, "visualContainerObjects", key, None, prop, val)

    if "background" in c:
        bg = c["background"]
        put("background", {"show": b(False)} if bg is False else
            {"show": b(True), "color": solid(ctx.colour(bg.get("color", "card"))), "transparency": n(bg.get("transparency", 0))})
    if "border" in c:
        bd = c["border"]
        props = {"show": b(False)} if bd is False else {"show": b(True), "color": solid(ctx.colour(bd.get("color", "border"))),
                                                        "width": n(bd.get("width", 1))}
        if bd and "radius" in bd:
            props["radius"] = n(ctx.number(bd["radius"], "container"))
        put("border", props)
    if "shadow" in c:
        put("dropShadow", {"show": b(False)} if c["shadow"] is False else shadow_props(ctx, c["shadow"]))
    if "padding" in c:
        p = c["padding"]
        p = [p] * 4 if isinstance(p, (int, float, str)) else p
        t, r, bt, l_ = (ctx.number(x, "container") for x in p)
        put("padding", {"top": n(t), "right": n(r), "bottom": n(bt), "left": n(l_)})
    for key, src in (("title", "title"), ("subTitle", "subtitle")):
        if src in c:
            tv = c[src]
            if tv is False:
                put(key, {"show": b(False)})
                continue
            tv = {"text": tv} if isinstance(tv, str) else tv
            props = {"show": b(True)}
            if "text" in tv:
                props["text"] = s(tv["text"])
            if "measure" in tv:
                props["text"] = ex(ctx.field(tv["measure"]))
            props["fontFamily"] = s(ctx.font(tv.get("font", "semibold" if key == "title" else None)))
            props["fontSize"] = n(ctx.number(tv.get("size", "cardTitle" if key == "title" else "caption")))
            props["fontColor"] = solid(ctx.colour(tv.get("color", "text" if key == "title" else "textMuted")))
            props["alignment"] = s(tv.get("align", "left"))
            put(key, props)
    if "header" in c:
        put("visualHeader", {"show": b(bool(c["header"]))})
    # general: layer order and alt text, selector-less as Desktop saved them in Rep 7
    if "keepLayerOrder" in c:
        put("general", {"keepLayerOrder": b(bool(c["keepLayerOrder"]))})
    if "altText" in c:
        put("general", {"altText": s(c["altText"])})
    if "spacing" in c:
        sp = c["spacing"]
        if sp is False:
            put("spacing", {"customizeSpacing": b(False)})
        else:
            props = {"customizeSpacing": b(True)}
            for key, prop in (("vertical", "verticalSpacing"), ("belowTitle", "spaceBelowTitle"),
                              ("belowSubtitle", "spaceBelowSubTitle"), ("belowTitleArea", "spaceBelowTitleArea")):
                if key in sp:
                    props[prop] = n(ctx.number(sp[key], "container"))
            unknown = set(sp) - {"vertical", "belowTitle", "belowSubtitle", "belowTitleArea"}
            if unknown:
                raise BuildError(f"{vid}: container.spacing keys {sorted(unknown)} (vertical, belowTitle, "
                                 f"belowSubtitle, belowTitleArea)")
            put("spacing", props)


def apply_text(ctx, vid, v, d):
    if "text" not in v:
        return
    paras = v["text"] if isinstance(v["text"], list) else [v["text"]]
    out = []
    for p in paras:
        p = {"runs": [p]} if isinstance(p, str) else ({"runs": p} if isinstance(p, list) else p)
        runs = []
        for r in p["runs"]:
            r = {"text": r} if isinstance(r, str) else r
            colour = ctx.colour(r.get("color", "text"))
            if not isinstance(colour, str):
                raise BuildError(f"{vid}: text box runs take a hex or token colour, not a theme colour")
            runs.append({"value": r["text"], "textStyle": {
                "fontFamily": ctx.font(r.get("font")), "fontSize": f"{ctx.number(r.get('size', 'body'))}pt",
                "color": colour}})
        para = {"textRuns": runs}
        if p.get("align"):
            para["horizontalTextAlignment"] = p["align"]
        out.append(para)
    set_prop(ctx, vid, d, "objects", "general", None, "paragraphs", out)


def apply_action(ctx, vid, v, d, page_ids):
    a = v.get("action")
    if not a:
        return
    t = a["type"]
    props = {"show": b(True), "type": s(t)}
    if t == "PageNavigation":
        target = a.get("page")
        pid = page_ids.get(target)
        if not pid:          # a display name, or a page that isn't in layout.json
            key = next((k for k, sp in ctx.layout.get("pages", {}).items() if sp.get("displayName") == target), None)
            hit = ctx.report.page_by(target)
            pid = page_ids.get(key) if key else (hit[0] if hit else None)
        if not pid:
            raise BuildError(f"{vid}: navigation target {target!r} is not a page in layout.json or the report")
        props["navigationSection"] = s(pid)
    elif t == "Bookmark":
        bdir = ctx.report.defn / "bookmarks"
        existing = {f.name[:-len(".bookmark.json")] for f in bdir.glob("*.bookmark.json")} if bdir.is_dir() else set()
        bid = BM.resolve(ctx.layout, v["page"], a["bookmark"], existing)
        if not bid:
            raise BuildError(f"{vid}: bookmark {a['bookmark']!r} is not a bookmark on page {v['page']} in layout.json "
                             "('<page key>/<name>' for another page) nor a bookmark in the report")
        props["bookmark"] = s(bid)
    elif t == "WebUrl":
        props["webUrl"] = s(a["url"])
    elif t not in ("ClearAllSlicers", "Back", "ApplyAllSlicers"):
        raise BuildError(f"{vid}: action {t!r} not supported (PageNavigation, ClearAllSlicers, Back, Bookmark, WebUrl)")
    for prop, val in props.items():
        set_prop(ctx, vid, d, "visualContainerObjects", "visualLink", None, prop, val)


def apply_style(ctx, vid, v, d):
    st = v.get("style")
    if not st or v["type"] != "shape":
        return
    tr = st.get("transparency", 0)
    tr = ctx.number(tr, "glass") if isinstance(tr, str) else tr
    rad = st.get("radius", 0)
    rad = ctx.number(rad, "container") if isinstance(rad, str) else rad
    objs = shape_objects(ctx.colour(st.get("fill", "card")), ctx.colour(st["outline"]) if st.get("outline") else None,
                         st.get("outlineWidth", 1), tr, rad)
    for key, entries in objs.items():
        set_entries(ctx, vid, d, "objects", key, entries)


def apply_cf(ctx, vid, v, d):
    for k, c in enumerate(v.get("cf", [])):
        t = c["type"]
        where = "visualContainerObjects" if c.get("where") == "container" else "objects"
        if t in ("measure", "field"):                 # a measure or an aggregated column
            fld = fmt_field(ctx, c.get("field", c.get("measure")), f"{vid} cf")
            target = c.get("target")
            if c.get("selector"):
                sel = selector_of(ctx, c["selector"])
            elif target and v["type"] in TABLES:
                sel = {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": qref(ctx.field(target))}
            elif target:                       # charts: Desktop saves fx per data point without the column
                sel = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}
            elif c.get("perPoint"):
                sel = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}
            else:
                sel = selector_of(ctx, c.get("selector"))
            val = ex(fld) if c.get("kind") == "value" else solid_ex(fld)
            set_prop(ctx, vid, d, where, c["object"], sel, c["property"], val)
        elif t == "rules":
            inp = ctx.field(c["field"])
            cases = []
            for r in c["rules"]:
                if "min" in r or "max" in r:
                    conds = []
                    if "min" in r:
                        conds.append({"Comparison": {"ComparisonKind": 2, "Left": inp, "Right": {"Literal": {"Value": f"{r['min']}D"}}}})
                    if "max" in r:
                        conds.append({"Comparison": {"ComparisonKind": 3, "Left": inp, "Right": {"Literal": {"Value": f"{r['max']}D"}}}})
                    cond = conds[0] if len(conds) == 1 else {"And": {"Left": conds[0], "Right": conds[1]}}
                else:
                    cond = {"Comparison": {"ComparisonKind": OPS[r["op"]], "Left": inp,
                                           "Right": {"Literal": {"Value": f"{r['value']}D"}}}}
                cases.append({"Condition": cond, "Value": colour_expr(ctx.colour(r["color"]))})
            cnd = {"Cases": cases}
            if c.get("else"):
                cnd["DefaultValue"] = colour_expr(ctx.colour(c["else"]))
            sel = cf_selector(ctx, v, c)
            set_prop(ctx, vid, d, where, c.get("object", "values"), sel, c.get("property", "fontColor"),
                     {"solid": {"color": {"expr": {"Conditional": cnd}}}})
        elif t == "dataBars":
            sel = {"metadata": qref(ctx.field(c["field"]))}
            bars = {"positiveColor": solid(ctx.colour(c.get("positive", "primary"))),
                    "negativeColor": solid(ctx.colour(c.get("negative", "bad"))),
                    "axisColor": solid(ctx.colour(c.get("axis", "card"))),
                    "reverseDirection": b(c.get("reverse", False)), "hideText": b(c.get("hideText", False))}
            set_prop(ctx, vid, d, "objects", "columnFormatting", sel, "dataBars", bars)
        elif t == "gradient":
            inp = ctx.field(c["field"])
            stops = {"min": {"color": colour_expr(ctx.colour(c["min"]))}}
            if c.get("mid"):
                stops["mid"] = {"color": colour_expr(ctx.colour(c["mid"]))}
            stops["max"] = {"color": colour_expr(ctx.colour(c["max"]))}
            stops["nullColoringStrategy"] = {"strategy": s(c.get("nulls", "asZero"))["expr"]}
            rule = {"linearGradient3" if c.get("mid") else "linearGradient2": stops}
            sel = cf_selector(ctx, v, c)
            set_prop(ctx, vid, d, where, c.get("object", "values"), sel, c.get("property", "backColor"),
                     {"solid": {"color": {"expr": {"FillRule": {"Input": inp, "FillRule": rule}}}}})
        elif t == "image":
            fld = fmt_field(ctx, c.get("field", c.get("measure")), f"{vid} image cf")
            sel = {"id": "default"}
            set_prop(ctx, vid, d, "objects", "image", sel, "show", b(True))
            set_prop(ctx, vid, d, "objects", "image", sel, "imageType", s("imageUrl"))
            set_prop(ctx, vid, d, "objects", "image", sel, "imageUrl", ex(fld))
        else:
            raise BuildError(f"{vid}: cf type {t!r} not supported (measure, field, rules, dataBars, gradient, image)")


def cf_selector(ctx, v, c):
    """Rules and gradients: a table or matrix colours one column (data wildcard + the column's metadata); a chart
    colours its data points (data wildcard only, as Desktop saves bar fx)."""
    if c.get("selector"):
        return selector_of(ctx, c["selector"])
    wild = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}
    if v["type"] in TABLES:
        return {**wild, "metadata": qref(ctx.field(c.get("target", c["field"])))}
    return wild


def apply_reference_labels(ctx, vid, v, d):
    """referenceLabels (new card): one or more reference labels under the card value, through
    objects.ref_labels with stable ids (the same ids on every build).
    {"field": "[Revenue]" (default: the first Data binding), "titleOff": true, "layout": "sentence" or null,
     "valueColor", "valueSize", "valueFont", "titleColor", "titleSize", "titleFont", "detailSize", "detailFont",
     "displayUnits", "labels": [{"title", "value": "[M]", "detail": "[M]", "detailColor": "[M]",
                                  "detailBackground": "[M]", "blankAs": "-"}]}"""
    spec = v.get("referenceLabels")
    if not spec:
        return
    if v["type"] != "cardVisual":
        raise BuildError(f"{vid}: referenceLabels are for new cards (cardVisual)")
    tile = spec.get("field")
    if not tile:
        data = (v.get("bindings") or {}).get("Data") or []
        if not data:
            raise BuildError(f"{vid}: referenceLabels needs a field (or a Data binding)")
        tile = data[0]["field"] if isinstance(data[0], dict) else data[0]
    tile_ref = qref(ctx.field(tile))
    labels, blanks, backgrounds = [], {}, {}
    for k, lab in enumerate(spec.get("labels", [])):
        title = lab.get("title") or f"label {k + 1}"
        labels.append((title, ctx.field(lab["value"]), ctx.field(lab["detail"]) if lab.get("detail") else None,
                       ctx.field(lab["detailColor"]) if lab.get("detailColor") else None))
        if "blankAs" in lab:
            blanks[title] = lab["blankAs"]
        if lab.get("detailBackground"):
            backgrounds[title] = ctx.field(lab["detailBackground"])
    fonts = {"regular": ctx.font(spec["titleFont"]) if spec.get("titleFont") else None,
             "semibold": ctx.font(spec["valueFont"]) if spec.get("valueFont") else None}
    colors = {"title": ctx.colour(spec["titleColor"]) if spec.get("titleColor") else None,
              "value": ctx.colour(spec["valueColor"]) if spec.get("valueColor") else None}
    size = lambda key: ctx.number(spec[key]) if key in spec else None   # noqa: E731
    tmp = {}
    ref_labels(tmp, vid, tile_ref, labels, fonts, colors, size("titleSize"), size("valueSize"), blanks,
               layout=spec.get("layout"), title_off=spec.get("titleOff", False), detail_size=size("detailSize"),
               backgrounds=backgrounds, display_units=spec.get("displayUnits"))
    for key, entries in tmp.items():
        set_entries(ctx, vid, d, "objects", key, entries)


def _lit_num(entries, prop):
    for e in entries or []:
        if "selector" not in e and prop in e.get("properties", {}):
            x = e["properties"][prop].get("expr", {}).get("Literal", {}).get("Value", "")
            try:
                return float(str(x).rstrip("DLM"))
            except ValueError:
                return None
    return None


def fit_widths(ctx, vid, v, d, spec):
    """columnWidths "fit" (or "fit" values): widths from the box (pbikit/tablefit.py)."""
    from . import tablefit as TF
    if v["type"] not in TABLES:
        raise BuildError(f"{vid}: columnWidths fit is for tables and matrices")
    roles = v.get("bindings") or {}
    if v["type"] == "pivotTable" and roles.get("Columns"):
        raise BuildError(f"{vid}: columnWidths fit can't size a matrix with fields on Columns (one set of value "
                         "columns per member); set the widths")
    if v["type"] == "pivotTable":               # Rows fields share one stepped column: the first Rows field
        items = (roles.get("Rows") or [])[:1] + list(roles.get("Values") or [])
    else:
        items = list(roles.get("Values") or [])
    if spec == "fit":
        spec = {(it["field"] if isinstance(it, dict) else it): "fit" for it in items}
    cols = []
    for it in items:
        it = it if isinstance(it, dict) else {"field": it}
        if "field" not in it:
            raise BuildError(f"{vid}: columnWidths fit doesn't size field parameters; set the widths")
        want = spec.get(it["field"])
        if want is None:
            continue
        f = ctx.field(it["field"])
        label = it.get("displayName") or f.get("Measure", f.get("Column", {})).get("Property", it["field"])
        if not hasattr(ctx, "text_measures"):
            from .daxtype import text_measures
            ctx.text_measures = text_measures(ctx.res.model) if ctx.res.model else set()
        kind = TF.kind_of(ctx.res.model, f, ctx.report.extensions(),
                          text_measure=lambda mm: (mm.table, mm.name) in ctx.text_measures)
        cols.append((it["field"], label, kind, None if want == "fit" else ctx.number(want, "container")))
    unknown = set(spec) - {c[0] for c in cols}
    if unknown:
        raise BuildError(f"{vid}: columnWidths names fields that aren't bound: {sorted(unknown)}")
    vco = d.get("visual", {}).get("visualContainerObjects", {})
    pl, pr = _lit_num(vco.get("padding"), "left") or 0, _lit_num(vco.get("padding"), "right") or 0
    tbl = ctx.tokens.get("table", {})
    hdr = _lit_num(d.get("visual", {}).get("objects", {}).get("columnHeaders"), "fontSize")
    if hdr is None:
        hs = tbl.get("headerSize", 10)
        hdr = ctx.number(hs) if isinstance(hs, str) else hs
    try:
        return TF.widths(cols, v["w"], pl, pr, hdr, tbl.get("scrollbarReserve", 16))
    except TF.FitError as e:
        raise BuildError(f"{vid}: columnWidths fit {e}")


def apply_table(ctx, vid, v, d):
    """columnWidths: {field: px} -> objects.columnWidth on each column's metadata selector (as Desktop saves);
    "fit" (all columns) or "fit" values: computed from the box."""
    spec = v.get("columnWidths")
    if not spec:
        return
    if spec == "fit" or (isinstance(spec, dict) and "fit" in spec.values()):
        spec = fit_widths(ctx, vid, v, d, spec)
    elif not isinstance(spec, dict):
        raise BuildError(f"{vid}: columnWidths is {{field: px or \"fit\"}} or \"fit\"")
    for fld, px in spec.items():
        set_prop(ctx, vid, d, "objects", "columnWidth", {"metadata": qref(ctx.field(fld))}, "value",
                 n(ctx.number(px, "container")))


def apply_sync(ctx, vid, v, d):
    """sync: {group, fieldChanges, filterChanges} -> visual.syncGroup (sync slicers: slicers on several pages with the
    same group name share their selection; one group per field)."""
    s_ = v.get("sync")
    if not s_:
        return
    if v["type"] not in ("slicer", "advancedSlicerVisual", "listSlicer", "textSlicer"):
        raise BuildError(f"{vid}: sync is for slicers")
    if isinstance(s_, str):
        s_ = {"group": s_}
    d["visual"]["syncGroup"] = {"groupName": s_["group"], "fieldChanges": bool(s_.get("fieldChanges", True)),
                                "filterChanges": bool(s_.get("filterChanges", True))}
    ctx.owned_new.setdefault(vid, []).append(["visual", "syncGroup", None, None])


def apply_slicer_mode(ctx, vid, v, d):
    """slicerMode: list (Basic), dropdown, between, before, after -> objects.data.mode (overrides the theme)."""
    mode = v.get("slicerMode")
    if mode is None:
        return
    m = SLICER_MODES.get(str(mode).lower())
    if not m:
        raise BuildError(f"{vid}: slicerMode {mode!r} ({', '.join(SLICER_MODES)})")
    set_prop(ctx, vid, d, "objects", "data", None, "mode", s(m))


NAV_STATES = ("default", "hover", "selected")


def apply_navigator(ctx, vid, v, d):
    """navigator (page / bookmark navigators): tile states as Desktop saved them in Rep 5 and Rep 8 (ids default /
    hover / selected; fill and outline `show` selector-less), through objects.navigator_states.
    {"fill": colour, "outline": colour (selected tile), "radius": px or token, "font": regular / semibold / family,
     "size": pt or fontPt token, "colors": {state: text colour}, "transparency": {state: 0-100 fill transparency}}"""
    nv = v.get("navigator")
    if not nv:
        return
    if v["type"] not in ("pageNavigator", "bookmarkNavigator"):
        raise BuildError(f"{vid}: navigator is for pageNavigator / bookmarkNavigator visuals")
    unknown = set(nv) - {"fill", "outline", "radius", "font", "size", "colors", "transparency"}
    if unknown:
        raise BuildError(f"{vid}: navigator keys {sorted(unknown)} (fill, outline, radius, font, size, colors, "
                         "transparency)")
    cols, trs = nv.get("colors", {}), nv.get("transparency", {})
    for st in NAV_STATES:
        if st not in cols or st not in trs:
            raise BuildError(f"{vid}: navigator colors and transparency need {', '.join(NAV_STATES)}")
    tmp = {}
    navigator_states(tmp, fill=ctx.colour(nv.get("fill", "card")), outline=ctx.colour(nv.get("outline", "border")),
                     radius=ctx.number(nv.get("radius", "control.radius"), "container"), text_family=ctx.font(nv.get("font")),
                     text_size=ctx.number(nv.get("size", "body")),
                     colours={st: ctx.colour(cols[st]) for st in NAV_STATES},
                     transparency={st: ctx.number(trs[st], "glass") for st in NAV_STATES})
    for key, entries in tmp.items():
        set_entries(ctx, vid, d, "objects", key, entries)


def apply_props(ctx, vid, v, d):
    for key, val in (v.get("props") or {}).items():
        where = "objects"
        if key.startswith("container:"):
            where, key = "visualContainerObjects", key[len("container:"):]
        path, has_sel, sel = key.partition("@")     # first @ only: a JSON selector may contain @ itself
        obj, _, prop = path.partition(".")
        if not prop:
            if val in ({}, {"raw": {}}):              # an entry with no properties, kept as Desktop saved it
                selector = selector_of(ctx, sel) if sel and sel != "none" else None
                ensure_entry(ctx, vid, d, where, obj, selector)
                continue
            raise BuildError(f"{vid}: prop {key!r} must be object.property[@selector] (or object@selector: {{}})")
        selector = selector_of(ctx, sel or None)
        objs, show_too = STATEFUL.get(v["type"], (set(), False))
        if not has_sel and where == "objects" and obj in objs and (prop != "show" or show_too):
            selector = {"id": "default"}      # where Desktop keeps it; "@none" forces no selector
        if sel == "none":
            selector = None
        set_prop(ctx, vid, d, where, obj, selector, prop, prop_value(ctx, prop, val))


def apply_selection(ctx, vid, v, d):
    sel = v.get("selection")
    if not sel:
        return
    fld = ctx.field(sel["field"])
    vals = sel["values"] if isinstance(sel.get("values"), list) else [sel.get("value")]
    set_prop(ctx, vid, d, "objects", "general", None, "filter",
             {"filter": F.selection_filter(fld, ctx.res.column_type(fld), vals)})


# ---------------------------------------------------------------- pages
def page_background(ctx, spec):
    bg = spec.get("background")
    if bg is None:
        return None
    if isinstance(bg, dict) and "theme" not in bg:
        colour, tr = bg.get("color"), bg.get("transparency", 0)
    else:
        colour, tr = bg, spec.get("backgroundTransparency", 0)
    return [{"properties": {"color": solid(ctx.colour(colour)), "transparency": n(tr)}}]


PANE_CARDS = {"applied": "Applied", "available": "Available"}


def pane_value(ctx, prop, v):
    """A filter pane / filter card value: fonts as Desktop's quoted text, the rest as for `props`."""
    if prop == "fontFamily" and isinstance(v, str):
        return s(ctx.font(v))
    return prop_value(ctx, prop, v)


def apply_page_pane(ctx, key, spec, d, page_url):
    """Page `filterPane` (page objects.outspacePane, no selector) and `filterCards` (objects.filterCard on selector
    {id: Applied} / {id: Available}, the `$id`s Desktop's base theme uses). Schema-checked; not Desktop-tested
    (roadmap batch 1, gap 1)."""
    owner = f"page:{key}"
    for prop, val in (spec.get("filterPane") or {}).items():
        schema_gate(ctx, owner, *SP.page_prop(page_url, "outspacePane", prop))
        set_prop(ctx, owner, d, "page", "outspacePane", None, prop, pane_value(ctx, prop, val))
    for card, props in (spec.get("filterCards") or {}).items():
        sel_id = PANE_CARDS.get(str(card).lower())
        if not sel_id:
            raise BuildError(f"{owner}: filterCards key {card!r} must be applied or available")
        for prop, val in (props or {}).items():
            schema_gate(ctx, owner, *SP.page_prop(page_url, "filterCard", prop))
            set_prop(ctx, owner, d, "page", "filterCard", {"id": sel_id}, prop, pane_value(ctx, prop, val))


def tree_gate(ctx, owner, url, path, node):
    """A whole JSON fragment pbik writes for an unverified feature, checked against the cached schema: a warning, or
    (strict) an error (roadmap batch 2)."""
    for status, msg in SP.tree_issues(url, path, node):
        schema_gate(ctx, owner, status, msg)


def set_annotations(lst, wanted, owner):
    for name, value in wanted.items():
        if not isinstance(value, str):
            raise BuildError(f"{owner}: annotation {name!r} must be text (the schema's #Annotation value is a string)")
        e = next((a for a in lst if a.get("name") == name), None)
        if e is None:
            lst.append({"name": name, "value": value})
        else:
            e["value"] = value


def apply_annotations(ctx, owner, d, wanted):
    """annotations [{name, value}] in place (roadmap gap 13): the names layout.json sets are owned, the rest stay."""
    if not wanted:
        return
    lst = d.setdefault("annotations", [])
    set_annotations(lst, wanted, owner)
    for name in wanted:
        ctx.owned_new.setdefault(owner, []).append(["annotations", name, None, None])
    ctx.unverified.add("annotations")
    tree_gate(ctx, owner, d.get("$schema", ""), ["annotations"], lst)


def visual_annotations(layout, v):
    ann = dict(v.get("annotations") or {})
    if layout.get("annotate"):
        ann.setdefault("pbik.id", v["id"])
        ann.setdefault("pbik.layout", layout_hash(v))
    return ann


def layout_hash(v):
    """12 hex of the visual's layout.json entry: tells whether a visual still matches the layout it was built from."""
    import hashlib
    return hashlib.sha1(json.dumps(v, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


PAGE_PROP_OBJECTS = {"pageInformation", "pageSize", "displayArea", "outspace", "pageRefresh", "personalizeVisual",
                     "background"}


def apply_page_props(ctx, key, spec, d):
    """Page `props` (roadmap gap 12): {"object.property[@selector]": value} on page.json objects, as visual `props`;
    each checked against the cached page schema (#PageFormattingObjects, closed per object). The page's own keys
    (background, filterPane, filterCards) stay the way to set those."""
    owner = f"page:{key}"
    for k, val in (spec.get("props") or {}).items():
        path, _, sel = k.partition("@")
        obj, _, prop = path.partition(".")
        if not prop:
            raise BuildError(f"{owner}: page prop {k!r} must be object.property[@selector]")
        if obj in ("outspacePane", "filterCard"):
            raise BuildError(f"{owner}: use the page's filterPane / filterCards keys for {obj}")
        schema_gate(ctx, owner, *SP.page_prop(d.get("$schema", ""), obj, prop))
        set_prop(ctx, owner, d, "page", obj, selector_of(ctx, sel or None), prop, prop_value(ctx, prop, val))
        if obj in PAGE_PROP_OBJECTS - {"background"}:
            ctx.unverified.add("page-props")


def schema_gate(ctx, owner, status, msg):
    """A property Microsoft's schema doesn't have: a warning, or (strict) an error."""
    if status not in (SP.UNKNOWN, SP.NEAREST):
        return
    if ctx.strict and status == SP.UNKNOWN:
        raise BuildError(f"{msg} (--strict)")
    ctx.res.warnings.append(f"{owner}: {msg}; Desktop may refuse the file (schema error) or ignore it")


def check_props_schema(ctx, vid, v, container_url):
    """Every `props` key against the cached schema (container objects are listed per object; a visual's objects are
    open in the schema for every visual type, so those pass here and the settings catalog checks them)."""
    for key in (v.get("props") or {}):
        where, k = ("visualContainerObjects", key[len("container:"):]) if key.startswith("container:") else ("objects", key)
        path = k.partition("@")[0]
        obj, _, prop = path.partition(".")
        schema_gate(ctx, vid, *SP.visual_prop(container_url, where, obj, prop or None))


REPORT_PANE = {"expanded", "visible"}


def apply_report(ctx, rep, layout, old_map):
    """Top-level `report`: `filterPane: {expanded, visible}` -> report.json objects.outspacePane, `settings: {...}`
    -> report.json settings (#ExplorationSettings). In place: everything else in report.json stays as Desktop wrote
    it (filterConfig, section, themes, resources). Each key pbik sets remembers the value Desktop had before, and goes
    back to it when the key leaves layout.json. Returns (report.json dict or None, owned dict for visual-map.json)."""
    spec = layout.get("report") or {}
    old = (old_map.get("reportOwned") or {})
    if not spec and not old:
        return None, {}
    rf = rep.defn / "report.json"
    d = load(rf)
    url = d.get("$schema", "")
    owned = {"settings": {}, "objects": {}, "annotations": []}
    pane = spec.get("filterPane") or {}
    for prop in pane:
        if prop not in REPORT_PANE:
            raise BuildError(f"report.filterPane.{prop}: only expanded and visible are report-level (page "
                             "`filterPane` formats the pane)")
    for prop, val in pane.items():
        if not isinstance(val, bool):
            raise BuildError(f"report.filterPane.{prop} must be true or false")
        schema_gate(ctx, "report", *SP.report_prop(url, "outspacePane", prop))
        entries = d.setdefault("objects", {}).setdefault("outspacePane", [])
        e = next((x for x in entries if not x.get("selector")), None)
        if e is None:
            e = {"properties": {}}
            entries.append(e)
        was = (old.get("objects") or {}).get(f"outspacePane.{prop}", {"was": e["properties"].get(prop)})
        owned["objects"][f"outspacePane.{prop}"] = was
        e["properties"][prop] = b(val)
    ann = spec.get("annotations") or {}
    lst = d.setdefault("annotations", [])
    set_annotations(lst, ann, "report")
    for name in (old.get("annotations") or []):
        if name not in ann:
            lst[:] = [a for a in lst if a.get("name") != name]
    if not lst:
        d.pop("annotations", None)
    if ann:
        owned["annotations"] = sorted(ann)
        ctx.unverified.add("annotations")
        tree_gate(ctx, "report", url, ["annotations"], lst)
    for key, val in (spec.get("settings") or {}).items():
        schema_gate(ctx, "report", *SP.report_setting(url, key, val))
        st = d.setdefault("settings", {})
        owned["settings"][key] = (old.get("settings") or {}).get(key, {"was": st.get(key)})
        st[key] = val
    # keys pbik set before and no longer in layout.json go back to Desktop's value (or away)
    for path, rec in (old.get("objects") or {}).items():
        if path in owned["objects"]:
            continue
        obj, prop = path.split(".", 1)
        for e in d.get("objects", {}).get(obj, []):
            if e.get("selector"):
                continue
            if rec.get("was") is None:
                e.get("properties", {}).pop(prop, None)
            else:
                e.setdefault("properties", {})[prop] = rec["was"]
        lst = d.get("objects", {}).get(obj)
        if lst is not None:
            lst[:] = [e for e in lst if e.get("properties") or e.get("selector")]
            if not lst:
                del d["objects"][obj]
        if "objects" in d and not d["objects"]:
            del d["objects"]
    for key, rec in (old.get("settings") or {}).items():
        if key in owned["settings"]:
            continue
        if rec.get("was") is None:
            d.get("settings", {}).pop(key, None)
        else:
            d.setdefault("settings", {})[key] = rec["was"]
    if d.get("settings"):          # Desktop writes settings in the schema's property order (pbik-smoke-013 save)
        order = SP.property_order(url, ["settings"])
        if order:
            rank = {k: n_ for n_, k in enumerate(order)}
            d["settings"] = dict(sorted(d["settings"].items(), key=lambda kv: rank.get(kv[0], len(rank))))
    owned = {k: v for k, v in owned.items() if v}
    if pane.get("visible") is False:
        ctx.res.warnings.append("report: filterPane.visible false hides the filter pane in view mode: a filter that "
                                "isn't hidden can't be changed there (pbik validate lists them)")
    return d, owned


def keep_desktop_filters(old, d):
    """--reset / a Deneb swap rebuilds a visual from its template: keep the filters Desktop saved (automatic filters,
    and filters made in the pane, any name not pbik_ / tpl_), so a rebuild never loses them (roadmap gap 24)."""
    mine = [f_ for f_ in (old.get("filterConfig") or {}).get("filters", [])
            if not f_.get("name", "").startswith(("pbik_", "tpl_"))]
    if not mine:
        return
    fc = d.setdefault("filterConfig", {}).setdefault("filters", [])
    have = {f_.get("name") for f_ in fc}
    fc.extend(f_ for f_ in mine if f_.get("name") not in have)


IMAGE_SCALING = {"fit": "Fit", "fill": "Fill", "normal": "Normal"}


def image_spec(v):
    """layout `image`: "<file>" or {file, scaling} -> (file, scaling)."""
    im = v["image"]
    im = {"file": im} if isinstance(im, str) else dict(im)
    if not im.get("file"):
        raise BuildError(f"{v['id']}: image needs a file (a PNG path from the project root)")
    sc = IMAGE_SCALING.get(str(im.get("scaling", "fit")).lower())
    if not sc:
        raise BuildError(f"{v['id']}: image scaling {im.get('scaling')!r} ({', '.join(IMAGE_SCALING)})")
    return im["file"], sc


def apply_image(ctx, vid, v, d):
    """image (roadmap gap 3): an image visual bound to a registered resource, in the form Desktop saved on the
    Patterns page (design/templates/image.json): general.imageUrl = ResourcePackageItem (RegisteredResources,
    PackageType 1), imageScaling.imageScalingType. The file is registered by build() first (`pbik resource add`)."""
    if "image" not in v:
        return
    if v["type"] != "image":
        raise BuildError(f"{vid}: image is for image visuals (type image); a card image is cf type image")
    _, sc = image_spec(v)
    item = ctx.images[vid]
    set_prop(ctx, vid, d, "objects", "general", None, "imageUrl", {"expr": {"ResourcePackageItem": {
        "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": item}}})
    set_prop(ctx, vid, d, "objects", "imageScaling", None, "imageScalingType", s(sc))


def apply_html_content(ctx, vid, v, d):
    """HTML Content visuals render with legacy rendering on (pbikit/htmlcontent.py); warn under 43px tall."""
    if not HC.is_html_content(v["type"]):
        return
    set_prop(ctx, vid, d, "objects", "compatibility", None, "legacyRendering", b(True))
    issue = HC.height_issue(v.get("h"))
    if issue:
        ctx.res.warnings.append(f"{vid}: {issue}")


def apply_deneb(ctx, vid, v, d):
    """A Deneb visual's spec and state, as Desktop saved them (pbikit/deneb.py)."""
    spec = v.get("_deneb")
    if spec is None:
        return
    projs = d.get("visual", {}).get("query", {}).get("queryState", {}).get("dataset", {}).get("projections", [])
    set_prop(ctx, vid, d, "objects", "vega", None, "jsonSpec", s(DN.spec_text(spec)))
    for prop, val in (("supportFieldConfiguration", s(DN.field_config(projs))), ("denebMetaVersion", s("2")),
                      ("consolidateFieldParameters", b(False)), ("viewportHeight", n(round(v["h"]))),
                      ("viewportWidth", n(round(v["w"])))):
        set_prop(ctx, vid, d, "objects", "stateManagement", None, prop, val)


def register_custom_visual(rep, name):
    """List an AppSource visual in report.json `publicCustomVisuals` (as Desktop did on adding Deneb)."""
    rf = rep.defn / "report.json"
    d = load(rf)
    lst = d.get("publicCustomVisuals", [])
    if name not in lst:
        new = {}
        for k, x in d.items():                   # Desktop put it just before resourcePackages
            if k == "resourcePackages" and "publicCustomVisuals" not in d:
                new["publicCustomVisuals"] = lst + [name]
            new[k] = x
        new["publicCustomVisuals"] = lst + [name]
        rep.write(rf, new)


def build(report_path, layout_path, prune=False, reset=False, map_path=None, tokens_path=None, templates=None,
          quiet=False, no_custom_visuals=False, project=None, strict=False):
    layout_path = pathlib.Path(layout_path).resolve()
    if project is None and (layout_path.parent / "project.json").exists():
        project = layout_path.parent / "project.json"        # design/specs/project.json, next to layout.json
    if not no_custom_visuals and project and pathlib.Path(project).exists()             and load(pathlib.Path(project)).get("customVisuals") is False:
        no_custom_visuals = True                # custom visuals blocked on this laptop: build every fallback
        if not quiet:
            print("project.json customVisuals false: building each Deneb visual's fallback (as --no-custom-visuals)")
    layout = load(layout_path)
    design = layout_path.parent.parent
    tokens_path = pathlib.Path(tokens_path) if tokens_path else design / "tokens.json"
    tokens = load(tokens_path) if tokens_path.exists() else {}
    templates = pathlib.Path(templates) if templates else design / "templates"
    map_path = pathlib.Path(map_path) if map_path else layout_path.parent / "visual-map.json"
    old_map = load(map_path) if map_path.exists() else {}
    theme_changed = []
    if layout.get("theme"):                     # the theme file (gen_theme.py writes it from tokens), registered first
        tf = pathlib.Path(layout["theme"])
        tf = tf if tf.is_absolute() else design.parent / tf
        if not tf.exists():
            fail(f"theme {tf} not found (run design/scripts/gen_theme.py first)")
        from .theme import apply as apply_theme
        theme_changed = apply_theme(report_path, tf, quiet=True, project=project)
    images, image_changed = {}, []
    for v in layout.get("visuals", []):        # roadmap gap 3: register each image visual's file first
        if "image" not in v:
            continue
        try:
            file, _ = image_spec(v)
        except BuildError as e:
            fail(str(e))
        src = pathlib.Path(file)
        src = src if src.is_absolute() else design.parent / src
        from .theme import register_image
        images[v["id"]], ch = register_image(report_path, src, project)
        image_changed += [c for c in ch if c not in image_changed]
    rep = Report(report_path)
    rep.project = project
    rep.changed.extend(theme_changed + [c for c in image_changed if c not in theme_changed])
    ctx = Ctx(rep, layout, tokens)
    ctx.images = images
    ctx.strict = strict
    errors, log = [], []
    try:
        report_doc, report_owned = apply_report(ctx, rep, layout, old_map)
    except BuildError as e:
        errors.append(f"report: {e}")
        report_doc, report_owned = None, {}

    pages_spec = layout.get("pages", {})
    visuals = [v for v in layout.get("visuals", []) if (v.get("build") or {}).get("method") != "page-background"]
    visuals, dn_errors = DN.resolve(visuals, no_custom_visuals, design.parent)
    if dn_errors:
        for e in dn_errors:
            print(f"error: {e}")
        fail(f"{len(dn_errors)} Deneb error(s) in layout.json; nothing written", 1)
    ids = [v["id"] for v in visuals]
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup:
        fail(f"duplicate visual IDs in layout.json: {dup}")
    for v in visuals:
        if not re.fullmatch(r"P\d+-V\d{2,}", v.get("id", "")):
            fail(f"bad visual ID {v.get('id')!r}: use P<page>-V<nn>")
        if v.get("page") not in pages_spec:
            fail(f"{v['id']}: page {v.get('page')!r} is not in layout.json pages")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", v.get("name", "")):
            fail(f"{v['id']}: name {v.get('name')!r} must be letters, digits, - or _ (kebab-case): it is the folder name, "
                 "and Desktop silently skipped visuals named with spaces, commas, # or % (v0.4.1)")
        if v.get("decorative") and (v.get("container") or {}) != "off" and isinstance(v.get("container"), dict)                 and v["container"].get("altText"):
            fail(f"{v['id']}: decorative and altText both set: a decorative visual is skipped by screen readers "
                 "(drop one)")
        if len(f"{v['id']}_{v['name']}") > 50:
            fail(f"{v['id']}: '<ID>_<name>' is longer than 50 characters (PBIR visual name limit)")

    bm_errors = BM.check(layout)
    if bm_errors:
        for e in bm_errors:
            print(f"error: {e}")
        fail(f"{len(bm_errors)} bookmark error(s) in layout.json; nothing written", 1)

    # pages
    meta = rep.pages_meta()
    order = meta.setdefault("pageOrder", [])
    existing = {name: (d, folder) for name, d, folder in rep.pages()}
    page_ids = {}
    page_docs = {}
    for key, spec in pages_spec.items():
        known = (old_map.get("pages") or {}).get(key, {}).get("name")
        name = spec.get("name") or (known if known in existing else None)
        if not name:
            name = next((nm for nm, (d, _) in existing.items() if d.get("displayName") == spec["displayName"]), None)
        if not name:
            name = stable_name("page", key, spec["displayName"])
        folder = existing.get(name, (None, rep.defn / "pages" / name))[1]
        d = existing.get(name, ({"$schema": rep.schema_version("page"), "name": name}, None))[0]
        d["displayName"] = spec["displayName"]
        d["displayOption"] = spec.get("displayOption", d.get("displayOption", "FitToPage"))
        canvas = tokens.get("canvas", {})
        d["height"] = spec.get("height", d.get("height", canvas.get("height", 1080)))
        d["width"] = spec.get("width", d.get("width", canvas.get("width", 1920)))
        dep = DEP.display_issue(d["displayOption"], SP.deprecated(d["$schema"], ["displayOption"]))
        if dep:
            ctx.res.warnings.append(f"page {key}: {dep}")
        bg = page_background(ctx, spec)
        if bg:
            d.setdefault("objects", {})["background"] = bg
        try:
            apply_page_pane(ctx, key, spec, d, d["$schema"])
            apply_page_props(ctx, key, spec, d)
            ann = dict(spec.get("annotations") or {})
            if layout.get("annotate"):
                ann.setdefault("pbik.page", key)
            apply_annotations(ctx, f"page:{key}", d, ann)
        except BuildError as e:
            errors.append(f"page {key}: {e}")
        new_p = {json.dumps(x) for x in ctx.owned_new.get(f"page:{key}", [])}
        for item in (old_map.get("owned") or {}).get(f"page:{key}", []):
            if json.dumps(item) not in new_p:
                release(d, *item)
        if "objects" in d and not d["objects"]:
            del d["objects"]
        if spec.get("hidden") is not None:
            if spec["hidden"]:
                d["visibility"] = "HiddenInViewMode"
            else:
                d.pop("visibility", None)
        if name not in order:
            order.append(name)
        page_ids[key] = name
        page_docs[key] = (d, folder)
    active = [k for k, sp in pages_spec.items() if sp.get("active")]
    if len(active) > 1:
        fail(f"pages {active} are all marked active: one page opens first")
    landing = [k for k, sp in pages_spec.items() if sp.get("landing")]      # roadmap gap 12
    if len(landing) > 1:
        fail(f"pages {landing} are all marked landing: one page is the landing page")
    old_landing = old_map.get("landing")
    if landing:
        st, msg = SP.check(meta.get("$schema", rep.schema_version("pagesMetadata")), ["landingPageName"],
                           "pages.json landingPageName")
        schema_gate(ctx, "pages.json", st, msg or "")
        meta["landingPageName"] = page_ids[landing[0]]
        ctx.unverified.add("landing")
    elif old_landing and meta.get("landingPageName") == old_landing:
        meta.pop("landingPageName", None)
    if active:
        meta["activePageName"] = page_ids[active[0]]
    elif order and meta.get("activePageName") not in order:
        meta["activePageName"] = order[0]

    # page filters (after page ids exist)
    for key, spec in pages_spec.items():
        d, _ = page_docs[key]
        try:
            if spec.get("filters") or any(f.get("name", "").startswith("pbik_")
                                          for f in d.get("filterConfig", {}).get("filters", [])):
                apply_filters(ctx, f"page:{key}", d, spec.get("filters", []))
        except BuildError as e:
            errors.append(f"page {key}: {e}")

    # groups: members by ID, each in at most one group, on the group's page, no cycles
    by_id = {v["id"]: v for v in visuals}
    parent = {}
    for g in (v for v in visuals if v["type"] == "group"):
        if not g.get("members"):
            fail(f"{g['id']}: a group needs members (visual or group IDs)")
        for m in g["members"]:
            if m not in by_id:
                fail(f"{g['id']}: member {m} is not in layout.json")
            if by_id[m]["page"] != g["page"]:
                fail(f"{g['id']}: member {m} is on page {by_id[m]['page']}, the group on {g['page']}")
            if m in parent:
                fail(f"{m} is in two groups ({parent[m]}, {g['id']})")
            parent[m] = g["id"]
    for vid in parent:
        seen, cur = {vid}, vid
        while cur in parent:
            cur = parent[cur]
            if cur in seen:
                fail(f"{vid}: groups contain each other")
            seen.add(cur)
    boxes = {}

    def box(vid):
        """(x, y, w, h) on the page: layout.json's box, a text box with its headroom, a group's own box or its
        members' bounding box."""
        if vid in boxes:
            return boxes[vid]
        v = by_id[vid]
        if v["type"] == "group" and not all(k in v for k in ("x", "y", "w", "h")):
            bs = [box(m) for m in v["members"]]
            x0, y0 = min(b_[0] for b_ in bs), min(b_[1] for b_ in bs)
            r = (x0, y0, max(b_[0] + b_[2] for b_ in bs) - x0, max(b_[1] + b_[3] for b_ in bs) - y0)
        else:
            x, y, w, h = v["x"], v["y"], v["w"], v["h"]
            if v["type"] in TEXT_FIT and v.get("textFit", True):
                y, h = y + TEXT_FIT[v["type"]][0], h + TEXT_FIT[v["type"]][1]
            r = (x, y, w, h)
        boxes[vid] = r
        return r

    # visuals
    old_owned = old_map.get("owned", {})
    vnames = {v["id"]: f"{v['id']}_{v['name']}" for v in visuals}
    vfiles, moves = {}, []
    for v in visuals:
        vid = v["id"]
        d_page, pfolder = page_docs[v["page"]]
        folder = pfolder / "visuals" / vnames[vid]
        found = [f.parent for f in rep.visual_by_id(vid)]
        if len(found) > 1:
            errors.append(f"{vid}: {len(found)} folders on disk {[str(x.name) for x in found]}; remove the extra one")
            continue
        f = folder / "visual.json"
        src = f
        if found and found[0] != folder:              # renamed, or moved to another page: keep its content
            moves.append((found[0], folder))
            src = found[0] / "visual.json"
        tpl = None
        if v["type"] == "group":
            try:
                d = load(src) if src.exists() else {"$schema": rep.schema_version("visualContainer"),
                                                    "name": vnames[vid], "position": {}}
                if "visual" in d:
                    errors.append(f"{vid}: on disk it is {d['visual'].get('visualType')}, layout says group: "
                                  "a new type takes a new ID (layout-schema.md)")
                    continue
                d["name"] = vnames[vid]
                set_position(d, vid, v, box(vid), parent, box, vnames, ctx)
                d["visualGroup"] = {"displayName": v.get("displayName", v["name"]),
                                    "groupMode": v.get("mode", "ScaleMode")}
                apply_annotations(ctx, vid, d, visual_annotations(layout, v))
                for item in old_owned.get(vid, []):
                    if json.dumps(item) not in {json.dumps(x) for x in ctx.owned_new.get(vid, [])}:
                        release(d, *item)
                vfiles[vid] = (f, d)
            except BuildError as e:
                errors.append(f"{vid}: {e}")
            continue
        swap = False                    # a Deneb visual and its fallback replace each other in the same folder
        if src.exists() and not reset and v.get("_swapFrom"):
            swap = load(src).get("visual", {}).get("visualType") == v["_swapFrom"]
            if swap:
                log.append(f"{vid}: {v['_swapFrom']} -> {v['type']} (Deneb visual / fallback)")
        if not src.exists() or reset or swap:
            tname = v.get("template") or v["type"]
            tf = templates / f"{tname}.json"
            tpl = load(tf) if tf.exists() else None
            if v.get("template") and tpl is None:
                errors.append(f"{vid}: template {tf} not found")
                continue
        try:
            if src.exists() and not reset and not swap:
                d = load(src)
                if d.get("visual", {}).get("visualType") != v["type"]:
                    on_disk = d.get("visual", {}).get("visualType") or ("group" if "visualGroup" in d else "?")
                    errors.append(f"{vid}: on disk it is {on_disk}, layout says {v['type']}: "
                                  "a new type takes a new ID (layout-schema.md)")
                    continue
            else:
                d = {"$schema": (tpl or {}).get("$schema") or rep.schema_version("visualContainer"), "name": vnames[vid],
                     "position": {}, "visual": {"visualType": v["type"], **copy.deepcopy((tpl or {}).get("visual", {})),
                                               }}
                d["visual"]["visualType"] = v["type"]
                d["visual"].setdefault("drillFilterOtherVisuals", True)
                if tpl and tpl.get("filterConfig"):
                    d["filterConfig"] = copy.deepcopy(tpl["filterConfig"])
                    for f_ in d["filterConfig"].get("filters", []):     # template filters belong to the template,
                        if f_.get("name", "").startswith("pbik_"):     # not to this visual's layout `filters`
                            f_["name"] = "tpl_" + f_["name"][5:]
                if tpl:                         # a template carries formatting only: its content (text, titles,
                    gone = FR.formatting_only(d, rep.model(), rep.extensions())     # field-bound settings) goes
                    if ctx.tokens.get("theme", {}).get("recolourTemplates"):     # a gen_tokens.py palette: the
                        from . import recolour                                    # template's colours follow it
                        rc = recolour.apply(d, recolour.load_palette(templates), ctx.colour)
                        if rc:
                            log.append(f"{vid}: template colours -> tokens ({len(rc)}: "
                                       + ", ".join(sorted({f'{o}->{n}' for _, o, n in rc})) + ")")
                    sel_fill = ctx.tokens.get("colors", {}).get("selected")
                    if sel_fill:                # one selected colour on every selected state from a template
                        from . import a11y
                        cols = ctx.tokens.get("colors", {})
                        done, warns = a11y.apply_selected_fill(
                            d, ctx.colour(sel_fill),
                            ctx.colour(cols["onSelected"]) if cols.get("onSelected") else None,
                            ctx.colour(cols.get("primary", "#12343B")))
                        for state, old_c, new_c, txt in done:
                            log.append(f"{vid}: template {state} fill {old_c} -> colors.selected {new_c}, text {txt}")
                        for w_ in warns:
                            ctx.res.warnings.append(f"{vid}: {w_}")
                    if gone:
                        ctx.res.warnings.append(f"{vid}: template {v.get('template') or v['type']} filters on fields "
                                                f"this model doesn't have; dropped {', '.join(gone)}")
                if src.exists() and (reset or swap):
                    old = load(src)
                    d["position"] = old.get("position", {})
                    keep_desktop_filters(old, d)
            apply_empty_query(v, d, tpl, existing=src.exists() and not reset)
            d["name"] = vnames[vid]
            set_position(d, vid, v, box(vid), parent, box, vnames, ctx)
            apply_query(ctx, v, d)
            if v.get("filters") or any(x.get("name", "").startswith("pbik_")
                                       for x in d.get("filterConfig", {}).get("filters", [])):
                apply_filters(ctx, vid, d, v.get("filters", []))
            apply_style(ctx, vid, v, d)
            apply_container(ctx, vid, v, d)
            apply_text(ctx, vid, v, d)
            apply_action(ctx, vid, v, d, page_ids)
            apply_reference_lines(ctx, vid, v, d)
            apply_selection(ctx, vid, v, d)
            apply_cf(ctx, vid, v, d)
            apply_reference_labels(ctx, vid, v, d)
            apply_table(ctx, vid, v, d)
            apply_slicer_mode(ctx, vid, v, d)
            apply_sync(ctx, vid, v, d)
            apply_navigator(ctx, vid, v, d)
            apply_image(ctx, vid, v, d)
            apply_props(ctx, vid, v, d)
            check_props_schema(ctx, vid, v, d["$schema"])
            retiring = DEP.visual_issue(v["type"], in_build=True) or DEP.link_issue(
                d["visual"].get("visualContainerObjects", {}).get("visualLink"))
            if retiring:
                ctx.res.warnings.append(f"{vid}: {retiring}")
            apply_annotations(ctx, vid, d, visual_annotations(layout, v))
            apply_deneb(ctx, vid, v, d)
            apply_html_content(ctx, vid, v, d)
            new = {json.dumps(x) for x in ctx.owned_new.get(vid, [])}
            for item in old_owned.get(vid, []):
                if json.dumps(item) not in new:
                    release(d, *item)
            vfiles[vid] = (f, d)
        except (BuildError, F.FieldError, KeyError) as e:
            errors.append(f"{vid}: {e}")

    if errors:
        for e in errors:
            print(f"error: {e}")
        fail(f"{len(errors)} error(s); nothing written", 1)

    # interactions (page-level, by visual name), in place; pairs pbik wrote before but no longer listed are removed
    old_inter = old_map.get("interactions", {})
    new_inter = {}
    for key, spec in pages_spec.items():
        d, _ = page_docs[key]
        pairs = []
        for it in spec.get("interactions", []):
            targets = it.get("targets", it.get("target"))
            targets = [x for x in vnames if x != it["source"] and pages_of(layout, x) == key] if targets == "*" else \
                (targets if isinstance(targets, list) else [targets])
            for t in targets:
                if it["source"] not in vnames or t not in vnames:
                    fail(f"page {key}: interaction {it['source']} -> {t}: unknown visual ID")
                pairs.append([vnames[it["source"]], vnames[t], it.get("type", "NoFilter")])
        lst = d.setdefault("visualInteractions", [])
        for src, tgt, typ in pairs:
            e = next((x for x in lst if x.get("source") == src and x.get("target") == tgt), None)
            if e is None:
                lst.append({"source": src, "target": tgt, "type": typ})
            else:
                e["type"] = typ
        keep = {(a, b_) for a, b_, _ in pairs}
        for a, b_, _ in old_inter.get(key, []):
            if (a, b_) not in keep:
                lst[:] = [x for x in lst if not (x.get("source") == a and x.get("target") == b_)]
        if not lst:
            d.pop("visualInteractions", None)
        if pairs:
            new_inter[key] = pairs

    # write
    pages_kept = {}
    for a_, b2 in moves:
        b2.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(a_), str(b2))
        log.append(f"moved {a_.name} -> {b2.relative_to(rep.defn)}")
    for key, (d, folder) in page_docs.items():
        rep.write(folder / "page.json", d)
    rep.write(rep.defn / "pages" / "pages.json", meta)
    for vid, (f, d) in vfiles.items():
        rep.write(f, d)
        if len(str(pathlib.Path(f).resolve())) >= versions.PATH_LIMIT:   # roadmap gap 23
            ctx.res.warnings.append(f"{vid}: {pathlib.Path(f).resolve()} is {len(str(pathlib.Path(f).resolve()))} "
                                    f"characters; Desktop needs every project path under {versions.PATH_LIMIT}")
    report_json_changed = report_doc is not None and rep.write(rep.defn / "report.json", report_doc)
    if any(v.get("_deneb") is not None for v in visuals):
        register_custom_visual(rep, DN.TYPE)
    for hc in sorted({v["type"] for v in visuals if HC.is_html_content(v["type"])}):
        register_custom_visual(rep, hc)
    bm_owned = BM.write(rep, layout, page_ids, vnames, {v["id"]: v["type"] for v in visuals}, old_map, prune, log)

    # prune
    removed = []
    for key, rec in (old_map.get("pages") or {}).items():       # pages pbik made that left layout.json (gap 12)
        if key in pages_spec:
            continue
        folder = rep.defn / "pages" / rec.get("name", "")
        if not rec.get("name") or not folder.is_dir():
            continue
        if not prune:
            log.append(f"page {key} ({rec.get('displayName')}) is not in layout.json (kept; --prune removes it)")
            pages_kept[key] = rec
            continue
        shutil.rmtree(folder)
        removed.append(f"page {rec.get('displayName')} ({rec['name']})")
        meta["pageOrder"] = [x for x in meta.get("pageOrder", []) if x != rec["name"]]
        for k_ in ("activePageName", "landingPageName"):
            if meta.get(k_) == rec["name"]:
                meta.pop(k_)
        if meta.get("pageOrder") and "activePageName" not in meta:
            meta["activePageName"] = meta["pageOrder"][0]
        rep.write(rep.defn / "pages" / "pages.json", meta)
    keep_ids = set(vnames)
    for key, (d, folder) in page_docs.items():
        for vf in sorted((folder / "visuals").glob("*")):
            m = ID_RE.match(vf.name)
            if m and m.group(1) not in keep_ids:
                if prune:
                    shutil.rmtree(vf)
                    removed.append(vf.name)
                else:
                    log.append(f"not in layout.json (kept; --prune removes it): {vf.name}")
            elif not m and vf.is_dir():
                log.append(f"not managed by pbik (no visual ID): {key}/{vf.name}")

    # ID map
    vis_map = {}
    for v in layout.get("visuals", []):
        f = vfiles.get(v["id"], (None,))[0]
        vis_map[v["id"]] = {"page": v.get("page"), "name": v["name"], "type": v["type"],
                            "method": (v.get("build") or {}).get("method", "native"),
                            "folder": str(f.parent.relative_to(rep.path.parent)).replace("\\", "/") if f else None}
        if v.get("decorative"):                 # roadmap gap 21: validate skips its alt text and tab order
            vis_map[v["id"]]["decorative"] = True
        if DN.is_deneb(v):                      # which of the two is in the report now
            vis_map[v["id"]]["built"] = "fallback" if no_custom_visuals else "deneb"
    out_map = {"_note": "Generated by pbik build. Don't edit.", "report": rep.path.name,
               "retired": layout.get("retired", []),
               "pages": {**pages_kept,
                         **{k: {"name": page_ids[k], "displayName": pages_spec[k]["displayName"]} for k in pages_spec}},
               "visuals": vis_map,
               "owned": {k: v for k, v in sorted(ctx.owned_new.items())},
               "interactions": new_inter,
               "bookmarks": bm_owned}
    if landing:
        out_map["landing"] = page_ids[landing[0]]
    if report_owned:                    # report.json keys pbik set, with the value Desktop had before
        out_map["reportOwned"] = report_owned
    if rep.target.pinned:              # files Desktop owns: only their $schema goes down to the target's version
        for f in (rep.defn / "report.json", rep.defn / "version.json"):
            d = load(f) if f.exists() else {}
            if d.get("$schema") and versions.capped_url(d["$schema"], rep.target) != d["$schema"]:
                rep.write(f, d)
    if save(map_path, out_map):
        rep.changed.append(str(map_path))

    if not quiet:
        if rep.target.pinned:
            print(f"target Desktop {rep.target.desktop}: $schema versions capped to {rep.target.note}")
        for key in sorted(ctx.unverified, key=lambda k: UV.FEATURES[k][0]):
            print(f"warning: {UV.message(key)}")
        for w in ctx.res.warnings:
            print(f"warning: {w}")
        for line in log:
            print(line)
        for r in removed:
            print(f"removed {r}")
        if report_json_changed:
            print("note: report.json changed (report settings or filter pane). Desktop's reload doesn't apply "
                  "report.json during the preview (Microsoft Learn, external editing): close Desktop without saving "
                  "and reopen instead of `pbik desktop reload`")
        if rep.changed:
            print(f"{len(rep.changed)} file(s) written:")
            for c in rep.changed:
                print(f"  {c}")
        else:
            print("No changes: the report already matches layout.json.")
    return rep.changed, removed


def set_position(d, vid, v, bx, parent, box, vnames, ctx):
    """position from the page box; inside a group it is relative to the group (as Desktop saves members), and
    parentGroupName (owned, so it goes when the visual leaves the group) names the group's folder."""
    x, y, w, h = bx
    if vid in parent:
        gx, gy = box(parent[vid])[:2]
        x, y = x - gx, y - gy
        d["parentGroupName"] = vnames[parent[vid]]
        ctx.owned_new.setdefault(vid, []).append(["top", "parentGroupName", None, None])
    idx = int(vid.rsplit("V", 1)[1])
    tab = v.get("tabOrder", idx * 100)      # default: visual number x 100 (number IDs in reading order, CLAUDE.md)
    if isinstance(tab, bool) or not isinstance(tab, int) or tab < 0:
        raise BuildError(f"{vid}: tabOrder {tab!r} must be a whole number (the default is the visual number x 100)")
    d.setdefault("position", {}).update({"x": round(x), "y": round(y), "z": v.get("z", 1) * 1000 + idx,
                                         "height": round(h), "width": round(w), "tabOrder": tab})
    if v.get("hidden") is not None:
        if v["hidden"]:
            d["isHidden"] = True
        else:
            d.pop("isHidden", None)


def pages_of(layout, vid):
    return next((v["page"] for v in layout.get("visuals", []) if v["id"] == vid), None)
