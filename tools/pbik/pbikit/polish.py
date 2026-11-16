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


def polish(layout, tokens=None, planned=None, measures=None):
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
    for v in list(vis):
        t = v.get("type")
        if t == "cardVisual":
            props = v.setdefault("props", {})
            if not any(k.startswith("value.horizontalAlignment") for k in props):
                props["value.horizontalAlignment@default"] = "center"
                props.setdefault("label.horizontalAlignment@default", "center")
                said.append(f"{v['id']}: the number centred, so the card fills its space")
            rl = v.get("referenceLabels")
            if isinstance(rl, dict):
                for key in ("detailSize", "valueSize"):     # the change line at body size (the title: the theme's)
                    rl.setdefault(key, "body")
                for lab in rl.get("labels", []) or []:
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
                    if not is_comparison(lab.get("value", "")):
                        continue
                    cmp_name = name_of(lab["value"])
                    table = table_of(lab["value"]) or (planned.get(cmp_name) or {}).get("table") or "_Measures"
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
            for f in (v.get("bindings") or {}).get("Values", []):
                if not is_comparison(f) or json.dumps(_field(f)) in have:
                    continue
                cmp_name = name_of(f)
                col = f"{cmp_name} colour"              # a colour measure: the form Desktop saves for a table column
                lower = lower_is_better(layout, cmp_name) or lower_is_better(layout, _base(f, planned))
                planned[col] = {"table": table_of(f) or "_Measures", "expression":
                                _colour(cmp_name, good, bad, lower), "dataType": "string"}
                rule = {"type": "measure", "object": "values", "property": "fontColor", "measure": f"[{col}]",
                        "target": _field(f)}
                if lower:
                    rule["lowerIsBetter"] = True
                v.setdefault("cf", []).append(rule)
                said.append(f"{v['id']}: {cmp_name} coloured by direction")
    said += header_band(layout)
    return said, why_not


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
            m = _base(n, planned) or (re.split(r"\s+(?:vs|change|growth|variance|diff|delta|yoy)", n, 1,
                                               flags=re.I)[0] if is_comparison(n) else n)
            if m and LOWER.search(m) and m.lower() not in said and not m.lower().endswith(" colour")                     and m not in out:
                out.append(m)
    return out


def header_band(layout):
    """A decorative band behind the top row (the title and any filter beside it), the full canvas width."""
    out = []
    for page in layout.get("pages", {}):
        vs = [v for v in layout.get("visuals", []) if v.get("page") == page]
        if any(v.get("name") == "header-band" for v in vs):
            continue
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
    said, why_not = polish(lay, tokens, planned, measures)
    if not lay.get("theme") and (root / "design" / "themes" / "pbip-polish.json").exists():
        lay["theme"] = "design/themes/pbip-polish.json"         # the theme is part of every plan (v1.7 live fix 6)
        said.append("the project's theme applied to the report")
    lf.write_text(json.dumps(lay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if planned:
        gf.parent.mkdir(parents=True, exist_ok=True)
        gf.write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return said, why_not
