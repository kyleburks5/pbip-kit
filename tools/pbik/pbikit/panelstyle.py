"""`pbik layout panels`: the panel style layout (a house style, learned from the maintainer's Rep 9 report, v1.12).

One full-height panel per member of a small dimension (2 to 6 members) side by side under a dark header band; each
panel tells the same story for its member, top to bottom (Rep 9's sizes, on a 1920 x 1080 page):
  the member's name in its identity colour and a kit-drawn icon on a tinted circle; its share of the whole as a line
  and a progress bar; the big number with a change chip vs last year (green / red by the member's polarity) beside
  quarterly mini columns (compact labels: 2.3K); a 1 px rule; a threshold histogram (bars within the threshold in the
  member's colour, beyond it grey, a dashed "avg: 2.95" line, a light value axis, "Days to resolve" under it, and the
  "8,246 within SLA (88.1%) · SLA 5 days · avg 2.95 days" line); the top N of a category as slim full-width bars with
  the name above each bar and the value at its end.
The page holds nothing else: details are a drill-through page reached by right-clicking a bar (the top N).
More than 6 members: the grid or rail + panel style (design/themes/presets/README.md "Styles").

Input: a spec (design/specs/panels.json; SPEC_EXAMPLE, docs/patterns/panel-style-layout.md). Output, all in the
project (never the model): layout.json visuals (stable IDs by name; the page's other visuals retired unless `keep`
lists them), planned measures in generate.json, the preset's colours, sizes and member palette in tokens.json
(design/themes/presets/panel-style.json), and the icons as SVG + PNG (Edge) in design/images/.
Every piece is a native visual built by `pbik build` from the kit's templates; the icons are image visuals (step 2 on
the visual-method ladder), drawn by the kit (pbikit/icons.py), no outside icon pack.
"""
import json, pathlib, re

from . import icons as IC

KIT = pathlib.Path(__file__).resolve().parents[3]
PRESET = KIT / "design" / "themes" / "presets" / "panel-style.json"
SPEC_EXAMPLE = {
    "page": "P1",
    "dimension": "Channel[Interaction Type]",
    "members": ["Calls", "Chats", "Emails", "Escalations"],
    "memberMeta": {"Escalations": {"lowerIsBetter": True}},
    "header": {"title": "IT Service Ticket Overview",
               "definition": "Calls, chats, emails and escalations · counted by date received · within SLA = resolved "
                             "in no more than the channel's SLA days", "icon": "headset", "year": "Date[Year]",
               "yearDefault": 2023},
    "count": "[Interactions]", "countLabel": "Interactions", "countNoun": "interactions",
    "countLY": "[Interactions PY]", "share": "[Share of Interactions %]", "measureTable": "DataTable",
    "period": "Date[Quarter]",
    "distribution": {"column": "DataTable[Resolution Time (Days)]", "threshold": "[SLA Days]",
                     "average": "[Avg Resolution Days]", "within": "[Interactions Within SLA]",
                     "rate": "[SLA Compliance %]", "title": "Resolution time", "axis": "Days to resolve",
                     "unit": "days", "thresholdName": "SLA"},
    "top": {"field": "DataTable[Category]", "n": 5, "title": "Top 5 categories"},
    "date": "'Date'[Date]",
}
MAX_MEMBERS, MIN_MEMBERS = 6, 2
# Rep 9's panel geometry (px from the panel's top, on a 912 px panel); a shorter panel shrinks the histogram and the
# top N together
BAND_H, PANEL_Y, PANEL_H = 200, 136, 912
OFF = {"background": False, "border": False, "shadow": False, "padding": 0}
CARD_OFF = {"fillCustom.show@default": False, "fillCustom.transparency@default": 100,
            "cardCalloutArea.backgroundTransparency@default": 100, "layout.backgroundShow@none": False,
            "layout.backgroundTransparency@none": 100, "outline.show@default": False, "shadowCustom.show@default": False,
            "accentBar.show@default": False, "padding.paddingSelection@default": "Custom",
            "padding.topMargin@default": 0, "padding.bottomMargin@default": 0, "padding.leftMargin@default": 0,
            "padding.rightMargin@default": 0}


class PanelError(Exception):
    pass


# ---------------------------------------------------------------- colour
def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _hex(c):
    return "#" + "".join(f"{max(0, min(255, round(x))):02X}" for x in c)


def lum(h):
    c = [x / 255 for x in _rgb(h)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a, b, t):
    return _hex([x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))])


def identity(mark, card="#FFFFFF", text=None, tint=None):
    """(mark, text, tint): the mark 3:1 on the card (bars), the text shade 4.5:1 on the card and on the tint."""
    while contrast(mark, card) < 3:
        mark = mix(mark, "#000000", 0.06)
    tint = tint or mix(mark, card, 0.9)
    text = text or mark
    while contrast(text, card) < 4.5 or contrast(text, tint) < 4.5:
        text = mix(text, "#000000", 0.06)
    return mark, text, tint


def preset():
    try:
        return json.loads(PRESET.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def member_colours(members, meta, palette=None):
    """{member: (mark, text, tint)}: a member's own `color`, else the preset's member palette in order (Rep 9: blue,
    green, teal, red, then purple, amber), each checked for AA (text 4.5:1 on white and on its tint)."""
    pal = palette if palette is not None else preset().get("memberPalette") or []
    out, used = {}, 0
    for m in members:
        mm = meta.get(m) or {}
        if mm.get("color"):
            out[m] = identity(mm["color"])
            continue
        p = pal[used % len(pal)] if pal else {"mark": "#3A63D8"}
        used += 1
        out[m] = identity(p["mark"], text=p.get("text"), tint=p.get("tint"))
    return out


# ---------------------------------------------------------------- names
def key_of(member):
    k = re.sub(r"[^A-Za-z0-9]+", " ", str(member)).strip().title().replace(" ", "")
    return (k[:1].lower() + k[1:]) or "member"


def bare(f):
    return re.sub(r"^.*\[|\]$", "", str(f or ""))


def table(f):
    m = re.match(r"^'?([^'\[]+)'?\[", str(f or ""))
    return m.group(1) if m else None


def col_ref(f):
    return f"'{table(f)}'[{bare(f)}]"


def grid(layout):
    g = layout.get("grid") or {}
    canvas = g.get("canvas") or [1920, 1080]
    return canvas[0], canvas[1], g.get("margin", 32), g.get("columns", 12), g.get("gutter", 24)


def panel_boxes(n, layout):
    """x, w per panel: n equal panels across the content width with the gutter between (3 columns each for 4)."""
    width, _, margin, _, gutter = grid(layout)
    w = (width - 2 * margin - (n - 1) * gutter) / n
    return [(round(margin + i * (w + gutter)), round(w)) for i in range(n)]


# ---------------------------------------------------------------- measures
def bin_column(dist):
    """The whole-unit bin the histogram counts on: `<column> Bin` = ROUNDUP ( column, 0 ) (5.2 days is day 6, so a
    bar is wholly within or beyond a whole-day threshold), unless `bin` is false or the column is already whole."""
    if dist.get("bin") is False:
        return dist["column"]
    return f"{table(dist['column'])}[{bare(dist['column'])} Bin]"


def planned_columns(spec):
    """{table: {column: {expression, dataType}}}: the histogram's whole-unit bin."""
    dist = spec.get("distribution") or {}
    if not dist or dist.get("bin") is False:
        return {}
    return {table(dist["column"]): {f"{bare(dist['column'])} Bin": {
        "dataType": "int64", "expression": f"ROUNDUP ( {col_ref(dist['column'])}, 0 )  // whole-unit bins for the histogram"}}}


def measures(spec, colours, tokens):
    """The planned measures the panels use (Rep 9's display measures, named after the count measure)."""
    C, dim, dist, per = bare(spec["count"]), spec["dimension"], spec.get("distribution") or {}, spec.get("period")
    ly = bare(spec.get("countLY") or f"{C} PY")
    share = bare(spec.get("share") or f"Share of {C} %")
    tbl = spec.get("measureTable") or table(dist.get("column") or dim)
    col = tokens.get("colors", {})
    good, bad, neutral = col.get("good", "#13795B"), col.get("bad", "#B3261E"), col.get("neutral", "#4A5568")
    gt, bt, nt = col.get("goodTint", "#E4F4EE"), col.get("badTint", "#FCEAE8"), col.get("neutralTint", "#EDF0F5")
    lower = [m for m in spec["members"] if (spec.get("memberMeta", {}).get(m) or {}).get("lowerIsBetter")]
    sel = f"SELECTEDVALUE ( {col_ref(dim)} )"
    pol = f"IF ( {sel} IN {{ {', '.join(json.dumps(m) for m in lower)} }}, -1, 1 )" if lower else "1"
    year = (spec.get("header") or {}).get("year")
    P = {}
    if not spec.get("countLY"):
        P[ly] = {"table": tbl, "formatString": "#,0",
                 "expression": f"CALCULATE ( [{C}], SAMEPERIODLASTYEAR ( {spec.get('date', chr(39) + 'Date' + chr(39) + '[Date]')} ) )"}
    if not spec.get("share"):
        P[share] = {"table": tbl, "formatString": "0.0%",
                    "expression": f"DIVIDE ( [{C}], CALCULATE ( [{C}], REMOVEFILTERS ( '{table(dim)}' ) ) )"}
    noun = spec.get("countNoun", C.lower())
    P[f"{C} Share Rest"] = {"table": tbl, "formatString": "0.0%",
                            "expression": f"IF ( ISBLANK ( [{share}] ), BLANK (), 1 - [{share}] )"}
    P[f"{C} Share Title"] = {"table": tbl, "dataType": "string", "expression":
                             f"IF ( ISBLANK ( [{share}] ), \"–\", FORMAT ( [{share}], \"0.0%\" ) & \" of all {noun}\" )"}
    vs = (f"VAR _Y = SELECTEDVALUE ( {col_ref(year)} ) VAR _Vs = IF ( ISBLANK ( _Y ), \"vs last year\", \"vs \" & ( _Y - 1 ) ) "
          f"VAR _No = IF ( ISBLANK ( _Y ), \"No last year\", \"No \" & ( _Y - 1 ) & \" data\" ) ") if year else \
        "VAR _Vs = \"vs last year\" VAR _No = \"No last year\" "
    P[f"{C} Change Text"] = {"table": tbl, "dataType": "string", "expression":
                             f"VAR _N = [{C}] VAR _PY = [{ly}] VAR _D = _N - _PY VAR _P = DIVIDE ( _D, _PY ) {vs}"
                             f"VAR _Sign = IF ( _D > 0, \"+\", IF ( _D < 0, \"−\", \"\" ) ) "
                             f"RETURN IF ( ISBLANK ( _N ), \"–\", IF ( ISBLANK ( _PY ), _No, "
                             f"IF ( _D > 0, \"▲ \", IF ( _D < 0, \"▼ \", \"■ \" ) ) & _Sign & FORMAT ( ABS ( _D ), \"#,0\" ) "
                             f"& \" · \" & _Sign & FORMAT ( ABS ( _P ), \"0.0%\" ) & \" \" & _Vs ) )"}
    for nm, g_, b_, n_ in ((f"{C} Change Font", good, bad, neutral), (f"{C} Change Fill", gt, bt, nt)):
        P[nm] = {"table": tbl, "dataType": "string", "expression":
                 f"VAR _D = [{C}] - [{ly}] VAR _Up = {pol} RETURN IF ( ISBLANK ( [{ly}] ) || _D = 0, \"{n_}\", "
                 f"IF ( _D * _Up > 0, \"{g_}\", \"{b_}\" ) )"}
    if per:
        P[f"Y Axis Max {bare(per)}"] = {"table": tbl, "formatString": "0", "expression":
                                        f"MAXX ( VALUES ( {col_ref(per)} ), [{C}] ) * 1.3"}
    if dist:
        name = dist.get("title", "Distribution")
        out_sla = col.get("outSla", "#C5CCD8")
        binc = bin_column(dist)
        cases = ", ".join(f"{json.dumps(m)}, \"{colours[m][0]}\"" for m in spec["members"])
        P[f"{name} Bar Colour"] = {"table": tbl, "dataType": "string", "expression":
                                   f"VAR _X = SELECTEDVALUE ( {col_ref(binc)} ) VAR _T = {dist['threshold']} "
                                   f"RETURN IF ( ISBLANK ( _X ) || ISBLANK ( _T ) || _X > _T, \"{out_sla}\", "
                                   f"SWITCH ( {sel}, {cases}, \"{out_sla}\" ) )"}
        unit, tn = dist.get("unit", ""), dist.get("thresholdName", "target")
        P[f"{name} Subtitle"] = {"table": tbl, "dataType": "string", "expression":
                                 f"IF ( ISBLANK ( [{C}] ), \"–\", FORMAT ( {dist['within']}, \"#,0\" ) & \" within {tn} (\" & "
                                 f"FORMAT ( {dist['rate']}, \"0.0%\" ) & \") · {tn} \" & {dist['threshold']} & \" {unit} · avg \" "
                                 f"& FORMAT ( {dist['average']}, \"0.00\" ) & \" {unit}\" )"}
        P[f"Y Axis Max {name}"] = {"table": tbl, "formatString": "0", "expression":
                                   f"MAXX ( VALUES ( {col_ref(binc)} ), [{C}] ) * 1.3"}
        # the x axis ends at the data: the 99th percentile or twice the threshold, whichever is larger, never past
        # the longest bin (one bin's room beyond it, so the last bar is whole)
        P[f"X Axis Max {name}"] = {"table": tbl, "formatString": "0", "expression":
                                   f"VAR _hi = MAX ( {col_ref(binc)} ) VAR _p = PERCENTILE.INC ( {col_ref(binc)}, 0.99 ) "
                                   f"VAR _t = {dist['threshold']} RETURN MIN ( _hi, MAX ( _p, 2 * _t ) ) + 0.5"}
    top = spec.get("top")
    if top:
        P["Top Bar Spacer"] = {"table": tbl, "formatString": "0", "expression": "0"}
        P[f"{bare(top['field'])} Bar Label"] = {"table": tbl, "dataType": "string",
                                               "expression": f"SELECTEDVALUE ( {col_ref(top['field'])} )"}
    return P, ly, share


# ---------------------------------------------------------------- the visuals
def make(spec, layout, tokens, used_ids=()):
    """(visuals, planned measures, colour tokens, icons). IDs: the next free numbers on the page in reading order
    (the header, then each panel top to bottom); run() keeps an earlier run's IDs by name."""
    members = list(spec.get("members") or [])
    if not MIN_MEMBERS <= len(members) <= MAX_MEMBERS:
        raise PanelError(f"the panel style layout compares {MIN_MEMBERS} to {MAX_MEMBERS} members side by side; "
                         f"{len(members)} given: use the grid or rail + panel style for more")
    page, meta = spec.get("page", "P1"), spec.get("memberMeta") or {}
    colours = member_colours(members, meta)
    P, ly, share = measures(spec, colours, tokens)
    C = bare(spec["count"])
    tbl = spec.get("measureTable") or table(spec["dimension"])
    used = set(used_ids) | {x for x in (spec.get("reuse") or {}).values()}
    counter = [0]

    def nid():
        counter[0] += 1
        while f"{page}-V{counter[0]:02d}" in used:
            counter[0] += 1
        used.add(f"{page}-V{counter[0]:02d}")
        return f"{page}-V{counter[0]:02d}"

    V, toks, icons = [], {}, {}
    width, height, margin, _, _ = grid(layout)
    band_h = spec.get("band", BAND_H)
    hd = spec.get("header") or {}
    reuse = spec.get("reuse") or {}

    def add(v, role=None):
        v.setdefault("page", page)
        v.setdefault("build", {"method": "native", "step": 1, "reason": v.pop("_why", "Panel style layout")})
        v.pop("_why", None)
        v["id"] = reuse[role] if role and reuse.get(role) else nid()
        V.append(v)
        return v

    image_build = {"method": "image", "step": 2, "nativeTried": "a text box with a Unicode glyph",
                   "reason": "a glyph can't sit on a tinted circle at a steady size; a kit-drawn picture can"}
    add({"name": "header-band", "type": "shape", "x": 0, "y": 0, "w": width, "h": band_h, "z": 0, "decorative": True,
         "style": {"fill": "header", "radius": 0}, "container": {"keepLayerOrder": True, "shadow": False},
         "_why": "Shape: the full-width dark header band"}, "band")
    tx = margin
    if hd.get("icon"):
        icons[hd["icon"] + "-header"] = IC.svg(hd["icon"], fg=tokens.get("colors", {}).get("onDark", "#FFFFFF"), bg=None, size=56)
        add({"name": "header-icon", "type": "image", "x": margin, "y": 36, "w": 56, "h": 56, "z": 1, "decorative": True,
             "image": f"design/images/{hd['icon']}-header.png", "scaling": "Fit", "container": dict(OFF),
             "build": dict(image_build)})
        tx = 108
    add({"name": "header-title", "type": "textbox", "tabOrder": 110, "x": tx, "y": 34, "w": 840, "h": 40, "z": 1,
         "container": "off",
         "text": [{"runs": [{"text": hd.get("title", "Overview"), "font": "semibold", "size": "title", "color": "onDark"}]}],
         "_why": "Text box: the page title on the band"}, "title")
    if hd.get("year"):
        add({"name": "year", "type": "slicer", "tabOrder": 120, "x": width - margin - 160, "y": 40, "w": 160, "h": 48,
             "z": 1, "bindings": {"Values": [hd["year"]]}, "slicerMode": "dropdown",
             **({"selection": {"field": hd["year"], "values": [hd["yearDefault"]]}} if hd.get("yearDefault") else {}),
             "props": {"selection.singleSelect": True, "selection.strictSingleSelect": True,
                       "selection.selectAllCheckboxEnabled": False, "header.show": False,
                       "items.fontFamily": "Segoe UI Semibold", "items.textSize": "body", "items.fontColor": "onDark",
                       "items.background": {"color": "headerControl"}, "items.outlineStyle": 0,
                       "general.outlineColor": "headerControl", "general.outlineWeight": 1},
             "container": {"background": False, "border": False, "shadow": False, "padding": [4, 6, 4, 10]},
             "_why": "Year dropdown on the band, single select"})
    if hd.get("definition"):
        add({"name": "header-definition", "type": "textbox", "tabOrder": 130, "x": tx, "y": 76,
             "w": width - margin - 160 - 24 - tx, "h": 24, "z": 1, "container": "off",
             "text": [{"runs": [{"text": hd["definition"], "size": "subtitle", "color": "onDarkMuted"}]}],
             "_why": "Text box: what the numbers count (the definition line)"})
    area = spec.get("area") or {"y": PANEL_Y, "h": height - PANEL_Y - margin}
    y0, ph = area["y"], area["h"]
    dist, top, per = spec.get("distribution"), spec.get("top"), spec.get("period")
    dim = spec["dimension"]
    label = spec.get("countLabel", C)
    noun = spec.get("countNoun", C.lower())
    rest = ph - 288 - 24                                     # Rep 9: histogram 332 + gap 24 + top 244 = 600
    hist_h = round(rest * 296 / 600) if top else rest   # the top N gets room for a name above each bar
    top_h = rest - hist_h - 24 if top else 0
    for (x0, pw), m in zip(panel_boxes(len(members), layout), members):
        k = key_of(m)
        mark, text, tint = colours[m]
        toks.update({k: mark, f"{k}Text": text, f"{k}Tint": tint})
        mm = meta.get(m) or {}
        flt = [{"field": dim, "values": [m], "hidden": True}]
        ix, iw = x0 + 24, pw - 48
        kw = round(iw * 214 / 398)                          # Rep 9: card 214 + 40 + columns 168 in 398
        qx, qw = ix + iw - round(iw * 168 / 398), round(iw * 168 / 398)
        add({"name": f"{k}-panel", "type": "shape", "pattern": "panel-style-layout", "x": x0, "y": y0, "w": pw, "h": ph, "z": 2,
             "decorative": True, "style": {"fill": "card", "radius": "radius"},
             "container": {"keepLayerOrder": True, "shadow": True}, "_why": f"Shape: the {m} panel"})
        add({"name": f"{k}-title", "type": "textbox", "x": ix, "y": y0 + 22, "w": round(iw * 300 / 398), "h": 36, "z": 3,
             "container": "off", "text": [{"runs": [{"text": m, "font": "semibold", "size": "cardTitle", "color": f"{k}Text"}]}],
             "_why": "Text box: the member's name in its identity colour"})
        icons[k] = IC.svg(mm.get("icon") or IC.guess(m), fg=text, bg=tint, size=52)
        add({"name": f"{k}-icon", "type": "image", "x": x0 + pw - 24 - 52, "y": y0 + 14, "w": 52, "h": 52, "z": 3,
             "decorative": True, "image": f"design/images/{k}.png", "scaling": "Fit", "container": dict(OFF),
             "build": dict(image_build)})
        add({"name": f"{k}-share-title", "type": "cardVisual", "x": ix, "y": y0 + 60, "w": iw, "h": 32, "z": 4,
             "bindings": {"Data": [f"[{C} Share Title]"]}, "filters": flt, "comparison": "the share bar under it (the whole)",
             "preview": "{value:[" + share + "]|0.0%} of all " + noun,
             "props": {**CARD_OFF, "label.show@default": False, "value.fontFamily@default": "Segoe UI",
                       "value.fontSize@default": "subtitle", "value.fontColor@default": "textMuted",
                       "value.horizontalAlignment@default": "left", "layout.calloutSize@none": 100,
                       "layout.alignment@none": "left"},
             "container": {**OFF, "altText": f"{m} share of all {noun}"}, "_why": "New card: the share line"})
        add({"name": f"{k}-share-bar", "type": "hundredPercentStackedBarChart", "x": ix, "y": y0 + 80, "w": iw, "h": 60,
             "z": 3, "bindings": {"Category": [dim], "Y": [{"field": f"[{share}]", "displayName": "Share"},
                                                          {"field": f"[{C} Share Rest]", "displayName": "Rest"}]},
             "filters": flt, "sort": {"field": f"[{share}]", "direction": "Descending"},
             "props": {"categoryAxis.show": False, "categoryAxis.innerPadding": 50, "categoryAxis.showAxisTitle": False,
                       "valueAxis.show": False, "valueAxis.gridlineShow": False, "valueAxis.showAxisTitle": False,
                       "legend.show": False, "labels.show": False,
                       f"dataPoint.fill@[{share}]": k, f"dataPoint.fill@[{C} Share Rest]": "track"},
             "container": {**OFF, "title": False, "altText": f"Bar showing the {m} share of all {noun}"},
             "_why": "100% stacked bar: the share as a progress bar"})
        add({"name": f"{k}-kpi", "type": "cardVisual", "x": ix, "y": y0 + 136, "w": kw, "h": 128, "z": 3,
             "bindings": {"Data": [{"field": spec["count"], "displayName": label}]}, "filters": flt,
             "referenceLabels": {"titleOff": True, "layout": None, "detailSize": "chip", "valueFont": "semibold",
                                 "labels": [{"title": "YoY", "value": f"[{ly}]", "detail": f"[{C} Change Text]",
                                             "detailColor": f"[{C} Change Font]",
                                             "detailBackground": f"[{C} Change Fill]", "chip": True,
                                             "lowerIsBetter": bool(mm.get("lowerIsBetter")),
                                             "preview": "{delta:" + spec["count"] + "|[" + ly + "]|"
                                                        + (str(int(hd["yearDefault"]) - 1) if hd.get("yearDefault") else "") + "}"}]},
             "props": {**CARD_OFF, "label.show@default": True, "label.position@default": "aboveValue",
                       "label.fontFamily@default": "Segoe UI", "label.fontSize@default": "caption",
                       "label.fontColor@default": "textMuted", "value.fontFamily@default": "Segoe UI Semibold",
                       "value.fontSize@default": "kpi", "value.fontColor@default": "text",
                       "value.horizontalAlignment@default": "left", "value.labelDisplayUnits@default": 1,
                       "value.showBlankAs@default": "–", "layout.calloutSize@none": 60,
                       "layout.alignment@none": "left", "padding.leftMargin@default": 4},
             "container": {**OFF, "altText": f"{m} {noun} in the selected year, with the change versus the year before"},
             "_why": "New card: the big number with its change chip"})
        if per:
            add({"name": f"{k}-quarters", "type": "clusteredColumnChart", "x": qx, "y": y0 + 136, "w": qw, "h": 128, "z": 3,
                 "bindings": {"Category": [per], "Y": [{"field": spec["count"], "displayName": label}]},
                 "filters": flt, "sort": {"field": per, "direction": "Ascending", "default": True},
                 "cf": [{"type": "measure", "object": "valueAxis", "property": "end", "measure": f"[Y Axis Max {bare(per)}]",
                         "kind": "value"}],
                 "props": {"categoryAxis.show": True, "categoryAxis.fontSize": "caption",
                           "categoryAxis.labelColor": "textMuted", "categoryAxis.showAxisTitle": False,
                           "categoryAxis.innerPadding": 30, "categoryAxis.gridlineShow": False, "valueAxis.show": False,
                           "valueAxis.gridlineShow": False, "valueAxis.showAxisTitle": False, "valueAxis.start": 0,
                           "legend.show": False, "labels.show": True, "labels.fontSize": "caption",
                           "labels.color": "text", "labels.labelDisplayUnits": 0,
                           "labels.enableBackground": False, "labels.labelPosition": "OutsideEnd", "dataPoint.fill": k},
                 "container": {**OFF, "title": False, "subtitle": False,
                               "altText": f"{m} {noun} by {bare(per).lower()} in the selected year"},
                 "_why": "Column chart: quarterly mini columns, compact labels (2.3K, display units Auto)"})
        add({"name": f"{k}-divider", "type": "shape", "x": ix, "y": y0 + 276, "w": iw, "h": 1, "z": 3, "decorative": True,
             "style": {"fill": "rule", "radius": 0}, "container": "off", "_why": "Shape: a 1 px rule"})
        if dist:
            name = dist.get("title", "Distribution")
            tn = dist.get("thresholdName", "target")
            add({"name": f"{k}-histogram", "type": "clusteredColumnChart", "pattern": "threshold-histogram",
                 "x": ix, "y": y0 + 288, "w": iw, "h": hist_h, "z": 3,
                 "bindings": {"Category": [bin_column(dist)], "Y": [{"field": spec["count"], "displayName": label}]},
                 "filters": flt, "sort": {"field": bin_column(dist), "direction": "Ascending", "default": True},
                 "cf": [{"type": "measure", "object": "dataPoint", "property": "fill", "measure": f"[{name} Bar Colour]",
                         "perPoint": True, "split": {"at": dist["threshold"], "within": k, "beyond": "outSla"}},
                        {"type": "measure", "object": "valueAxis", "property": "end", "measure": f"[Y Axis Max {name}]",
                         "kind": "value"},
                        {"type": "measure", "object": "categoryAxis", "property": "end", "measure": f"[X Axis Max {name}]",
                         "kind": "value"}],
                 "referenceLines": [{"axis": "category", "value": dist["average"], "label": "avg", "color": "text",
                                     "style": "dashed", "width": 1, "labelVertical": "above",
                                     "labelHorizontal": "right"}],
                 "props": {"categoryAxis.show": True, "categoryAxis.axisType": "Scalar", "categoryAxis.fontSize": "caption",
                           "categoryAxis.labelColor": "textMuted", "categoryAxis.showAxisTitle": True,
                           "categoryAxis.titleText": dist.get("axis", bare(dist["column"])),
                           "categoryAxis.titleFontSize": "caption", "categoryAxis.titleColor": "textMuted",
                           "categoryAxis.gridlineShow": False, "categoryAxis.innerPadding": 12,
                           "categoryAxis.start": 0.5,
                           "valueAxis.show": True, "valueAxis.fontSize": "caption", "valueAxis.labelColor": "textMuted",
                           "valueAxis.showAxisTitle": False, "valueAxis.start": 0, "valueAxis.gridlineShow": True,
                           "valueAxis.gridlineColor": "divider", "valueAxis.gridlineThickness": 1,
                           "valueAxis.labelDisplayUnits": 1, "valueAxis.labelPrecision": 0, "legend.show": False,
                           "labels.show": False, 'xAxisReferenceLine.dataLabelDecimalPoints@{"id": "1"}': 2,
                           "dataPoint.fill": k},
                 "container": {**OFF, "title": {"text": name, "size": "chartTitle", "color": "text"},
                               "subtitle": {"measure": f"[{name} Subtitle]", "size": "caption", "color": f"{k}Text",
                                            "preview": "{value:" + dist["within"] + "|#,0} within " + tn + " ({value:"
                                                       + dist["rate"] + "|0.0%}) · " + tn + " {value:" + dist["threshold"]
                                                       + "|0} " + dist.get("unit", "") + " · avg {value:" + dist["average"]
                                                       + "|0.00} " + dist.get("unit", "")},
                               "altText": f"{m} {noun} by {dist.get('axis', 'value').lower()} in the selected year; bars "
                                          f"within the {tn} in colour, the rest in grey, dashed line at the average"},
                 "_why": "Column chart on a continuous axis: the threshold histogram"})
        if top:
            n = int(top.get("n", 5))
            spacer = f"{tbl}.Top Bar Spacer"
            sel_ = json.dumps({"metadata": spacer})
            agg = {"raw": {"expr": {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {
                "Entity": table(top["field"])}}, "Property": bare(top["field"])}}, "Function": 3}}}}
            add({"name": f"{k}-top", "type": "clusteredBarChart", "pattern": "label-above-bars",
                 "x": ix, "y": y0 + 288 + hist_h + 24, "w": iw, "h": top_h, "z": 3,
                 "bindings": {"Category": [top["field"]],
                              "Y": [{"field": "[Top Bar Spacer]", "displayName": bare(top["field"])},
                                    {"field": spec["count"], "displayName": label}]},
                 "filters": flt + [{"type": "TopN", "field": top["field"], "by": spec["count"], "n": n, "direction": "Top"}],
                 "sort": {"field": spec["count"], "direction": "Descending", "default": True},
                 "props": {"categoryAxis.show": False, "categoryAxis.showAxisTitle": False,
                           "categoryAxis.maxMarginFactor": 40, "categoryAxis.innerPadding": 25,
                           "layout.clusteredGapSize": 30, "valueAxis.show": False, "valueAxis.gridlineShow": False,
                           "valueAxis.showAxisTitle": False, "valueAxis.start": 0, "legend.show": False,
                           "labels.show": True, "labels.color": "text", "labels.fontSize": "caption",
                           "labels.fontFamily": "Segoe UI", "labels.labelPosition": "OutsideEnd",
                           "labels.labelDisplayUnits": 1, "labels.labelPrecision": {"int": 0},
                           "labels.enableBackground": False,
                           f"labels.showSeries@{sel_}": True, f"labels.labelPosition@{sel_}": "OutsideEnd",
                           f"labels.labelOverflow@{sel_}": True, f"labels.horizontalAlignment@{sel_}": "left",
                           f"labels.enableTitleDataLabel@{sel_}": False, f"labels.enableValueDataLabel@{sel_}": False,
                           f"labels.enableDetailDataLabel@{sel_}": True,
                           f"labels.dynamicLabelDetail@{sel_}": {"expr": f"[{bare(top['field'])} Bar Label]"},
                           f"labels.detailColor@{sel_}": "text", f"labels.detailFontSize@{sel_}": "caption",
                           f"labels.detailFontFamily@{sel_}": "Segoe UI",
                           "labels.dynamicLabelDetail@" + json.dumps({"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                                                       "metadata": spacer, "highlightMatching": 1}): agg,
                           f"dataPoint.fill@{spec['count']}": k,
                           "dataPoint.fill@[Top Bar Spacer]": "card", 'y1AxisReferenceLine.show@{"id": "1"}': False},
                 "container": {**OFF, "title": {"text": top.get("title", f"Top {n}"), "size": "chartTitle", "color": "text"},
                               "subtitle": False,
                               "altText": f"The {n} {bare(top['field']).lower()} values with the most {m.lower()} in the "
                                          "selected year; right-click a bar to drill through"},
                 "_why": "Bar chart: the name above each slim bar (a zero spacer series carries it), the value at the end"})
    toks.setdefault("outSla", tokens.get("colors", {}).get("outSla", "#C5CCD8"))
    return numeric_sizes(V), P, toks, icons


MIN_PT = 10


def numeric_sizes(V):
    """Rep 9's text sizes as numbers from the preset (a project's own `kpi` may be smaller), none under 10 pt."""
    fp = {k: v for k, v in (preset().get("fontPt") or {}).items() if not k.startswith("_")}

    def fix(x):
        if isinstance(x, dict):
            for k, val in list(x.items()):
                key = k.split("@")[0]
                sizey = key in ("size", "detailSize", "valueSize") or key.endswith(("fontSize", "FontSize", "textSize"))
                if sizey and isinstance(val, str) and val in fp:
                    x[k] = max(MIN_PT, fp[val])
                elif sizey and isinstance(val, (int, float)) and not isinstance(val, bool):
                    x[k] = max(MIN_PT, val)
                else:
                    fix(val)
        elif isinstance(x, list):
            for i in x:
                fix(i)
    fix(V)
    return V


def interactions(visuals, spec):
    """Each panel's charts filter only their own panel (a click in Calls never empties Chats)."""
    page = spec.get("page", "P1")
    panels = {}
    for v in visuals:
        if v.get("page") == page and v.get("bindings") and v["type"] != "slicer" and "-" in v.get("name", ""):
            panels.setdefault(v["name"].split("-", 1)[0], []).append(v["id"])
    out = []
    for k, ids in panels.items():
        others = [x for k2, l2 in panels.items() if k2 != k for x in l2]
        out += [{"source": x, "targets": others, "type": "NoFilter"} for x in ids]
    return out


def apply_preset(tokens, overwrite=False):
    """The panel style preset's colours, sizes, container and header into tokens.json (missing names only, unless
    overwrite): Rep 9's band, background, chip tints, outSla, track, rule and the subtitle / chartTitle / chip sizes."""
    pre = preset()
    for sec in ("colors", "fontPt", "font", "container", "chip", "header"):
        src = pre.get(sec) or {}
        dst = tokens.setdefault(sec, {})
        for k, v in src.items():
            if k.startswith("_"):
                continue
            if overwrite or k not in dst:
                dst[k] = v
    return tokens


def run(root, spec_path, layout_path=None, render_png=True):
    """Write the panels into layout.json (the page's other visuals retired, unless the spec's `keep` lists them), the
    measures into generate.json, the preset and identity colours into tokens.json, and the icons into design/images/.
    An earlier run's visuals keep their IDs by name. Returns plain lines."""
    from .objects import stable_id
    root = pathlib.Path(root)
    spec = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    lf = pathlib.Path(layout_path) if layout_path else root / "design" / "specs" / "layout.json"
    lay = json.loads(lf.read_text(encoding="utf-8"))
    tf, gf = root / "design" / "tokens.json", root / "design" / "specs" / "generate.json"
    tokens = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else {"colors": {}}
    apply_preset(tokens)
    for k in ("header", "background", "onDarkMuted", "headerControl", "outSla", "track", "rule", "divider",
              "goodTint", "badTint", "neutralTint", "good", "bad", "neutral"):   # Rep 9's look: these follow the preset
        if spec.get("presetColors", True) and (preset().get("colors") or {}).get(k):
            tokens["colors"][k] = preset()["colors"][k]
    page = spec.get("page", "P1")
    keep_ids = set(spec.get("keep") or [])
    old = [v for v in lay.get("visuals", []) if v.get("page") == page and v.get("panelStyle")]
    disk = {}
    try:                                                 # what an earlier build made: the same name keeps its ID
        vm = json.loads((root / "design" / "specs" / "visual-map.json").read_text(encoding="utf-8")).get("visuals") or {}
        disk = {e["name"]: vid for vid, e in vm.items() if e.get("page") == page and e.get("name")
                and vid not in set(lay.get("retired", []))}
    except (OSError, ValueError):
        pass
    by_name = dict(disk)                                 # what is on disk wins over an unbuilt layout
    for v in old:
        if v["name"] not in by_name and v["id"] not in disk.values():
            by_name[v["name"]] = v["id"]
    others = [v for v in lay.get("visuals", []) if v.get("page") == page and not v.get("panelStyle")
              and v["id"] not in keep_ids and v["id"] not in (spec.get("reuse") or {}).values()]
    keep = [v for v in lay.get("visuals", []) if v not in old and v not in others
            and v["id"] not in (spec.get("reuse") or {}).values()]
    used = {v["id"] for v in keep} | set(lay.get("retired", [])) | {v["id"] for v in others}   # never reuse an ID
    V, P, toks, icons = make(spec, lay, tokens, used_ids=used)
    taken = set(used) | set(by_name.values())           # never hand out an ID a built visual has
    kept_ids = {v["name"]: by_name[v["name"]] for v in V if v["name"] in by_name}
    taken |= set(kept_ids.values()) | set((spec.get("reuse") or {}).values())
    n = 0
    for v in V:                                          # same name as last time: same ID (stable across runs)
        if v["name"] in kept_ids:
            v["id"] = kept_ids[v["name"]]
        elif v["id"] in taken and v["id"] not in (spec.get("reuse") or {}).values():
            while True:
                n += 1
                cand = f"{page}-V{n:02d}"
                if cand not in taken:
                    break
            v["id"] = cand
        taken.add(v["id"])
        v["panelStyle"] = True
    home = spec.get("countTable") or spec.get("measureTable") or table(spec["dimension"])
    for v in V:                                          # the chip card: last year's value hidden, only the chip shows
        if v["name"].endswith("-kpi"):
            ref = f"{home}.{bare(spec['count'])}"
            v["props"]["referenceLabelValue.show@" + json.dumps({"metadata": ref, "id": stable_id(v["id"], ref, "YoY")})] = False
    gone = sorted((set(by_name.values()) - {v["id"] for v in V}) | {v["id"] for v in others})
    lay["retired"] = sorted(set(lay.get("retired", [])) | set(gone))
    lay["visuals"] = keep + V
    lay.setdefault("pages", {}).setdefault(page, {})["interactions"] = interactions(V, spec)
    lay["_layoutStyle"] = "panel style layout"
    lf.write_text(json.dumps(lay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    g = json.loads(gf.read_text(encoding="utf-8")) if gf.exists() else {}
    g.setdefault("plannedMeasures", {}).update(P)
    for t_, cols_ in planned_columns(spec).items():
        g.setdefault("plannedColumns", {}).setdefault(t_, {}).update(cols_)
    gf.parent.mkdir(parents=True, exist_ok=True)
    gf.write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tokens["colors"].update(toks)
    tf.write_text(json.dumps(tokens, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_dir = root / "design" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    pngs = 0
    for name, svg in icons.items():
        (out_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
        if render_png:
            try:
                import sys
                sys.path.insert(0, str(KIT / "design" / "scripts"))
                import svg_to_png
                svg_to_png.render(svg, out_dir / f"{name}.png", scale=4)
                pngs += 1
            except Exception:                            # no Edge: the SVG is used instead (pbik resource add takes it)
                pass
    if pngs < len(icons):
        for v in V:
            if v["type"] == "image":
                v["image"] = v["image"][:-4] + ".svg"
        lf.write_text(json.dumps(lay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return [f"panel style layout: {len(spec['members'])} panels on {page}, {len(V)} visuals, {len(P)} planned measures, "
            f"{len(icons)} icons ({'PNG' if pngs == len(icons) else 'SVG'})"] + \
        ([f"retired: {', '.join(gone)}"] if gone else [])
