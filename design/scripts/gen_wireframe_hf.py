"""High-fidelity wireframe (the kit default): design/wireframes/wireframe.html from layout.json, tokens and the theme.

    python design/scripts/gen_wireframe_hf.py                          numbers from design/wireframes/wireframe-data.json
    python design/scripts/gen_wireframe_hf.py --data none              no numbers: sample shapes and a red "No data –
                                                                       placeholder values" banner (/plan: only for a
                                                                       live connection or PHI)
    python design/scripts/gen_wireframe_hf.py --layout L --tokens T --theme TH --out OUT

Generic for any layout and design. Every visual is drawn from:
- layout.json: page, position, size, z, hidden, groups, bindings (labels), text, style, container, props (any
  "object.property@selector", as pbik build reads them), referenceLabels, navigator, selection, slicerMode;
- tokens.json: colours, fonts, radius, shadow (and the names layout.json uses);
- the theme (design/themes/*.json): data colours and the container defaults of `visualStyles` ("*" and per type),
  which a visual's own container settings override, as in Power BI.
One renderer per visual type (cards, line / area, bar / column (clustered, stacked, 100%), combo, donut / pie, gauge,
table, matrix, slicers (list, dropdown), button slicer, page / bookmark navigator, button, text box, shape, image,
group); any other type is a styled placeholder naming its type. A visual with a `pattern` (docs/patterns/) is drawn by
that pattern's renderer instead. A Deneb visual (`type: "deneb"`) draws its Vega-Lite spec (`deneb.spec`, inline or a
file) over its own aggregates, or sample records. layout.json `vega` (or --vega) chooses: "cdn" (default) draws with
Vega-Lite itself (pinned scripts from cdn.jsdelivr.net, loaded when the page opens; docs/it-security.md) and falls back
to a built-in subset renderer when they don't load; "offline" writes a page that loads nothing and uses the subset
renderer (at work: docs/it-security.md).
docs/patterns/gallery.html shows every pattern (gallery-layout.json).
Numbers come from each visual's own bindings through wireframe_data.py (aggregates only, groups under 5 hidden; the
save fails if anything could identify a person). Without a data file the visuals show sample shapes and no numbers.
Image visuals, page-background visuals (wallpapers), a page's `background.image` and a container's
`background.image` are drawn from their files (`resource` / `image`, or the registered ItemName found in design/images,
design/assets or the report's RegisteredResources), embedded once each; a missing file is a placeholder naming it.
Cards draw no value when `value.show` is off (image cards) and use `value.labelPrecision` for decimals.
props: a value on Desktop's `{"id": "default"}` selector is the visual-wide value, as with no selector; colours saved
as theme colours (ThemeDataColor ColorId / Percent: 0 background, 1 foreground, 2 onwards dataColors) resolve to the
theme's colours. HTML Content (any `htmlContent<GUID>` type, tagged "HTML Content"): with data, the measure's HTML in a
sandboxed frame (no scripts, no network: a CSP that loads nothing but data: images); without, a labelled box.
Drawn as Desktop draws them (the Rep 10 limits W1-W9, test_wireframe.py DesktopMatchTests): a matrix with a field on
Columns as a grid with its cell colours, line charts over negative values (ranks) with their label measures at the
ends, image cards and table images from the SVG their measure returned (wireframe_data.py), new cards with their
alignment, fonts and several fields, chart totals, label measures, axis ranges and round ticks, the combo line on its
secondary axis, and button slicer outlines.
URL hash: `#page=2&labels=off&shot` opens page 2 without labels, at 1:1 with no toolbar (fidelity_check.py).
Keys: B ID badges, T tags (the Power BI visual: "Line chart", "Matrix", "Card (new)", "Button slicer", "SVG in Table")
and the other wireframe notes, 1-9 or the tabs switch pages. Every visual element carries data-id="<ID>" (audit_ids.py).
The box wireframe (gen_wireframe.py) is the fallback when this one can't be drawn.
"""
import argparse, base64, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

TAGS = {"cardVisual": "Card (new)", "card": "Card", "multiRowCard": "Multi-row card", "kpi": "KPI",
        "lineChart": "Line chart", "areaChart": "Area chart", "stackedAreaChart": "Stacked area chart",
        "barChart": "Stacked bar chart", "clusteredBarChart": "Clustered bar chart",
        "hundredPercentStackedBarChart": "100% stacked bar chart", "columnChart": "Stacked column chart",
        "clusteredColumnChart": "Clustered column chart", "hundredPercentStackedColumnChart": "100% stacked column chart",
        "lineStackedColumnComboChart": "Line and stacked column chart",
        "lineClusteredColumnComboChart": "Line and clustered column chart", "donutChart": "Donut chart",
        "pieChart": "Pie chart", "gauge": "Gauge", "tableEx": "Table", "pivotTable": "Matrix", "slicer": "Slicer",
        "advancedSlicerVisual": "Button slicer", "listSlicer": "List slicer", "textSlicer": "Text slicer",
        "pageNavigator": "Page navigator", "bookmarkNavigator": "Bookmark navigator", "actionButton": "Button",
        "textbox": "Text box", "shape": "Shape", "basicShape": "Shape", "image": "Image", "group": "Group",
        "scatterChart": "Scatter chart", "waterfallChart": "Waterfall chart", "funnel": "Funnel",
        "treemap": "Treemap", "map": "Map", "filledMap": "Filled map", "ribbonChart": "Ribbon chart",
        "deneb": "Deneb"}
PATTERNS = {"range-band", "dumbbell", "small-multiples-expected", "brushed-range", "partial-period", "freshness-line",
            "exception-list", "direct-labels"}                       # docs/patterns/; one renderer each in JS (P)
VEGA_MODES = {"cdn": "cdn", "auto": "cdn", "offline": "offline", "subset": "offline"}   # auto, subset: older names
VEGA_CDN = ["https://cdn.jsdelivr.net/npm/vega@5.30.0/build/vega.min.js",
            "https://cdn.jsdelivr.net/npm/vega-lite@5.21.0/build/vega-lite.min.js",
            "https://cdn.jsdelivr.net/npm/vega-embed@6.26.0/build/vega-embed.min.js"]
SLICER_MODES = {"list": "list", "basic": "list", "dropdown": "dropdown", "between": "between", "before": "between",
                "after": "between"}
HTML_CONTENT_RE = re.compile(r"htmlContent[0-9A-Fa-f]{32}")       # the HTML Content visual, any version GUID
METHOD_TAG = {"svg-measure": "SVG in {}", "svg": "SVG in {}", "html-measure": "HTML Content in {}",
              "html": "HTML Content in {}", "custom-visual": "Custom visual", "deneb": "Deneb"}


def load(f):
    return json.loads(pathlib.Path(f).read_text(encoding="utf-8"))


class Resolver:
    """Token, theme and props lookups for one layout."""

    def __init__(self, tokens, theme):
        self.T, self.theme = tokens, theme or {}
        self.C = tokens.get("colors", {})
        self.data_colors = self.theme.get("dataColors") or [self.C.get(n, n) for n in tokens.get("chart", {}).get("series", [])] \
            or ["#118DFF", "#12239E", "#E66C37", "#6B007B", "#E044A7"]

    def colour(self, v, default=None):
        if v is None:
            return default
        if isinstance(v, dict):
            if "theme" in v:
                return self.theme_colour(v["theme"], v.get("percent", 0))
            if "color" in v:
                return self.colour(v["color"], default)
            if "fx" in v or "expr" in v:
                return default                           # from a measure: not known on disk
            if "raw" in v:
                th = plain(v)
                if isinstance(th, dict) and "theme" in th:
                    return self.colour(th, default)
                m = re.search(r"#[0-9A-Fa-f]{6}", json.dumps(v["raw"]))
                return m.group(0) if m else default
            return default
        if not isinstance(v, str):
            return default
        if v.startswith("#"):
            return v
        m = re.fullmatch(r"theme:(\d+)(?::(-?[\d.]+))?", v)
        if m:
            return self.theme_colour(int(m.group(1)), float(m.group(2) or 0))
        cur = self.T
        for part in (f"colors.{v}" if "." not in v else v).split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if isinstance(cur, str) and cur != v:
            return self.colour(cur, default)
        return default

    def theme_colour(self, idx, pct=0):
        base = (self.theme.get("background", self.C.get("card", "#FFFFFF")) if idx == 0 else
                self.theme.get("foreground", self.C.get("text", "#252423")) if idx == 1 else
                self.data_colors[(idx - 2) % len(self.data_colors)])
        return shade(base, pct)

    def number(self, v, group="fontPt", default=None):
        if isinstance(v, bool):
            return default
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, dict) and "int" in v:
            return v["int"]
        if isinstance(v, str):
            x = self.T.get(group, {}).get(v)
            if isinstance(x, (int, float)):
                return x
            cur = self.T
            for part in v.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
            if isinstance(cur, (int, float)):
                return cur
        return default

    def font(self, v=None, default=400):
        """(family, weight) of a token word or a Power BI font: "Segoe UI Semibold", or the CSS list Desktop saves
        ("'Segoe UI Bold', wf_segoe-ui_bold, helvetica, arial, sans-serif")."""
        fam = self.T.get("font", {}).get("family", "Segoe UI")
        if v is None:
            return fam, default
        if v == "regular":
            return fam, 400
        if v in ("semibold", "bold", "light"):
            return fam, {"semibold": 600, "bold": 700, "light": 300}[v]
        v = str(v).split(",")[0].strip().strip("'\"")
        w = 600 if "Semibold" in v else 700 if "Bold" in v else 300 if "Light" in v else 400
        return re.sub(r"\s+(Semibold|Bold|Light)$", "", v), w

    def theme_style(self, vtype, obj):
        vs = self.theme.get("visualStyles", {})
        out = {}
        for key in ("*", vtype):
            for e in (vs.get(key, {}).get("*", {}).get(obj) or []):
                out.update(e)
        return out


def shade(hexc, pct):
    if not pct:
        return hexc
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    t = 255 if pct > 0 else 0
    p = abs(pct)
    return "#" + "".join(f"{round(c + (t - c) * p):02X}" for c in (r, g, b))


def theme_ref(r):
    """{"theme": n, "percent": p} for a colour Desktop saved as a theme colour
    ({"expr": {"ThemeDataColor": {"ColorId": n, "Percent": p}}}), or None."""
    td = r.get("expr", {}).get("ThemeDataColor") if isinstance(r, dict) and isinstance(r.get("expr"), dict) else None
    if isinstance(td, dict) and isinstance(td.get("ColorId"), (int, float)):
        return {"theme": int(td["ColorId"]), "percent": float(td.get("Percent") or 0)}
    return None


def plain(x):
    """A props value as plain Python: {"raw": <PBIR literal>} -> 'Dropdown' / True / 10.0 / '#hex'; a theme colour
    (ThemeDataColor ColorId / Percent) -> {"theme": n, "percent": p}; {"int": n} -> n."""
    if isinstance(x, dict) and "raw" in x:
        r = x["raw"]
        if isinstance(r, dict) and "solid" in r:
            r = r["solid"].get("color", {})
        if theme_ref(r):
            return theme_ref(r)
        lit = r.get("expr", {}).get("Literal", {}).get("Value") if isinstance(r, dict) else None
        if lit is None:
            return x
        if lit in ("true", "false"):
            return lit == "true"
        if lit.startswith("'") and lit.endswith("'"):
            return lit[1:-1].replace("''", "'")
        m = re.fullmatch(r"(-?[\d.]+)[DLM]?", lit)
        return float(m.group(1)) if m else lit
    if isinstance(x, dict) and set(x) == {"int"}:
        return x["int"]
    return x


DEFAULT_SELS = ("", "default", "none")


def visual_wide(sel):
    """True for the selectors that mean the whole visual: none, 'default', 'none', and Desktop's {"id": "default"}."""
    if sel in DEFAULT_SELS:
        return True
    try:
        d = json.loads(sel)
    except ValueError:
        return False
    return d == {"id": "default"}


def prop(v, key, *sels):
    """A props value for object.property under any of the selectors ('' = none, 'default', '{json}', ...); without
    selectors, the visual-wide value (no selector, 'default', or Desktop's {"id": "default"})."""
    pr = v.get("props") or {}
    for sel in sels or DEFAULT_SELS:
        k = key if sel == "" else f"{key}@{sel}"
        if k in pr:
            return plain(pr[k])
    if not sels or any(s in DEFAULT_SELS for s in sels):
        for k, val in pr.items():
            base, at, sel = k.partition("@")
            if base == key and at and visual_wide(sel):
                return plain(val)
    return None


def pt_px(pt):
    return round(pt * 4 / 3, 1) if isinstance(pt, (int, float)) else None


def theme_val(x):
    if isinstance(x, dict) and "solid" in x:
        return x["solid"].get("color")
    return x


# ---------------------------------------------------------------- the render spec of one visual
def container(R, v):
    """Box style: theme visualStyles defaults, then layout container, then container: props."""
    c = v.get("container")
    t = v["type"]
    box = {"bg": None, "border": None, "bw": 1, "radius": 0, "shadow": False, "pad": [0, 0, 0, 0],
           "title": None, "subtitle": None}
    bg = R.theme_style(t, "background")
    if bg.get("show"):
        box["bg"] = theme_val(bg.get("color")) or R.C.get("card", "#FFFFFF")
    bd = R.theme_style(t, "border")
    if bd.get("show"):
        box["border"] = theme_val(bd.get("color")) or R.C.get("border")
        box["radius"] = bd.get("radius", 0)
    if R.theme_style(t, "dropShadow").get("show"):
        box["shadow"] = True
    pd = R.theme_style(t, "padding")
    if pd:
        box["pad"] = [pd.get(k, 0) for k in ("top", "right", "bottom", "left")]
    ti = R.theme_style(t, "title")
    if c == "off":
        return {**box, "bg": None, "border": None, "shadow": False, "pad": [0, 0, 0, 0]}
    c = c or {}
    if "background" in c:
        b_ = c["background"]
        box["bg"] = None if b_ is False else R.colour(b_.get("color", "card"), "#FFFFFF")
        if b_ and b_.get("transparency"):
            box["bgAlpha"] = 1 - b_["transparency"] / 100
        if b_ and b_.get("image") and getattr(R, "images", None):     # a background image file under the content
            box["bgImage"] = {"src": R.images.key(b_["image"]), "name": b_["image"],
                              "scaling": SCALING.get(str(b_.get("scaling", "Fill")).lower(), "cover")}
    if "border" in c:
        b_ = c["border"]
        if b_ is False:
            box["border"] = None
        else:
            box["border"] = R.colour(b_.get("color", "border"), "#DDDDDD")
            box["bw"] = b_.get("width", 1)
            if "radius" in b_:
                box["radius"] = R.number(b_["radius"], "container", 0)
    if "shadow" in c:
        box["shadow"] = c["shadow"] is not False
    if "padding" in c:
        p = c["padding"]
        p = [p] * 4 if not isinstance(p, list) else p
        box["pad"] = [R.number(x, "container", 0) for x in p]
    for key, src, dsize, dcol, dfont in (("title", "title", "cardTitle", "text", "semibold"),
                                         ("subtitle", "subtitle", "caption", "textMuted", None)):
        tv = c.get(src)
        if tv in (None, False):
            continue
        tv = {"text": tv} if isinstance(tv, str) else tv
        fam, wt = R.font(tv.get("font", dfont))
        box[key] = {"text": tv.get("text") or (f"[{tv['measure'].strip('[]')}]" if tv.get("measure") else ""),
                    "measure": bool(tv.get("measure")), "size": pt_px(R.number(tv.get("size", dsize), default=10)),
                    "color": R.colour(tv.get("color", dcol), "#252423"), "weight": wt, "family": fam,
                    "align": tv.get("align", "left")}
    # container: props (a visual's own settings, as Desktop saved them)
    if prop(v, "container:background.show") is False:
        box["bg"] = None
    if prop(v, "container:border.show") is False:
        box["border"] = None
    if prop(v, "container:dropShadow.show") is False:
        box["shadow"] = False
    if prop(v, "container:title.show") is True and not box["title"]:
        fam, wt = R.font(prop(v, "container:title.fontFamily") or ti.get("fontFamily"))
        box["title"] = {"text": prop(v, "container:title.text") or "", "measure": False,
                        "size": pt_px(R.number(prop(v, "container:title.fontSize"), default=ti.get("fontSize", 10))),
                        "color": R.colour(prop(v, "container:title.fontColor"), theme_val(ti.get("fontColor")) or "#252423"),
                        "weight": wt, "family": fam, "align": prop(v, "container:title.alignment") or "left"}
    return box


def selector_key(sel):
    """The series or member a props selector names: [Measure] / Table[Measure] -> Measure, {"metadata":
    "Table.Measure"} -> Measure, a scopeId comparison -> the member ('CHN'); None for the visual-wide selectors."""
    if sel in ("", "default", "none", "*"):
        return None
    m = re.fullmatch(r"(?:.*)?\[(.+)\]", sel)
    if m and not sel.startswith("{"):
        return m.group(1)
    try:
        d = json.loads(sel)
    except ValueError:
        return sel
    if not isinstance(d, dict):
        return None
    if d.get("id") in ("default", None) and not d.get("metadata") and not d.get("data"):
        return None
    if isinstance(d.get("metadata"), str):
        return d["metadata"].split(".", 1)[-1]
    lit = re.search(r'"Right":\s*\{"Literal":\s*\{"Value":\s*"(.*?)"\}', json.dumps(d))
    if lit:
        x = lit.group(1)
        return x[1:-1].replace("''", "'") if x.startswith("'") else re.sub(r"[DLM]$", "", x)
    return None


def series_props(v, key):
    """{series or member: plain value} for object.property per selector, with each field's displayName as well;
    "" holds the visual-wide value."""
    out = {}
    for k, val in (v.get("props") or {}).items():
        base, _, sel = k.partition("@")
        if base != key:
            continue
        name = selector_key(sel)
        out["" if name is None else name] = plain(val)
    for b in (v.get("bindings") or {}).values():          # displayName -> the same value
        for it in b if isinstance(b, list) else [b]:
            if isinstance(it, dict) and it.get("displayName"):
                name = re.sub(r"^.*\[|\]$", "", it.get("field", ""))
                if name in out:
                    out[it["displayName"]] = out[name]
    return out


def series_colours(R, v):
    out = {k or "*": R.colour(x) for k, x in series_props(v, "dataPoint.fill").items()}
    return {k: c for k, c in out.items() if c}


def chart_spec(R, v):
    """Axis, legend, data label and total settings of a bar, column, line, area or combo chart (props, then the
    theme's visualStyles, then Power BI's defaults)."""
    t = v["type"]

    def get(key, default=None):
        x = prop(v, key)
        if x is None:
            obj, _, pr = key.partition(".")
            x = R.theme_style(t, obj).get(pr)
            x = theme_val(x) if isinstance(x, dict) else x
        return default if x is None else x

    def fnt(key, default=400):
        fam, wt = R.font(get(key), default)
        return {"family": fam, "weight": wt}

    def colours(key, default):
        return {k or "": R.colour(x, default) for k, x in series_props(v, key).items()}

    muted, text = R.C.get("textMuted", "#605E5C"), R.C.get("text", "#252423")
    return {
        "labels": {"show": bool(get("labels.show", False)), "showBy": series_props(v, "labels.show"),
                   "color": R.colour(get("labels.color"), text), "colorBy": colours("labels.color", text),
                   "font": fnt("labels.fontFamily"), "size": pt_px(R.number(get("labels.fontSize"), default=9)),
                   "position": get("labels.labelPosition"), "precision": R.number(get("labels.labelPrecision")),
                   "units": R.number(get("labels.labelDisplayUnits"))},
        "totals": {"show": bool(get("totals.show", False)),
                   "color": R.colour(get("totals.fontColor") or get("labels.color"), R.C.get("textSecondary", text)),
                   "font": fnt("totals.fontFamily", 600)},
        "cat": {"color": R.colour(get("categoryAxis.labelColor"), muted), "font": fnt("categoryAxis.fontFamily"),
                "size": pt_px(R.number(get("categoryAxis.fontSize"), default=9)),
                "type": get("categoryAxis.axisType")},
        "val": {"color": R.colour(get("valueAxis.labelColor"), muted), "units": R.number(get("valueAxis.labelDisplayUnits")),
                "size": pt_px(R.number(get("valueAxis.fontSize"), default=9)),
                "grid": get("valueAxis.gridlineShow", True) is not False,
                "gridColor": R.colour(get("valueAxis.gridlineColor"), R.C.get("border", "#E1DFDD")),
                "start": R.number(get("valueAxis.start")), "end": R.number(get("valueAxis.end")),
                "secStart": R.number(get("valueAxis.secStart")), "secEnd": R.number(get("valueAxis.secEnd")),
                "secShow": get("valueAxis.secShow", True) is not False},
        "legend": {"position": str(get("legend.position", "Top")), "color": R.colour(get("legend.labelColor"), muted)},
        "line": {"width": R.number(get("lineStyles.strokeWidth"), default=3),
                 "widthBy": {k: R.number(x) for k, x in series_props(v, "lineStyles.strokeWidth").items()},
                 "marker": bool(get("lineStyles.showMarker", False))},
    }


def text_runs(R, v):
    paras = v.get("text")
    if paras is None:
        return None
    paras = paras if isinstance(paras, list) else [paras]
    out = []
    for p in paras:
        p = {"runs": [p]} if isinstance(p, str) else ({"runs": p} if isinstance(p, list) else p)
        runs = []
        for r in p.get("runs", []):
            r = {"text": r} if isinstance(r, str) else r
            fam, wt = R.font(r.get("font"))
            runs.append({"text": r.get("text", ""), "size": pt_px(R.number(r.get("size", "body"), default=11)),
                         "color": R.colour(r.get("color", "text"), "#252423"), "weight": wt, "family": fam})
        out.append({"runs": runs, "align": p.get("align", "left")})
    return out


def labels_of(v):
    out = []
    for role, b in (v.get("bindings") or {}).items():
        for it in b if isinstance(b, list) else [b]:
            it = it if isinstance(it, dict) else {"field": it}
            name = it.get("displayName") or re.sub(r"^.*\[|\]\)?$", "", it.get("field", it.get("fieldParameter", "?")))
            out.append({"role": role, "label": name, "field": it.get("field") or it.get("fieldParameter")})
    return out


def spec_for(R, v, layout, member_of):
    t = v["type"]
    s = {"id": v["id"], "name": v.get("name", ""), "type": t, "page": v["page"],
         "x": v.get("x", 0), "y": v.get("y", 0), "w": v.get("w", 0), "h": v.get("h", 0), "z": v.get("z", 1),
         "hidden": bool(v.get("hidden")), "group": member_of.get(v["id"]), "box": container(R, v),
         "fields": labels_of(v), "colors": series_colours(R, v),
         "catAxis": prop(v, "categoryAxis.show") is not False, "valAxis": prop(v, "valueAxis.show") is not False,
         "legend": prop(v, "legend.show") is not False,
         # category label above each bar (docs/lessons/charts.md): a zero spacer series carries the label as its detail
         "aboveLabels": any(k.startswith("labels.enableDetailDataLabel") for k in (v.get("props") or {})),
         "refStyle": [{"color": R.colour(rl.get("color", "text"), R.C.get("text", "#252423")),
                       "dash": rl.get("style", "dashed") != "solid", "width": rl.get("width", 1),
                       "dataLabel": rl.get("dataLabel", True) is not False, "labelText": rl.get("labelText")}
                      for rl in v.get("referenceLines") or []]}
    if t in CHARTS:
        s["chart"] = chart_spec(R, v)
    srt = v.get("sort") or {}
    srt = (srt[0] if srt else {}) if isinstance(srt, list) else srt      # a list of sorts: the first one leads
    if srt.get("field"):
        lab = next((f["label"] for f in s["fields"] if f["field"] == srt["field"]), srt["field"])
        s["sort"] = {"field": lab, "desc": str(srt.get("direction", "Descending")).lower().startswith("desc")}
    method = (v.get("build") or {}).get("method", "native")
    base = TAGS.get(t, t)
    if HTML_CONTENT_RE.fullmatch(t):
        base = "HTML Content"
        s["render"] = "htmlContent"
    if t == "slicer":
        mode = SLICER_MODES.get(str(v.get("slicerMode") or prop(v, "data.mode") or
                                    R.theme_style("slicer", "data").get("mode") or "list").lower(), "list")
        base = {"list": "Slicer (list)", "dropdown": "Slicer (dropdown)", "between": "Slicer (between)"}[mode]
        s["mode"] = mode
    s["tag"] = base if s.get("render") == "htmlContent" else (METHOD_TAG[method].format(base) if method in METHOD_TAG
                                                             else base)
    s["method"] = "html" if s.get("render") == "htmlContent" else method
    s["known"] = t in TAGS or s.get("render") == "htmlContent"
    s["pattern"] = v.get("pattern") if v.get("pattern") in PATTERNS else None
    if t == "deneb":
        s["deneb"] = deneb_spec(v, layout)
    if t in ("textbox",):
        s["text"] = text_runs(R, v) or []
    if t in ("shape", "basicShape"):
        st = v.get("style") or {}
        tr = st.get("transparency", 0)
        s["shape"] = {"fill": R.colour(st.get("fill", prop(v, "fill.fillColor")), R.C.get("card", "#FFFFFF")),
                      "alpha": 1 - (R.number(tr, "glass", 0) if isinstance(tr, str) else tr) / 100,
                      "outline": R.colour(st.get("outline")), "radius": R.number(st.get("radius", 0), "container", 0)}
    if t == "actionButton":
        fam, wt = R.font(prop(v, "text.fontFamily"))
        s["button"] = {"text": prop(v, "text.text") if prop(v, "text.show") is not False else "",
                       "color": R.colour(prop(v, "text.fontColor"), R.C.get("text", "#252423")),
                       "size": pt_px(R.number(prop(v, "text.fontSize"), default=11)), "family": fam, "weight": wt,
                       "align": prop(v, "text.horizontalAlignment") or "center",
                       "fill": R.colour(prop(v, "fill.fillColor")) if prop(v, "fill.show") is not False else None,
                       "fillAlpha": 1 - (R.number(prop(v, "fill.transparency"), default=0) or 0) / 100,
                       "outline": R.colour(prop(v, "outline.lineColor")) if prop(v, "outline.show") is not False else None,
                       "ow": R.number(prop(v, "outline.weight"), default=1),
                       "radius": R.number(prop(v, "shape.rectangleRoundedCurve") or prop(v, "shape.roundEdge"),
                                          "container", 0),
                       "action": (v.get("action") or {}).get("type")}
    if t in ("pageNavigator", "bookmarkNavigator"):
        nv = v.get("navigator") or {}
        cols, trs = nv.get("colors", {}), nv.get("transparency", {})
        s["nav"] = {"pages": [p.get("displayName", k) for k, p in layout.get("pages", {}).items() if not p.get("hidden")],
                    "fill": R.colour(nv.get("fill", "card"), "#FFFFFF"),
                    "outline": R.colour(nv.get("outline", "border"), "#DDDDDD"),
                    "radius": R.number(nv.get("radius", "control.radius"), "container", 4),
                    "size": pt_px(R.number(nv.get("size", "body"), default=11)),
                    "states": {st: {"color": R.colour(cols.get(st), R.C.get("text", "#252423")),
                                    "alpha": 1 - (trs.get(st, 0 if st == "selected" else 100)) / 100}
                               for st in ("default", "hover", "selected")},
                    "current": layout.get("pages", {}).get(v["page"], {}).get("displayName")}
    if t in ("slicer", "advancedSlicerVisual", "listSlicer"):
        sel = v.get("selection") or {}
        vals = sel.get("values") if isinstance(sel.get("values"), list) else ([sel["value"]] if "value" in sel else [])
        sel_id = '{"id": "selection:selected"}'
        hdr = prop(v, "header.text") or prop(v, "container:title.text") or \
            (s["fields"][0]["label"] if s["fields"] else "")
        vfam, vwt = R.font(prop(v, "value.fontFamily") or prop(v, "items.fontFamily"))
        s["slicer"] = {"selected": [str(x) for x in vals], "header": hdr,
                       "headerShow": prop(v, "header.show") is not False and (t == "slicer" or prop(v, "container:title.show") is True),
                       "rows": R.number(prop(v, "layout.rowCount"), default=None),
                       "cols": R.number(prop(v, "layout.columnCount"), default=None),
                       "single": bool(prop(v, "selection.singleSelect")),
                       "fill": R.colour(prop(v, "fillCustom.fillColor"), R.C.get("card", "#FFFFFF")),
                       "selFill": R.colour(prop(v, "fillCustom.fillColor", sel_id), R.C.get("primary", "#118DFF")),
                       "outline": R.colour(prop(v, "outline.lineColor"), R.C.get("border", "#DDDDDD"))
                       if prop(v, "outline.show") is not False else None,
                       "selOutline": R.colour(prop(v, "outline.lineColor", sel_id))
                       if prop(v, "outline.show", sel_id) is not False and prop(v, "outline.show") is not False else None,
                       "fillAlpha": 1 - (R.number(prop(v, "fillCustom.transparency"), default=0) or 0) / 100,
                       "family": vfam, "weight": vwt,
                       "size": pt_px(R.number(prop(v, "value.fontSize") or prop(v, "items.fontSize"), default=10)),
                       "color": R.colour(prop(v, "value.fontColor") or prop(v, "items.fontColor"), R.C.get("text", "#252423")),
                       "selColor": R.colour(prop(v, "value.fontColor", sel_id), "#FFFFFF"),
                       "radius": R.number(prop(v, "shapeCustomRectangle.rectangleRoundedCurve"), "container", 4),
                       "items": v.get("items")}
    if t == "cardVisual":
        rl = v.get("referenceLabels") or {}
        vs = R.theme_style(t, "value")
        ls = R.theme_style(t, "label")
        vfam, vwt = R.font(prop(v, "value.fontFamily") or vs.get("fontFamily"), 600)
        lfam, lwt = R.font(prop(v, "label.fontFamily") or ls.get("fontFamily"))
        s["card"] = {"valueSize": pt_px(R.number(prop(v, "value.fontSize"), default=R.number("kpi", default=27))),
                     "valueColor": R.colour(prop(v, "value.fontColor"), R.C.get("text", "#252423")),
                     "value": prop(v, "value.show") is not False,           # image cards hide their value
                     "precision": R.number(prop(v, "value.labelPrecision"), default=None),
                     "align": prop(v, "value.horizontalAlignment") or "center",
                     "labelAlign": prop(v, "label.horizontalAlignment") or prop(v, "value.horizontalAlignment") or "center",
                     "valign": prop(v, "layout.alignment") or "middle",
                     "family": vfam, "weight": vwt, "labelFamily": lfam, "labelWeight": lwt,
                     "labelSize": pt_px(R.number(prop(v, "label.fontSize") or ls.get("fontSize"), default=10)),
                     "wrap": bool(prop(v, "value.textWrap")),
                     "units": R.number(prop(v, "value.labelDisplayUnits")),
                     "cols": R.number(prop(v, "layout.columnCount")),
                     "label": prop(v, "label.show") is not False, "labelPos": prop(v, "label.position") or "belowValue",
                     "labelColor": R.colour(prop(v, "label.fontColor"), R.C.get("textMuted", "#605E5C")),
                     "tile": R.colour(prop(v, "fillCustom.fillColor")) if prop(v, "fillCustom.show") is not False else None,
                     "accent": R.colour(prop(v, "accentBar.color")) if prop(v, "accentBar.show") else None,
                     "radius": R.number(prop(v, "shapeCustomRectangle.rectangleRoundedCurve"), "container", 0),
                     "refs": [{"title": l.get("title"), "value": l.get("value"), "detail": l.get("detail")}
                              for l in rl.get("labels", [])],
                     "refSize": pt_px(R.number(rl.get("valueSize", "caption"), default=10)),
                     "refColor": R.colour(rl.get("valueColor", "textMuted"), "#605E5C"),
                     "image": bool(any(c.get("type") == "image" for c in v.get("cf", []))),
                     # padding: each margin the layout sets (default: the card's built-in 8 / 16 px)
                     "pad": [R.number(prop(v, f"padding.{k}Margin"), default=dflt) or 0
                             for k, dflt in (("top", 8), ("right", 16), ("bottom", 8), ("left", 16))]}
    if t == "gauge":
        s["gauge"] = {"fill": R.colour(prop(v, "dataPoint.fill"), R.data_colors[0]),
                      "target": R.colour(prop(v, "dataPoint.target"), R.C.get("text", "#252423"))}
    if t == "group":
        s["members"] = v.get("members", [])
    if t == "image" and getattr(R, "images", None):
        s["img"] = image_of(R.images, v)
    if t in ("tableEx", "pivotTable"):
        s["widths"] = v.get("columnWidths") if isinstance(v.get("columnWidths"), dict) else None
        s["grid"] = grid_spec(R, v)
    return s


CHARTS = {"lineChart", "areaChart", "stackedAreaChart", "barChart", "clusteredBarChart", "hundredPercentStackedBarChart",
          "columnChart", "clusteredColumnChart", "hundredPercentStackedColumnChart", "ribbonChart",
          "lineStackedColumnComboChart", "lineClusteredColumnComboChart"}


def grid_spec(R, v):
    """Fonts, colours, gaps and padding of a table or matrix (props, then the theme)."""
    t = v["type"]

    def get(key, default=None):
        x = prop(v, key)
        if x is None:
            obj, _, pr = key.partition(".")
            x = theme_val(R.theme_style(t, obj).get(pr))
        return default if x is None else x

    def part(obj, color, weight=400):
        fam, wt = R.font(get(f"{obj}.fontFamily"), weight)
        return {"color": R.colour(get(f"{obj}.fontColor"), color), "bg": R.colour(get(f"{obj}.backColor")),
                "family": fam, "weight": wt, "size": pt_px(R.number(get(f"{obj}.fontSize"), default=10)),
                "align": str(get(f"{obj}.alignment") or "").lower() or None}

    text, muted = R.C.get("text", "#252423"), R.C.get("textMuted", "#605E5C")
    return {"values": part("values", text), "colHead": part("columnHeaders", muted, 600),
            "rowHead": part("rowHeaders", text),
            "h": R.number(get("grid.gridHorizontalWeight"), default=1) if get("grid.gridHorizontal", True) is not False else 0,
            "hColor": R.colour(get("grid.gridHorizontalColor"), R.C.get("neutralTint", "#F3F2F1")),
            "v": R.number(get("grid.gridVerticalWeight"), default=1) if get("grid.gridVertical", False) else 0,
            "vColor": R.colour(get("grid.gridVerticalColor"), R.C.get("neutralTint", "#F3F2F1")),
            "rowPadding": R.number(get("grid.rowPadding"), default=3)}


def deneb_spec(v, layout):
    """The Vega-Lite spec of a Deneb visual: layout `deneb.spec` inline, or a JSON file path from the project root."""
    d = v.get("deneb") or {}
    spec = d.get("spec")
    if isinstance(spec, str):
        f = pathlib.Path(layout.get("_root", ROOT)) / spec
        spec = load(f) if f.exists() else {"_error": f"spec file not found: {spec}"}
    return {"spec": spec or {"_error": "no deneb.spec"}, "provider": d.get("provider", "vegaLite")}


SLICERS = {"slicer", "advancedSlicerVisual", "listSlicer", "textSlicer"}


def missing_alt_text(layout):
    """IDs of data visuals (bindings, not a slicer) and images without container.altText (CLAUDE.md Accessibility;
    the same rule pbik validate warns on)."""
    out = []
    for v in layout.get("visuals", []):
        data = bool(v.get("bindings")) and v["type"] not in SLICERS
        if not (data or v["type"] == "image"):
            continue
        c = v.get("container")
        alt = c.get("altText") if isinstance(c, dict) else None
        if not (isinstance(alt, str) and alt.strip()):
            out.append(v["id"])
    return out


MISSING_IMAGES = []                               # image files the last build_html could not find
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".svg": "image/svg+xml", ".webp": "image/webp"}
SCALING = {"fit": "100% 100%", "fill": "cover", "normal": "auto", "tile": "auto"}   # Power BI image scaling -> CSS


class Images:
    """Static image files drawn in the wireframe (image visuals, page and container background images), embedded once
    each as a data URI. A file is the layout's `resource` / `image` path (from the project root), else the registered
    image's ItemName looked up in design/images, design/assets and the report's RegisteredResources, else a file of
    the same stem there (hero-p1.svg for hero-p1.png)."""

    def __init__(self, root):
        self.root, self.uris, self.missing = pathlib.Path(root), {}, []

    def find(self, path=None, item=None):
        dirs = [self.root / "design" / "images", self.root / "design" / "assets"] + \
            sorted(self.root.glob("*.Report/StaticResources/RegisteredResources"))
        if path and (self.root / path).is_file():
            return self.root / path
        for name in [x for x in (item, pathlib.Path(path).name if path else None) if x]:
            for d in dirs:
                hit = next((f for f in sorted(d.rglob(name)) if f.is_file()), None) if d.is_dir() else None
                if hit:
                    return hit
            stem = pathlib.Path(name).stem
            for d in dirs:
                hit = next((f for f in sorted(d.rglob(stem + ".*")) if f.suffix.lower() in IMAGE_TYPES), None) \
                    if d.is_dir() else None
                if hit:
                    return hit
        return None

    def key(self, path=None, item=None):
        """The key of the embedded file in `uris`, or None (the name is listed in `missing`)."""
        f = self.find(path, item)
        if f is None or f.suffix.lower() not in IMAGE_TYPES:
            if path or item:
                self.missing.append(str(path or item))
            return None
        k = f.relative_to(self.root).as_posix() if f.is_relative_to(self.root) else f.name
        if k not in self.uris:
            self.uris[k] = f"data:{IMAGE_TYPES[f.suffix.lower()]};base64," + base64.b64encode(f.read_bytes()).decode()
        return k


def registered_item(x):
    """The ItemName of a ResourcePackageItem in a props value ({"raw": {"expr": {"ResourcePackageItem": ...}}})."""
    m = re.search(r'"ItemName":\s*"([^"]+)"', json.dumps(x)) if x is not None else None
    return m.group(1) if m else None


def image_of(imgs, v):
    """{src, scaling} for an image visual or a page-background visual, or None."""
    pr = v.get("props") or {}
    item = registered_item(pr.get("general.imageUrl") or pr.get("image.imageUrl"))
    path = v.get("resource") or (v.get("image") if isinstance(v.get("image"), str) else None)
    if not (path or item):
        return None
    sc = str(plain(pr.get("imageScaling.imageScalingType")) or v.get("scaling") or "Fit").lower()
    return {"src": imgs.key(path, item), "name": path or item, "scaling": SCALING.get(sc, "100% 100%")}


def page_bg(R, p):
    bg = p.get("background")
    if isinstance(bg, dict) and "theme" not in bg:
        return R.colour(bg.get("color"), "#FFFFFF")
    return R.colour(bg, R.theme.get("background", "#FFFFFF"))


def page_images(R, layout, key, p, cw, ch):
    """Background images of one page: the page's `background.image`, and its page-background visuals (wallpapers,
    drawn at their own box, else the whole page)."""
    out = []
    bg = p.get("background")
    if isinstance(bg, dict) and bg.get("image"):
        out.append({"src": R.images.key(bg["image"]), "name": bg["image"], "x": 0, "y": 0, "w": cw, "h": ch,
                    "scaling": SCALING.get(str(bg.get("scaling", "Fit")).lower(), "100% 100%")})
    for v in layout.get("visuals", []):
        if v.get("page") == key and (v.get("build") or {}).get("method") == "page-background":
            im = image_of(R.images, v)
            if im:
                out.append({**im, "x": v.get("x", 0), "y": v.get("y", 0), "w": v.get("w") or cw, "h": v.get("h") or ch})
    return out


def build_html(layout, tokens, theme, data, title="Wireframe", vega=None):
    vega = VEGA_MODES.get(str(vega or layout.get("vega") or "cdn").lower())
    if not vega:
        raise SystemExit(f"vega: {layout.get('vega')!r} is not \"cdn\" or \"offline\"")
    R = Resolver(tokens, theme)
    R.images = Images(layout.get("_root", ROOT))
    member_of = {m: g["id"] for g in layout.get("visuals", []) if g["type"] == "group" for m in g.get("members", [])}
    specs = [spec_for(R, v, layout, member_of) for v in layout.get("visuals", [])
             if (v.get("build") or {}).get("method") != "page-background"]
    pages = [{"key": k, "name": p.get("displayName", k), "bg": page_bg(R, p),
              "w": p.get("width", tokens.get("canvas", {}).get("width", 1920)),
              "h": p.get("height", tokens.get("canvas", {}).get("height", 1080))}
             for k, p in layout.get("pages", {}).items()]
    for pg in pages:
        pg["walls"] = page_images(R, layout, pg["key"], layout["pages"][pg["key"]], pg["w"], pg["h"])
    by_group = {}
    for s in specs:
        by_group.setdefault(s["group"], []).append(s)

    def el(s):
        inner = "".join(el(m) for m in by_group.get(s["id"], [])) if s["type"] == "group" else ""
        cls = "grp" if s["type"] == "group" else "v"
        return f'<div class="{cls}" data-id="{s["id"]}"{" hidden" if s["hidden"] else ""}>{inner}</div>'

    static = "".join(f'<div class="page" data-page="{html.escape(p["key"])}">' +
                     "".join(el(s) for s in specs if s["page"] == p["key"] and not s["group"]) + "</div>" for p in pages)
    fam = tokens.get("font", {}).get("family", "Segoe UI")
    tags = tokens.get("tags", {})
    tag_native = {k: R.colour(x) for k, x in (tags.get("native") or {"text": "#334", "fill": "#EEF"}).items()}
    tag_svg = {k: R.colour(x) for k, x in (tags.get("svg") or {"text": "#055", "fill": "#E7F3F5"}).items()}
    tag_html = {k: R.colour(x) for k, x in (tags.get("html") or {"text": "#529", "fill": "#F2ECF8"}).items()}
    accent = R.colour("primary", "#118DFF")
    js = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")   # noqa: E731
    have = data is not None
    note = ("Numbers: aggregates from each visual's own bindings (wireframe_data.py), groups under "
            f"{(layout.get('privacy') or {}).get('minGroup', 5)} hidden. " + " | ".join(data.get("privacy", []))
            if have else "No data file: sample shapes, no numbers.")
    queries = "\n".join(f"[{k}] {q}" for k, q in (data or {}).get("queries", {}).items()).replace("--", "- -")
    MISSING_IMAGES[:] = R.images.missing
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<!--
High-fidelity wireframe, generated by design/scripts/gen_wireframe_hf.py from layout.json, tokens.json and the theme.
Do not edit by hand. {html.escape(note)}
{queries}
-->
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: #2b3138; font-family: '{fam}', 'Segoe UI', system-ui, sans-serif; }}
#bar {{ position: sticky; top: 0; z-index: 50; display: flex; gap: 8px; align-items: center; padding: 8px 16px; background: #1d2228; color: #cfd6de; font-size: 13px; flex-wrap: wrap; }}
#bar button {{ background: #39414a; color: #e6ebf0; border: 0; border-radius: 6px; padding: 6px 12px; cursor: pointer; font: inherit; }}
#bar button.on {{ background: {accent}; color: #fff; }}
#bar .hint {{ margin-left: auto; opacity: .8; }}
#stage {{ padding: 16px; }}
.page {{ position: relative; transform-origin: 0 0; overflow: hidden; display: none; }}
.page.on {{ display: block; }}
.grp {{ position: absolute; inset: 0; pointer-events: none; }}
.grp[hidden], .v[hidden] {{ display: none !important; }}
.grp > .v {{ pointer-events: auto; }}
.v {{ position: absolute; overflow: hidden; display: flex; flex-direction: column; }}
.v .ttl {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: none; }}
.v .body {{ flex: 1; min-height: 0; position: relative; }}
.badge {{ position: absolute; top: 2px; left: 2px; z-index: 40; background: #111; color: #fff; font: 600 11px/1 Consolas, monospace; padding: 3px 5px; border-radius: 4px; }}
.tag {{ position: absolute; top: 2px; right: 2px; z-index: 40; white-space: nowrap; font: 600 10px/1 '{fam}'; padding: 3px 7px; border-radius: 10px; color: {tag_native.get('text')}; background: {tag_native.get('fill')}; }}
.tag.svg {{ color: {tag_svg.get('text')}; background: {tag_svg.get('fill')}; }}
.tag.html {{ color: {tag_html.get('text')}; background: {tag_html.get('fill')}; }}
.tag.unknown {{ color: #8a5b00; background: #fbf0d6; }}
.tag.deneb {{ color: #fff; background: #5b4a9e; }}
.ptn {{ position: absolute; bottom: 2px; left: 2px; z-index: 40; font: 600 10px/1 '{fam}'; padding: 3px 7px; border-radius: 10px; color: #3b4a5a; background: #e3e8ef; }}
body.notag .ptn {{ display: none; }}
.vlnote {{ position: absolute; left: 4px; bottom: 3px; font-size: 10px; color: #8a5b00; }}
body.nobadge .badge, body.notag .tag, body.notag .nodata, body.notag .hiddenrows, body.notag .vlnote {{ display: none; }}
body.shot #bar, body.shot #nodata-banner {{ display: none; }}
#nodata-banner {{ position: sticky; top: 0; z-index: 49; background: #C62828; color: #fff; font-weight: 600; font-size: 14px; padding: 8px 16px; text-align: center; }}
body.shot #stage {{ padding: 0; }}
.nodata {{ position: absolute; right: 4px; bottom: 3px; font-size: 10px; color: #8a96a3; }}
.hiddenrows {{ position: absolute; right: 4px; bottom: 3px; z-index: 40; font-size: 10px; color: #6b7682; background: rgba(255,255,255,.85); padding: 1px 4px; border-radius: 4px; }}
svg {{ display: block; overflow: visible; }}
svg text {{ font-family: '{fam}', sans-serif; }}
table.grid {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
table.grid th, table.grid td {{ padding: 4px 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: right; }}
table.grid th:first-child, table.grid td:first-child, table.grid .l {{ text-align: left; }}
.placeholder {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; text-align: center; border: 1px dashed #b0b8c2; background: repeating-linear-gradient(45deg, rgba(0,0,0,.025) 0 8px, transparent 8px 16px); color: #6b7682; font-size: 13px; }}
</style></head>
<body>
<div id="bar"><span id="tabs"></span><button id="labels" class="on" type="button" aria-pressed="true" title="Show or hide every visual ID badge, visual-type tag and wireframe note">Labels</button><span class="hint">B ID badges · T visual tags · 1–9 pages · {html.escape("aggregates only, groups under 5 hidden" if have else "no data: sample shapes")}</span></div>
{"" if have else '<div id="nodata-banner" role="alert">No data – placeholder values</div>'}
<div id="stage">{static}</div>
{"".join(f'<script src="{u}"></script>' for u in VEGA_CDN) if vega == "cdn" else ""}
<script type="application/json" id="spec">{js({"pages": pages, "visuals": specs, "images": R.images.uris, "dataColors": R.data_colors, "vega": vega, "tokens": {"colors": R.C, "font": tokens.get("font", {})}})}</script>
<script type="application/json" id="data">{js((data or {}).get("visuals", {}))}</script>
<script>
{JS}
</script>
</body></html>
"""


JS = r"""
const S = JSON.parse(document.getElementById('spec').textContent);
const D = JSON.parse(document.getElementById('data').textContent);
const HAVE = Object.keys(D).length > 0;
const C = S.tokens.colors, FONT = (S.tokens.font || {}).family || 'Segoe UI';
const PX = pt => (pt || 0);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const txt = (C.text || '#252423'), muted = (C.textMuted || '#605E5C'), grid = (C.border || '#E1DFDD');

// ---- number format from a Power BI format string (the parts the kit uses)
function fmt(v, f) {
  if (v == null || v === '') return '–';
  if (typeof v !== 'number') return String(v);
  f = (f || '#,0').replace(/\\(.)/g, '$1');
  const parts = f.split(';'); let p = parts[0];
  if (v < 0 && parts[1] !== undefined) { p = parts[1]; v = -v; } else if (v === 0 && parts[2] !== undefined) p = parts[2];
  if (!/[#0]/.test(p)) return p.replace(/"/g, '');
  const lit = p.match(/"([^"]*)"/g) || []; let pre = '', post = '';
  const core = p.replace(/"[^"]*"/g, m => { return ''; });
  const m = core.match(/^([^#0,.%]*)([#0,.]+)([^#0,.]*)$/);
  let sign = '', num = core;
  if (m) { pre = m[1]; num = m[2]; post = m[3]; }
  const q = p.indexOf('"') >= 0 ? p.split('"') : null;
  if (q) { pre = q[0].replace(/[#0,.%]+.*$/, '') + (q[1] && p.trim().startsWith('"') ? q[1] : ''); post = (p.trim().endsWith('"') ? q[q.length - 2] : '') }
  let scale = 1; const trail = (num.match(/,+$/) || [''])[0].length; if (trail) scale = Math.pow(1000, trail);
  if (/%/.test(core)) { v = v * 100; post = post.includes('%') ? post : '%' + post; }
  const dec = (num.split('.')[1] || '').replace(/,/g, '').length;
  const s = Math.abs(v / scale).toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec,
                                                     useGrouping: /,/.test(num.replace(/,+$/, ''))});
  return (v < 0 ? '−' : '') + pre.replace(/[+]/, v > 0 ? '+' : '') + s + post.replace(/%+/, '%');
}

// a visual's decimal places (value.labelPrecision) replace the format string's: '0.0%' at 0 -> '0%'
function precision(f, p) {
  if (p == null) return f;
  const dec = p > 0 ? '.' + '0'.repeat(p) : '';      // every section, so a format's negative section stays
  return (f || '#,0').split(';').map(x => /[0#]\.[0#]+/.test(x) ? x.replace(/([0#])\.[0#]+/, '$1' + dec) :
    /[0#]/.test(x) ? x.replace(/([0#])(?![\s\S]*[0#])/, '$1' + dec) : x).join(';');
}

// display units (labelDisplayUnits): 1000 K, 1e6 M, 1e9 bn, 1e12 T; none (1) and auto (0) show the full number
function unitFmt(v, f, u, p) {
  const k = {1000: 'K', 1000000: 'M', 1000000000: 'bn', 1000000000000: 'T'}[u];
  if (!k || typeof v !== 'number' || /%/.test((f || '').split(';')[0])) return fmt(v, precision(f, p));
  const x = v / u; return fmt(x, precision((f || '#,0').split(';')[0].replace(/,+$/, ''), p == null ? (Math.abs(x) < 10 && x % 1 ? 1 : 0) : p)) + k;
}

// round axis ticks (1, 2, 2.5, 5 x 10^n) covering lo..hi; a fixed start or end (valueAxis.start / end) is kept as is
// the step is the 1-2-5 value nearest range / n, as Desktop picks it (85 -> 20, 32K -> 10K)
function ticks(lo, hi, n, fixLo, fixHi) {
  if (!(hi > lo)) hi = lo + 1;
  const m = (hi - lo) / (n || 4), e = Math.pow(10, Math.floor(Math.log10(m)));
  const step = [1, 2, 5, 10].map(k => k * e).reduce((a, c) => Math.abs(Math.log(c / m)) < Math.abs(Math.log(a / m)) ? c : a);
  const a = fixLo != null ? fixLo : Math.floor(lo / step + 1e-9) * step, b = fixHi != null ? fixHi : Math.ceil(hi / step - 1e-9) * step;
  const out = []; for (let v = Math.ceil(a / step - 1e-9) * step; v <= b + step * 1e-6; v += step) out.push(+(Math.round(v / step) * step).toPrecision(12));
  return {lo: a, hi: b, ticks: out};
}
// the value axis range: valueAxis start / end (secStart / secEnd), literal in props or a measure (d.axis), else the data
// a fixed end keeps the data's own start (Desktop doesn't widen it to a tick)
function valueRange(min, max, ch, d, sec, zero) {
  const ax = (d && d.axis) || {}, V = (ch || {}).val || {};
  const s0 = sec ? (ax.secStart ?? V.secStart) : (ax.start ?? V.start), e0 = sec ? (ax.secEnd ?? V.secEnd) : (ax.end ?? V.end);
  if (!isFinite(min) || !isFinite(max)) { min = 0; max = 1; }
  const lo = s0 != null ? +s0 : (zero ? Math.min(0, min) : min), hi = e0 != null ? +e0 : (zero ? Math.max(0, max) : max);
  return ticks(lo, hi > lo ? hi : lo + 1, 4, s0 != null ? +s0 : (e0 != null ? lo : null), e0 != null ? +e0 : null);
}
// an axis label: the format's decimals cut to the tick step's (Desktop draws +80, not +80.0)
function tickFmt(v, f, units, step) {
  const dec = step > 0 && step < 1 ? Math.min(6, Math.ceil(-Math.log10(step) - 1e-9)) : 0;
  return unitFmt(v, f, units, /[0#]\.[0#]/.test((f || '').split(';')[0]) && !/%/.test(f || '') ? dec : null);
}

// ---- sample rows when there is no data: deterministic shapes, no numbers
function seed(id) { let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0; return () => ((h = (h * 1103515245 + 12345) >>> 0) / 4294967296); }
function sample(s, n) {
  const r = seed(s.id), groups = s.fields.filter(f => /\[/.test(f.field || '') && !/^\[/.test(f.field || '')).map(f => f.label);
  const vals = s.fields.filter(f => /^\[|\(/.test(f.field || '')).map(f => f.label);
  const cats = Array.from({length: n || 6}, (_, i) => 'Item ' + (i + 1));
  return {groups: groups.length ? groups.slice(0, 1) : ['Category'], values: vals.length ? vals : ['Value'], formats: [],
          cat: 0, leg: null, rows: cats.map(c => [c, ...(vals.length ? vals : [0]).map(() => 20 + r() * 80)]), hidden: 0, sample: true};
}
function dataOf(s, n) { return D[s.id] || sample(s, n); }

// ---- svg helpers
const NS = 'http://www.w3.org/2000/svg';
function svg(w, h) { const e = document.createElementNS(NS, 'svg'); e.setAttribute('width', w); e.setAttribute('height', h); e.setAttribute('viewBox', `0 0 ${w} ${h}`); return e; }
function add(p, tag, a, text) { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); if (text != null) e.textContent = text; p.appendChild(e); return e; }
function nice(m) { if (!(m > 0)) return 1; const e = Math.pow(10, Math.floor(Math.log10(m))); for (const k of [1, 2, 2.5, 5, 10]) if (k * e >= m) return k * e; return 10 * e; }
const color = (s, label, i) => s.colors[label] || s.colors['*'] || S.dataColors[i % S.dataColors.length];
const label = (d, v) => d.sample ? '' : v;

// series: [{name, measure, values per category, rows: the data row of each point}] from rows
function series(d) {
  const nG = d.groups.length, cats = [], idx = {};
  const ci = d.cat ?? 0;
  for (const r of d.rows) { const c = nG ? r[ci] : ''; if (!(c in idx)) { idx[c] = cats.length; cats.push(c); } }
  const out = [];
  if (d.leg != null && d.values.length) {
    const legs = [...new Set(d.rows.map(r => r[d.leg]))];
    for (const l of legs) { const vals = cats.map(() => null), ix = cats.map(() => null);
      d.rows.forEach((r, j) => { if (r[d.leg] === l) { vals[idx[r[ci]]] = r[nG]; ix[idx[r[ci]]] = j; } });
      out.push({name: String(l), measure: d.values[0], values: vals, rows: ix, format: d.formats[0]}); }
  } else {
    d.values.forEach((v, k) => { const vals = cats.map(() => null), ix = cats.map(() => null);
      d.rows.forEach((r, j) => { const i = idx[nG ? r[ci] : '']; vals[i] = r[nG + k]; ix[i] = j; });
      out.push({name: v, measure: v, values: vals, rows: ix, format: d.formats[k]}); });
  }
  return {cats, series: out};
}

// data labels: a label measure's text (d.labels, wireframe_data.py) where there is one, else the value; '' when off
function labelOf(d, x, i) {
  const L = d.labels; if (!L || x.rows[i] == null) return undefined;
  const set = L[x.name] || L[x.measure] || L['*']; return set ? set[x.rows[i]] : undefined;
}
function dataLabel(s, d, x, i, v) {
  const L = (s.chart || {}).labels || {}, by = L.showBy || {};
  const show = by[x.name] ?? by[x.measure] ?? by[''] ?? L.show;
  if (!show || d.sample) return '';
  const m = labelOf(d, x, i); if (m !== undefined) return m == null ? '' : String(m);
  return v == null ? '' : unitFmt(v, x.format, L.units, L.precision);
}
function labelStyle(s, x) { const L = (s.chart || {}).labels || {}, c = L.colorBy || {}, f = L.font || {};
  return {fill: c[x.name] || c[x.measure] || L.color || txt, 'font-size': L.size || 12, 'font-family': f.family || FONT, 'font-weight': f.weight || 400}; }
const tw = (t, px) => String(t ?? '').length * (px || 12) * .55;      // text width estimate

// the legend (legend.position); returns the room it takes
function legend(s, g, names, w, h, colourOf) {
  const L = (s.chart || {}).legend || {}, pos = String(L.position || 'Top'), lc = L.color || muted;
  if (names.length < 2 || s.legend === false) return {top: 0, bottom: 0, left: 0, right: 0};
  const ws = names.map(n => tw(n, 12) + 22), total = ws.reduce((a, b) => a + b, 0);
  if (/^(Right|Left)/.test(pos)) { const lw = Math.min(Math.max(...ws), w * .3), x0 = /^Right/.test(pos) ? w - lw : 0;
    names.forEach((n, k) => { const y = 14 + k * 18; add(g, 'circle', {cx: x0 + 5, cy: y - 4, r: 5, fill: colourOf(n, k)}); add(g, 'text', {x: x0 + 14, y, 'font-size': 12, fill: lc}, n); });
    return {top: 0, bottom: 0, left: /^Left/.test(pos) ? lw + 8 : 0, right: /^Right/.test(pos) ? lw + 8 : 0}; }
  const bottom = /^Bottom/.test(pos); let x = /Center/.test(pos) ? Math.max((w - total) / 2, 0) : 4; const y = bottom ? h - 6 : 12;
  names.forEach((n, k) => { add(g, 'circle', {cx: x + 5, cy: y - 4, r: 5, fill: colourOf(n, k)}); add(g, 'text', {x: x + 14, y, 'font-size': 12, fill: lc}, n); x += ws[k]; });
  return {top: bottom ? 0 : 22, bottom: bottom ? 22 : 0, left: 0, right: 0};
}

// reference lines (layout referenceLines): category-axis lines on numeric categories, value-axis lines; the label
// as the layout says (dataLabel off: none; labelText Name / Value, else both)
function refLines(s, d, g, f) {
  (d.refLines || []).forEach((rl, k) => {
    if (rl.value == null || d.sample) return;
    const st = (s.refStyle || [])[k] || {color: txt, dash: true, dataLabel: true}, v = +rl.value;
    const lab = !st.dataLabel ? '' : st.labelText === 'Name' ? (rl.label || '') : st.labelText === 'Value' ? f.fmt(v) : [rl.label, f.fmt(v)].filter(Boolean).join(' ');
    const ln = {stroke: st.color, 'stroke-width': st.width || 1, 'stroke-dasharray': st.dash ? '4 3' : ''};
    if (rl.axis === 'category' || rl.axis === 'x') {
      const nums = f.cats.map(Number); if (nums.some(isNaN) || !nums.length) return;
      let j = nums.findIndex((c, i) => i === nums.length - 1 || (v >= c && v < nums[i + 1])); if (v < nums[0]) j = 0;
      const step = j < nums.length - 1 ? nums[j + 1] - nums[j] : 1, pos = f.band * (j + .5) + f.band * (v - nums[j]) / (step || 1);
      if (f.horizontal) add(g, 'line', {x1: f.padL, x2: f.padL + f.W, y1: f.padT + pos, y2: f.padT + pos, ...ln});
      else { const x = f.padL + pos; add(g, 'line', {x1: x, x2: x, y1: f.padT, y2: f.padT + f.H, ...ln}); if (lab) add(g, 'text', {x: x + 4, y: f.padT + 10, 'font-size': 11, fill: st.color}, lab); }
    } else {
      const pos = f.sc(v);
      if (f.horizontal) { const x = f.padL + pos; add(g, 'line', {x1: x, x2: x, y1: f.padT, y2: f.padT + f.H, ...ln}); if (lab) add(g, 'text', {x: x - 4, y: f.padT + 10, 'font-size': 11, fill: st.color, 'text-anchor': 'end'}, lab); }
      else { const y = f.padT + f.H - pos; add(g, 'line', {x1: f.padL, x2: f.padL + f.W, y1: y, y2: y, ...ln}); if (lab) add(g, 'text', {x: f.padL + f.W - 4, y: y - 4, 'font-size': 11, fill: st.color, 'text-anchor': 'end'}, lab); }
    }
  });
}

// an ImageUrl value as Power BI reads it: %-decoded unless a raw % is in it (.claude/rules/svg.md), then re-encoded
function svgSrc(uri) {
  const s = String(uri || ''), i = s.indexOf(',');
  if (!/^data:image\/svg\+xml/i.test(s) || i < 0 || /;base64/i.test(s.slice(0, i))) return s;
  let body = s.slice(i + 1);
  if (!/%(?![0-9A-Fa-f]{2})/.test(body)) { try { body = decodeURIComponent(body); } catch (e) { /* keep it raw */ } }
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(body);
}
const isImg = x => typeof x === 'string' && /^data:image\//i.test(x);

// ---- renderers (one per visual type)
const R = {};
R.cardVisual = (s, el, w, h) => {
  const d = dataOf(s, 1), c = s.card, row = d.rows[0] || [], nG = d.groups.length;
  if (c.tile) { el.style.background = c.tile; el.style.borderRadius = c.radius + 'px'; }
  el.style.justifyContent = {top: 'flex-start', bottom: 'flex-end'}[c.valign] || 'center';
  el.style.padding = (c.pad || [8, 16, 8, 16]).map(p => PX(p) + 'px').join(' ');
  if (c.accent) el.style.borderLeft = `4px solid ${c.accent}`;
  const img = (d.images || [])[0];
  if (c.image && isImg(img)) {                      // the SVG the image measure returned (wireframe_data.py)
    el.insertAdjacentHTML('beforeend', `<img alt="" src="${esc(svgSrc(img))}" style="display:block;flex:1;min-height:0;width:100%;object-fit:contain">`);
    return;
  }
  const names = d.values.length ? d.values : s.fields.map(f => f.label), n = Math.max(names.length, 1);
  const cols = Math.max(1, Math.min(c.cols || n, n)), al = c.align === 'left' || c.align === 'right' ? c.align : 'center';
  const lal = c.labelAlign === 'left' || c.labelAlign === 'right' ? c.labelAlign : 'center', shown = [];
  const tiles = names.map((nm, k) => {
    const v = d.sample ? '–' : unitFmt(row[nG + k], d.formats[k], c.units, c.precision); shown.push(v);
    const lab = c.label ? `<div style="font-family:'${c.labelFamily}';font-weight:${c.labelWeight};font-size:${c.labelSize}px;color:${c.labelColor};text-align:${lal};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(nm)}</div>` : '';
    const val = c.value ? `<div style="font-family:'${c.family}';font-weight:${c.weight};font-size:${c.valueSize}px;color:${c.valueColor};line-height:1.15;text-align:${al};${c.wrap ? 'white-space:normal' : 'white-space:nowrap;overflow:hidden;text-overflow:ellipsis'}">${esc(v)}</div>` : '';
    return `<div style="min-width:0">${c.labelPos === 'aboveValue' ? lab + val : val + lab}</div>`; });
  const refs = (c.refs || []).map(r => `<span>${esc((r.title ? r.title + ' ' : '') + '[' + String(r.value).replace(/[\[\]]/g, '') + ']' + (r.detail ? ' · [' + String(r.detail).replace(/[\[\]]/g, '') + ']' : ''))}</span>`).join(' ');
  el.insertAdjacentHTML('beforeend', `<div style="display:grid;grid-template-columns:repeat(${cols},minmax(0,1fr));gap:4px 16px;width:100%">${tiles.join('')}</div>` +
    (refs ? `<div style="font-size:${c.refSize}px;color:${c.refColor};margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;text-align:${al}">${refs}</div>` : '') +
    (c.image ? `<div class="nodata">image from data</div>` : ''));
  el.dataset.main = c.value && !d.sample ? shown.join(' | ') : '';
};
R.card = R.cardVisual;
// HTML Content (any htmlContent<GUID> type): the measure's HTML in a sandboxed frame (no scripts, no network)
const HTML_CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:";
R.htmlContent = (s, el) => {
  const d = D[s.id], nG = d ? d.groups.length : 0;
  const parts = d ? d.rows.map(r => r.slice(nG).filter(x => typeof x === 'string').join('')).filter(Boolean) : [];
  if (!parts.length) {
    el.insertAdjacentHTML('beforeend', `<div class="placeholder"><div><b>HTML Content</b><br>${esc(s.fields.map(f => f.label).join(', '))}<br><small>${d ? 'the measure returned no HTML' : 'no data: the HTML shows here with data'}</small></div></div>`);
    return;
  }
  const f = document.createElement('iframe');
  f.setAttribute('sandbox', '');                    // no scripts, forms, popups or same-origin access
  f.setAttribute('referrerpolicy', 'no-referrer');
  f.title = 'HTML Content ' + s.id;
  f.srcdoc = `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${HTML_CSP}"><style>body{margin:0;font-family:'${FONT}',sans-serif;color:${txt}}</style>` + parts.join('');
  Object.assign(f.style, {border: '0', width: '100%', height: '100%', display: 'block', background: 'transparent'});
  el.appendChild(f);
};
function axisChart(s, el, w, h, horizontal, mode, dIn, secRoom) {
  const d = dIn || dataOf(s, horizontal ? 6 : 8), sr = series(d), cats = sr.cats, ch = s.chart || {};
  const CA = ch.cat || {}, VA = ch.val || {}, TT = ch.totals || {}, LB = ch.labels || {};
  const ss = s.aboveLabels ? sr.series.filter(x => x.values.some(v => v)) : sr.series;   // drop the zero spacer
  const above = s.aboveLabels && horizontal;
  const g = svg(w, h); el.appendChild(g);
  const catAx = s.catAxis !== false, valAx = s.valAxis !== false, cpx = CA.size || 12, vpx = VA.size || 12;
  const lg = legend(s, g, ss.map(x => x.name), w, h, (n, k) => color(s, n, k));
  let max = 0, min = 0; const tot = cats.map(() => 0);
  cats.forEach((_, i) => {
    if (mode === 'stack' || mode === 'pct') { let p = 0, q = 0; ss.forEach(x => { const v = x.values[i] || 0; v >= 0 ? p += v : q += v; }); max = Math.max(max, p); min = Math.min(min, q); tot[i] = p + q; }
    else ss.forEach(x => { max = Math.max(max, x.values[i] || 0); min = Math.min(min, x.values[i] || 0); });
  });
  const rg = mode === 'pct' ? ticks(0, 1, 4, 0, 1) : valueRange(min, max, ch, d, false, true), lo = rg.lo, span = (rg.hi - lo) || 1;
  const step = rg.ticks.length > 1 ? rg.ticks[1] - rg.ticks[0] : 1;
  const vf = v => mode === 'pct' ? fmt(v, '0%') : tickFmt(v, (ss[0] || {}).format, VA.units, step);
  // category labels: all of them, turned 45 degrees when they don't fit side by side, thinned only when too dense
  const cw = Math.max(0, ...cats.map(c => tw(String(c ?? '').slice(0, 10), cpx))), bandE = w * .9 / Math.max(cats.length, 1);
  const rot = !horizontal && catAx && !d.sample && cw > bandE - 4 && bandE >= cpx * .9;
  const inside = /^Inside/.test(LB.position || '');           // no position on a stack: Auto (below)
  const outside = (LB.show && !inside) || (TT.show && mode === 'stack');
  const longest = Math.max(0, ...cats.map(c => tw(c, cpx)));
  const padL = lg.left + (horizontal ? (catAx && !above ? Math.min(w * .32, longest + 10) : 4) : (valAx ? Math.max(...rg.ticks.map(v => tw(vf(v), vpx))) + 8 : 6));
  const padB = lg.bottom + (horizontal ? (valAx ? vpx + 6 : 4) : (catAx ? (rot ? cw * .72 + cpx : cpx + 8) : 4));
  const padT = lg.top + (!horizontal && outside ? 18 : 6), padR = lg.right + (horizontal && outside ? 48 : 8) + (secRoom || 0);
  const W = Math.max(w - padL - padR, 4), H = Math.max(h - padT - padB, 4), n = Math.max(cats.length, 1);
  const sc = v => (Math.min(Math.max(v, lo), rg.hi) - lo) / span * (horizontal ? W : H);
  rg.ticks.forEach(v => { const p = sc(v);
    if (horizontal) { if (VA.grid !== false) add(g, 'line', {x1: padL + p, x2: padL + p, y1: padT, y2: padT + H, stroke: VA.gridColor || grid});
                      if (valAx && !d.sample) add(g, 'text', {x: padL + p, y: h - lg.bottom - 4, 'font-size': vpx, fill: VA.color || muted, 'text-anchor': 'middle'}, vf(v)); }
    else { if (VA.grid !== false) add(g, 'line', {x1: padL, x2: padL + W, y1: padT + H - p, y2: padT + H - p, stroke: VA.gridColor || grid});
           if (valAx && !d.sample) add(g, 'text', {x: padL - 6, y: padT + H - p + 4, 'font-size': vpx, fill: VA.color || muted, 'text-anchor': 'end'}, vf(v)); } });
  const band = (horizontal ? H : W) / n, inner = band * (above ? .42 : .7), bw = (mode === 'cluster') ? inner / Math.max(ss.length, 1) : inner;
  const lpx = LB.size || 12, base = sc(0);
  cats.forEach((c, i) => {
    let ttl = 0; if (mode === 'pct') ss.forEach(x => ttl += Math.abs(x.values[i] || 0));
    const top = ss.reduce((a, x, k) => (x.values[i] || 0) > 0 ? k : a, -1);      // the stack's top segment
    let up = 0, dn = 0, end = base;
    ss.forEach((x, k) => {
      const raw = x.values[i]; let v = raw || 0; if (mode === 'pct') v = ttl ? v / ttl : 0;
      const a = mode === 'cluster' ? 0 : (v >= 0 ? up : dn); if (mode !== 'cluster') { if (v >= 0) up += v; else dn += v; }
      const p0 = sc(a), p1 = sc(a + v), lo_ = Math.min(p0, p1), len = Math.abs(p1 - p0);
      const o = band * i + band * (above ? .48 : .15) + (mode === 'cluster' ? k * bw : 0);
      const r = horizontal ? {x: padL + lo_, y: padT + o, width: len, height: bw} : {x: padL + o, y: padT + H - lo_ - len, width: bw, height: len};
      const pc = (d.colours && d.colours[x.rows[i]]) ? d.colours[x.rows[i]] : color(s, x.name, k);
      add(g, 'rect', {...r, rx: 2, fill: pc, opacity: d.sample ? .35 : 1});
      end = horizontal ? Math.max(end, lo_ + len) : Math.max(end, lo_ + len);
      const t = dataLabel(s, d, x, i, raw); if (!t) return;
      const st = labelStyle(s, x), neg = v < 0;
      const fits = horizontal ? tw(t, lpx) + 6 <= len && lpx <= bw : lpx + 8 <= len && tw(t, lpx) <= bw + 2;
      const auto = mode !== 'cluster' && !LB.position;            // Auto: inside where it fits, else past the top
      if (inside || (auto && (fits || k !== top || mode === 'pct'))) {
        if (!fits) return;
        if (horizontal) add(g, 'text', {...st, x: r.x + r.width / 2, y: r.y + bw / 2 + lpx * .35, 'text-anchor': 'middle'}, t);
        else add(g, 'text', {...st, x: r.x + bw / 2, y: r.y + r.height / 2 + lpx * .35, 'text-anchor': 'middle'}, t);
      } else if (horizontal) add(g, 'text', {...st, x: neg ? r.x - 4 : r.x + r.width + 4, y: r.y + bw / 2 + lpx * .35, 'text-anchor': neg ? 'end' : 'start'}, t);
      else add(g, 'text', {...st, x: r.x + bw / 2, y: neg ? r.y + r.height + lpx + 2 : r.y - 4, 'text-anchor': 'middle'}, t);
    });
    if (TT.show && mode === 'stack' && !d.sample) {                   // totals (totals.show) at the end of the stack
      const tf = TT.font || {}, at = {fill: TT.color || muted, 'font-size': lpx, 'font-family': tf.family || FONT, 'font-weight': tf.weight || 600};
      const t = unitFmt(tot[i], (ss[0] || {}).format, LB.units, LB.precision);
      if (horizontal) add(g, 'text', {...at, x: padL + sc(up) + 6, y: padT + band * i + band * .15 + bw / 2 + lpx * .35}, t);
      else add(g, 'text', {...at, x: padL + band * i + band * .15 + bw / 2, y: padT + H - sc(up) - 6, 'text-anchor': 'middle'}, t);
    }
    const lab = String(c ?? ''); const sh = lab.length > 18 ? lab.slice(0, 17) + '…' : lab;
    const cf = CA.font || {}, ct = {'font-size': cpx, fill: CA.color || muted, 'font-family': cf.family || FONT, 'font-weight': cf.weight || 400};
    if (above && !d.sample) add(g, 'text', {...ct, x: padL, y: padT + band * i + band * .42}, sh);
    if (!catAx) return;
    if (horizontal) add(g, 'text', {...ct, x: padL - 6, y: padT + band * i + band / 2 + cpx * .35, 'text-anchor': 'end'}, label(d, sh));
    else if (rot) { const x = padL + band * i + band / 2, y = padT + H + cpx; add(g, 'text', {...ct, x, y, 'text-anchor': 'end', transform: `rotate(-45 ${x} ${y})`}, label(d, sh.slice(0, 10))); }
    else if (cw <= band - 4 || i % Math.ceil(n / Math.max(1, Math.floor(W / (cw + 8)))) === 0) add(g, 'text', {...ct, x: padL + band * i + band / 2, y: h - lg.bottom - 6, 'text-anchor': 'middle'}, label(d, sh.slice(0, 10)));
  });
  const geo = {g, padL, padT, W, H, band, n, cats, horizontal, sc, fmt: vf};
  refLines(s, d, g, geo);
  return geo;
}
function lineChart(s, el, w, h, area) {
  const d = dataOf(s, 12), {cats, series: ss} = series(d), ch = s.chart || {}, CA = ch.cat || {}, VA = ch.val || {}, LN = ch.line || {};
  const g = svg(w, h); el.appendChild(g);
  const catAx = s.catAxis !== false, valAx = s.valAxis !== false, cpx = CA.size || 12, vpx = VA.size || 12, lpx = ((ch.labels || {}).size) || 12;
  const lg = legend(s, g, ss.map(x => x.name), w, h, (n, k) => color(s, n, k));
  let min = Infinity, max = -Infinity; ss.forEach(x => x.values.forEach(v => { if (v != null) { min = Math.min(min, v); max = Math.max(max, v); } }));
  const rg = valueRange(min, max, ch, d, false, area), lo = rg.lo, span = (rg.hi - lo) || 1;
  const vf = v => tickFmt(v, (ss[0] || {}).format, VA.units, rg.ticks.length > 1 ? rg.ticks[1] - rg.ticks[0] : 1);
  const n = cats.length, first = ss.map(x => x.values.findIndex(v => v != null)), last = ss.map(x => { let i = x.values.length - 1; while (i > 0 && x.values[i] == null) i--; return i; });
  const texts = ss.map((x, k) => x.values.map((v, i) => v == null ? '' : dataLabel(s, d, x, i, v)));
  const room = side => Math.max(0, ...ss.map((x, k) => { const i = side ? last[k] : first[k]; return i >= 0 && texts[k][i] && (side ? i === n - 1 : i === 0) ? tw(texts[k][i], lpx) + 12 : 0; }));
  const padL = lg.left + Math.max(valAx ? Math.max(...rg.ticks.map(v => tw(vf(v), vpx))) + 8 : 6, room(0));
  const padR = lg.right + Math.max(8, room(1)), padT = lg.top + 10 + (texts.some(a => a.some((t, i) => t && i > 0 && i < n - 1)) ? lpx : 0);
  const padB = lg.bottom + (catAx ? cpx + 8 : 4), W = Math.max(w - padL - padR, 4), H = Math.max(h - padT - padB, 4);
  const nums = cats.map(Number), continuous = CA.type !== 'Categorical' && n > 2 && nums.every(x => isFinite(x)) && !d.sample;
  const X = i => continuous ? padL + (nums[n - 1] > nums[0] ? (nums[i] - nums[0]) / (nums[n - 1] - nums[0]) : .5) * W : padL + W * (i + .5) / Math.max(n, 1);
  const Y = v => padT + H - (v - lo) / span * H;
  rg.ticks.forEach(v => { const y = Y(v); if (VA.grid !== false) add(g, 'line', {x1: padL, x2: padL + W, y1: y, y2: y, stroke: VA.gridColor || grid});
    if (valAx && !d.sample) add(g, 'text', {x: padL - 6, y: y + 4, 'font-size': vpx, fill: VA.color || muted, 'text-anchor': 'end'}, vf(v)); });
  const ends = {0: [], 1: []};
  ss.forEach((x, k) => {
    const c = color(s, x.name, k), sw = (LN.widthBy || {})[x.name] ?? (LN.widthBy || {})[x.measure] ?? LN.width ?? 3;
    let seg = [];
    const flush = () => { if (seg.length > 1 || (seg.length && LN.marker)) {
      if (area) add(g, 'polygon', {points: `${seg[0][0]},${Y(Math.max(lo, 0))} ${seg.map(p => p.join(',')).join(' ')} ${seg[seg.length - 1][0]},${Y(Math.max(lo, 0))}`, fill: c, opacity: .2});
      if (sw > 0) add(g, 'polyline', {points: seg.map(p => p.join(',')).join(' '), fill: 'none', stroke: c, 'stroke-width': sw, opacity: d.sample ? .4 : 1}); } seg = []; };
    x.values.forEach((v, i) => { if (v == null) flush(); else seg.push([X(i), Y(v)]); }); flush();
    x.values.forEach((v, i) => { if (v == null) return;
      if (LN.marker || sw === 0 || n === 1) add(g, 'circle', {cx: X(i), cy: Y(v), r: 4, fill: c});
      const t = texts[k][i]; if (!t) return;
      if (i === 0 && n > 1) ends[0].push({x: X(i) - 8, y: Y(v) + lpx * .35, t, x_: x});
      else if (i === n - 1 && n > 1) ends[1].push({x: X(i) + 8, y: Y(v) + lpx * .35, t, x_: x});
      else add(g, 'text', {...labelStyle(s, x), x: X(i), y: Y(v) - 8, 'text-anchor': 'middle'}, t); });
  });
  [0, 1].forEach(side => ends[side].sort((a, b) => a.y - b.y).forEach((e, k, a) => { if (k && e.y - a[k - 1].y < lpx + 1) e.y = a[k - 1].y + lpx + 1;
    add(g, 'text', {...labelStyle(s, e.x_), x: e.x, y: e.y, 'text-anchor': side ? 'start' : 'end'}, e.t); }));
  const cf = CA.font || {}, ct = {'font-size': cpx, fill: CA.color || muted, 'font-family': cf.family || FONT, 'font-weight': cf.weight || 400, 'text-anchor': 'middle'};
  if (catAx) cats.forEach((c, i) => { if (n <= 14 || i % Math.ceil(n / 12) === 0) add(g, 'text', {...ct, x: X(i), y: h - lg.bottom - 6}, label(d, String(c ?? '').slice(0, 10))); });
  refLines(s, d, g, {padL, padT, W, H, band: W / Math.max(n, 1), n, cats, horizontal: false, sc: v => (v - lo) / span * H, fmt: vf});
}
R.lineChart = (s, el, w, h) => lineChart(s, el, w, h, false);
R.areaChart = (s, el, w, h) => lineChart(s, el, w, h, true);
R.stackedAreaChart = R.areaChart;
R.clusteredBarChart = (s, el, w, h) => axisChart(s, el, w, h, true, 'cluster');
R.barChart = (s, el, w, h) => axisChart(s, el, w, h, true, 'stack');
R.hundredPercentStackedBarChart = (s, el, w, h) => axisChart(s, el, w, h, true, 'pct');
R.clusteredColumnChart = (s, el, w, h) => axisChart(s, el, w, h, false, 'cluster');
R.columnChart = (s, el, w, h) => axisChart(s, el, w, h, false, 'stack');
R.hundredPercentStackedColumnChart = (s, el, w, h) => axisChart(s, el, w, h, false, 'pct');
R.ribbonChart = R.columnChart;
// combo: columns on the value axis, lines (Y2) on the secondary axis, its range from secStart / secEnd when set
function combo(s, el, w, h, mode) {
  const d = dataOf(s, 12), nG = d.groups.length, ch = s.chart || {}, VA = ch.val || {};
  const y2 = s.fields.filter(f => f.role === 'Y2').map(f => f.label);
  const keep = d.values.map(v => !y2.includes(v));
  const cols = {...d, values: d.values.filter((_, k) => keep[k]), formats: d.formats.filter((_, k) => keep[k]),
                rows: d.rows.map(r => r.filter((_, k) => k < nG || keep[k - nG]))};
  const {series: all} = series(d), lines = all.filter(x => y2.includes(x.name));
  let min = 0, max = 0; lines.forEach(x => x.values.forEach(v => { if (v != null) { min = Math.min(min, v); max = Math.max(max, v); } }));
  const rg = valueRange(min, max, ch, d, true, true), span = (rg.hi - rg.lo) || 1;
  const vf = v => tickFmt(v, (lines[0] || {}).format, VA.units, rg.ticks.length > 1 ? rg.ticks[1] - rg.ticks[0] : 1), showSec = VA.secShow !== false && s.valAxis !== false && lines.length && !d.sample;
  const f = axisChart(s, el, w, h, false, mode, cols, showSec ? Math.max(...rg.ticks.map(v => tw(vf(v), VA.size || 12))) + 8 : 0);
  if (!lines.length) return;
  const g = f.g, X = i => f.padL + f.band * i + f.band / 2, Y = v => f.padT + f.H - (Math.min(Math.max(v, rg.lo), rg.hi) - rg.lo) / span * f.H;
  if (showSec) rg.ticks.forEach(v => add(g, 'text', {x: f.padL + f.W + 6, y: Y(v) + 4, 'font-size': VA.size || 12, fill: VA.color || muted}, vf(v)));
  const LN = ch.line || {};
  lines.forEach((x, k) => { const c = color(s, x.name, k + cols.values.length), sw = (LN.widthBy || {})[x.name] ?? LN.width ?? 3;
    const pts = x.values.map((v, i) => v == null ? null : [X(i), Y(v)]).filter(Boolean);
    add(g, 'polyline', {points: pts.map(p => p.join(',')).join(' '), fill: 'none', stroke: c, 'stroke-width': sw, opacity: d.sample ? .4 : 1});
    if (LN.marker) pts.forEach(p => add(g, 'circle', {cx: p[0], cy: p[1], r: 3.5, fill: c}));
    x.values.forEach((v, i) => { const t = v == null ? '' : dataLabel(s, d, x, i, v); if (t) add(g, 'text', {...labelStyle(s, x), x: X(i), y: Y(v) - 8, 'text-anchor': i === x.values.length - 1 ? 'end' : 'middle'}, t); }); });
}
R.lineStackedColumnComboChart = (s, el, w, h) => combo(s, el, w, h, 'stack');
R.lineClusteredColumnComboChart = (s, el, w, h) => combo(s, el, w, h, 'cluster');
function pie(s, el, w, h, hole) {
  const d = dataOf(s, 4), {cats, series: ss} = series(d), vals = (ss[0] || {values: []}).values.map(v => Math.max(v || 0, 0));
  const tot = vals.reduce((a, b) => a + b, 0) || 1, g = svg(w, h); el.appendChild(g);
  const r = Math.min(w * .5, h) / 2 - 6, cx = Math.min(w * .3, r + 8), cy = h / 2; let a = -Math.PI / 2;
  vals.forEach((v, i) => { const b = a + v / tot * Math.PI * 2, big = b - a > Math.PI ? 1 : 0;
    add(g, 'path', {d: `M${cx},${cy} L${cx + r * Math.cos(a)},${cy + r * Math.sin(a)} A${r},${r} 0 ${big} 1 ${cx + r * Math.cos(b)},${cy + r * Math.sin(b)} Z`, fill: color(s, String(cats[i]), i), opacity: d.sample ? .4 : 1}); a = b; });
  if (hole) add(g, 'circle', {cx, cy, r: r * .6, fill: el.dataset.bg || '#fff'});
  cats.forEach((c, i) => { const y = 14 + i * 18; if (y > h - 4) return; add(g, 'rect', {x: cx + r + 16, y: y - 9, width: 10, height: 10, rx: 2, fill: color(s, String(c), i)});
    add(g, 'text', {x: cx + r + 32, y, 'font-size': 12, fill: txt}, d.sample ? '' : `${c}  ${Math.round(vals[i] / tot * 100)}%`); });
}
R.donutChart = (s, el, w, h) => pie(s, el, w, h, true);
R.pieChart = (s, el, w, h) => pie(s, el, w, h, false);
R.gauge = (s, el, w, h) => {
  const d = dataOf(s, 1), row = d.rows[0] || [], nG = d.groups.length, v = row[nG], t = row[nG + 1];
  const g = svg(w, h); el.appendChild(g); const r = Math.min(w / 2, h * .85) - 8, cx = w / 2, cy = h - 12;
  const arc = (f, col, sw) => add(g, 'path', {d: `M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r * Math.cos(Math.PI * (1 - f))},${cy - r * Math.sin(Math.PI * (1 - f))}`, fill: 'none', stroke: col, 'stroke-width': sw});
  arc(1, grid, r * .28); const max = nice(Math.max(v || 0, t || 0) * 1.25) || 1; arc(d.sample ? .6 : Math.min((v || 0) / max, 1), s.gauge.fill, r * .28);
  if (t != null) { const f = Math.min(t / max, 1), a = Math.PI * (1 - f); add(g, 'line', {x1: cx + (r - r * .18) * Math.cos(a), y1: cy - (r - r * .18) * Math.sin(a), x2: cx + (r + r * .18) * Math.cos(a), y2: cy - (r + r * .18) * Math.sin(a), stroke: s.gauge.target, 'stroke-width': 2}); }
  add(g, 'text', {x: cx, y: cy - 6, 'font-size': Math.max(14, r * .32), 'font-weight': 600, fill: txt, 'text-anchor': 'middle'}, d.sample ? '–' : fmt(v, d.formats[0]));
};
function cellCss(p) { return p ? `font-family:'${p.family}';font-weight:${p.weight};font-size:${p.size}px;color:${p.color}${p.bg ? ';background:' + p.bg : ''}` : ''; }
function tableGrid(s, el, w, h, matrix) {
  const d = dataOf(s, 8), nG = d.groups.length, head = [...(matrix ? d.groups.slice(0, 1) : d.groups), ...d.values];
  const rows = matrix ? d.rows.map(r => [r[0], ...r.slice(nG)]) : d.rows, G = s.grid || {}, pad = G.rowPadding ?? 3;
  const wd = s.widths ? Object.values(s.widths) : null;
  let h2 = `<div style="position:absolute;inset:0;overflow:hidden"><table class="grid" style="${cellCss(G.values)};color:${(G.values || {}).color || txt}">` +
    (wd ? '<colgroup>' + wd.map(x => `<col style="width:${x}px">`).join('') + '</colgroup>' : '') +
    `<tr>${head.map((x, k) => `<th class="${k < (matrix ? 1 : nG) ? 'l' : ''}" style="${cellCss(G.colHead) || 'color:' + muted + ';font-weight:600'};border-bottom:1px solid ${grid}">${esc(x)}</th>`).join('')}</tr>`;
  rows.slice(0, 40).forEach((r, j) => { h2 += `<tr>${r.map((x, k) => { const vk = k - (matrix ? 1 : nG);
      const on = t_ => vk >= 0 && (!t_ || t_ === head[k]);         // a cf colour on its target column only
      const fc = d.fonts && on(d.fontTarget) ? d.fonts[j] : null, bc = d.backs && on(d.backTarget) ? d.backs[j] : null;
      const body = d.sample ? (vk < 0 ? '—' : '') : isImg(x) ? `<img alt="" src="${esc(svgSrc(x))}" style="height:${(G.values || {}).size * 1.6 || 20}px;max-width:100%;vertical-align:middle">` : esc(vk < 0 ? x : fmt(x, d.formats[vk]));
      return `<td class="${vk < 0 ? 'l' : ''}" style="padding:${pad}px 8px;border-bottom:${G.h ?? 1}px solid ${G.hColor || C.neutralTint || '#F3F2F1'}${fc ? ';color:' + fc : ''}${bc ? ';background:' + bc : ''}">${body}</td>`; }).join('')}</tr>`; });
  el.insertAdjacentHTML('beforeend', h2 + '</table></div>');
}
// a matrix with a field on Columns: rows x columns, each cell's colours from its cf measures; a cell without a value
// (none, or hidden as a small group) shows an en dash
function matrixGrid(s, el, w, h) {
  const d = dataOf(s, 8);
  if (d.sample || d.leg == null || d.groups.length < 2) return tableGrid(s, el, w, h, true);
  const ri = d.cat ?? 0, ci = d.leg, nG = d.groups.length, G = s.grid || {}, lv = d.levels || [], K = '\u0001';
  const rowsK = lv[ri] ? [...lv[ri]] : [...new Set(d.rows.map(r => r[ri]))], colsK = lv[ci] ? [...lv[ci]] : [...new Set(d.rows.map(r => r[ci]))];
  const at = {}; d.rows.forEach((r, j) => at[r[ri] + K + r[ci]] = j);
  if (s.sort && d.values.includes(s.sort.field)) {   // rows by their total (wireframe_data.py rowTotals), else the cells'
    const RT = d.rowTotals || {};
    const tot = k => RT[k] != null ? RT[k] : colsK.reduce((a, c) => { const j = at[k + K + c], v = j == null ? 0 : d.rows[j][nG]; return a + (typeof v === 'number' && v > 0 ? v : 0); }, 0);
    rowsK.sort((a, b) => s.sort.desc ? tot(b) - tot(a) : tot(a) - tot(b)); }
  const fRow = s.fields.find(f => f.role === 'Rows'), fVal = s.fields.find(f => f.role === 'Values'), wd = s.widths || {};
  const gap = G.v || 0, rw = fRow && wd[fRow.field] && wd[fRow.field] - gap, vw = fVal && wd[fVal.field] && wd[fVal.field] - gap, pad = G.rowPadding ?? 3;
  const V = G.values || {}, CH = G.colHead || {}, RH = G.rowHead || {};
  const width = rw && vw ? `width:${rw + vw * colsK.length + (G.v || 0) * (colsK.length + 2)}px` : 'width:100%';
  let t = `<div style="position:absolute;inset:0;overflow:hidden"><table style="border-collapse:separate;border-spacing:${G.v || 0}px ${G.h || 0}px;table-layout:fixed;${width};margin:-${G.h || 0}px -${G.v || 0}px">` +
    `<colgroup><col style="width:${rw ? rw + 'px' : '14%'}">${colsK.map(() => `<col${vw ? ` style="width:${vw}px"` : ''}>`).join('')}</colgroup>` +
    `<tr><th style="${cellCss(CH)};text-align:left;padding:${pad}px 6px;white-space:nowrap;overflow:hidden">${esc(d.groups[ri])}</th>` +
    colsK.map(c => `<th style="${cellCss(CH)};text-align:${CH.align || 'right'};padding:${pad}px 6px;white-space:nowrap;overflow:hidden">${esc(c)}</th>`).join('') + '</tr>';
  for (const r of rowsK) {
    t += `<tr><th style="${cellCss(RH)};text-align:left;padding:${pad}px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(r)}</th>`;
    for (const c of colsK) { const j = at[r + K + c], v = j == null ? null : d.rows[j][nG];
      const fc = j != null && d.fonts ? d.fonts[j] : null, bc = j != null && d.backs ? d.backs[j] : null;
      t += `<td style="${cellCss(V)};text-align:${V.align || 'right'};padding:${pad}px 6px;white-space:nowrap;overflow:hidden${j == null ? ';color:' + muted : ''}${fc ? ';color:' + fc : ''}${bc ? ';background:' + bc : ''}">${esc(j == null || v == null ? '–' : fmt(v, d.formats[0]))}</td>`; }
    t += '</tr>'; }
  el.insertAdjacentHTML('beforeend', t + '</table></div>');
}
R.tableEx = (s, el, w, h) => tableGrid(s, el, w, h, false);
R.pivotTable = matrixGrid;
function members(s, n) { const d = D[s.id]; if (d) return d.rows.map(r => String(r[0])); const it = s.slicer.items;
  return Array.isArray(it) ? it.map(String) : Array.from({length: typeof it === 'number' ? it : (n || 4)}, (_, i) => 'Item ' + (i + 1)); }
R.advancedSlicerVisual = (s, el, w, h) => {
  const sl = s.slicer, items = members(s, 4), cols = sl.cols || items.length, rows = sl.rows || Math.ceil(items.length / cols);
  const head = sl.headerShow ? `<div style="font-size:12px;font-weight:600;color:${muted};margin-bottom:4px">${esc(sl.header)}</div>` : '';
  const sel = new Set(sl.selected.length ? sl.selected : []);
  const paint = (b, on) => { b.dataset.on = on ? '1' : ''; b.style.background = on ? sl.selFill : hexA(sl.fill, sl.fillAlpha); b.style.color = on ? sl.selColor : sl.color;
    const o = on ? sl.selOutline || (sl.outline ? sl.selFill : null) : sl.outline; b.style.border = o ? `1px solid ${o}` : '0'; };
  el.insertAdjacentHTML('beforeend', head + `<div style="flex:1;display:grid;gap:6px;grid-template-columns:repeat(${cols},1fr);grid-template-rows:repeat(${rows},1fr)">` +
    items.slice(0, cols * rows).map(x => `<div data-item="${esc(x)}" style="display:flex;align-items:center;justify-content:center;border-radius:${sl.radius}px;font-family:'${sl.family}';font-weight:${sl.weight};font-size:${sl.size || 13}px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:0 6px;cursor:pointer">${esc(x)}</div>`).join('') + '</div>');
  el.querySelectorAll('[data-item]').forEach(b => { paint(b, sel.has(b.dataset.item));
    b.onclick = () => { const on = !b.dataset.on; if (sl.single) el.querySelectorAll('[data-item]').forEach(o => paint(o, false)); paint(b, on); }; });
};
R.slicer = (s, el, w, h) => {
  const sl = s.slicer, items = members(s, 5);
  const head = sl.headerShow ? `<div style="font-size:12px;font-weight:600;color:${muted};margin-bottom:4px">${esc(sl.header)}</div>` : '';
  if (s.mode === 'dropdown') {
    el.insertAdjacentHTML('beforeend', head + `<div style="height:32px;border:1px solid ${grid};border-radius:8px;display:flex;align-items:center;justify-content:space-between;padding:0 10px;font-size:13px;color:${sl.color};background:transparent"><span>${esc(sl.selected.join(', ') || 'All')}</span><span>⌄</span></div>`);
  } else {
    el.insertAdjacentHTML('beforeend', head + items.slice(0, 12).map(x => `<div style="font-size:13px;color:${sl.color};padding:2px 0"><span style="display:inline-block;width:12px;height:12px;border:1px solid ${muted};border-radius:2px;margin-right:6px;vertical-align:-1px;background:${sl.selected.includes(x) ? (C.primary || '#118DFF') : 'transparent'}"></span>${esc(x)}</div>`).join(''));
  }
};
R.listSlicer = R.slicer; R.textSlicer = (s, el) => el.insertAdjacentHTML('beforeend', `<div class="placeholder">Search…</div>`);
R.pageNavigator = (s, el, w, h) => {
  const n = s.nav; el.style.flexDirection = 'row'; el.style.gap = '8px';
  el.insertAdjacentHTML('beforeend', n.pages.map(p => { const st = n.states[p === n.current ? 'selected' : 'default'];
    const fill = st.alpha > 0 ? n.fill : 'transparent';
    return `<div data-goto="${esc(p)}" style="flex:1;display:flex;align-items:center;justify-content:center;border-radius:${n.radius}px;background:${fill};opacity:1;color:${st.color};font-size:${n.size}px;border:${p === n.current ? '1px solid ' + n.outline : '0'};cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(p)}</div>`; }).join(''));
  el.querySelectorAll('[data-goto]').forEach(b => b.onclick = () => show(S.pages.findIndex(p => p.name === b.dataset.goto)));
};
R.bookmarkNavigator = R.pageNavigator;
R.actionButton = (s, el, w, h) => {
  const b = s.button; el.style.justifyContent = 'center'; el.style.alignItems = {left: 'flex-start', right: 'flex-end'}[b.align] || 'center';
  if (b.fill) { el.style.background = b.fill; el.style.opacity = 1; el.style.setProperty('--a', b.fillAlpha); el.style.background = hexA(b.fill, b.fillAlpha); }
  if (b.outline) el.style.border = `${b.ow || 1}px solid ${b.outline}`;
  el.style.borderRadius = (b.radius || 0) + 'px'; el.style.padding = '0 12px';
  el.insertAdjacentHTML('beforeend', `<div style="font-family:'${b.family}';font-weight:${b.weight};font-size:${b.size}px;color:${b.color};white-space:nowrap">${esc(b.text || '')}</div>`);
};
R.textbox = (s, el) => {
  el.insertAdjacentHTML('beforeend', (s.text || []).map(p => `<div style="text-align:${p.align};line-height:1.25">${p.runs.map(r =>
    `<span style="font-family:'${r.family}';font-weight:${r.weight};font-size:${r.size}px;color:${r.color}">${esc(r.text)}</span>`).join('')}</div>`).join(''));
};
R.shape = (s, el) => { const sh = s.shape; el.style.background = hexA(sh.fill, sh.alpha); el.style.borderRadius = sh.radius + 'px'; if (sh.outline) el.style.border = `1px solid ${sh.outline}`; };
R.basicShape = R.shape;
// static images (image visuals, page and container backgrounds): the files embedded once each in S.images
function imgCss(el, im) { Object.assign(el.style, {backgroundImage: `url("${S.images[im.src]}")`, backgroundSize: im.scaling || '100% 100%',
  backgroundRepeat: 'no-repeat', backgroundPosition: 'center'}); }
R.image = (s, el) => { const im = s.img;
  if (im && im.src && S.images[im.src]) return imgCss(el, im);
  el.insertAdjacentHTML('beforeend', `<div class="placeholder" style="border-style:solid">🖼 image${im ? '<br><small>not found: ' + esc(im.name) + '</small>' : ''}</div>`); };
R._unknown = (s, el) => el.insertAdjacentHTML('beforeend', `<div class="placeholder"><div><b>${esc(s.tag)}</b><br>${esc(s.fields.map(f => f.label).join(', '))}<br><small>no wireframe renderer for this type</small></div></div>`);

// ---- pattern renderers (docs/patterns/): layout.json `pattern` picks one over the visual type's renderer
const P = {};
const tint = C.slateTint || C.neutralTint || '#EDF0F6', good = C.good || C.teal || '#038D96', bad = C.bad || C.red || '#A84545', soft = C.slateLight || C.border || '#B8C2D6';
function frame(w, h, padL, padB, padT, padR) { return {padL, padB, padT, padR, W: Math.max(w - padL - padR, 4), H: Math.max(h - padT - padB, 4)}; }
function seasonal(s, n, k) { const r = seed(s.id + (k || '')); return Array.from({length: n}, (_, i) => 50 + 25 * Math.sin(i / n * Math.PI * 2) + r() * 8); }
function gridLines(g, f) { for (let t = 0; t <= 4; t++) { const y = f.padT + f.H * t / 4; add(g, 'line', {x1: f.padL, x2: f.padL + f.W, y1: y, y2: y, stroke: grid}); } }
P['range-band'] = (s, el, w, h) => {
  if (!/line|area/i.test(s.type)) return (R[s.type] || R._unknown)(s, el, w, h);
  const d = dataOf(s, 12), sr = series(d); let cats = sr.cats, lo, hi, val;
  if (!d.sample && sr.series.length >= 3) { lo = sr.series[0].values; hi = sr.series[1].values; val = sr.series[sr.series.length - 1].values; }
  else { const b = seasonal(s, 12), r = seed(s.id + 'v'); cats = Array.from({length: 12}, (_, i) => 'M' + (i + 1));
         lo = b.map(x => x - 12); hi = b.map(x => x + 12); val = b.map((x, i) => i === 7 ? x + 20 : i > 9 ? null : x + (r() - .5) * 10); }
  const g = svg(w, h); el.appendChild(g); const f = frame(w, h, 40, 22, 6, 8);
  let max = 0; [lo, hi, val].forEach(a => a.forEach(v => max = Math.max(max, v || 0))); max = nice(max);
  const X = i => f.padL + (cats.length > 1 ? f.W * i / (cats.length - 1) : f.W / 2), Y = v => f.padT + f.H - (v || 0) / max * f.H;
  gridLines(g, f);
  const up = hi.map((v, i) => `${X(i)},${Y(v)}`), dn = lo.map((v, i) => `${X(i)},${Y(v)}`).reverse();
  add(g, 'polygon', {points: up.concat(dn).join(' '), fill: tint, stroke: soft, 'stroke-width': 1});
  val.forEach((v, i) => { if (v == null) return; const out = v < lo[i] || v > hi[i];
    add(g, 'circle', {cx: X(i), cy: Y(v), r: 5, fill: out ? bad : good}); });
  cats.forEach((c, i) => { if (i % Math.ceil(cats.length / 12) === 0) add(g, 'text', {x: X(i), y: h - 6, 'font-size': 10, fill: muted, 'text-anchor': 'middle'}, d.sample ? '' : String(c).slice(0, 8)); });
};
P['dumbbell'] = (s, el, w, h) => {
  const d = D[s.id], r = seed(s.id); let rows, ix = [];
  if (d) { const nG = d.groups.length; ix = d.values.map((_, k) => k).filter(k => d.rows.length && d.rows.every(x => x[nG + k] == null || typeof x[nG + k] === 'number')); }
  if (d && ix.length >= 2) rows = d.rows.map(x => [String(x[0]), x[d.groups.length + ix[0]], x[d.groups.length + ix[1]]]);
  else rows = Array.from({length: 7}, (_, i) => ['Item ' + (i + 1), 30 + r() * 50, 30 + r() * 50]);
  rows = rows.filter(x => x[1] != null && x[2] != null).sort((a, b) => (b[2] - b[1]) - (a[2] - a[1]));
  if (!rows.length) return;
  const lo = Math.min(...rows.flatMap(x => [x[1], x[2]])), hi = Math.max(...rows.flatMap(x => [x[1], x[2]]));
  const rh = Math.min(32, h / rows.length), labW = Math.min(130, w * .3), chW = Math.max(w - labW - 90, 20);
  const g = svg(w, h); el.appendChild(g);
  const X = v => labW + 8 + (hi > lo ? (v - lo) / (hi - lo) : .5) * (chW - 16);
  rows.forEach((x, i) => { const y = rh * i + rh / 2, ch = x[2] - x[1], col = ch >= 0 ? good : bad;
    add(g, 'text', {x: 0, y: y + 4, 'font-size': 12, fill: txt}, x[0]);
    add(g, 'line', {x1: X(x[1]), x2: X(x[2]), y1: y, y2: y, stroke: grid, 'stroke-width': 3});
    add(g, 'circle', {cx: X(x[1]), cy: y, r: 5, fill: '#fff', stroke: soft, 'stroke-width': 2});
    add(g, 'circle', {cx: X(x[2]), cy: y, r: 6, fill: col});
    add(g, 'text', {x: w - 4, y: y + 4, 'font-size': 12, fill: col, 'text-anchor': 'end', 'font-weight': 600},
        (ch >= 0 ? '▲ +' : '▼ −') + (d && ix.length >= 2 ? fmt(Math.abs(ch), d.formats[ix[1]]) : d ? '' : Math.abs(ch).toFixed(1))); });
};
P['small-multiples-expected'] = (s, el, w, h) => {
  const d = D[s.id], rowsF = s.fields.find(f => f.role === 'Rows'); let panels = {};
  if (d && rowsF && d.groups.length >= 2 && d.values.length >= 2) {
    const pi = Math.max(d.groups.indexOf(rowsF.label), 0), ci = pi === 0 ? 1 : 0, nG = d.groups.length;
    d.rows.forEach(x => { (panels[x[pi]] = panels[x[pi]] || []).push([x[ci], x[nG], x[nG + 1]]); });
  } else ['North', 'South', 'East', 'West', 'Central', 'Online'].forEach((p, k) => { const b = seasonal(s, 12, p), r = seed(p);
    panels[p] = b.map((v, i) => [i, v + (k === 2 ? -i * 2 : (r() - .5) * 8), v]); });
  const names = Object.keys(panels).slice(0, 16), n = names.length;
  if (!n) return;
  const cols = Math.min(n, Math.max(1, Math.round(Math.sqrt(n * w / Math.max(h, 1))))), rws = Math.ceil(n / cols);
  const pw = w / cols, ph = h / rws; let max = 0; names.forEach(p => panels[p].forEach(x => max = Math.max(max, x[1] || 0, x[2] || 0))); max = nice(max);
  const g = svg(w, h); el.appendChild(g);
  names.forEach((p, k) => { const ox = (k % cols) * pw, oy = Math.floor(k / cols) * ph, pts = panels[p], m = pts.length;
    const X = i => ox + 6 + (pw - 14) * (m > 1 ? i / (m - 1) : .5), Y = v => oy + ph - 6 - (v || 0) / max * (ph - 26);
    add(g, 'rect', {x: ox + 2, y: oy + 2, width: pw - 4, height: ph - 4, fill: 'none', stroke: grid, rx: 4});
    add(g, 'text', {x: ox + 8, y: oy + 15, 'font-size': 11, 'font-weight': 600, fill: txt}, String(p));
    add(g, 'polyline', {points: pts.map((x, i) => `${X(i)},${Y(x[2])}`).join(' '), fill: 'none', stroke: C.slate || '#5D6B8A', 'stroke-width': 1.2, 'stroke-dasharray': '4 3'});
    add(g, 'polyline', {points: pts.map((x, i) => `${X(i)},${Y(x[1])}`).join(' '), fill: 'none', stroke: good, 'stroke-width': 2.2}); });
};
P['brushed-range'] = (s, el, w, h) => {
  const a = .55, b = .8;
  if (/slicer/i.test(s.type)) { const g = svg(w, h); el.appendChild(g); const y = h / 2 + 6, x0 = 10, x1 = w - 10, X = q => x0 + (x1 - x0) * q;
    add(g, 'line', {x1: x0, x2: x1, y1: y, y2: y, stroke: grid, 'stroke-width': 4, 'stroke-linecap': 'round'});
    add(g, 'line', {x1: X(a), x2: X(b), y1: y, y2: y, stroke: good, 'stroke-width': 4});
    [a, b].forEach(q => add(g, 'circle', {cx: X(q), cy: y, r: 8, fill: '#fff', stroke: good, 'stroke-width': 2}));
    add(g, 'text', {x: x0, y: y - 14, 'font-size': 11, fill: muted}, 'range slider (Between)'); return; }
  (R[s.type] || R.lineChart)(s, el, w, h);
  const g = el.querySelector('svg'); if (!g) return;
  const r = add(g, 'rect', {x: w * a, y: 0, width: w * (b - a), height: h, fill: C.tealTint || '#E7F3F5', opacity: .7}); g.insertBefore(r, g.firstChild);
};
P['partial-period'] = (s, el, w, h) => {
  if (!/line|area/i.test(s.type)) return (R[s.type] || R._unknown)(s, el, w, h);
  const d = dataOf(s, 12), sr = series(d), cats = sr.cats, s0 = sr.series[0] || {values: []}, s1 = sr.series[1] || {values: []};
  let v = s0.values.map((x, i) => x != null ? x : s1.values[i]);
  if (d.sample) v = seasonal(s, 12).map((x, i) => i === 11 ? x * .45 : x);
  const n = v.length; if (n < 2) return (R[s.type] || R._unknown)(s, el, w, h);
  const g = svg(w, h); el.appendChild(g); const f = frame(w, h, 40, 22, 10, 60);
  let max = 0; v.forEach(x => max = Math.max(max, x || 0)); max = nice(max);
  const X = i => f.padL + f.W * i / (n - 1), Y = x => f.padT + f.H - (x || 0) / max * f.H;
  gridLines(g, f);
  add(g, 'polyline', {points: v.slice(0, n - 1).map((x, i) => `${X(i)},${Y(x)}`).join(' '), fill: 'none', stroke: good, 'stroke-width': 3});
  v.slice(0, n - 1).forEach((x, i) => add(g, 'circle', {cx: X(i), cy: Y(x), r: 3, fill: good}));
  add(g, 'line', {x1: X(n - 2), y1: Y(v[n - 2]), x2: X(n - 1), y2: Y(v[n - 1]), stroke: good, 'stroke-width': 2, 'stroke-dasharray': '5 4'});
  add(g, 'circle', {cx: X(n - 1), cy: Y(v[n - 1]), r: 6, fill: '#fff', stroke: good, 'stroke-width': 2.5});
  add(g, 'text', {x: X(n - 1) + 10, y: Y(v[n - 1]) + 4, 'font-size': 11, fill: muted}, 'partial');
  if (!d.sample) cats.forEach((c, i) => { if (i % Math.ceil(n / 12) === 0) add(g, 'text', {x: X(i), y: h - 6, 'font-size': 10, fill: muted, 'text-anchor': 'middle'}, String(c).slice(0, 8)); });
};
P['freshness-line'] = (s, el, w, h) => {
  if (s.type === 'cardVisual' || s.type === 'card') { const d = D[s.id], row = d && d.rows[0];
    const text = row ? String(row[d.groups.length]) : 'Data to dd mmm yyyy';
    el.style.justifyContent = 'center';
    el.insertAdjacentHTML('beforeend', `<div style="text-align:${(s.card || {}).align || 'right'};font-size:13px;color:${muted};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(text)}</div>`); if (row) el.dataset.main = text; return; }
  (R[s.type] || R._unknown)(s, el, w, h);
  const g = el.querySelector('svg'); if (!g) return; const x = w * .86;
  add(g, 'line', {x1: x, x2: x, y1: 4, y2: h - 22, stroke: muted, 'stroke-dasharray': '4 3'});
  add(g, 'text', {x: x - 4, y: 14, 'font-size': 10, fill: muted, 'text-anchor': 'end'}, 'data to');
};
P['exception-list'] = (s, el, w, h) => {
  const d = D[s.id];
  if (d) { if (!d.rows.length) { el.insertAdjacentHTML('beforeend', `<div class="placeholder" style="border:0;background:none">No exceptions</div>`); return; }
           return tableGrid(s, el, w, h, false); }
  const r = seed(s.id), head = s.fields.map(f => f.label);
  const rows = Array.from({length: 4}, (_, i) => head.map((_, k) => k === 0 ? 'Item ' + (i + 1) : k === 1 ? -(4 - i) * (2 + r() * 3) : 20 + r() * 60));
  el.insertAdjacentHTML('beforeend', `<div style="position:absolute;inset:0;overflow:hidden"><table class="grid" style="font-size:14px;color:${txt}"><tr>${head.map((x, k) => `<th class="${k ? '' : 'l'}" style="color:${muted};font-weight:600;border-bottom:1px solid ${grid}">${esc(x)}</th>`).join('')}</tr>` +
    rows.map(x => `<tr>${x.map((v, k) => `<td class="${k ? '' : 'l'}" style="border-bottom:1px solid ${C.neutralTint || '#F3F2F1'};${k === 1 ? 'color:' + bad + ';font-weight:600' : ''}">${k === 0 ? esc(v) : (k === 1 ? '▼ ' : '') + '—'}</td>`).join('')}</tr>`).join('') + '</table></div>');
};
P['direct-labels'] = (s, el, w, h) => {
  if (!/line|area/i.test(s.type)) return (R[s.type] || R._unknown)(s, el, w, h);
  const d = dataOf(s, 12), ss0 = series(d).series;
  if (d.labels && !d.sample) return (R[s.type] || R.lineChart)(s, el, w, h);
  const ss = d.sample ? s.fields.filter(f => f.role === 'Y').map((fl, k) => ({name: fl.label, values: seasonal(s, 12, fl.label).map(v => v + k * 15)})) : ss0;
  if (!ss.length) return (R[s.type] || R._unknown)(s, el, w, h);
  const longest = Math.max(...ss.map(x => String(x.name).length)), g = svg(w, h); el.appendChild(g);
  const f = frame(w, h, 40, 22, 8, Math.min(longest * 7 + 14, w * .3));
  let lo = Infinity, hi = -Infinity; ss.forEach(x => x.values.forEach(v => { if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }));
  const rg = valueRange(lo, hi, null, d, false, lo >= 0), span = (rg.hi - rg.lo) || 1;
  const n = Math.max(...ss.map(x => x.values.length)), X = i => f.padL + (n > 1 ? f.W * i / (n - 1) : f.W / 2), Y = v => f.padT + f.H - ((v ?? rg.lo) - rg.lo) / span * f.H;
  gridLines(g, f);
  const ends = [];
  ss.forEach((x, k) => { const c = color(s, x.name, k); add(g, 'polyline', {points: x.values.map((v, i) => `${X(i)},${Y(v)}`).join(' '), fill: 'none', stroke: c, 'stroke-width': 3});
    let i = x.values.length - 1; while (i > 0 && x.values[i] == null) i--; ends.push({y: Y(x.values[i]), x: X(i), c, name: x.name}); });
  ends.sort((a, b) => a.y - b.y).forEach((e, k, a) => { if (k && e.y - a[k - 1].y < 13) e.y = a[k - 1].y + 13;
    add(g, 'text', {x: e.x + 6, y: e.y + 4, 'font-size': 12, 'font-weight': 600, fill: e.c}, String(e.name)); });
};

// ---- Deneb: the visual's Vega-Lite spec over its own aggregated dataset (sample records without data).
// Vega-Lite itself draws it when its pinned scripts loaded (vega "cdn", online); otherwise (or vega "offline") a subset renderer does
// (marks bar, line, area, point, circle, square, tick, rule, rect, text; encodings x, y, x2, y2, color, size, opacity,
// text, strokeDash with conditions; transforms calculate and filter; layer; an x interval selection in params is
// shaded). Anything else is listed under the visual as not drawn.
const READY = [];                                  // renders still running (Vega-Lite): window.pageReady waits for them
function denebData(s) {
  const d = D[s.id];
  if (d) { const names = [...d.groups, ...d.values]; return {rows: d.rows.map(r => Object.fromEntries(names.map((n, k) => [n, r[k]]))), sample: false}; }
  const r = seed(s.id), cats = Array.from({length: 8}, (_, i) => 'Item ' + (i + 1));
  const grp = s.fields.filter(f => /\[/.test(f.field || '') && !/^\[/.test(f.field || '') && !/^\w+\(/.test(f.field || ''));
  const val = s.fields.filter(f => !grp.includes(f));
  return {rows: cats.map((c, i) => Object.fromEntries([...grp.map((f, k) => [f.label, k ? 'Group ' + (1 + (i % 2)) : c]),
                                                      ...val.map(f => [f.label, 20 + r() * 80])])), sample: true};
}
function pbiColors(o) {     // Deneb's pbiColor(n) -> the theme's data colours
  const pick = n => S.dataColors[+n % S.dataColors.length];
  if (typeof o === 'string') { const m = o.match(/^pbiColor\(\s*(\d+)/); return m ? pick(m[1]) : o; }
  if (Array.isArray(o)) return o.map(pbiColors);
  if (o && typeof o === 'object') { const out = {};
    for (const k in o) out[k] = k === 'expr' && typeof o[k] === 'string' ? o[k].replace(/pbiColor\(\s*(\d+)(?:\s*,\s*[-\d.]+)?\s*\)/g, (_, n) => `'${pick(n)}'`) : pbiColors(o[k]);
    if (out.expr && /^'#[0-9a-f]{6}'$/i.test(out.expr)) return out.expr.slice(1, -1);
    return out; }
  return o;
}
R.deneb = (s, el, w, h) => {
  const dn = s.deneb || {}, spec0 = dn.spec || {};
  if (spec0._error) { el.insertAdjacentHTML('beforeend', `<div class="placeholder">Deneb: ${esc(spec0._error)}</div>`); return; }
  if (dn.provider && dn.provider !== 'vegaLite') { el.insertAdjacentHTML('beforeend', `<div class="placeholder">Deneb (${esc(dn.provider)}): only Vega-Lite specs are drawn</div>`); return; }
  const data = denebData(s), spec = pbiColors(JSON.parse(JSON.stringify(spec0)));
  if (data.sample) el.insertAdjacentHTML('beforeend', '<span class="nodata">sample records · no data</span>');
  if (S.vega === 'cdn' && window.vegaEmbed) {
    const full = {...spec, data: {values: data.rows}, width: w - 10, height: h - 10, autosize: {type: 'fit', contains: 'padding'}};
    const box = document.createElement('div'); el.appendChild(box);
    READY.push(window.vegaEmbed(box, full, {actions: false, renderer: 'svg'}).catch(e => { box.remove(); vlSubset(s, el, w, h, spec, data.rows);
      el.insertAdjacentHTML('beforeend', `<span class="vlnote" style="bottom:14px">Vega-Lite: ${esc(e.message)}</span>`); }));
    return;
  }
  vlSubset(s, el, w, h, spec, data.rows);
  if (S.vega === 'cdn') el.insertAdjacentHTML('beforeend', '<span class="vlnote" style="bottom:14px">offline: drawn by the Vega-Lite subset renderer</span>');
};
const VL_ENC = ['x', 'y', 'x2', 'y2', 'color', 'size', 'opacity', 'text', 'strokeDash', 'tooltip', 'order', 'detail', 'shape'];
const VLX = {indexof: (a, v) => (a || []).indexOf(v), isValid: x => x != null && !Number.isNaN(x), toNumber: Number, toString: String,
             abs: Math.abs, round: Math.round, floor: Math.floor, ceil: Math.ceil, min: Math.min, max: Math.max};
function vlExpr(expr) { try { return new Function('datum', 'VLX', 'with (VLX) { return (' + expr + '); }'); } catch (e) { return null; } }
function vlRun(f, r) { try { return f(r, VLX); } catch (e) { return null; } }
function vlTransform(rows, ts, skipped) {
  for (const t of ts || []) {
    if (t.calculate != null && t.as) { const f = vlExpr(t.calculate); if (!f) { skipped.add('transform calculate'); continue; }
      rows = rows.map(r => ({...r, [t.as]: vlRun(f, r)})); }
    else if (typeof t.filter === 'string') { const f = vlExpr(t.filter); if (!f) { skipped.add('transform filter'); continue; } rows = rows.filter(r => vlRun(f, r)); }
    else if (t.filter && t.filter.field) { const F = t.filter;
      rows = rows.filter(r => { const x = r[F.field]; return F.equal !== undefined ? x === F.equal : F.oneOf ? F.oneOf.includes(x) : F.range ? x >= F.range[0] && x <= F.range[1] : true; }); }
    else skipped.add('transform ' + Object.keys(t)[0]);
  }
  return rows;
}
function vlChan(c, r, dflt) {                      // a channel's value for one row: its conditions, then its value
  if (!c) return dflt;
  for (const k of [].concat(c.condition || [])) { const f = k.test && vlExpr(k.test); if (f && vlRun(f, r)) return k.value; }
  return c.value !== undefined ? c.value : dflt;
}
function vlSubset(s, el, w, h, spec, rows0) {
  const skipped = new Set(), g = svg(w, h); el.appendChild(g);
  ['facet', 'repeat', 'concat', 'hconcat', 'vconcat'].forEach(k => { if (spec[k]) skipped.add(k); });
  const layers = [];
  (function walk(node, enc, rows) { const e = {...enc, ...(node.encoding || {})}, rs = vlTransform(rows, node.transform, skipped);
    if (node.layer) node.layer.forEach(l => walk(l, e, rs)); else if (node.mark) layers.push({mark: typeof node.mark === 'string' ? {type: node.mark} : node.mark, enc: e, rows: rs}); })(spec, {}, rows0);
  const all = layers.length ? layers.flatMap(l => l.rows) : rows0;
  const f = frame(w, h, 44, 24, 10, 10);
  const field = c => c && (c.field != null ? String(c.field).replace(/\\\./g, '.') : null);
  function scale(axis) {
    const encs = layers.flatMap(l => [l.enc[axis], l.enc[axis + '2']]).filter(c => c && field(c) != null);
    if (!encs.length) return null;
    const len = axis === 'x' ? f.W : f.H;
    if (encs.some(c => c.type === 'quantitative' || c.aggregate)) {
      const vals = encs.flatMap(c => all.map(r => +r[field(c)]).filter(isFinite));
      const zero = !encs.some(c => c.scale && c.scale.zero === false);
      let lo = zero ? Math.min(0, ...vals) : Math.min(...vals), hi = nice(Math.max(0, ...vals)); if (!vals.length) { lo = 0; hi = 1; }
      const sp = (hi - lo) || 1;
      return {q: true, lo, hi, bw: 0, f: v => axis === 'x' ? f.padL + (v - lo) / sp * len : f.padT + len - (v - lo) / sp * len};
    }
    const dom = [...new Set(all.map(r => r[field(encs[0])]))]; if (/^(descending|-[xy])$/.test(encs[0].sort || '')) dom.reverse();
    const bw = len / Math.max(dom.length, 1);
    return {q: false, dom, bw, f: v => (axis === 'x' ? f.padL : f.padT) + bw * Math.max(dom.indexOf(v), 0) + bw / 2};
  }
  const sx = scale('x'), sy = scale('y');
  const colEnc = layers.map(l => l.enc.color).find(c => c && field(c) != null), colDom = colEnc ? [...new Set(all.map(r => r[field(colEnc)]))] : [];
  const colour = (l, r) => { const c = l.enc.color; if (c && (c.value !== undefined || c.condition)) return vlChan(c, r, l.mark.color || S.dataColors[0]);
    if (c && field(c) != null) return (c.scale && c.scale.range && c.scale.range[Math.max(colDom.indexOf(r[field(c)]), 0)]) || S.dataColors[Math.max(colDom.indexOf(r[field(c)]), 0) % S.dataColors.length];
    return l.mark.color || l.mark.fill || l.mark.stroke || S.dataColors[0]; };
  if (sy) { if (sy.q) for (let t = 0; t <= 4; t++) { const v = sy.lo + (sy.hi - sy.lo) * t / 4, y = sy.f(v); add(g, 'line', {x1: f.padL, x2: f.padL + f.W, y1: y, y2: y, stroke: grid}); add(g, 'text', {x: f.padL - 4, y: y + 4, 'font-size': 10, fill: muted, 'text-anchor': 'end'}, fmt(v)); }
            else sy.dom.forEach(v => add(g, 'text', {x: f.padL - 4, y: sy.f(v) + 4, 'font-size': 10, fill: txt, 'text-anchor': 'end'}, String(v).slice(0, 14))); }
  if (sx) { if (sx.q) for (let t = 0; t <= 4; t++) { const v = sx.lo + (sx.hi - sx.lo) * t / 4; add(g, 'text', {x: sx.f(v), y: h - 6, 'font-size': 10, fill: muted, 'text-anchor': 'middle'}, fmt(v)); }
            else sx.dom.forEach((v, i) => { if (sx.dom.length <= 14 || i % Math.ceil(sx.dom.length / 12) === 0) add(g, 'text', {x: sx.f(v), y: h - 6, 'font-size': 10, fill: muted, 'text-anchor': 'middle'}, String(v).slice(0, 10)); }); }
  (spec.params || []).forEach(p => { if (p.select && (p.select === 'interval' || p.select.type === 'interval')) add(g, 'rect', {x: f.padL + f.W * .4, y: f.padT, width: f.W * .25, height: f.H, fill: C.tealTint || '#E7F3F5', opacity: .8}); });
  const pos = (sc, enc, r) => enc && field(enc) != null ? (sc ? sc.f(sc.q ? +r[field(enc)] : r[field(enc)]) : null) : (enc && enc.value != null ? enc.value : null);
  layers.forEach(l => { const m = l.mark, t = m.type, e = l.enc, rows = l.rows;
    Object.keys(e).forEach(k => { if (!VL_ENC.includes(k)) skipped.add('encoding ' + k); });
    const op = r => vlChan(e.opacity, r, m.opacity ?? 1);
    const dash = (e.strokeDash && e.strokeDash.value) || m.strokeDash;
    if (t === 'line' || t === 'area') {
      const groups = {}; rows.forEach(r => { const k = e.color && field(e.color) != null ? r[field(e.color)] : '_'; (groups[k] = groups[k] || []).push(r); });
      Object.values(groups).forEach(gr => { const pts = gr.map(r => [pos(sx, e.x, r), pos(sy, e.y, r), pos(sy, e.y2, r)]).filter(p => p[0] != null && p[1] != null && isFinite(p[1]));
        if (!pts.length) return; pts.sort((a, b) => a[0] - b[0]); const c = colour(l, gr[0]);
        if (t === 'area') { const lower = pts.map(p => [p[0], p[2] != null ? p[2] : f.padT + f.H]).reverse();
          add(g, 'polygon', {points: [...pts.map(p => p[0] + ',' + p[1]), ...lower.map(p => p.join(','))].join(' '), fill: c, opacity: m.opacity ?? (e.y2 ? 1 : .3)}); }
        else add(g, 'polyline', {points: pts.map(p => p[0] + ',' + p[1]).join(' '), fill: 'none', stroke: c, 'stroke-width': m.strokeWidth || 2, 'stroke-dasharray': dash ? dash.join(' ') : ''});
        if (m.point) pts.forEach(p => add(g, 'circle', {cx: p[0], cy: p[1], r: 3, fill: c})); });
      return; }
    rows.forEach(r => { const c = colour(l, r), x = pos(sx, e.x, r), y = pos(sy, e.y, r), x2 = pos(sx, e.x2, r), y2 = pos(sy, e.y2, r);
      if (t === 'bar') { const horiz = sx && sx.q && sy && !sy.q;
        if (horiz && x != null) { const x0 = x2 != null ? x2 : sx.f(Math.max(sx.lo, 0)); add(g, 'rect', {x: Math.min(x, x0), y: y - sy.bw * .35, width: Math.abs(x - x0), height: sy.bw * .7, fill: c, opacity: op(r), rx: 2}); }
        else if (sx && sy && y != null) { const y0 = y2 != null ? y2 : sy.f(Math.max(sy.lo, 0)); add(g, 'rect', {x: x - sx.bw * .35, y: Math.min(y, y0), width: sx.bw * .7, height: Math.abs(y - y0), fill: c, opacity: op(r), rx: 2}); } }
      else if (t === 'rect') { const xa = x2 != null ? Math.min(x, x2) : x != null ? x - (sx ? sx.bw / 2 : 0) : f.padL, ya = y2 != null ? Math.min(y, y2) : y != null ? y - (sy ? sy.bw / 2 : 0) : f.padT;
        add(g, 'rect', {x: xa, y: ya, width: x2 != null ? Math.abs(x2 - x) : (sx ? sx.bw || 4 : f.W), height: y2 != null ? Math.abs(y2 - y) : (sy ? sy.bw || 4 : f.H), fill: c, opacity: op(r)}); }
      else if (t === 'rule') add(g, 'line', {x1: x ?? f.padL, x2: x2 ?? x ?? f.padL + f.W, y1: y ?? f.padT, y2: y2 ?? y ?? f.padT + f.H, stroke: c, 'stroke-width': m.strokeWidth || 1.5, 'stroke-dasharray': dash ? dash.join(' ') : ''});
      else if (t === 'tick') { if (y != null) add(g, 'line', {x1: (x ?? f.padL) - 6, x2: (x ?? f.padL) + 6, y1: y, y2: y, stroke: c, 'stroke-width': 2}); }
      else if (t === 'point' || t === 'circle' || t === 'square') { if (x == null || y == null) return;
        const sz = vlChan(e.size, r, m.size || 50), rr = Math.sqrt(sz / Math.PI), filled = t !== 'point' ? m.filled !== false : m.filled === true;
        if (t === 'square') add(g, 'rect', {x: x - rr, y: y - rr, width: rr * 2, height: rr * 2, fill: filled ? c : '#fff', stroke: c, 'stroke-width': 2});
        else add(g, 'circle', {cx: x, cy: y, r: rr, fill: filled ? c : '#fff', stroke: c, 'stroke-width': filled ? 0 : 2, opacity: op(r)}); }
      else if (t === 'text') { const tv = e.text ? (field(e.text) != null ? r[field(e.text)] : vlChan(e.text, r, '')) : m.text;
        add(g, 'text', {x: (x ?? f.padL) + (m.dx || 0), y: (y ?? f.padT) + (m.dy || 0) + 4, 'font-size': m.fontSize || 11, 'font-weight': m.fontWeight || 400, fill: vlChan(e.color, r, null) || m.color || txt,
                        'text-anchor': m.align === 'left' ? 'start' : m.align === 'right' ? 'end' : 'middle'}, typeof tv === 'number' ? fmt(tv, e.text && e.text.format) : String(tv ?? '')); }
      else skipped.add('mark ' + t); }); });
  if (skipped.size) el.insertAdjacentHTML('beforeend', `<span class="vlnote">not drawn (subset renderer; Vega-Lite online draws all): ${esc([...skipped].join(', '))}</span>`);
}

function hexA(hex, a) { if (!hex || !/^#[0-9a-f]{6}$/i.test(hex)) return hex || 'transparent'; const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a == null ? 1 : a})`; }

// ---- layout
const pagesEl = [...document.querySelectorAll('.page')];
const byId = {}; S.visuals.forEach(v => byId[v.id] = v);
const abs = id => { const v = byId[id]; return v; };
function draw(s, el) {
  const b = s.box, isGroup = s.type === 'group';
  const offX = s.group ? (byId[s.group].x || 0) : 0, offY = s.group ? (byId[s.group].y || 0) : 0;
  if (isGroup) { return; }
  Object.assign(el.style, {left: s.x + 'px', top: s.y + 'px', width: s.w + 'px', height: s.h + 'px', zIndex: s.z * 1000 + parseInt(s.id.split('V')[1])});
  if (b.bg) el.style.background = hexA(b.bg, b.bgAlpha);
  if (b.bgImage && b.bgImage.src && S.images[b.bgImage.src]) imgCss(el, b.bgImage);
  if (b.border) el.style.border = `${b.bw}px solid ${b.border}`;
  el.style.borderRadius = (b.radius || 0) + 'px';
  if (b.shadow) el.style.boxShadow = '0 1px 2px rgba(0,0,0,.06), 0 6px 16px rgba(0,0,0,.08)';
  el.style.padding = b.pad.map(p => p + 'px').join(' ');
  el.dataset.bg = b.bg || '#ffffff';
  const T = (D[s.id] || {}).titles || {};            // title measures evaluated by wireframe_data.py
  const ttl = k => b[k] && T[k] != null ? {...b[k], text: String(T[k]), measure: false} : b[k];
  const add_t = t => t && el.insertAdjacentHTML('beforeend', `<div class="ttl" style="font-family:'${t.family}';font-weight:${t.weight};font-size:${t.size}px;color:${t.color};text-align:${t.align}${t.measure ? ';font-style:italic' : ''}">${esc(t.text)}</div>`);
  const title = ttl('title'); add_t(title); add_t(ttl('subtitle'));
  const body = document.createElement('div'); body.className = 'body'; el.appendChild(body);
  body.style.display = 'flex'; body.style.flexDirection = 'column';
  const tagCls = s.type === 'deneb' || s.method === 'deneb' ? 'deneb' : s.method && /svg/.test(s.method) ? 'svg' : (s.method && /html/.test(s.method) ? 'html' : (s.known ? '' : 'unknown'));
  el.insertAdjacentHTML('beforeend', `<span class="badge">${s.id}</span><span class="tag ${tagCls}">${esc(s.tag)}</span>` +
    (s.pattern ? `<span class="ptn">pattern: ${esc(s.pattern)}</span>` : ''));
  {
    const w = Math.max(body.clientWidth, 10), h = Math.max(body.clientHeight, 10);
    try { (s.type === 'deneb' ? R.deneb : (s.pattern && P[s.pattern]) || R[s.render || s.type] || R._unknown)(s, body, w, h); } catch (e) { body.insertAdjacentHTML('beforeend', `<div class="placeholder">render error: ${esc(e.message)}</div>`); console.error(s.id, e); }
    const d = D[s.id]; if (!HAVE && !['textbox', 'shape', 'basicShape', 'actionButton', 'pageNavigator', 'bookmarkNavigator', 'group', 'image', 'deneb'].includes(s.type) && s.fields.length) body.insertAdjacentHTML('beforeend', '<span class="nodata">sample shape · no data</span>');
    if (d && d.hidden) body.insertAdjacentHTML('beforeend', `<span class="hiddenrows">${d.hidden} group(s) under the minimum hidden</span>`);
  }
  // what fidelity_check.py compares with Desktop: the visual type and its main text
  el.dataset.type = s.type;
  const own = ['textbox', 'actionButton', 'cardVisual', 'card'].includes(s.type);
  el.dataset.main = s.type === 'textbox' ? [...body.children].map(p => p.textContent).join(' ').replace(/\s+/g, ' ').trim() :
    s.type === 'actionButton' ? ((s.button || {}).text || '') : own ? (body.dataset.main || '') : ((title && title.text) || '');
  if (!own && title && title.measure) el.dataset.mainMeasure = '1';
}
S.pages.forEach((p, i) => { const el = pagesEl[i]; Object.assign(el.style, {width: p.w + 'px', height: p.h + 'px', background: p.bg});
  (p.walls || []).filter(im => im.src && S.images[im.src]).forEach(im => { const wl = document.createElement('div'); wl.className = 'wall';
    Object.assign(wl.style, {position: 'absolute', left: im.x + 'px', top: im.y + 'px', width: im.w + 'px', height: im.h + 'px', zIndex: 0, pointerEvents: 'none'});
    imgCss(wl, im); el.insertBefore(wl, el.firstChild); }); });
pagesEl.forEach(p => p.classList.add('on'));             // measure every page while it is shown, then hide
document.querySelectorAll('[data-id][hidden]').forEach(g => { g.hidden = false; g.dataset.wasHidden = '1'; });
document.querySelectorAll('[data-id]').forEach(el => { const s = byId[el.dataset.id]; if (s) draw(s, el); });
document.querySelectorAll('[data-was-hidden]').forEach(g => g.hidden = true);
// group members: positions are page coordinates in layout.json; groups are full-page layers
const tabs = document.getElementById('tabs');
S.pages.forEach((p, i) => { const b = document.createElement('button'); b.textContent = `${i + 1} ${p.name}`; b.onclick = () => show(i); tabs.appendChild(b); });
function fit() { const on = pagesEl.find(p => p.classList.contains('on')); if (!on) return; const k = document.body.classList.contains('shot') ? 1 : Math.min(1, (window.innerWidth - 32) / on.offsetWidth); on.style.transform = `scale(${k})`; document.getElementById('stage').style.height = (on.offsetHeight * k + 32) + 'px'; }
function show(i) { if (i < 0 || i >= pagesEl.length) return; pagesEl.forEach((p, k) => p.classList.toggle('on', k === i)); [...tabs.children].forEach((b, k) => b.classList.toggle('on', k === i)); fit(); }
window.addEventListener('resize', fit);
// Labels button: hides or shows the ID badges and the visual-type tags together (B and T still toggle each one)
const labelsBtn = document.getElementById('labels');
const labelsShown = () => !document.body.classList.contains('nobadge') && !document.body.classList.contains('notag');
function syncLabels() { const on = labelsShown(); labelsBtn.classList.toggle('on', on); labelsBtn.setAttribute('aria-pressed', String(on)); }
labelsBtn.onclick = () => { const hide = labelsShown(); document.body.classList.toggle('nobadge', hide);
  document.body.classList.toggle('notag', hide); syncLabels(); };
document.addEventListener('keydown', e => { if (e.target.tagName === 'INPUT') return; const k = e.key.toLowerCase();
  if (k === 'b') { document.body.classList.toggle('nobadge'); syncLabels(); } else if (k === 't') { document.body.classList.toggle('notag'); syncLabels(); }
  else if (/^[1-9]$/.test(k)) show(+k - 1); });
// URL hash: page=<n or key or name>, labels=off, shot (1:1, no toolbar: fidelity_check.py screenshots)
const HP = new URLSearchParams(location.hash.slice(1)), P0 = HP.get('page');
if (HP.get('labels') === 'off') { document.body.classList.add('nobadge', 'notag'); syncLabels(); }
if (HP.has('shot')) document.body.classList.add('shot');
show(P0 ? (/^\d+$/.test(P0) ? +P0 - 1 : S.pages.findIndex(p => p.key === P0 || p.name === P0)) : 0);
window.pageReady = Promise.allSettled(READY);
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--layout", default=str(ROOT / "design" / "specs" / "layout.json"))
    ap.add_argument("--tokens", default=str(ROOT / "design" / "tokens.json"))
    ap.add_argument("--theme", help="theme JSON (default: layout.json `theme`, else design/themes/*.json)")
    ap.add_argument("--data", default=str(ROOT / "design" / "wireframes" / "wireframe-data.json"),
                    help="wireframe_data.py output, or 'none'")
    ap.add_argument("--out", default=str(ROOT / "design" / "wireframes" / "wireframe.html"))
    ap.add_argument("--vega", choices=sorted(VEGA_MODES),
                    help="Deneb specs (default: layout.json `vega`, else cdn): cdn draws with Vega-Lite itself from "
                         "cdn.jsdelivr.net (pinned scripts, loaded when the page opens) and falls back to the built-in "
                         "subset renderer when they don't load; offline writes a page that loads nothing (auto and "
                         "subset are older names for the two)")
    a = ap.parse_args(argv)
    layout, tokens = load(a.layout), load(a.tokens)
    base = pathlib.Path(a.layout).resolve().parents[2]
    layout["_root"] = str(base)
    th = a.theme or (str(base / layout["theme"]) if layout.get("theme") else None)
    if not th:
        found = sorted((base / "design" / "themes").glob("*.json"))
        th = str(found[0]) if found else None
    if not th:                                   # the custom theme registered in the report
        for rj in base.glob("*.Report/definition/report.json"):
            name = load(rj).get("themeCollection", {}).get("customTheme", {}).get("name")
            f = rj.parents[1] / "StaticResources" / "RegisteredResources" / (name or "")
            if name and f.exists():
                th = str(f)
    theme = load(th) if th and pathlib.Path(th).exists() else None
    data = None
    if a.data != "none" and pathlib.Path(a.data).exists():
        data = load(a.data)
        if not data.get("privacy") or not any("passed" in x for x in data["privacy"]):
            sys.exit(f"{a.data}: no passed privacy check in the data file; rerun wireframe_data.py")
    title = next(iter(layout.get("pages", {}).values()), {}).get("displayName", "Wireframe") + " wireframe"
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(layout, tokens, theme, data, title, a.vega), encoding="utf-8")
    if MISSING_IMAGES:
        print(f"image file(s) not found, drawn as placeholders: {', '.join(sorted(set(MISSING_IMAGES)))}")
    missing = missing_alt_text(layout)
    if missing:
        print(f"alt text missing on {len(missing)} data visual(s): {', '.join(missing)} "
              "(layout.json container.altText; /plan writes one sentence each)")
    n = sum(1 for v in layout.get("visuals", []) if v["type"] not in TAGS)
    print(f"wrote {out} ({len(layout.get('visuals', []))} visuals, {len(layout.get('pages', {}))} page(s), "
          f"{'with' if data else 'no'} data{f', {n} placeholder type(s)' if n else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
