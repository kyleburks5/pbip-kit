"""Fidelity check: does the high-fidelity wireframe draw what Power BI Desktop shows?

    python design/scripts/fidelity_check.py                       every page; the report open and saved in Desktop
    python design/scripts/fidelity_check.py --port auto           also title measures and card values from the model
    python design/scripts/fidelity_check.py --pages P1 --no-desktop    the wireframe against the report files only

For each page it takes a screenshot of the wireframe page (headless Edge, labels off, 1:1) and of the Desktop page
(`pbik desktop screenshot`, Desktop Bridge), shows them side by side in <out>/fidelity.html, and lists in
<out>/fidelity.md the visuals whose position, type or main text differ:
- position and size: the wireframe's box against the report's visual.json, as Desktop saved it (a group member's
  position is relative to its group there; a text box gets the headroom pbik build gives it, TEXT_FIT), within
  --tolerance px;
- type: the wireframe's visual type against visual.json `visualType` (a Deneb visual is "deneb");
- main text: a text box's or button's text, a card's values, else the title. Desktop's side comes from visual.json
  (literal text) or, with --port, from the open model: title measures, and card values formatted with the measure's
  format string (FORMAT in DAX), under the layout's default state (wireframe_data.py). Anything that can't be read on
  one side is "not compared", with the reason.
A visual on one side only is listed too. The files are what Desktop shows only once Desktop has saved, so the check
stops when Desktop reports unsaved changes. Desktop also reports them right after opening a report (.claude/rules/
pbik.md): when you know nothing changed, pass --assume-saved (the check then says so). Aggregates only: the queries are wireframe_data.py's (privacy rules
included). Exit 0 when nothing differs, 1 when something does, 3 when Desktop couldn't be checked.
"""
import argparse, html, html.parser, json, pathlib, re, subprocess, sys, unicodedata

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "tools" / "pbik"))

import edge_page  # noqa: E402
import wireframe_data as W  # noqa: E402
from pbikit.build import TEXT_FIT  # noqa: E402

TYPE_ALIASES = {"basicShape": "shape"}
CARDS = ("cardVisual", "card")


def norm_type(t):
    t = t or ""
    return "deneb" if t.lower().startswith("deneb") else TYPE_ALIASES.get(t, t)


def norm_text(s):
    s = unicodedata.normalize("NFKC", str(s or "")).replace("−", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- the wireframe, as Edge draws it
class _Visuals(html.parser.HTMLParser):
    """[{id, page, type, main, measure, x, y, w, h, hidden}] from the drawn wireframe's DOM."""

    def __init__(self):
        super().__init__()
        self.out, self.page, self.depth = [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-page" in a:
            self.page = a["data-page"]
        cls = (a.get("class") or "").split()
        if "data-id" in a and "v" in cls:
            st = {k.strip(): x.strip() for k, x in (s.split(":", 1) for s in (a.get("style") or "").split(";") if ":" in s)}
            px = lambda k: float(re.sub(r"[^\d.\-]", "", st.get(k, "0")) or 0)   # noqa: E731
            self.out.append({"id": a["data-id"], "page": self.page, "type": a.get("data-type", ""),
                             "main": a.get("data-main") or "", "measure": a.get("data-main-measure") == "1",
                             "x": px("left"), "y": px("top"), "w": px("width"), "h": px("height"),
                             "hidden": "hidden" in a})


def visuals_of(dom):
    """The drawn visuals in a wireframe DOM (data-id, data-type, data-main and the box draw() sets)."""
    p = _Visuals()
    p.feed(dom)
    return p.out


def wireframe_visuals(page_html):
    return visuals_of(edge_page.dom(page_html, hash_="#labels=off"))


# ---------------------------------------------------------------- the report, as Desktop saved it
def literal(x):
    """A PBIR literal ({"expr": {"Literal": {"Value": "'text'"}}}) as Python, or None."""
    v = (((x or {}).get("expr") or {}).get("Literal") or {}).get("Value") if isinstance(x, dict) else None
    if v is None:
        return None
    if v in ("true", "false"):
        return v == "true"
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1].replace("''", "'")
    return v


def measure_of(x):
    m = (((x or {}).get("expr") or {}).get("Measure") or {}) if isinstance(x, dict) else {}
    return m.get("Property")


def objects_props(objs, name):
    """The properties of an object entry without a selector, or with the default one."""
    for e in (objs or {}).get(name) or []:
        sel = e.get("selector")
        if not sel or sel.get("id") == "default":
            return e.get("properties") or {}
    return {}


def report_visuals(report_dir):
    """{page displayName: [{id, type, x, y, w, h, hidden, text, title, titleMeasure, valueShow, file}]}"""
    from pbikit.report import Report
    rep, out = Report(report_dir), {}
    for name, pd, folder in rep.pages():
        items = []
        for d, f in rep.visuals(folder):
            m = re.match(r"(P\d+-V\d+)_", f.parent.name)
            vis = d.get("visual") or {}
            objs, cont = vis.get("objects") or {}, vis.get("visualContainerObjects") or {}
            it = {"id": m.group(1) if m else None, "name": d.get("name"), "parent": d.get("parentGroupName"),
                  "type": "group" if "visualGroup" in d else vis.get("visualType", ""), "file": str(f),
                  "hidden": bool(d.get("isHidden")), **{k: (d.get("position") or {}).get(p, 0) for k, p in
                                                         (("x", "x"), ("y", "y"), ("w", "width"), ("h", "height"))}}
            if it["type"] == "textbox":
                paras = objects_props(objs, "general").get("paragraphs") or []
                it["text"] = " ".join("".join(r.get("value", "") for r in p.get("textRuns", [])) for p in paras)
            elif it["type"] == "actionButton":
                tp = objects_props(objs, "text")
                it["text"] = literal(tp.get("text")) or "" if literal(tp.get("show")) is not False else ""
            tt = objects_props(cont, "title")
            if literal(tt.get("show")) is True:
                it["title"], it["titleMeasure"] = literal(tt.get("text")), measure_of(tt.get("text"))
            else:
                it["title"] = ""
            it["valueShow"] = literal(objects_props(objs, "value").get("show")) is not False
            items.append(it)
        by_name = {i["name"]: i for i in items}
        for i in items:                           # a member's position is relative to its group
            p = by_name.get(i["parent"])
            while p:
                i["x"], i["y"] = i["x"] + p["x"], i["y"] + p["y"]
                p = by_name.get(p["parent"])
        out[pd.get("displayName", name)] = items
    return out


# ---------------------------------------------------------------- Desktop's text from the open model
def precision(fmt, p):
    """value.labelPrecision on a format string, as the wireframe applies it ('0.0%' at 0 -> '0%')."""
    if p is None:
        return fmt
    f = (fmt or "#,0").split(";")[0]
    dec = "." + "0" * int(p) if p > 0 else ""
    if re.search(r"[0#]\.[0#]+", f):
        return re.sub(r"([0#])\.[0#]+", lambda m: m.group(1) + dec, f, count=1)
    return re.sub(r"([0#])(?![\s\S]*[0#])", lambda m: m.group(1) + dec, f, count=1)


def model_texts(layout, model, port, runner=None):
    """{visual ID: {"title": text, "values": [formatted]}} evaluated on the open model under the layout's default
    state: title measures, and card values through FORMAT with each measure's format string."""
    runner = runner or W.run
    privacy, sels, out = layout["privacy"], W.selections(layout), {}
    for v in layout.get("visuals", []):
        q = W.visual_query(v, layout, model, privacy, sels)
        if not q:
            continue
        got = {}
        if q.get("refDax") and ["title", "title"] in q.get("rowItems", []):
            row = runner(W.with_defines(q["refDax"]), port)[0]
            nm = sum(1 for r in q.get("refs", []) if "value" not in r)
            items = dict(zip([k for _, k in q["rowItems"]], row[1 + nm:]))
            if isinstance(row[0], (int, float)) and row[0] >= privacy.get("minGroup", 5):
                got["title"] = items.get("title")
        if v["type"] in CARDS and not q["groups"] and q["values"]:
            dax = q["dax"]
            pr = v.get("props") or {}
            prec = number(pr.get("value.labelPrecision@default", pr.get("value.labelPrecision")))
            for k, x in enumerate(q["values"]):
                f = precision(x["format"], prec) if x["format"] else None
                dax = dax.replace(f'"v{k}", {x["ref"]}', f'"v{k}", ' + (f'FORMAT ( {x["ref"]}, "{f.replace(chr(34), chr(34) * 2)}" )'
                                                                        if f else x["ref"]), 1)
            row = runner(W.with_defines(dax), port)[0]
            n = row[0]
            if isinstance(n, (int, float)) and n >= privacy.get("minGroup", 5):
                got["values"] = [("" if x is None else (f"{x:g}" if isinstance(x, float) else str(x)))
                                 for x in row[1:1 + len(q["values"])]]
        if got:
            out[v["id"]] = got
    return out


def number(x):
    if isinstance(x, dict) and "int" in x:
        return x["int"]
    return x if isinstance(x, (int, float)) else None


# ---------------------------------------------------------------- compare
def compare(wf, rp, model=None, tolerance=2):
    """Differences on one page: [(id, what, wireframe, desktop)]; and the not-compared notes [(id, reason)]."""
    diffs, notes = [], []
    rp_by = {i["id"]: i for i in rp if i["id"]}
    wf_by = {v["id"]: v for v in wf}
    for vid in sorted(set(wf_by) | set(rp_by), key=lambda x: (x[:x.index("-")], int(x.split("V")[1]))):
        a, b = wf_by.get(vid), rp_by.get(vid)
        if not b:
            if not a["hidden"]:
                diffs.append((vid, "missing in the report", a["type"], ""))
            continue
        if not a:
            if b["type"] != "group" and not b["hidden"]:
                diffs.append((vid, "missing in the wireframe", "", b["type"]))
            continue
        if b["type"] == "group":
            continue
        if a["hidden"] != b["hidden"]:
            diffs.append((vid, "hidden", str(a["hidden"]), str(b["hidden"])))
        if a["hidden"] and b["hidden"]:
            continue
        if norm_type(a["type"]) != norm_type(b["type"]):
            diffs.append((vid, "type", a["type"], b["type"]))
        dy, dh = TEXT_FIT.get(a["type"], (0, 0))   # pbik build's headroom for text boxes
        a = {**a, "y": a["y"] + dy, "h": a["h"] + dh}
        off = [k for k in ("x", "y", "w", "h") if abs(float(a[k]) - float(b[k])) > tolerance]
        if off:
            diffs.append((vid, "position", ", ".join(f"{k} {a[k]:g}" for k in off), ", ".join(f"{k} {b[k]:g}" for k in off)))
        t = b["type"]
        if t in ("textbox", "actionButton"):
            want = b.get("text", "")
        elif t in CARDS:
            mv = (model or {}).get(vid, {})
            if not b["valueShow"]:
                want = ""
            elif "values" in mv:
                want = " | ".join(mv["values"])
            else:
                notes.append((vid, "card value needs --port" if model is None else "card value: a group under the minimum"))
                continue
        else:
            if b.get("titleMeasure"):
                mv = (model or {}).get(vid, {})
                if "title" not in mv:
                    notes.append((vid, f"title measure [{b['titleMeasure']}]: needs --port"))
                    continue
                want = mv["title"]
            else:
                want = b.get("title") or ""
            if a["measure"]:
                notes.append((vid, "the wireframe's title measure isn't evaluated (rerun wireframe_data.py)"))
                continue
        if norm_text(a["main"]) != norm_text(want):
            diffs.append((vid, "main text", a["main"], want or ""))
    return diffs, notes


# ---------------------------------------------------------------- report files
def write_report(out, pages):
    """fidelity.md and fidelity.html in out."""
    md = ["# Fidelity check: wireframe against Desktop", "",
          "Generated by design/scripts/fidelity_check.py. Position from visual.json as Desktop saved it; main text "
          "is a text box's or button's text, a card's values, else the title.", ""]
    for pg in pages:
        md += [f"## {pg['name']}", ""]
        if pg["diffs"]:
            md += ["| Visual | Differs in | Wireframe | Desktop |", "|---|---|---|---|"]
            md += [f"| {v} | {w} | {a.replace('|', '/')} | {b.replace('|', '/')} |" for v, w, a, b in pg["diffs"]]
        else:
            md.append("No differences in position, type or main text.")
        if pg["notes"]:
            md += ["", "Not compared: " + "; ".join(f"{v} ({r})" for v, r in pg["notes"])]
        md.append("")
    (out / "fidelity.md").write_text("\n".join(md), encoding="utf-8")
    flagged = lambda pg: {v for v, *_ in pg["diffs"]}   # noqa: E731
    secs = []
    for pg in pages:
        boxes = "".join(f'<div class="box" style="left:{b["x"] / pg["w"] * 100:.3f}%;top:{b["y"] / pg["h"] * 100:.3f}%;'
                        f'width:{b["w"] / pg["w"] * 100:.3f}%;height:{b["h"] / pg["h"] * 100:.3f}%"><span>{html.escape(b["id"])}</span></div>'
                        for b in pg["boxes"] if b["id"] in flagged(pg))
        shot = lambda f, label: (f'<figure><figcaption>{label}</figcaption><div class="frame"><img src="{html.escape(f)}" alt="{label}">'   # noqa: E731
                                 f'{boxes}</div></figure>' if f else f'<figure><figcaption>{label}</figcaption><p>no screenshot</p></figure>')
        rows = "".join(f"<tr><td>{html.escape(v)}</td><td>{html.escape(w)}</td><td>{html.escape(a)}</td><td>{html.escape(b)}</td></tr>"
                       for v, w, a, b in pg["diffs"]) or '<tr><td colspan="4">No differences.</td></tr>'
        secs.append(f'<section><h2>{html.escape(pg["name"])}</h2><div class="pair">{shot(pg["wireframe_png"], "Wireframe")}'
                    f'{shot(pg["desktop_png"], "Desktop")}</div><table><tr><th>Visual</th><th>Differs in</th><th>Wireframe</th>'
                    f'<th>Desktop</th></tr>{rows}</table></section>')
    (out / "fidelity.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Fidelity check</title><style>
body {{ margin: 0; padding: 16px; font: 14px 'Segoe UI', system-ui, sans-serif; background: #f4f6f9; color: #1d2733; }}
.pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }} figure {{ margin: 0; }}
figcaption {{ font-weight: 600; margin-bottom: 4px; }} .frame {{ position: relative; }} .frame img {{ width: 100%; display: block; border: 1px solid #cdd5df; }}
.box {{ position: absolute; border: 2px solid #d1343e; box-sizing: border-box; }} .box span {{ position: absolute; top: 0; left: 0; background: #d1343e; color: #fff; font: 600 10px Consolas, monospace; padding: 1px 3px; }}
table {{ border-collapse: collapse; margin: 12px 0 28px; width: 100%; background: #fff; }} th, td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid #e3e8ef; vertical-align: top; }}
@media (max-width: 900px) {{ .pair {{ grid-template-columns: 1fr; }} }}
</style></head><body><h1>Fidelity check: wireframe against Desktop</h1>{"".join(secs)}</body></html>""", encoding="utf-8")


def desktop_state():
    """0 clean, 3 bridge not available, 4 unsaved changes (pbik desktop state --fail-if-dirty)."""
    r = subprocess.run([sys.executable, str(KIT / "tools" / "pbik" / "pbik.py"), "desktop", "state", "--fail-if-dirty"],
                       cwd=KIT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def desktop_screenshot(report_dir, page, out, w, h):
    r = subprocess.run([sys.executable, str(KIT / "tools" / "pbik" / "pbik.py"), "desktop", "screenshot", "--report",
                        str(report_dir), "--page", page, "--out", str(out), "--region", f"0,0,{w},{h}"],
                       cwd=KIT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode or not pathlib.Path(out).exists():
        raise RuntimeError((r.stdout + r.stderr).strip()[:400] or "no screenshot")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", default=str(KIT), help="the project root (default: this kit)")
    ap.add_argument("--layout", help="default: <project>/design/specs/layout.json")
    ap.add_argument("--wireframe", help="default: <project>/design/wireframes/wireframe.html")
    ap.add_argument("--report", help="the *.Report folder (default: the one in the project root)")
    ap.add_argument("--out", help="default: <project>/design/reviews/fidelity")
    ap.add_argument("--pages", nargs="*", help="layout page keys (default: every page)")
    ap.add_argument("--port", help="the open Desktop model ('auto'): title measures and card values")
    ap.add_argument("--no-desktop", action="store_true", help="no Desktop screenshots (files and wireframe only)")
    ap.add_argument("--assume-saved", action="store_true",
                    help="go on although Desktop reports unsaved changes (the flag it sets on opening a report)")
    ap.add_argument("--tolerance", type=float, default=2, help="position difference allowed, px (default 2)")
    a = ap.parse_args(argv)
    root = pathlib.Path(a.project).resolve()
    layout = json.loads(pathlib.Path(a.layout or root / "design" / "specs" / "layout.json").read_text(encoding="utf-8"))
    page_html = pathlib.Path(a.wireframe or root / "design" / "wireframes" / "wireframe.html").read_text(encoding="utf-8")
    report_dir = pathlib.Path(a.report) if a.report else next(root.glob("*.Report"), None)
    if not report_dir:
        ap.error("no *.Report folder in the project (pass --report)")
    out = pathlib.Path(a.out or root / "design" / "reviews" / "fidelity")
    out.mkdir(parents=True, exist_ok=True)
    if not a.no_desktop:
        code, msg = desktop_state()
        if code == 4 and a.assume_saved:
            print("Desktop reports unsaved changes; going on as asked (--assume-saved): the files are taken as what "
                  "it shows.")
        elif code == 4:
            print("Desktop has unsaved changes: the files aren't what it shows. Save (or close without saving and "
                  "reopen), then run the check again.")
            return 3
        elif code:
            print(msg.splitlines()[0] if msg else "Desktop bridge not available")
            print("Not checked. Open the report in Desktop with the Desktop Bridge on, or pass --no-desktop.")
            return 3
    model_txt = None
    if a.port:
        from pbikit import slicerfit, tmdl
        try:
            port = slicerfit.require_port(a.port)
        except RuntimeError as e:
            ap.error(str(e))
        mf = next(root.glob("*.SemanticModel"), None)
        W.load_extensions(root)
        model_txt = model_texts(layout, tmdl.load(mf) if mf else None, port)
    wf = wireframe_visuals(page_html)
    rp = report_visuals(report_dir)
    keys = a.pages or list(layout.get("pages", {}))
    pages, total = [], 0
    for i, key in enumerate(keys):
        lp = layout["pages"][key]
        name = lp.get("displayName", key)
        w = lp.get("width", 1920)
        h = lp.get("height", 1080)
        diffs, notes = compare([v for v in wf if v["page"] == key], rp.get(name, []), model_txt, a.tolerance)
        wpng = out / f"{key}-wireframe.png"
        edge_page.screenshot(page_html, wpng, w, h, hash_=f"#shot&labels=off&page={list(layout['pages']).index(key) + 1}")
        dpng = None
        if not a.no_desktop:
            try:
                dpng = desktop_screenshot(report_dir, name, out / f"{key}-desktop.png", w, h)
            except RuntimeError as e:
                notes.append(("page", f"Desktop screenshot failed: {e}"))
        boxes = [v for v in wf if v["page"] == key] + [b for b in rp.get(name, []) if b["id"]]
        pages.append({"name": f"{key} {name}", "w": w, "h": h, "diffs": diffs, "notes": notes, "boxes": boxes,
                      "wireframe_png": wpng.name, "desktop_png": dpng.name if dpng else None})
        total += len(diffs)
        print(f"{key} {name}: {len(diffs)} difference(s)" + (f", {len(notes)} not compared" if notes else ""))
        for v, what, x, y in diffs:
            print(f"  {v} {what}: wireframe {x!r} / Desktop {y!r}")
    write_report(out, pages)
    print(f"wrote {out / 'fidelity.md'} and {out / 'fidelity.html'}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
