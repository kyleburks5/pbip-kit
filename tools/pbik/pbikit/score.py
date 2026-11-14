"""`pbik score`: the polish score, on every build's final screen and in the wrap-up (phase1-usability.md, A6).

Ten pass/fail items, one point each. Items 2, 4, 5, 6, 8, 9 and 10 are computed here from the files; items 1
(matches the approved picture: the agent's own judgment, always labelled so), 3 (KPI cards filled: a DAX query) and 7
(interactions working: slicers filter, buttons and bookmarks go where they should) are given by the agent from its
own checks (`--item 1=pass`). An item nobody checked counts 0 and is named "not checked". Target: 7/10 before
showing colleagues.
"""
import json, pathlib, re, subprocess, sys

ITEMS = {1: "matches the approved picture (my own judgment)", 2: "alignment and spacing", 3: "KPI cards filled",
         4: "right visual types", 5: "right measures", 6: "fonts and colours from the theme",
         7: "interactions working", 8: "no overlaps or clutter", 9: "accessibility", 10: "no check errors"}
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
    out = set()
    for xs in (b or {}).values():
        for x in xs if isinstance(xs, list) else [xs]:
            out.add((x.get("field") if isinstance(x, dict) else str(x)).replace("'", ""))
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
        full = validate_fn(report, layout=None)
        plain = validate_fn(report, layout=None, use_a11y=False)
    a11y = [w for w in full.warnings if w not in plain.warnings]
    colour_warn = [w for w in full.warnings if re.search(r"colou?r|font", w, re.I) and w not in a11y]
    res[6] = (not hc and not colour_warn, f"written into the layout: {', '.join(hc[:5])}" if hc else
              (colour_warn[0] if colour_warn else ""))
    res[9] = (not a11y, f"{len(a11y)} accessibility warning(s)" if a11y else "")
    res[10] = (not full.errors, f"{len(full.errors)} error(s)" if full.errors else "")
    return res


def total(res):
    return sum(1 for ok, _ in res.values() if ok)


def say(res):
    """The plain lines for the final screen and the wrap-up."""
    t = total(res)
    lines = [f"Polish {t}/10 (target {TARGET} before showing colleagues)."]
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
