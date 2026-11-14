"""`pbik score`: the polish score, on every build's final screen and in the wrap-up (phase1-usability.md, A6).

Fifteen pass/fail checks, shown out of 10 (passed / 15 x 10, rounded). Checks 2, 4-6 and 8-15 are computed here
from the files; 1 (matches the approved picture: the agent's own judgment, always labelled so), 3 (KPI cards filled:
a DAX query) and 7 (interactions working: slicers filter, buttons and bookmarks go where they should) are given by
the agent from its own checks (`--item 1=pass`). A check nobody ran counts 0 and is named "not checked". Target: 7/10
before showing colleagues. Checks 11-15 (v1.7 walkthrough fix 15) are the polish a person notices: KPI cards that
fill their space with the change line readable and coloured by direction; numbers that read well (thousands
separators, number headers over their numbers, "vs" columns coloured); charts that read well (months in month order,
straight lines); text sized for the 1920 canvas; and a finished look (a header band with the filter in it). The
walkthrough page of 2026-11-14 scores 6/10 by them (9 of 15), where the ten checks alone gave 8.
"""
import json, pathlib, re, subprocess, sys

ITEMS = {1: "matches the approved picture (my own judgment)", 2: "alignment and spacing", 3: "KPI cards filled",
         4: "right visual types", 5: "right measures", 6: "fonts and colours from the theme",
         7: "interactions working", 8: "no overlaps or clutter", 9: "accessibility", 10: "no check errors",
         11: "KPI cards read well", 12: "numbers read well", 13: "charts read well", 14: "text sized for the canvas",
         15: "finished look (header band, styled filter)"}
AGENT = (1, 3, 7)
TARGET = 7
BUDGET = 12                      # data visuals per page before it counts as clutter (patterns' own budgets are lower)
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
DECOR = {"shape", "basicShape", "textbox", "image"}


def _grid_edges():
    col = (1920 - 64 - 11 * 24) / 12
    lefts = [32 + i * (col + 24) for i in range(12)]
    return lefts, [x + col for x in lefts]


def check_grid(layout):
    lefts, rights = _grid_edges()
    bad = []
    for v in layout.get("visuals", []):
        x, w, y = v.get("x", 0), v.get("w", 0), v.get("y", 0)
        full = x == 0 or x + w >= 1920
        on_left = full or min(abs(x - e) for e in lefts) <= 1
        on_right = full or min(abs(x + w - e) for e in rights) <= 1
        if not (on_left and on_right) or (v.get("type") not in DECOR and y % 8):
            bad.append(v["id"])
    return bad


def overlaps(layout):
    bad = []
    vs = [v for v in layout.get("visuals", []) if v.get("type") not in ("shape", "basicShape", "image")
          and not v.get("hidden") and not v.get("group")]
    for i, a in enumerate(vs):
        for b in vs[i + 1:]:
            if a["page"] != b["page"]:
                continue
            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"]
                    and b["y"] < a["y"] + a["h"]):
                bad.append(f"{a['id']}/{b['id']}")
    per_page = {}
    for v in vs:
        if v.get("bindings"):
            per_page[v["page"]] = per_page.get(v["page"], 0) + 1
    crowded = [p for p, n in per_page.items() if n > BUDGET]
    return bad, crowded


def hardcoded(layout):
    """Colours or fonts written into layout.json instead of the tokens and theme."""
    bad = []
    for v in layout.get("visuals", []):
        text = json.dumps({k: x for k, x in v.items() if k not in ("bindings", "deneb", "notes", "reference")})
        if HEX.search(text) or re.search(r'"(fontFamily|font)":\s*"(?!regular|semibold|bold|light|title)[A-Z]', text):
            bad.append(v["id"])
    return bad


def built_visuals(report):
    """{id: (visualType, {role: [fields]})} from the report's visual folders named <ID>_<name>."""
    from .fromreport import visual_fields
    out = {}
    for vf in pathlib.Path(report).glob("definition/pages/*/visuals/*/visual.json"):
        m = re.match(r"(P\d+-V\d+)_", vf.parent.name)
        if not m:
            continue
        v = json.loads(vf.read_text(encoding="utf-8"))
        out[m.group(1)] = ((v.get("visual") or {}).get("visualType"), visual_fields(v))
    return out


def _fields(b):
    """The bound field names. A measure is compared by its name only: layout.json may write `_Measures[X]` where the
    built visual says `[X]` (the walkthrough's false "fields differ" on every card)."""
    out = set()
    for xs in (b or {}).values():
        for x in xs if isinstance(xs, list) else [xs]:
            f = (x.get("field") if isinstance(x, dict) else str(x)) or ""
            out.add("[" + f.replace("'", "").split("[", 1)[-1] if "[" in f else f.replace("'", ""))
    return out


def compute(report, layout, agent=None, validate_fn=None):
    """{item: (passed True/False/None, why)}. `agent`: {1: True, 3: False, ...} from the agent's own checks."""
    agent = agent or {}
    res = {}
    for n in AGENT:
        res[n] = (agent.get(n), "" if n in agent else "not checked")
    bad = check_grid(layout)
    res[2] = (not bad, f"off the grid: {', '.join(bad[:5])}" if bad else "")
    built = built_visuals(report)
    want = {v["id"]: v for v in layout.get("visuals", [])}
    missing = sorted(set(want) - set(built))
    types = [i for i in want if i in built and built[i][0] != want[i].get("type") and want[i].get("type") != "deneb"]
    res[4] = (not types and not missing, (f"not built: {', '.join(missing[:5])}" if missing else "")
              + (f" type differs: {', '.join(types[:5])}" if types else ""))
    fields = [i for i in want if i in built and want[i].get("bindings")
              and _fields(want[i]["bindings"]) != _fields(built[i][1])]
    res[5] = (not fields, f"fields differ: {', '.join(fields[:5])}" if fields else "")
    hc = hardcoded(layout)
    ov, crowded = overlaps(layout)
    res[8] = (not ov and not crowded, "; ".join(x for x in (f"overlap: {', '.join(ov[:3])}" if ov else "",
                                                            f"crowded page: {', '.join(crowded)}" if crowded else "")
                                                if x))
    if validate_fn is None:
        from .validate import validate as validate_fn
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        lf = pathlib.Path(report).parent / "design" / "specs" / "layout.json"     # decorative shapes, IDs
        lp = str(lf) if lf.exists() else None
        full = validate_fn(report, layout=lp)
        plain = validate_fn(report, layout=lp, use_a11y=False)
    a11y = [w for w in full.warnings if w not in plain.warnings]
    colour_warn = [w for w in full.warnings if re.search(r"colou?r|font", w, re.I) and w not in a11y]
    res[6] = (not hc and not colour_warn, f"written into the layout: {', '.join(hc[:5])}" if hc else
              (colour_warn[0] if colour_warn else ""))
    res[9] = (not a11y, f"{len(a11y)} accessibility warning(s)" if a11y else "")
    res[10] = (not full.errors, f"{len(full.errors)} error(s)" if full.errors else "")
    res.update(polish_checks(report, layout))
    return res


# ---------------------------------------------------------------- checks 11-15: the polish a person notices
CMP = re.compile(r"\bvs\b|change|growth|variance|\bdiff|delta|\byoy\b", re.I)
MONTH_NUMBER = re.compile(r"month\s*(no|number|num|nr|index|sort|order)\b|monthno|monthnumber", re.I)


def _name(f):
    f = (f.get("field") if isinstance(f, dict) else f) or ""
    return f.split("[", 1)[-1].rstrip("]") if "[" in f else f


def _table(f):
    f = (f.get("field") if isinstance(f, dict) else f) or ""
    return f.split("[", 1)[0].strip("'") if "[" in f else ""


def theme_of(report):
    """The report's custom theme (its registered resource), else the project's design/themes/*.json."""
    rp = pathlib.Path(report)
    try:
        rj = json.loads((rp / "definition" / "report.json").read_text(encoding="utf-8"))
        name = rj.get("themeCollection", {}).get("customTheme", {}).get("name")
        f = rp / "StaticResources" / "RegisteredResources" / (name or "")
        if name and f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    for f in sorted((rp.parent / "design" / "themes").glob("*.json")):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
    return {}


def _style(theme, vtype, obj, prop, default=None):
    vs = theme.get("visualStyles", {})
    for t in (vtype, "*"):
        for e in (vs.get(t, {}).get("*", {}).get(obj) or []):
            if isinstance(e, dict) and prop in e:
                return e[prop]
    return default


def _prop(v, obj_prop):
    for k, x in (v.get("props") or {}).items():
        if k.split("@", 1)[0] == obj_prop:
            return x
    return None


def _pt(x, tokens_pt):
    if isinstance(x, (int, float)):
        return x
    return tokens_pt.get(x) if isinstance(x, str) else None


def polish_checks(report, layout):
    from .report import Report
    rp = pathlib.Path(report)
    theme = theme_of(report)
    tok = {}
    tf = rp.parent / "design" / "tokens.json"
    if tf.exists():
        try:
            tok = json.loads(tf.read_text(encoding="utf-8")).get("fontPt", {})
        except ValueError:
            tok = {}
    try:
        model = Report(report).model()
    except SystemExit:
        model = None
    planned = {}
    gf = rp.parent / "design" / "specs" / "generate.json"
    if gf.exists():
        try:
            planned = json.loads(gf.read_text(encoding="utf-8")).get("plannedMeasures", {})
        except ValueError:
            planned = {}
    vis = layout.get("visuals", [])
    res = {}

    # 11 KPI cards read well
    bad = []
    for v in vis:
        if v.get("type") != "cardVisual" or any(c.get("type") == "image" for c in v.get("cf", [])):
            continue
        data = (v.get("bindings") or {}).get("Data") or []
        align = _prop(v, "value.horizontalAlignment") or _style(theme, "cardVisual", "value", "horizontalAlignment",
                                                                "center")
        if len(data) == 1 and v.get("w", 0) >= 300 and str(align).lower() == "left":
            bad.append(f"{v['id']} leaves its right side empty")
        rl = v.get("referenceLabels") if isinstance(v.get("referenceLabels"), dict) else {}
        for lab in rl.get("labels", []) or []:
            if CMP.search(_name(lab.get("value", "")) + " " + _name(lab.get("detail", ""))) and \
                    not lab.get("detailColor"):
                bad.append(f"{v['id']} change isn't coloured by direction")
        if rl.get("labels"):
            size = _pt(rl.get("detailSize") or rl.get("valueSize"), tok) or _style(
                theme, "cardVisual", "referenceLabelValue", "valueFontSize", 10)
            if (size or 0) < 11:
                bad.append(f"{v['id']} change line is small")
    res[11] = (not bad, "; ".join(dict.fromkeys(bad))[:200])

    # 12 numbers read well
    bad = []
    built = built_visuals(report)
    for v in vis:
        for role, xs in (v.get("bindings") or {}).items():
            for x in xs if isinstance(xs, list) else [xs]:
                name = _name(x)
                fmt = None
                if model:
                    home = model.measure_home(name)
                    if home:
                        fmt = model.tables[home[0]].measures[name].format_string
                fmt = fmt or (planned.get(name) or {}).get("formatString")
                if model and model.measure_home(name) or name in planned:
                    if not fmt or not ("," in fmt or "%" in fmt or "\"" in fmt):
                        bad.append(f"{name} has no thousands separator")
        if v.get("type") in ("tableEx", "pivotTable"):
            vals = (v.get("bindings") or {}).get("Values", [])
            cmp_cols = [_name(x) for x in vals if CMP.search(_name(x))]
            coloured = {_name(c.get("target") or c.get("field", "")) for c in v.get("cf", [])
                        if c.get("type") in ("rules", "measure")}
            for c in cmp_cols:
                if c not in coloured:
                    bad.append(f"{v['id']} {c} isn't coloured by direction")
            vf = next(rp.glob(f"definition/pages/*/visuals/{v['id']}_*/visual.json"), None)
            if vf and v["id"] in built:
                d = json.loads(vf.read_text(encoding="utf-8"))
                cf = d.get("visual", {}).get("objects", {}).get("columnFormatting", [])
                aligned = sum(1 for e in cf if "alignment" in (e.get("properties") or {}))
                numbers = sum(1 for x in vals if model and model.measure_home(_name(x)))
                if numbers and aligned < numbers:
                    bad.append(f"{v['id']} number headers aren't over their numbers")
    res[12] = (not bad, "; ".join(dict.fromkeys(bad))[:200])

    # 13 charts read well
    bad = []
    for v in vis:
        if v.get("type") not in CHARTS:
            continue
        for x in (v.get("bindings") or {}).get("Category", []):
            t, c = _table(x), _name(x)
            if "month" in c.lower() and not MONTH_NUMBER.search(c) and model and t in model.tables:
                col = model.tables[t].columns.get(c)
                if col is not None and not col.sort_by and (col.data_type or "string") == "string":
                    bad.append(f"{v['id']} months sort A to Z")
        if v.get("type") in ("lineChart", "areaChart"):
            kind = _prop(v, "lineStyles.lineChartType") or _style(theme, "lineChart", "lineStyles", "lineChartType",
                                                                  "smooth")
            if str(kind).strip("'").lower() == "smooth":
                bad.append(f"{v['id']} lines are smoothed")
    res[13] = (not bad, "; ".join(dict.fromkeys(bad))[:200])

    # 14 text sized for the 1920 canvas
    bad = []
    title = _style(theme, "*", "title", "fontSize", 12)
    if any(isinstance(v.get("container"), dict) and v["container"].get("title") for v in vis) and (title or 0) < 14:
        bad.append(f"visual titles {title}pt (14 or more)")
    for t in {v.get("type") for v in vis if v.get("type") in CHARTS}:
        ax = _style(theme, t, "categoryAxis", "fontSize", 9)
        if (ax or 0) < 11:
            bad.append(f"axis labels {ax}pt (11 or more)")
        if any(v.get("type") == t and _prop(v, "legend.show") is not False and
               len((v.get("bindings") or {}).get("Y", [])) > 1 for v in vis):
            lg = _style(theme, t, "legend", "fontSize", 9)
            if (lg or 0) < 11:
                bad.append(f"legends {lg}pt (11 or more)")
    res[14] = (not bad, "; ".join(dict.fromkeys(bad))[:200])

    # 15 finished look: a header band behind the top row, the filter part of it
    bad = []
    for page in layout.get("pages", {}):
        pv = [v for v in vis if v.get("page") == page]
        band = next((v for v in pv if v.get("type") in ("shape", "basicShape") and v.get("y", 99) <= 0
                     and v.get("w", 0) >= 1800), None)
        if not band:
            bad.append(f"{page} has no header band")
            continue
        for v in pv:
            if v.get("type") in ("slicer", "advancedSlicerVisual") and v.get("y", 0) < band["y"] + band["h"]:
                c = v.get("container") if isinstance(v.get("container"), dict) else {}
                if v.get("type") == "slicer" and c.get("background") is not False:
                    bad.append(f"{v['id']} filter sits in its own box on the band")
    res[15] = (not bad, "; ".join(dict.fromkeys(bad))[:200])
    return res


CHARTS = {"lineChart", "areaChart", "barChart", "clusteredBarChart", "columnChart", "clusteredColumnChart",
          "lineStackedColumnComboChart", "lineClusteredColumnComboChart", "ribbonChart"}


def passed(res):
    return sum(1 for ok, _ in res.values() if ok)


def total(res):
    """The score out of 10: the share of checks passed (15 checks)."""
    return round(passed(res) * 10 / max(len(res), 1))


def say(res):
    """The plain lines for the final screen and the wrap-up."""
    t = total(res)
    lines = [f"Polish {t}/10 ({passed(res)} of {len(res)} checks; target {TARGET} before showing colleagues)."]
    no = [ITEMS[n] for n in sorted(res) if res[n][0] is False]
    unchecked = [ITEMS[n] for n in sorted(res) if res[n][0] is None]
    if no:
        lines.append("Not yet: " + "; ".join(no) + ".")
    if unchecked:
        lines.append("Not checked: " + "; ".join(unchecked) + ".")
    if t < TARGET:
        lines.append("Below the target: I'd fix these before you show it to colleagues.")
    return lines


def write_review(root, res, mode=None):
    f = pathlib.Path(root) / "design" / "reviews" / "polish.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    rows = ["# Polish score", "", *say(res), "", "| # | Item | Result | Why |", "| --- | --- | --- | --- |"]
    rows += [f"| {n} | {ITEMS[n]} | {'pass' if ok else 'not checked' if ok is None else 'no'} | {why} |"
             for n, (ok, why) in sorted(res.items())]
    if mode:
        rows += ["", f"Build option: {mode}."]
    f.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return f


def parse_items(xs):
    out = {}
    for x in xs or []:
        k, _, v = x.partition("=")
        if k.strip().isdigit() and int(k) in AGENT:
            out[int(k)] = v.strip().lower() in ("pass", "yes", "ok", "true", "1")
    return out
