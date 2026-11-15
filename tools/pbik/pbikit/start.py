"""The start of a build: what the person gave, and the starter layouts (docs/design/phase1-usability.md, A2).

    pbik start detect            what is in the inputs folder, and the path the kit takes
    pbik start inputs            open the inputs folder in File Explorer ("drop a copy here")
    pbik start starters [--kpi M ...] [--date F] [--category F] [--detail F] [--title T]
                                 the 2-3 starter layouts, filled with the model's names, as layout files to draw

Paths: from report (a .Report folder), from wireframe (HTML), from picture (a wireframe image or a screenshot of any
report), starter layouts (requirements only, or nothing). A report or wireframe wins over requirements; the
requirements then fill the KPI list and the assumptions. Data files are never read: a .pbix or .pbit is refused
(save it as a Power BI project), and a data file (csv, xlsx, ...) is named so the person can take it out.
"""
import json, pathlib, shutil

STARTERS = pathlib.Path(__file__).resolve().parents[3] / "docs" / "layouts" / "starters"
HTML = {".html", ".htm"}
IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
REQUIREMENTS = {".md", ".txt", ".docx", ".rtf"}
DATA = {".csv", ".xlsx", ".xls", ".parquet", ".json", ".abf", ".pbix", ".pbit"}
ORDER = ["from report", "from wireframe", "from picture", "starter layouts"]
PLAIN = {"from report": "an existing report", "from wireframe": "a wireframe page",
         "from picture": "a picture (a wireframe image or a report screenshot)",
         "starter layouts": "no layout yet: I'll show you starter layouts"}
STARTER_NAMES = {"executive-summary": "Executive summary", "trend-dashboard": "Trend dashboard",
                 "detail-table": "Detail table", "profile-explorer": "Profile explorer"}
GRID = {"width": 1920, "margin": 32, "columns": 12, "gutter": 24}


class StartError(Exception):
    pass


def inputs_dir(root):
    """The Reference folder (pbikit/drops.py); the old design/reference/inputs is never read."""
    from . import drops
    return drops.reference_dir(root)


def is_report(p):
    return p.is_dir() and p.name.lower().endswith(".report") and (
        (p / "definition.pbir").exists() or (p / "definition").is_dir())


def detect(root):
    """{"path", "reportType", "inputs": [(kind, name)], "requirements": [names], "refused": [names]}."""
    folder = inputs_dir(root)
    found, reqs, refused = [], [], []
    from . import drops
    for p in sorted(folder.rglob("*")) if folder.is_dir() else []:
        if drops.LIVE_PICK in p.relative_to(folder).parts:
            continue                                              # the live-model pick, not a layout input
        if any(is_report(q) for q in p.parents if folder in q.parents or q == folder):
            continue                                              # inside a .Report folder: read as a report
        if is_report(p):
            found.append(("from report", p.name))
        elif p.is_file():
            ext = p.suffix.lower()
            if p.name.lower() in ("readme.txt", ".gitignore", ".gitkeep", "desktop.ini", "thumbs.db"):
                continue                                          # the kit's own notes, not the person's inputs
            if ext in (".pbix", ".pbit"):
                refused.append(p.name)
            elif ext in HTML:
                found.append(("from wireframe", p.name))
            elif ext in IMAGES:
                found.append(("from picture", p.name))
            elif ext in REQUIREMENTS:
                reqs.append(p.name)
            elif ext in DATA:
                refused.append(p.name)
    kinds = [k for k, _ in found]
    path = next((k for k in ORDER if k in kinds), "starter layouts")
    return {"path": path, "reportType": path if path != "starter layouts" else None,
            "inputs": found, "requirements": reqs, "refused": refused}


def say(d):
    """The plain lines for a detect result (facts, then one next line)."""
    out = []
    if d["inputs"] or d["requirements"]:
        what = [f"{n} ({PLAIN[k].split(' (')[0]})" for k, n in d["inputs"]] + [f"{n} (requirements)"
                                                                              for n in d["requirements"]]
        out.append(f"You gave me {len(what)} thing(s): " + "; ".join(what) + ".")
    else:
        out.append("There's nothing in the Reference folder yet.")
    for n in d["refused"]:
        out.append(f"warning: I won't read {n}: it can hold data. Take it out of the Reference folder"
                   + (" and save the report as a Power BI project instead." if n.lower().endswith((".pbix", ".pbit"))
                      else "."))
    out.append(f"Path: {PLAIN[d['path']]}.")
    if d["path"] == "starter layouts":
        out.append("next: tell me what this report should help people decide; then I'll show 2-3 starter layouts as "
                   "pictures")
    else:
        out.append("next: I'll turn it into a plan and show it to you as a picture")
    return out


def open_inputs(root):
    """Make sure the Reference folder exists. It never opens File Explorer (one window per folder lost a copy in the
    walkthrough): the agent names the folder instead."""
    from . import drops
    drops.make(root)
    return inputs_dir(root)


def check(root):
    """At the start of every build: one plain line per drop folder, what it holds and what is missing, and one next
    line. Lists names only: the Model folder is never read here (model intake deletes data files first)."""
    from . import drops, synth as S
    root = pathlib.Path(root)
    drops.make(root)
    lines = []
    model = drops.entries(drops.model_dir(root))
    contract = S.read_json(S.specs(root) / "contract.json") or {}
    approved = bool((contract.get("approval") or {}).get("by"))
    if model:
        names = ", ".join(p.name for p in model)
        lines.append(f"Model: {names}" + (" (read and approved)." if approved else
                                          " (I'll read it now; any data files in it are deleted first)."))
    elif contract:
        lines.append("Model: the model you gave me before" + (" (approved)." if approved else "."))
    else:
        lines.append("Model: empty. Put a copy of your semantic model export in the Model folder (a .SemanticModel "
                     "folder, a TMDL folder or a TMSL export).")
    d = detect(root)
    got = [f"{n} ({PLAIN[k].split(' (')[0]})" for k, n in d["inputs"]] + [f"{n} (requirements)"
                                                                         for n in d["requirements"]]
    if got:
        lines.append("Reference: " + "; ".join(got) + ", kept in the Reference folder.")
    else:
        lines.append("Reference: empty, so I'll ask what the report should help people decide and show starter "
                     "layouts. (A wireframe, screenshot, requirements or an existing report goes in the Reference "
                     "folder.)")
    for n in d["refused"]:
        lines.append(f"warning: I won't read {n} in the Reference folder: it can hold data.")
    lines += drops.old_lines(root)
    if not model and not contract:
        lines.append("next: put the model in the Model folder and say done")
    elif not got:
        lines.append("next: tell me what this report should help people decide")
    else:
        lines.append("next: I'll turn it into a plan and show it to you as a picture")
    return lines


# ---------------------------------------------------------------- starter layouts
def col_x(i):
    col = (GRID["width"] - 2 * GRID["margin"] - (GRID["columns"] - 1) * GRID["gutter"]) / GRID["columns"]
    return round(GRID["margin"] + i * (col + GRID["gutter"]))


def span_w(n):
    col = (GRID["width"] - 2 * GRID["margin"] - (GRID["columns"] - 1) * GRID["gutter"]) / GRID["columns"]
    return round(n * col + (n - 1) * GRID["gutter"])


def starter_names():
    have = {p.stem for p in STARTERS.glob("*.json")} if STARTERS.is_dir() else set()
    return [n for n in STARTER_NAMES if n in have] + sorted(have - set(STARTER_NAMES))


def _fill_text(x, slots):
    if isinstance(x, str):
        for k, v in slots.items():
            x = x.replace("{" + k + "}", v)
        return x
    if isinstance(x, list):
        return [_fill_text(y, slots) for y in x]
    if isinstance(x, dict):
        return {k: _fill_text(v, slots) for k, v in x.items()}
    return x


def _plain(field):
    """ "Table[Column]" -> "Column", "[Measure]" -> "Measure"; anything else unchanged."""
    s = str(field)
    return s[s.index("[") + 1:-1] if "[" in s and s.endswith("]") else s


def fill(name, kpis=(), date=None, category=None, title=None, detail=None):
    """A starter (docs/layouts/starters/<name>.json) as a layout.json: columns to pixels on the grid, slots filled
    with the model's names; unfilled slots keep a readable label ("KPI 2"). `detail` is the field inside a category
    (the profile explorer's second picker). A visual with `edge: left` starts at the page edge (x 0) and ends on its
    last column's edge: the rail of the rail + panel style."""
    src = json.loads((STARTERS / f"{name}.json").read_text(encoding="utf-8"))
    slots = {f"kpi{i}": f"[KPI {i}]" for i in range(1, 5)}
    slots.update({f"kpi{i}": (k if k.startswith("[") or "[" in k else f"[{k}]") for i, k in enumerate(kpis, 1)})
    slots.update(date=date or "Calendar[Date]", category=category or "Category[Name]",
                 detail=detail or "Detail[Name]", title=title or STARTER_NAMES.get(name, name))
    out = {k: v for k, v in src.items() if k not in ("visuals", "_slots")}
    out["visuals"] = []
    plain = {k: _plain(s) for k, s in slots.items()}                 # words people read: "Revenue", not "[Revenue]"
    out["pages"] = _fill_text(out.get("pages", {}), plain)
    for v in src["visuals"]:
        v = dict(v)
        words = {k: v.pop(k) for k in ("container", "text") if k in v}
        v = _fill_text(v, slots)
        v.update(_fill_text(words, plain))
        col, span, edge = v.pop("col"), v.pop("span"), v.pop("edge", None)
        v["x"], v["w"] = col_x(col), span_w(span)
        if edge == "left":
            v["x"], v["w"] = 0, col_x(col + span - 1) + span_w(1)
        out["visuals"].append(v)
    return out


def write_starters(root, kpis=(), date=None, category=None, title=None, detail=None):
    """design/specs/starters/<name>.layout.json for each starter; returns the paths."""
    folder = pathlib.Path(root) / "design" / "specs" / "starters"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    out = []
    for name in starter_names():
        f = folder / f"{name}.layout.json"
        f.write_text(json.dumps(fill(name, kpis, date, category, title, detail), indent=1, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        out.append(f)
    return out
