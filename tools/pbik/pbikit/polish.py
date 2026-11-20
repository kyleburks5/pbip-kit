"""`pbik layout polish`: the kit's polish defaults written into layout.json before the plan picture (v1.7 walkthrough
fix 15), so the person approves what will be built and the polish score checks it.

What it does, each only where the layout doesn't say otherwise (it never removes anything; run it again: no change):
- KPI cards: a comparison label ("vs last year" with a % change measure) becomes last year's value with the change
  beside it as the detail, ▲ / ▼ and green / red by direction (a colour measure on the detail: the Rep 2 pattern, the
  form Desktop renders; a wildcard rule on the detail colour doesn't), at body size; the value centred so the card
  fills its space. The measures it needs (last year, the colour) are planned measures (design/specs/generate.json
  `plannedMeasures`): the synthetic model gets them, and `bind prepare` keeps them in the report on a live model.
- Tables: a "vs" / change column is coloured by direction (rules: good at 0 and above, bad below).
- The top row: a header band (a decorative shape behind the title and the filter, the full canvas width) and the
  filter styled as part of it (no box of its own: it sits in the band).
"Lower is better" (v1.7 live walkthrough fix 10): layout.json `lowerIsBetter` lists the measures where a fall is good
(returns, costs); measures named like that (returns, refunds, costs, complaints, churn, defects ...) are added with a
note the person can change. Their change is ▼ green / ▲ red, in the colour measures and the plan picture alike.
Line charts drawn straight, larger titles, axis labels and legends, and bar labels without needless decimals come
from the theme (design/scripts/gen_theme.py and the kit's tokens), not from here.
"""
import json, pathlib, re

CMP = re.compile(r"\bvs\b|change|growth|variance|\bdiff|delta|\byoy\b", re.I)     # a share is no comparison
LY_IN = re.compile(r"SAMEPERIODLASTYEAR\s*\(\s*([^)]+?)\s*\)", re.I)
ARROWS = '"▲ "0.0%;"▼ "0.0%;0.0%'
LOWER = re.compile(r"\b(returns?|refunds?|costs?|expenses?|spend|complaints?|churn|defects?|errors?|incidents?|"
                   r"cancell?ations?|late|delays?|overdue|backlog|absen\w*|turnover|write.?offs?|bad debt|losses|loss)\b",
                   re.I)



def _card_align(tokens):
    """KPI card alignment from the tokens' `card.align` (a preset setting: left, center or right); left when the tokens
    don't say (v1.12: label, value, comparison and chart line up on the left edge)."""
    a = ((tokens or {}).get("card") or {}).get("align")
    return a if a in ("left", "center", "right") else "left"


def lower_is_better(layout, name):
    """True when a fall in this measure is good: layout.json `lowerIsBetter` (names, or {name: false} to say no)."""
    lib = layout.get("lowerIsBetter")
    n = (name or "").strip("[]")
    if isinstance(lib, dict):
        for k, v in lib.items():
            if k.strip("[]").lower() == n.lower():
                return bool(v)
    elif isinstance(lib, list) and any(k.strip("[]").lower() == n.lower() for k in lib):
        return True
    return False


def _colour(cmp_name, good, bad, lower):
    """The colour measure: green when the change goes the good way (up, or down for lower-is-better)."""
    op = "<=" if lower else ">="
    return (f'IF ( ISBLANK ( [{cmp_name}] ), BLANK (), IF ( [{cmp_name}] {op} 0, "{good}", "{bad}" ) )')


def _field(x):
    return (x.get("field") if isinstance(x, dict) else x) or ""


def name_of(field):
    f = _field(field)
    return f.split("[", 1)[-1].rstrip("]") if "[" in f else f


def table_of(field):
    f = _field(field)
    t = f.split("[", 1)[0].strip("'") if "[" in f else ""
    return t or None


def is_comparison(field):
    return bool(CMP.search(name_of(field)))


def _next_id(layout, page):
    used = {v["id"] for v in layout.get("visuals", [])} | set(layout.get("retired", []))
    n = 1
    while f"{page}-V{n:02d}" in used:
        n += 1
    return f"{page}-V{n:02d}"


def _base(field, planned):
    """The KPI measure a comparison measure compares (from its planned DAX: the first [Measure] it uses)."""
    p = planned.get(name_of(field)) or {}
    m = re.search(r"\[([^\]]+)\]", p.get("expression", ""))
    return m.group(1) if m else None


def _date_of(field, planned):
    p = planned.get(name_of(field)) or {}
    m = LY_IN.search(p.get("expression", ""))
    return m.group(1) if m else None


def polish(layout, tokens=None, planned=None, measures=None, expressions=None):
    """Apply the defaults in place. Returns plain lines: what changed, and what it couldn't do and why."""
    tokens, planned = tokens or {}, planned if planned is not None else {}
    colors = tokens.get("colors", {})
    good, bad = colors.get("good", "#197982"), colors.get("bad", "#B94642")
    said, why_not = [], []
    vis = layout.setdefault("visuals", [])
    found = _detect_lower(layout, planned, measures)
    if found:
        lib = layout.get("lowerIsBetter")
        if isinstance(lib, dict):
            lib.update({k: True for k in found})
        else:
            layout["lowerIsBetter"] = sorted(set(lib or []) | set(found))
        why_not.append("lower is better for " + ", ".join(found) + " (a fall shows ▼ in green); say if that's wrong")
    said += drill_card_comparisons(layout, expressions)
    for v in list(vis):
        t = v.get("type")
        if t == "cardVisual" and v.get("pattern") == "live-headline":
            props = v.setdefault("props", {})
            if not any(k.startswith("fillCustom.show") for k in props):
                props.update({"fillCustom.show@default": False, "fillCustom.transparency@default": 100,
                              "cardCalloutArea.backgroundTransparency@default": 100, "layout.backgroundShow@none": False,
                              "outline.show@default": False, "shadowCustom.show@default": False})
                said.append(f"{v['id']}: the headline card draws no box of its own")
        if t == "cardVisual":
            props = v.setdefault("props", {})
            if not any(k.startswith("value.horizontalAlignment") for k in props) and v.get("pattern") != "live-headline":
                align = _card_align(tokens)            # the preset's card.align (tokens.json); left by default
                props["value.horizontalAlignment@default"] = align
                props.setdefault("label.horizontalAlignment@default", align)
                said.append(f"{v['id']}: the number {'centred' if align == 'center' else align + '-aligned'} (the style's card alignment)")
            rl = v.get("referenceLabels")
            if isinstance(rl, dict):
                for key in ("detailSize", "valueSize"):     # the change line at body size (the title: the theme's)
                    rl.setdefault(key, "body")
                for lab in rl.get("labels", []) or []:
                    if lab.get("chip") or lab.get("detailBackground"):
                        continue                       # a chip colours itself (its own font and fill measures)
                    if lab.get("detail") and not lab.get("detailColor") and is_comparison(lab["detail"]) \
                            and not lab.get("preview"):
                        # v1.12: a change beside last year's value is always coloured by direction (lower is better:
                        # a rise in breaches or days is red), the colour measure the kit's own
                        cmp_name = name_of(lab["detail"])
                        base = re.sub(r"\s+(PY|LY)$", "", name_of(lab.get("value", "")))
                        lower = lower_is_better(layout, base) or lower_is_better(layout, cmp_name) or bool(lab.get("lowerIsBetter"))
                        col = f"{cmp_name} colour"
                        planned[col] = {"table": table_of(lab["detail"]) or (planned.get(cmp_name) or {}).get("table")
                                        or layout.get("measureTable") or "_Measures",
                                        "expression": _colour(cmp_name, good, bad, lower), "dataType": "string"}
                        lab["detailColor"] = f"[{col}]"
                        said.append(f"{v['id']}: the change coloured by direction ({'a fall' if lower else 'a rise'} is good)")
                    if lab.get("detailColor") and lab.get("detail"):        # polished before: the direction may change
                        cmp_name = name_of(lab["detail"])
                        base = name_of(lab.get("value", "")).removesuffix(" LY")
                        lower = lower_is_better(layout, base) or lower_is_better(layout, cmp_name)
                        col = name_of(lab["detailColor"])
                        if col in planned:
                            planned[col]["expression"] = _colour(cmp_name, good, bad, lower)
                        if lower:
                            lab["lowerIsBetter"] = True
                        else:
                            lab.pop("lowerIsBetter", None)
                        continue
                    if not is_comparison(lab.get("value", "")) or lab.get("preview") or \
                            (planned.get(name_of(lab.get("value", ""))) or {}).get("dataType") == "string":
                        continue                       # a plain text line ("under the SLA") is no number to colour
                    cmp_name = name_of(lab["value"])
                    table = table_of(lab["value"]) or (planned.get(cmp_name) or {}).get("table") or layout.get("measureTable") or "_Measures"
                    base, date = _base(lab["value"], planned), _date_of(lab["value"], planned)
                    if not base or not date:
                        why_not.append(f"{v['id']}: the change isn't coloured: I can't tell which number it compares "
                                       "(it isn't a measure I planned)")
                        continue
                    ly = f"{base} LY"
                    planned.setdefault(ly, {"table": table, "expression":
                                            f"CALCULATE ( [{base}], SAMEPERIODLASTYEAR ( {date} ) )",
                                            "formatString": (planned.get(base) or {}).get("formatString", "#,0")})
                    col = f"{cmp_name} colour"
                    lower = lower_is_better(layout, base) or lower_is_better(layout, cmp_name)
                    planned[col] = {"table": table, "expression": _colour(cmp_name, good, bad, lower),
                                    "dataType": "string"}           # the kit's own: rewritten when the setting changes
                    if lower:
                        lab["lowerIsBetter"] = True
                    else:
                        lab.pop("lowerIsBetter", None)
                    if cmp_name in planned and planned[cmp_name].get("formatString") != ARROWS:
                        planned[cmp_name]["formatString"] = ARROWS
                    title = re.sub(r"^vs\.?\s+", "", lab.get("title") or "last year", flags=re.I)
                    lab.update({"title": title, "value": f"[{ly}]", "detail": f"[{cmp_name}]",
                                "detailColor": f"[{col}]"})
                    said.append(f"{v['id']}: {title}'s value with the change beside it, ▲ / ▼ in green or red")
        if t in ("tableEx", "pivotTable"):
            have = {json.dumps(c.get("target") or c.get("field")) for c in v.get("cf", [])}
            for c in v.get("cf", []):                    # coloured before: "lower is better" may have changed since
                col = name_of(c.get("measure", "")) if c.get("type") == "measure" else ""
                cmp_name = col[: -len(" colour")] if col.endswith(" colour") else ""
                shown = {name_of(f) for f in (v.get("bindings") or {}).get("Values", [])}
                if cmp_name in shown and col in planned and planned[col].get("dataType") == "string":   # the kit's own
                    lower = lower_is_better(layout, cmp_name)
                    expr = _colour(cmp_name, good, bad, lower)
                    if planned[col].get("expression") != expr:
                        planned[col]["expression"] = expr
                        if lower:
                            c["lowerIsBetter"] = True
                        else:
                            c.pop("lowerIsBetter", None)
                        said.append(f"{v['id']}: {cmp_name} coloured {'lower' if lower else 'higher'} is better")
            for f in (v.get("bindings") or {}).get("Values", []):
                if not is_comparison(f) or json.dumps(_field(f)) in have:
                    continue
                cmp_name = name_of(f)
                col = f"{cmp_name} colour"              # a colour measure: the form Desktop saves for a table column
                lower = lower_is_better(layout, cmp_name) or lower_is_better(layout, _base(f, planned))
                planned[col] = {"table": table_of(f) or layout.get("measureTable") or "_Measures", "expression":
                                _colour(cmp_name, good, bad, lower), "dataType": "string"}
                rule = {"type": "measure", "object": "values", "property": "fontColor", "measure": f"[{col}]",
                        "target": _field(f)}
                if lower:
                    rule["lowerIsBetter"] = True
                v.setdefault("cf", []).append(rule)
                said.append(f"{v['id']}: {cmp_name} coloured by direction")
    said += header_band(layout)
    said += back_buttons(layout, colors)
    said += matching_pickers(layout)
    said += pill_colours(layout, tokens)
    said += rail_pickers(layout, tokens)
    said += tab_order(layout)
    s2, w2 = target_lines(layout, planned, measures)
    return said + s2, why_not + w2


def _detect_lower(layout, planned, measures=None):
    """KPI measures named like returns or costs, not yet in `lowerIsBetter` either way."""
    lib = layout.get("lowerIsBetter")
    said = {k.strip("[]").lower() for k in (lib or [])} if not isinstance(lib, dict) else \
        {k.strip("[]").lower() for k in lib}
    out = []
    for v in layout.get("visuals", []):
        names = [name_of(x) for xs in (v.get("bindings") or {}).values() for x in (xs if isinstance(xs, list) else [xs])
                 if _field(x).startswith("[") or name_of(x) in planned or name_of(x) in (measures or ())]
        # measures only, never a column such as Return Reason
        rl = v.get("referenceLabels") if isinstance(v.get("referenceLabels"), dict) else {}
        names += [name_of(lab.get("value", "")) for lab in rl.get("labels", []) or []]
        uc = v.get("udfCard") if isinstance(v.get("udfCard"), dict) else None
        if uc and "lowerIsBetter" not in uc:           # a UDF card's current value: its colours swap (pbik udf)
            names += [name_of(a) for k, a in (uc.get("args") or {}).items()
                      if re.search("Current", k) and isinstance(a, str) and a.strip().startswith("[")]
        for n in names:
            m = _base(n, planned) or (re.split(r"\s+(?:vs|change|growth|variance|diff|delta|yoy)\b", n, 1,
                                               flags=re.I)[0] if is_comparison(n) else n)
            if m and LOWER.search(m) and m.lower() not in said and not m.lower().endswith(" colour")                     and m not in out:
                out.append(m)
    return out


def header_band(layout):
    """A decorative band behind the top row (the title and any filter beside it), the full canvas width."""
    out = []
    for page in layout.get("pages", {}):
        vs = [v for v in layout.get("visuals", []) if v.get("page") == page]
        if any(v.get("name") == "header-band" for v in vs) or _rail(layout, page):
            continue                                       # a rail page has its title in the rail
        title = next((v for v in vs if v.get("type") == "textbox" and v.get("y", 999) <= 48), None)
        if not title:
            continue
        top = [v for v in vs if v.get("y", 999) < title["y"] + title.get("h", 0)]
        bottom = max(v["y"] + v.get("h", 0) for v in top)
        nxt = min((v.get("y", 0) for v in vs if v not in top), default=bottom + 32)
        if nxt - 8 < bottom:
            out.append(f"{page}: no header band: the top row and the next row would overlap")
            continue
        bottom = min(bottom + 16, nxt - 8)                  # a little room under the top row, never into the next
        vid = _next_id(layout, page)
        layout["visuals"].append({
            "id": vid, "name": "header-band", "page": page, "type": "shape", "x": 0, "y": 0, "w": 1920,
            "h": bottom, "z": 0, "decorative": True, "style": {"fill": "card"},
            "container": {"keepLayerOrder": True},              # a click never brings it in front (C-11)
            "build": {"method": "native", "step": 1, "reason": "Shape: the header band behind the title and filter"}})
        for v in top:
            if v.get("type") in ("slicer", "advancedSlicerVisual"):
                c = v.setdefault("container", {})
                if isinstance(c, dict):                 # the band is its background: no box of its own
                    c["background"], c["shadow"] = False, False
        out.append(f"{page}: a header band behind the title and the filter")
    return out


def _dark(hexc):
    """True for a colour light text reads on (relative luminance under 0.3)."""
    h = str(hexc or "").lstrip("#")
    if len(h) < 6:
        return False
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] < 0.3


def _band(layout, page):
    return next((v for v in layout.get("visuals", []) if v.get("page") == page and v.get("type") in ("shape", "basicShape")
                 and v.get("y", 1) == 0 and v.get("w", 0) >= 1800 and (v.get("header") or v.get("name", "").startswith("header-band"))),
                None)


def back_buttons(layout, colors=None):
    """v1.12: every drill-through page gets a Back button in its header (Desktop adds one only when a page is made a
    drill-through page in its own UI), left of the title, which moves right to make room; on a dark band the button's
    label and outline are the band's light text colour."""
    colors, out = colors or {}, []
    for page, spec in (layout.get("pages") or {}).items():
        if not isinstance(spec, dict) or not spec.get("drillthrough"):
            continue
        vs = [v for v in layout.get("visuals", []) if v.get("page") == page]
        band = _band(layout, page)
        dark = bool(band) and _dark(colors.get(str((band.get("style") or {}).get("fill", "")), (band.get("style") or {}).get("fill")))
        back = next((v for v in vs if v.get("type") == "actionButton" and (v.get("action") or {}).get("type") == "Back"), None)
        rail = _rail(layout, page)
        if not back and rail:                            # a rail page: the button at the top of the rail
            back = {"id": _next_id(layout, page), "name": "back", "page": page, "type": "actionButton", "x": 32,
                    "y": 32, "w": 112, "h": 40, "z": 2, "action": {"type": "Back"}, "text": "← Back", "tabOrder": 1,
                    "build": {"method": "native", "step": 1, "reason": "Back to the page drilled from"}}
            layout["visuals"].append(back)
            for v in vs:                                 # the rail's contents move down to make room
                if v is not rail and v.get("x", 999) < rail.get("w", 0) and v.get("y", 0) < 32 + 40 + 24:
                    v["y"] = 32 + 40 + 24
            out.append(f"{page}: a Back button at the top of the rail")
        if not back:
            top = band["h"] if band else 96
            h, w = 40, 112
            back = {"id": _next_id(layout, page), "name": "back", "page": page, "type": "actionButton", "x": 32,
                    "y": max(8, (top - h) // 2), "w": w, "h": h, "z": 2, "action": {"type": "Back"}, "text": "← Back",
                    "tabOrder": 1, "build": {"method": "native", "step": 1, "reason": "Back to the page drilled from"}}
            layout["visuals"].append(back)
            for v in vs:                                     # the title (and anything else at the left of the band)
                if v is not band and v.get("y", 999) < top and v.get("x", 0) < 32 + w + 24 and v.get("type") != "shape":
                    shift = 32 + w + 24 - v["x"]
                    v["x"] += shift
                    v["w"] = max(v.get("w", 0) - shift, 48)
            out.append(f"{page}: a Back button in the header, left of the title")
        if dark:
            props = back.setdefault("props", {})
            if not any(k.startswith("text.fontColor") for k in props):
                props.update({"text.fontColor@default": "onDark", "outline.lineColor@default": "onDark",
                              "fill.show": True, "fill.fillColor@default": (band.get("style") or {}).get("fill", "primary")})
                out.append(f"{back['id']}: the Back button's label in the band's light text colour")
    return out


def pill_colours(layout, tokens=None):
    """v1.12: on a dark theme, button-slicer pills take the theme's colours (card fill, text, the selected colour):
    Desktop's own pill is white, and the theme's light text vanishes on it (test 3: the Season and Quarter pills read
    blank). A picker with fill or text colours of its own, or an image picker, is left as it is."""
    from .a11y import contrast
    c = (tokens or {}).get("colors") or {}
    if not c.get("text") or contrast(c["text"], "#FFFFFF") >= 4.5:      # light theme: Desktop's white pill reads fine
        return []
    out = []
    for v in layout.get("visuals", []):
        if v.get("type") != "advancedSlicerVisual" or v.get("template", "").endswith(
                (".image-list", ".image-cards", ".svg-kpi-card-buttons")):
            continue
        props = v.setdefault("props", {})
        if any(k.split(".")[0] in ("fillCustom", "value") for k in props):
            continue
        sel = "selected" if "selected" in c else "brand"
        on = "onSelected" if "onSelected" in c else "background"
        props.update({"fillCustom.show@default": True, "fillCustom.fillColor@default": "card",
                      "fillCustom.transparency@default": 0, "fillCustom.fillColor@selection:selected": sel,
                      "value.fontColor@default": "text", "value.fontColor@selection:selected": on,
                      "outline.show@default": True, "outline.lineColor@default": "border",
                      "outline.lineColor@selection:selected": sel})
        out.append(f"{v['id']}: pills in the theme's colours (card fill, text; the selected pill in {sel}), "
                   "not Desktop's white")
    return out


def tab_order(layout):
    """v1.12: tab order follows reading order (lessons A-04, Rep 9): when a page's tab numbers (visual number x 100, or
    `tabOrder`) don't read in the order validate expects (the band first, then each full-height panel as a column,
    left to right), every tab stop on that page gets `tabOrder` in reading order. A visual added later (a quarter
    chart beside a KPI, a picker moved into the rail) no longer jumps the queue (tests 1 and 2)."""
    from .a11y import reading_order
    out = []
    num = lambda v: int(str(v["id"]).rsplit("V", 1)[1]) if re.search(r"V\d+$", str(v.get("id", ""))) else 0  # noqa
    pages = {v.get("page") for v in layout.get("visuals", [])}
    for page in sorted(p for p in pages if p):
        vs = [v for v in layout.get("visuals", []) if v.get("page") == page and v.get("type") != "group"
              and all(isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool) for k in ("x", "y", "w", "h"))]
        cols = [(v["x"], v["y"], v["w"], v["h"]) for v in vs if v.get("type") in ("shape", "basicShape")
                and v["h"] >= 700 and 0 < v["w"] <= 960]
        stops = [v for v in vs if v.get("type") not in ("shape", "basicShape", "image") and not v.get("decorative")
                 and not v.get("hidden") and v.get("tabOrder", 0) >= 0]
        if len(stops) < 2:
            continue
        want = reading_order([(v["id"], v["x"], v["y"], v["w"], v["h"]) for v in stops], cols)
        got = [v["id"] for v in sorted(stops, key=lambda v: v.get("tabOrder", num(v) * 100))]
        if want == got:
            continue
        by = {v["id"]: v for v in stops}
        for i, vid in enumerate(want, 1):
            by[vid]["tabOrder"] = i * 100
        out.append(f"{page}: tab order set to reading order ({len(want)} tab stops; the band, then each panel)")
    return out


def matching_pickers(layout):
    """v1.12: button slicers side by side (the same top and height) share one row count, so their pills are the same
    height (Desktop divides the visual's height by the rows): a 3-year picker beside a 4 x 2 channel grid gets 2 rows."""
    out, rows_of = [], {}
    for v in layout.get("visuals", []):
        if v.get("type") != "advancedSlicerVisual" or v.get("template", "").endswith((".image-list", ".image-cards")):
            continue
        rows_of.setdefault((v.get("page"), v.get("y"), v.get("h")), []).append(v)
    for group in rows_of.values():
        if len(group) < 2:
            continue
        rc = lambda v: next((x for k, x in (v.get("props") or {}).items() if k.split("@")[0] == "layout.rowCount"), 1)
        most = max(int(rc(v) or 1) for v in group)
        for v in group:
            if int(rc(v) or 1) < most:
                props = v.setdefault("props", {})
                key = next((k for k in props if k.split("@")[0] == "layout.rowCount"), "layout.rowCount@none")
                props[key] = most
                out.append(f"{v['id']}: {most} rows, like the picker beside it, so the pills are the same height")
    return out


THRESH = re.compile(r"\b(sla|target|threshold|goal|limit|budget|quota)\b", re.I)


def target_lines(layout, planned, measures=None):
    """v1.12: a KPI card compared only with a target (an SLA, a budget) is compared with last year like the other
    cards, and the target becomes a plain line under it ("2.7 days under the SLA on average"): the change from last
    year is what moves, the target is context. Needs a date the model shifts (a planned last-year measure)."""
    said, why = [], []
    date = next((m.group(1) for p in planned.values() for m in [LY_IN.search(p.get("expression", ""))] if m), None)
    for v in layout.get("visuals", []):
        rl = v.get("referenceLabels") if v.get("type") == "cardVisual" else None
        if not isinstance(rl, dict) or not rl.get("labels") or v.get("pattern") == "live-headline":
            continue
        labs = rl["labels"]
        if any(LY_IN.search((planned.get(name_of(l.get("value", ""))) or {}).get("expression", "")) or
               re.search(r"\b(LY|PY|last year)\b", name_of(l.get("value", "")), re.I) for l in labs):
            continue                                       # already compared with last year
        tgt = next((l for l in labs if THRESH.search(str(l.get("title", ""))) or THRESH.search(name_of(l.get("value", "")))), None)
        data = [name_of(x) for x in (v.get("bindings") or {}).get("Data", [])]
        if not tgt or not data:
            continue
        if not date:
            why.append(f"{v['id']}: compared only with a target; no last-year measure to copy the date from")
            continue
        base, table = data[0], layout.get("measureTable") or "_Measures"
        fmt = (planned.get(base) or {}).get("formatString", "#,0")
        ly, chg, line = f"{base} PY", f"{base} vs PY %", f"{base} vs target text"
        planned.setdefault(ly, {"table": table, "formatString": fmt,
                                "expression": f"CALCULATE ( [{base}], SAMEPERIODLASTYEAR ( {date} ) )"})
        planned.setdefault(chg, {"table": table, "formatString": "+0.0%;-0.0%;0.0%",
                                 "expression": f"VAR _py = [{ly}] RETURN IF ( NOT ISBLANK ( _py ), DIVIDE ( [{base}] - _py, _py ) )"})
        gap = name_of(tgt.get("detail", "")) or None
        word = re.sub(r"^vs\.?\s+", "", str(tgt.get("title") or "the target"), flags=re.I)
        unit = " days" if re.search(r"days|hours", base, re.I) else ""
        avg = " on average" if re.search(r"\bavg\b|average|mean", base, re.I) else ""   # the title says which target
        diff = f"[{gap}]" if gap else f"( [{base}] - {tgt.get('value')} )"
        planned.setdefault(line, {"table": table, "dataType": "string", "expression":
                                  f"VAR _d = {diff} RETURN IF ( ISBLANK ( _d ), BLANK (), FORMAT ( ABS ( _d ), \"0.0\" ) & "
                                  f"\"{unit} \" & IF ( _d <= 0, \"under\", \"over\" ) & \"{avg}\" )"})
        lower = lower_is_better(layout, base) or bool(tgt.get("lowerIsBetter"))
        new = [{"title": "last year", "value": f"[{ly}]", "detail": f"[{chg}]"},
               {"title": word, "value": f"[{line}]",
                "preview": "{abs:" + diff.strip("() ") + "|0.0}" + unit + " {word:" + diff.strip("() ") + "|under|over}" + avg}
               if gap else {"title": word, "value": tgt.get("value")}]
        if lower:
            new[0]["lowerIsBetter"] = True
        rl["labels"] = new
        said.append(f"{v['id']}: {base} compared with last year, the {word} as a plain line under it")
    return said, why


COUNT_RULE = re.compile(r"COUNTROWS\s*\(\s*FILTER\s*\(\s*(?:VALUES|ALLSELECTED|DISTINCT)\s*\(\s*('?[^'()]*'?\[[^\]]+\])\s*\)\s*,"
                        r"\s*\[([^\]]+)\]\s*(>=|<=|<>|>|<|=)\s*(-?[\d.]+)\s*\)", re.I)


def count_titles(layout, expressions):
    """v1.12: a title measure that counts the list's rows ("4 categories with more than 10% ...",
    COUNTROWS ( FILTER ( VALUES ( col ), [m] > 0.1 ) )) must use the rule the list itself filters by (the visual's
    `filters` on [m], the same operator and value) and the list must show that column; otherwise the count and the
    rows disagree. Returns plain lines, one per mismatch. `expressions`: {measure name: DAX}."""
    out = []
    for v in layout.get("visuals", []):
        c = v.get("container") if isinstance(v.get("container"), dict) else {}
        t = c.get("title")
        if not isinstance(t, dict) or not t.get("measure"):
            continue
        m = COUNT_RULE.search(expressions.get(name_of(t["measure"]), "") or "")
        if not m:
            continue
        col, msr, op, val = m.group(1), m.group(2), m.group(3), float(m.group(4))
        cols = {name_of(f) for xs in (v.get("bindings") or {}).values() for f in (xs if isinstance(xs, list) else [xs])}
        flt = [f for f in v.get("filters") or [] if name_of(f.get("field", "")) == msr]
        same = any(f.get("op", ">") == op and isinstance(f.get("value"), (int, float)) and abs(f["value"] - val) < 1e-9
                   for f in flt)
        if name_of(col) not in cols:
            out.append(f"{v['id']}: the title counts {name_of(col)} values, but the list doesn't show {name_of(col)}")
        if not same:
            have = ", ".join(f"[{msr}] {f.get('op', '>')} {f.get('value')}" for f in flt) or "no filter on it"
            out.append(f"{v['id']}: the title counts rows where [{msr}] {op} {m.group(4)}, but the list's own filter is "
                       f"{have}: the count and the rows would disagree; filter the list by the same rule")
    return out


def keep_picker_labels(layout, contract):
    """v1.12: a picker on an option table (labels written in the model's DAX: a field parameter, a DATATABLE list)
    shows the model's labels, kept as they are in the made-up model too: layout.json `items` follows them (a typed
    list that differs is replaced, and said)."""
    from . import synthgen as SG
    labels = {}
    for t, tb in ((contract or {}).get("tables") or {}).items():
        if tb.get("source") != "calculated":
            continue
        try:
            lit = SG.literal_rows(contract, t)
        except Exception:                               # a table the parser doesn't follow: left alone
            lit = None
        if not lit:
            continue
        types, rows = lit
        cols = rows["columns"]
        order = next((i for i, x in enumerate(cols) if re.search(r"order|sort", x, re.I) and types.get(x) == "int64"), None)
        body = sorted(rows["rows"], key=lambda r: r[order]) if order is not None else rows["rows"]
        for i, x in enumerate(cols):
            if types.get(x) == "string" and not re.search(r"fields", x, re.I) and i != order:
                labels[(t, x)] = [str(r[i]) for r in body]
    out = []
    for v in layout.get("visuals", []):
        if v.get("type") not in ("advancedSlicerVisual", "slicer", "listSlicer"):
            continue
        f = ((v.get("bindings") or {}).get("Values") or [None])[0]
        hit = labels.get((table_of(f) or "", name_of(f))) if f else None
        if hit and isinstance(v.get("items"), list) and v["items"] != hit:
            v["items"] = hit
            out.append(f"{v['id']}: the picker's labels are the model's own ({', '.join(hit)})")
    return out


def comparison_colours(layout, expressions):
    """v1.12, checked at every build (pbik validate): each KPI card's change beside last year is coloured, and its
    colour measure goes the right way: for a lower-is-better measure (breaches, days to resolve) a rise is red.
    Plain lines, one per card label that isn't."""
    out = []
    for v in layout.get("visuals", []):
        rl = v.get("referenceLabels") if v.get("type") == "cardVisual" else None
        for lab in (rl or {}).get("labels", []) if isinstance(rl, dict) else []:
            if not lab.get("detail") or not is_comparison(lab["detail"]) or lab.get("preview"):
                continue
            cmp_name = name_of(lab["detail"])
            base = re.sub(r"\s+(PY|LY)$", "", name_of(lab.get("value", "")))
            lower = lower_is_better(layout, base) or lower_is_better(layout, cmp_name)
            if not lab.get("detailColor"):
                out.append(f"{v['id']}: the change {cmp_name} isn't coloured ({'a rise' if lower else 'a fall'} should "
                           "show red): run `pbik layout polish`")
                continue
            e = expressions.get(name_of(lab["detailColor"]), "")
            m = re.search(r"\[" + re.escape(cmp_name) + r"\]\s*(<=|>=|<|>)\s*0", e)
            if m and (m.group(1).startswith("<") != lower):
                out.append(f"{v['id']}: {cmp_name} is coloured {'higher' if not lower else 'lower'}-is-better the wrong way "
                           f"round ({base} is {'lower' if lower else 'higher'} is better)")
    return out


def quote_tables(expr, tables):
    """'Table'[Column] for every model table named before a [ in DAX: an unquoted DataTable[...] or Date[...] reads as
    the DATATABLE / DATE function and the measure fails to parse (test 2 of the batch studies, v1.12). Text inside
    "..." is left alone."""
    if not expr or not tables:
        return expr
    names = sorted(tables, key=len, reverse=True)
    pat = re.compile(r"(?<!['\w])(" + "|".join(re.escape(t) for t in names if re.fullmatch(r"\w+", t)) + r")(?=\s*\[)")
    parts = re.split(r'("(?:[^"]|"")*")', expr)
    return "".join(x if i % 2 else pat.sub(lambda m: f"'{m.group(1)}'", x) for i, x in enumerate(parts))


def quote_planned(g, contract):
    """Quote table names in generate.json's planned measures and columns (quote_tables); returns plain lines."""
    tables = list((contract or {}).get("tables") or {})
    out = []
    for kind in ("plannedMeasures",):
        for k, v in (g.get(kind) or {}).items():
            new = quote_tables(v.get("expression", ""), tables)
            if new != v.get("expression", ""):
                v["expression"] = new
                out.append(f"[{k}]: table names quoted ('Table'[Column])")
    for t, cols in (g.get("plannedColumns") or {}).items():
        for k, v in (cols or {}).items():
            new = quote_tables(v.get("expression", ""), tables)
            if new != v.get("expression", ""):
                v["expression"] = new
                out.append(f"{t}[{k}]: table names quoted")
    return out


SCOPE_FN = re.compile(r"\b(ALLSELECTED|ALL|REMOVEFILTERS|ALLEXCEPT)\s*\(\s*('?)([^'()\[\]]+)\2\[([^\]]+)\]\s*\)", re.I)


def sort_by_scope(g, contract):
    """v1.12: a planned measure that clears one column (ALLSELECTED ( 'Shots'[Quarter] )) clears its sort-by column
    too: a visual grouped by a column sorted by another is filtered by both, so clearing the label alone leaves the
    sort column filtering and every bar is its own "best" (test 3: all five quarters in amber). Plain lines."""
    sorts = {}
    for t, td in ((contract or {}).get("tables") or {}).items():
        for cn, cd in (td.get("columns") or {}).items():
            if isinstance(cd, dict) and cd.get("sortBy"):
                sorts[(t, cn)] = cd["sortBy"]
    for t, cols in (g.get("plannedColumns") or {}).items():
        for cn, cd in (cols or {}).items():
            if isinstance(cd, dict) and cd.get("sortBy"):
                sorts[(t, cn)] = cd["sortBy"]
    out = []

    def fix(m):
        fn, _, t, cn = m.group(1), m.group(2), m.group(3).strip(), m.group(4)
        sb = sorts.get((t, cn))
        if not sb or fn.upper() == "ALLEXCEPT":
            return m.group(0)
        return f"{fn} ( '{t}'[{cn}], '{t}'[{sb}] )"
    for k, v in (g.get("plannedMeasures") or {}).items():
        e = v.get("expression", "")
        new = SCOPE_FN.sub(fix, e)
        if new != e:
            v["expression"] = new
            out.append(f"[{k}]: clears the sort-by column with the column it sorts, or each item is compared only "
                       "with itself")
    return out


COLUMN_TYPES = {"columnChart", "clusteredColumnChart", "lineClusteredColumnComboChart", "lineStackedColumnComboChart"}
KNOWN_N = {"quarter": 4, "month": 12, "weekday": 7, "day of week": 7}


def label_collisions(layout, tokens=None):
    """v1.12: data labels side by side on a column chart must fit their column's slot, or Desktop draws them over
    each other (quarter labels of 48,645 in a 168 px chart). The label width is estimated from its display units
    (Auto, thousands or more: "48.6K", 5 characters; none: "48,645", up to 7) and size; the slot is the plot width
    over the categories, when their count is known (quarters, months, weekdays, a Top N). Plain lines."""
    pts = ((tokens or {}).get("fontPt") or {})
    out = []
    for v in layout.get("visuals", []):
        if v.get("type") not in COLUMN_TYPES:
            continue
        pr = v.get("props") or {}
        if not pr.get("labels.show"):
            continue
        cat = ((v.get("bindings") or {}).get("Category") or [None])[0]
        cname = name_of(cat).lower() if cat else ""
        n = next((k for w_, k in KNOWN_N.items() if w_ in cname), None)
        topn = next((int(f.get("n", 0)) for f in v.get("filters") or [] if f.get("type") == "TopN"), None)
        n = topn or n
        if not n:
            continue
        units = pr.get("labels.labelDisplayUnits")
        chars = 4.5 if units in (0, 1000, 1000000) else 7          # "56.7K" against "48,645"
        size = pr.get("labels.fontSize", 9)
        size = pts.get(size, 10) if isinstance(size, str) else size
        label_px = chars * size * 4 / 3 * 0.5 + 4                 # Segoe digits about half an em
        plot = v.get("w", 0) - (16 if pr.get("valueAxis.show") is False else 56)
        slot = plot / n
        if label_px > slot:
            out.append(f"{v['id']}: data labels ~{label_px:.0f} px wide in {slot:.0f} px columns would overlap; use "
                       "compact labels (display units Auto: 2.3K), a smaller label size, or a wider chart")
    return out


def project_expressions(root):
    """{measure: DAX} from the project's model contract and planned measures (design/specs)."""
    spec, out = pathlib.Path(root) / "design" / "specs", {}
    for f, get in (("contract.json", lambda d: [m for t in (d.get("tables") or {}).values() for m in (t.get("measures") or {}).items()]),
                   ("generate.json", lambda d: list((d.get("plannedMeasures") or {}).items()))):
        try:
            d = json.loads((spec / f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.update({k: (v or {}).get("expression", "") for k, v in get(d) if isinstance(v, dict)})
    return out


def _rail(layout, page):
    """The page's rail (pattern rail-panel: a shape at the left edge, full height), or None."""
    return next((v for v in layout.get("visuals", []) if v.get("page") == page and v.get("pattern") == "rail-panel"
                 and v.get("type") in ("shape", "basicShape") and v.get("x", 1) == 0), None)


PILL, PICK_TITLE, PICK_GAP = 40, 28, 24          # a rail picker: its title, its pills, the gap to the next picker


def rail_pickers(layout, tokens=None):
    """v1.12: the pickers in a rail line up: the same left edge and width (the rail less its inset on both sides),
    one pill height (40 px, rows x pill + 8 px between rows under the title, sized from the theme: 28 px or more), and the same gap (24 px) between
    pickers, top to bottom in their order; a dropdown keeps its own height."""
    pts = (tokens or {}).get("fontPt") or {}
    pt = pts.get("chartTitle") or pts.get("cardTitle") or 12
    title_h = max(PICK_TITLE, round(pt * 4 / 3 * 1.35 + 10))   # v1.12: a 15 pt title needs 37 px, or the pills shrink
    out = []
    for page in layout.get("pages", {}):
        rail = _rail(layout, page)
        if not rail:
            continue
        inset = 32
        ps = sorted((v for v in layout.get("visuals", []) if v.get("page") == page and v.get("type") in
                     ("advancedSlicerVisual", "slicer", "listSlicer") and v.get("x", 999) < rail.get("w", 0)),
                    key=lambda v: v.get("y", 0))
        if not ps:
            continue
        y, changed = ps[0].get("y", 0), []
        for v in ps:
            box = (v.get("x"), v.get("y"), v.get("w"), v.get("h"))
            v["x"], v["w"], v["y"] = inset, rail["w"] - 2 * inset, y
            if v["type"] == "slicer":                     # a dropdown: its title like the others' (the container title)
                props, c = v.setdefault("props", {}), v.setdefault("container", {})
                if isinstance(c, dict) and not c.get("title"):
                    f = ((v.get("bindings") or {}).get("Values") or [None])[0]
                    c["title"] = (f.get("displayName") if isinstance(f, dict) else None) or name_of(f)
                props["header.show"] = False                  # one title, not the header as well
                v["h"] = title_h + PILL
            if v["type"] == "advancedSlicerVisual":
                rows = next((int(x) for k, x in (v.get("props") or {}).items() if k.split("@")[0] == "layout.rowCount"), 1)
                v["h"] = title_h + rows * PILL + (rows - 1) * 8
            y = v["y"] + v["h"] + PICK_GAP
            if (v["x"], v["y"], v["w"], v["h"]) != box:
                changed.append(v["id"])
        if changed:
            out.append(f"{page}: the rail's pickers lined up ({', '.join(changed)}): one width, {PILL} px pills, "
                       f"{PICK_GAP} px apart")
    return out


def drill_card_comparisons(layout, expressions=None):
    """v1.12: a KPI card on a drill-through page compares like the same card on the page it drills from (its
    reference labels copied), so the drilled numbers read against last year too; without such a card (or when that
    card shows a chip of its own), last year's value from the model's own last-year measure (CALCULATE ( [X],
    SAMEPERIODLASTYEAR ... )) with its change beside it (a measure using both, named with vs or change)."""
    out = []
    pages = layout.get("pages") or {}
    drill = {k for k, p in pages.items() if isinstance(p, dict) and p.get("drillthrough")}
    vis = layout.get("visuals", [])
    for v in vis:
        if v.get("page") not in drill or v.get("type") != "cardVisual" or v.get("referenceLabels") \
                or v.get("pattern") == "live-headline":
            continue
        data = [name_of(x) for x in (v.get("bindings") or {}).get("Data", [])]
        src = next((s for s in vis if s.get("page") not in drill and s.get("type") == "cardVisual"
                    and s.get("referenceLabels") and [name_of(x) for x in (s.get("bindings") or {}).get("Data", [])] == data),
                   None)
        if src and any(l.get("chip") or l.get("detailBackground") for l in src["referenceLabels"].get("labels", [])):
            src = None                               # a chip is the panel's own form; a drill card takes the plain one
        if src:
            import copy
            v["referenceLabels"] = copy.deepcopy(src["referenceLabels"])
            v.pop("comparison", None)
            out.append(f"{v['id']}: compared with last year like {src['id']}")
            continue
        ex = expressions or {}
        base = data[0] if data else None
        ly = next((k for k, e in ex.items() if base and re.match(r"\s*CALCULATE\s*\(\s*\[" + re.escape(base) +
                                                                r"\]\s*,\s*SAMEPERIODLASTYEAR", e or "", re.I)), None)
        if not ly:
            continue
        chg = next((k for k, e in ex.items() if CMP.search(k) and f"[{ly}]" in (e or "") and k != ly
                    and (f"[{base}]" in (e or "") or k.lower().startswith(base.lower()) or "_cy" in (e or ""))), None)
        lab = {"title": "last year", "value": f"[{ly}]"}
        if chg:
            lab["detail"] = f"[{chg}]"
        v["referenceLabels"] = {"labels": [lab]}
        v.pop("comparison", None)
        out.append(f"{v['id']}: compared with last year ({ly})")
    return out


OTHER_WORDS = re.compile(r"\s*(?:;\s*)?(?:,|\band\b|\+)?\s*(?:an?\s+)?\bOther\b(?:\s+group)?", re.I)


def other_subtitles(layout, contract, planned_columns):
    """v1.12: a title or subtitle mentions "Other" only when the top-N + Other column it shows can have an Other:
    when the model's own labels (an option table) number N or fewer, the words go (and say so)."""
    from . import synthgen as SG
    labels = {}
    for t in ((contract or {}).get("tables") or {}):
        try:
            lit = SG.literal_rows(contract, t)
        except Exception:
            lit = None
        if lit:
            types, rows = lit
            for i, x in enumerate(rows["columns"]):
                if types.get(x) == "string":
                    labels[x] = len({r[i] for r in rows["rows"]})
    tops = {}
    for t, cols in (planned_columns or {}).items():
        for name, spec in (cols or {}).items():
            e = spec.get("expression", "")
            m = re.search(r"TOPN\s*\(\s*(\d+)", e, re.I) or re.search(r"_rank\s*<=\s*(\d+)", e, re.I)
            base = next((c for c in re.findall(r"\[([^\]]+)\]", e) if c in labels), None)
            if '"Other"' in e and m and base:
                tops[name] = labels[base] > int(m.group(1))
    out = []
    for v in layout.get("visuals", []):
        cols = {name_of(f) for xs in (v.get("bindings") or {}).values() for f in (xs if isinstance(xs, list) else [xs])}
        if not any(c in tops and not tops[c] for c in cols):
            continue
        c = v.get("container") if isinstance(v.get("container"), dict) else {}
        for k in ("title", "subtitle"):
            if isinstance(c.get(k), str) and re.search(r"\bOther\b", c[k]):
                new = OTHER_WORDS.sub("", c[k]).strip()
                new = re.sub(r"\s*(?:\band\b|,|;)\s*$", "", new)
                new = re.sub(r"\(\s*top\s+\d+\s*\)", "", new).replace("()", "").strip()
                if new != c[k]:
                    c[k] = new
                    out.append(f"{v['id']}: no 'Other' in its {k}: every channel is in the top group")
    return out


def exception_columns(layout):
    """v1.12: a worst-first list (pattern exception-list) shows what backs up, never a "vs target" difference that
    is good in most rows (negative days against an SLA read as fine): plain lines naming each such column."""
    out = []
    for v in layout.get("visuals", []):
        if v.get("pattern") != "exception-list":
            continue
        for c in v.get("cf", []) or []:
            tgt = name_of(c.get("target", ""))
            if c.get("lowerIsBetter") and CMP.search(tgt):
                out.append(f"{v['id']}: '{tgt}' is a difference from a target in a worst-first list: most rows look "
                           "good there; show what backs up instead (a breach count, or the excess over the target)")
    return out


def run(root=".", layout=None):
    """Polish design/specs/layout.json (and generate.json plannedMeasures) in place; returns (said, why_not)."""
    root = pathlib.Path(root)
    lf = pathlib.Path(layout) if layout else root / "design" / "specs" / "layout.json"
    lay = json.loads(lf.read_text(encoding="utf-8"))
    tf = root / "design" / "tokens.json"
    tokens = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else {}
    gf = root / "design" / "specs" / "generate.json"
    g = json.loads(gf.read_text(encoding="utf-8")) if gf.exists() else {}
    planned = g.setdefault("plannedMeasures", {})
    c = {}
    cf = root / "design" / "specs" / "contract.json"
    if cf.exists():
        c = json.loads(cf.read_text(encoding="utf-8"))
    measures = {m for t in (c.get("tables") or {}).values() for m in (t.get("measures") or {})}
    said, why_not = polish(lay, tokens, planned, measures, {**project_expressions(root),
                                                            **{k: v.get("expression", "") for k, v in planned.items()}})
    said += keep_picker_labels(lay, c)
    said += quote_planned(g, c)
    said += sort_by_scope(g, c)
    said += other_subtitles(lay, c, g.get("plannedColumns"))
    why_not += exception_columns(lay)
    if not lay.get("theme") and (root / "design" / "themes" / "pbip-polish.json").exists():
        lay["theme"] = "design/themes/pbip-polish.json"         # the theme is part of every plan (v1.7 live fix 6)
        said.append("the project's theme applied to the report")
    lf.write_text(json.dumps(lay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if planned:
        gf.parent.mkdir(parents=True, exist_ok=True)
        gf.write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return said, why_not
