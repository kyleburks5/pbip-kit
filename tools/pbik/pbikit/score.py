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
N/A (v1.10): a check that can't apply (interactions on a report with no slicers, buttons, bookmarks or cross-filtering
visuals; KPI cards with no cards; charts with no charts ...) is "N/A" with its reason and left out of the score, so the
score is passed / applicable x 10. A "no" is never N/A: mark_na() leaves a failure, computed or the agent's, as it is.
Alignment and spacing (v1.10) lists each visual out of line, which edge and by how many pixels (gridsnap.py).
"""
import json, pathlib, re, subprocess, sys

ITEMS = {1: "matches the approved picture (my own judgment)", 2: "alignment and spacing", 3: "KPI cards filled",
         4: "right visual types", 5: "right measures", 6: "fonts and colours from the theme",
         7: "interactions working", 8: "no overlaps or clutter", 9: "accessibility", 10: "no check errors",
         11: "KPI cards read well", 12: "numbers read well", 13: "charts read well", 14: "text sized for the canvas",
         15: "finished look (header band, styled filter)"}
AGENT = (1, 3, 7)
TARGET = 7
PICKERS = ("slicer", "advancedSlicerVisual", "listSlicer", "textSlicer")
BUDGET = 12                      # data visuals per page before it counts as clutter (patterns' own budgets are lower)
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
DECOR = {"shape", "basicShape", "textbox", "image"}


# patterns whose card shows a sentence from a text measure (docs/patterns/app-visuals): left-aligned, no number format
TEXT_PATTERNS = {"live-headline", "context-strip"}


def check_grid(layout):
    """Visual IDs out of line (gridsnap.issues: column edges, the 8 px baseline, row bottoms). A full-width band may
    span 0..1920; a rail (pattern rail-panel, study 2026-11-15) may touch one page edge, with its inner edge on the
    grid; everything else sits on the grid."""
    from . import gridsnap as GS
    return list(dict.fromkeys(i["id"] for i in GS.issues(layout)))


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
                strip = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
                bare = lambda v: isinstance(v.get("container"), dict) and v["container"].get("background") is False  # noqa
                if strip <= 12 and bare(a) and bare(b):
                    continue          # two visuals with no background touching by their padding: nothing overlaps (v1.12)
                bad.append(f"{a['id']}/{b['id']}")
    per_page = {}
    partners = {v.get("comparison") for v in vs if v.get("comparison")}     # a KPI card's own chart: one tile with it
    for v in vs:
        if v.get("type") in PICKERS:                     # pickers are the page's controls, not data to read (v1.12)
            continue
        if v.get("bindings") and not _image_card(v) and v["id"] not in partners:   # card + image card: one tile (v1.11)
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


def lost_since_approval(report, layout, approved):
    """What the approved plan had that the built report lost (v1.7 live walkthrough fix 16): a visual, a table's
    total row, a card's comparison line. [] when nothing was lost or there is no approved plan."""
    if not approved:
        return []
    out = []
    built = built_visuals(report)
    now = {v["id"]: v for v in layout.get("visuals", [])}
    for a in approved.get("visuals", []):
        vid = a.get("id")
        if not vid or a.get("decorative"):
            continue
        if vid not in now or vid not in built:
            out.append(f"{vid} ({a.get('type')}) is gone")
            continue
        vf = next(pathlib.Path(report).glob(f"definition/pages/*/visuals/{vid}_*/visual.json"), None)
        try:
            vd = json.loads(vf.read_text(encoding="utf-8")) if vf else {}
        except ValueError:
            vd = {}
        objs = vd.get("visual", {}).get("objects", {})
        if a.get("type") in ("tableEx", "pivotTable") and (a.get("props") or {}).get("total.totals") is not False:
            for e in objs.get("total", []):
                show = ((e.get("properties") or {}).get("totals") or {}).get("expr", {}).get("Literal", {})
                if str(show.get("Value", "")).lower() == "false":
                    out.append(f"{vid} lost its total row")
                    break
        rl = a.get("referenceLabels") if isinstance(a.get("referenceLabels"), dict) else {}
        if rl.get("labels") and not (now[vid].get("referenceLabels") or {}).get("labels"):
            out.append(f"{vid} lost its comparison line")
    return out


def flat_layout(layout):
    """A layout from before pbik (pages a list, each with its own visuals: Reps 1-4) in pbik's form (pages by id,
    visuals in one list), so an old rep can be scored (v1.12, Part D: Rep 4's score stopped on the list)."""
    if not isinstance((layout or {}).get("pages"), list):
        return layout
    pages, vis = {}, list(layout.get("visuals") or [])
    for p in layout["pages"]:
        if isinstance(p, dict):
            pid = p.get("id") or p.get("name")
            pages[pid] = {k: x for k, x in p.items() if k != "visuals"}
            vis += [{**v, "page": v.get("page", pid)} for v in p.get("visuals") or [] if isinstance(v, dict)]
    return {**layout, "pages": pages, "visuals": vis}


def compute(report, layout, agent=None, validate_fn=None, approved=None):
    """{item: (passed True/False/None, why)}. `agent`: {1: True, 3: False, 7: "how it was tested"} from the agent's
    own checks. Item 7 (interactions) passes only with how it was tested; "pass" alone stays "not checked" (fix 16).
    Item 1 fails whatever the agent says when something in the approved plan was lost."""
    agent = agent or {}
    layout = flat_layout(layout)
    res = {}
    for n in AGENT:
        res[n] = (agent.get(n), "" if n in agent else "not checked")
    if 7 in agent:
        tested = agent[7]
        if tested is True or tested is None or (isinstance(tested, str) and not tested.strip()):
            res[7] = (None, "not checked: say what was clicked and what changed")
        elif tested is False:
            res[7] = (False, "")
        else:
            res[7] = (True, f"tested: {tested}")
    if approved is None:
        af = pathlib.Path(report).parent / "design" / "plan" / "approved-layout.json"
        try:
            approved = json.loads(af.read_text(encoding="utf-8")) if af.exists() else None
        except ValueError:
            approved = None
    lost = lost_since_approval(report, layout, approved)
    if lost:
        res[1] = (False, "lost since the approved plan: " + "; ".join(lost[:5]))
    from . import gridsnap as GS
    off = GS.issues(layout)                     # v1.10: exactly which visuals, which edge and by how many pixels
    res[2] = (not off, "out of line: " + "; ".join(i["text"] for i in off) if off else "")
    built = built_visuals(report)
    want = {v["id"]: v for v in layout.get("visuals", [])}
    missing = sorted(set(want) - set(built))
    types = [i for i in want if i in built and built[i][0] != want[i].get("type")
             and want[i].get("type") not in ("deneb", "custom")]     # both resolve to a visual id at build (v1.11)
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
    for n, reason in not_applicable(layout).items():
        mark_na(res, n, reason)
    return res


# ---------------------------------------------------------------- N/A: a check that can't apply (v1.10)
NA = "n/a"
CARDS = {"cardVisual", "card", "multiRowCard", "kpi"}
SLICER_TYPES = {"slicer", "advancedSlicerVisual", "listSlicer", "textSlicer"}
NAV_TYPES = {"pageNavigator", "bookmarkNavigator"}
VALUE_ROLES = {"Data", "Values", "Y", "Y2", "Tooltips", "Indicator", "Goal", "TargetValue", "Value", "Size",
               "MinValue", "MaxValue", "Target"}


def _image_card(v):
    return "udfCard" in v or any(c.get("type") == "image" for c in v.get("cf", []) or [])


def _cross_filters(v):
    """A data visual a person can click to filter the others: it has a category-like field (axis, rows, legend)."""
    return any(role not in VALUE_ROLES and xs for role, xs in (v.get("bindings") or {}).items())


def not_applicable(layout):
    """{item: reason} for the checks that can't apply to this layout. mark_na() never turns a failure into N/A."""
    vis = [v for v in layout.get("visuals", []) if not v.get("decorative")]
    out = {}
    if not any(v.get("type") in CARDS for v in vis):
        out[3] = "no KPI cards in the report"
    if not any(v.get("type") == "cardVisual" and not _image_card(v) for v in vis) and             not any(v.get("type") in CARDS - {"cardVisual"} for v in vis):
        out[11] = ("no native KPI cards: image cards draw their own change line" if
                   any(v.get("type") in CARDS for v in vis) else "no KPI cards in the report")
    interactive = []
    for page in {v.get("page") for v in vis}:
        pv = [v for v in vis if v.get("page") == page]
        data = [v for v in pv if v.get("bindings") or "udfCard" in v]
        if any(v.get("type") in SLICER_TYPES | NAV_TYPES for v in pv) or                 any(v.get("type") == "actionButton" and v.get("action") for v in pv) or                 (len(data) > 1 and any(_cross_filters(v) for v in data)) or                 ((layout.get("pages") or {}).get(page) or {}).get("bookmarks") or                 ((layout.get("pages") or {}).get(page) or {}).get("drillthrough"):
            interactive.append(page)
    if not interactive:
        out[7] = "no slicers, buttons, bookmarks or cross-filtering visuals on any page"
    if not any(v.get("bindings") and not _image_card(v) for v in vis):
        out[12] = "no visual shows numbers as values: image cards draw their own, and the numbers audit checks them"
    if not any(v.get("type") in CHARTS for v in vis):
        out[13] = "no charts in the report"
    titled = any(isinstance(v.get("container"), dict) and v["container"].get("title") for v in vis)
    if not titled and not any(v.get("type") in CHARTS for v in vis):
        out[14] = "no visual titles, axes or legends to size"
    return out


def mark_na(res, n, reason):
    """N/A only where nothing failed: a "no" (computed, or the agent's own) always stays a "no", and a check the
    agent passed with how it tested it stays a pass."""
    ok, why = res.get(n, (None, ""))
    if ok is False:
        return False
    if n == 7 and ok is True:
        return False
    if n in (1, 3) and ok is True:
        return False
    res[n] = (NA, reason)
    return True


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
        if v.get("type") != "cardVisual" or any(c.get("type") == "image" for c in v.get("cf", []))                 or v.get("pattern") in TEXT_PATTERNS:   # a sentence, not a number (v1.11 app-visual patterns)
            continue
        data = (v.get("bindings") or {}).get("Data") or []
        if len(data) == 1 and str((planned.get(_name(data[0])) or {}).get("dataType", "")).lower() in ("string", "text"):
            continue                                       # a sentence card (a share line), not a number (v1.12)
        align = _prop(v, "value.horizontalAlignment") or _style(theme, "cardVisual", "value", "horizontalAlignment",
                                                                "center")
        rl_ = v.get("referenceLabels") if isinstance(v.get("referenceLabels"), dict) else {}
        if len(data) == 1 and v.get("w", 0) >= 300 and str(align).lower() == "left" and not rl_.get("labels"):
            # a left-aligned value with its comparison line under it is the house style (v1.12); a bare number isn't
            bad.append(f"{v['id']} leaves its right side empty")
        rl = v.get("referenceLabels") if isinstance(v.get("referenceLabels"), dict) else {}
        for lab in rl.get("labels", []) or []:
            if CMP.search(_name(lab.get("value", "")) + " " + _name(lab.get("detail", ""))) and \
                    not lab.get("detailColor"):
                bad.append(f"{v['id']} change isn't coloured by direction")
        if rl.get("labels") and _last_year(rl) and not year_chosen(layout, v.get("page")):
            bad.append(f"{v['id']} compares with last year, but no year is chosen on the page, so it isn't clear "
                       "which years it compares (add a year filter, or say the year in the title)")
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
        if v.get("pattern") in TEXT_PATTERNS:
            continue
        for role, xs in (v.get("bindings") or {}).items():
            for x in xs if isinstance(xs, list) else [xs]:
                name = _name(x)
                fmt = None
                if model:
                    home = model.measure_home(name)
                    if home:
                        fmt = model.tables[home[0]].measures[name].format_string
                fmt = fmt or (planned.get(name) or {}).get("formatString")
                home = model.measure_home(name) if model else None
                text = (home and model.tables[home[0]].measures[name].is_text()) or                     str((planned.get(name) or {}).get("dataType", "")).lower() in ("string", "text")
                if (home or name in planned) and not text:      # a text measure has no number format (v1.12)
                    if not fmt or not ("," in fmt or "%" in fmt or "\"" in fmt):
                        bad.append(f"{name} has no thousands separator")
        if v.get("type") in ("tableEx", "pivotTable"):
            vals = (v.get("bindings") or {}).get("Values", [])
            cmp_cols = [_name(x) for x in vals if CMP.search(_name(x))]
            coloured = {_name(c.get("target") or c.get("field", "")) for c in v.get("cf", [])
                        if c.get("type") in ("rules", "measure") or      # a diverging gradient around a middle
                        (c.get("type") == "gradient" and c.get("mid") and c.get("midValue") is not None)}   # (v1.12)
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
    for page, sp in (layout.get("pages") or {}).items():
        if isinstance(sp, dict) and (sp.get("tooltip") or sp.get("drillthrough") and sp.get("hidden")):
            continue                                   # a tooltip (or hidden drill-through) page has no header
        pv = [v for v in vis if v.get("page") == page]
        band = next((v for v in pv if v.get("type") in ("shape", "basicShape") and v.get("y", 99) <= 0
                     and v.get("w", 0) >= 1800), None)
        if not band:                                   # a full-height rail at the left frames the page the same way
            band = next((v for v in pv if v.get("type") in ("shape", "basicShape") and v.get("x", 99) <= 0
                         and v.get("h", 0) >= 900 and v.get("pattern") == "rail-panel"), None)   # (v1.12, test 3)
            if band:
                band = {**band, "h": 0}                # the pickers in a rail aren't on a band
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


LY = re.compile(r"last year|\bLY\b|prior year|previous year|\bPY\b|year ago|same period", re.I)
YEARISH = re.compile(r"year|date|calendar|period|fiscal|month", re.I)


def _last_year(rl):
    return any(LY.search(" ".join(str(lab.get(k, "")) for k in ("title", "value", "detail")))
               for lab in rl.get("labels", []) or [])


def year_chosen(layout, page):
    """True when the page (or report) has a slicer or filter on a year or date field."""
    def fields(x):
        out = []
        for f in (x if isinstance(x, list) else [x]):
            out.append(str(f.get("field", "")) if isinstance(f, dict) else str(f))
        return out
    for v in layout.get("visuals", []):
        if v.get("page") == page and v.get("type") in ("slicer", "advancedSlicerVisual", "listSlicer",
                                                       "textSlicer"):
            if any(YEARISH.search(f) for xs in (v.get("bindings") or {}).values() for f in fields(xs)):
                return True
    pages = layout.get("pages", {}) or {}
    if isinstance(pages.get(page), dict) and pages[page].get("drillthrough"):     # a drill keeps the source page's
        if any(year_chosen(layout, k) for k, sp in pages.items()               # filters: its year comes along (v1.12)
               if k != page and not (isinstance(sp, dict) and sp.get("drillthrough"))):
            return True
    flt = list((pages.get(page) or {}).get("filters", []) or []) + list(
        ((layout.get("report") or {}).get("filters")) or [])
    return any(YEARISH.search(str(f.get("field", "")) if isinstance(f, dict) else str(f)) for f in flt)


def passed(res):
    return sum(1 for ok, _ in res.values() if ok is True)


def applicable(res):
    return {n: r for n, r in res.items() if r[0] != NA}


def total(res):
    """The score out of 10: the share of the checks that apply that passed (N/A left out, v1.10)."""
    return round(passed(res) * 10 / max(len(applicable(res)), 1))


def result_word(ok):
    return "pass" if ok is True else "N/A" if ok == NA else "not checked" if ok is None else "no"


def say(res):
    """The plain lines for the final screen and the wrap-up."""
    t = total(res)
    na = [n for n in sorted(res) if res[n][0] == NA]
    lines = [f"Polish {t}/10 ({len(applicable(res))} of {len(res)} checks applied"
             + (f", {len(na)} N/A" if na else "") + f"; {passed(res)} passed; target {TARGET} before showing "
             "colleagues)."]
    if len(na) * 3 > len(res):                  # more than a third didn't apply: the score says less than it seems
        lines.append(f"Limited score: many checks didn't apply ({len(na)} of {len(res)} N/A).")
    no = [ITEMS[n] for n in sorted(res) if res[n][0] is False]
    unchecked = [ITEMS[n] for n in sorted(res) if res[n][0] is None]
    if no:
        lines.append("Not yet: " + "; ".join(no) + ".")
    if unchecked:
        lines.append("Not checked: " + "; ".join(unchecked) + ".")
    if na:
        lines.append("Not applicable: " + "; ".join(f"{ITEMS[n]} ({res[n][1]})" for n in na) + ".")
    if t < TARGET:
        lines.append("Below the target: I'd fix these before you show it to colleagues.")
    return lines


def write_review(root, res, mode=None):
    f = pathlib.Path(root) / "design" / "reviews" / "polish.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    rows = ["# Polish score", "", *say(res), "", "| # | Item | Result | Why |", "| --- | --- | --- | --- |"]
    rows += [f"| {n} | {ITEMS[n]} | {result_word(ok)} | {why} |" for n, (ok, why) in sorted(res.items())]
    if mode:
        rows += ["", f"Build option: {mode}."]
    f.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return f


def parse_items(xs):
    """--item 1=pass, --item 3=no, --item 7=pass:clicked the region slicer, the cards changed. Item 7 keeps the
    words after "pass:" as how it was tested; without them it is "not checked"."""
    out = {}
    for x in xs or []:
        k, _, v = x.partition("=")
        if not (k.strip().isdigit() and int(k) in AGENT):
            continue
        word, _, how = v.partition(":")
        ok = word.strip().lower() in ("pass", "yes", "ok", "true", "1")
        if int(k) == 7:
            out[7] = (how.strip() or True) if ok else False
        else:
            out[int(k)] = ok
    return out
