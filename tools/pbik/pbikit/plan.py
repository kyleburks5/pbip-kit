"""The plan as a picture (docs/design/phase1-usability.md, A3): what will be built, drawn, plus a short list.

    pbik plan show [--layout L] [--purpose "P1=..."] [--assume "..."]   draw each page as a PNG (design/plan/) and
                                                                          write design/plan/plan.md (the short list)
    pbik plan picture <layout> --out <folder>                           draw any layout (a starter, a draft)
    pbik plan approve                                                    the person said OK in the chat: record the
                                                                          plan's hash and the page purposes

The picture is the high-fidelity wireframe (design/scripts/gen_wireframe_hf.py) screenshotted page by page in headless
Edge. The list: per page its purpose; each KPI and the measure it uses (and what it is compared with); the
assumptions (design/specs/plan.json `assumptions`, the agent's defaults: which total measure, colour rules, defaults);
each fallback with the native option tried (so OK on the plan approves it); the build option, data class and model.
The approved hash is checked by the build: a plan changed after OK is shown again first.
"""
import hashlib, json, pathlib, subprocess, sys

KIT = pathlib.Path(__file__).resolve().parents[3]
SCRIPTS = KIT / "design" / "scripts"
PLAN_DIR = pathlib.Path("design") / "plan"
DATA_TYPES = {"cardVisual", "card", "multiRowCard", "kpi"}


class PlanError(Exception):
    pass


def layout_file(root, layout=None):
    return pathlib.Path(layout) if layout else pathlib.Path(root) / "design" / "specs" / "layout.json"


def plan_file(root):
    return pathlib.Path(root) / "design" / "specs" / "plan.json"


def load(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save(path, doc):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


GRID_COL = (1920 - 64 - 11 * 24) / 12 + 24          # one grid column with its gutter


def _measures(v):
    """The fields a visual shows (bindings and reference labels), by name: what the person approved it shows."""
    out = set()

    def add(x):
        f = x.get("field") if isinstance(x, dict) else x
        if isinstance(f, str) and f:
            out.add("[" + f.replace("'", "").split("[", 1)[-1] if "[" in f else f)
    for xs in (v.get("bindings") or {}).values():
        for x in xs if isinstance(xs, list) else [xs]:
            add(x)
    rl = v.get("referenceLabels")
    if isinstance(rl, dict):
        add(rl.get("field", ""))
        for lab in rl.get("labels", []) or []:
            add(lab.get("value", "") if isinstance(lab, dict) else "")
    return sorted(out)


def structure(layout):
    """What the person approved on the plan picture: the pages, and per visual its type, what it shows and roughly where
    it sits (grid column and row band). Not: pixels within a cell, formatting, titles' wording, colours, assumptions.
    Changes the kit makes itself after the OK (polish, fixes, a slicer made taller) keep this the same, so a quick
    build doesn't stop for them (walkthrough fix 5)."""
    pages = {k: p.get("displayName", k) for k, p in (layout.get("pages") or {}).items()}
    vis = {}
    for v in layout.get("visuals", []):
        if not v.get("id"):
            continue
        x, y, w, h = (float(v.get(k, 0) or 0) for k in ("x", "y", "w", "h"))
        cell = (round((x - 32) / GRID_COL), round((x + w - 32) / GRID_COL), round(y / 120), round((y + h) / 120))
        vis[v["id"]] = {"page": v.get("page"), "type": v.get("type"), "shows": _measures(v), "cell": cell}
    return {"pages": pages, "visuals": vis}


def plan_hash(layout, plan):
    """What the person approves: the layout's structure (`structure`) and the page purposes."""
    body = json.dumps([structure(layout), plan.get("purposes", {})], sort_keys=True)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def what_changed(old, new):
    """Plain lines: how the structure differs from the approved one."""
    out = []
    ov, nv = old.get("visuals", {}), new.get("visuals", {})
    for vid in sorted(set(nv) - set(ov)):
        out.append(f"a new {nv[vid]['type']} ({vid})")
    for vid in sorted(set(ov) - set(nv)):
        out.append(f"the {ov[vid]['type']} {vid} is gone")
    for vid in sorted(set(ov) & set(nv)):
        a, b = ov[vid], nv[vid]
        if a["type"] != b["type"]:
            out.append(f"{vid} is now a {b['type']}")
        if a["shows"] != b["shows"]:
            out.append(f"{vid} shows different numbers")
        if list(a["cell"]) != list(b["cell"]) or a["page"] != b["page"]:
            out.append(f"{vid} moved")
    if old.get("pages") != new.get("pages"):
        out.append("the pages changed")
    return out


def _plain_field(f):
    if isinstance(f, dict):
        f = f.get("field", "")
    return str(f)


def kpis(layout):
    """[(page, label, measure, compared with)] for every card."""
    out = []
    for v in layout.get("visuals", []):
        if v.get("type") not in DATA_TYPES:
            continue
        fields = [_plain_field(f) for f in (v.get("bindings") or {}).get("Data", [])]
        if not fields:
            continue
        label = (v.get("container") or {}).get("title") or plain_name(fields[0])
        out.append((v["page"], label, plain_name(fields[0]),
                    comparison(v) or "nothing yet: every headline number needs a comparison"))
    return out


def plain_name(field):
    """A measure or column as a person reads it: its name without the table or brackets (`_Measures[Orders]` ->
    Orders)."""
    f = _plain_field(field)
    return f.split("[", 1)[-1].rstrip("]") if "[" in f else f


COMPARE_WORDS = [(r"\b(LY|PY|SPLY|last year|prior year|previous year|year ago)\b", "last year"),
                 (r"\b(LM|PM|last month|prior month|previous month)\b", "last month"),
                 (r"\btarget|goal|plan\b", "target"), (r"\bbudget\b", "budget"), (r"\bforecast\b", "forecast"),
                 (r"\b(avg|average)\b", "the average")]


def comparison(v):
    """What a card's number is compared with, in plain words ("last year"), from its reference labels' titles and
    measures; "" when it has none."""
    import re
    rl = v.get("referenceLabels")
    labels = (rl.get("labels") or []) if isinstance(rl, dict) else (rl or [])
    found = []
    for lab in labels:
        text = " ".join(str(lab.get(k, "")) for k in ("title", "value", "detail")) if isinstance(lab, dict) \
            else str(lab)
        word = next((w for pat, w in COMPARE_WORDS if re.search(pat, text, re.I)), None)
        if not word and isinstance(lab, dict) and lab.get("title"):
            word = re.sub(r"^vs\.?\s+", "", str(lab["title"]), flags=re.I)
        if word and word not in found:
            found.append(word)
    return ", ".join(found)


def fallbacks(layout):
    """[(id, method, step, native tried, reason)] for every visual above step 1 of the ladder."""
    return [(v["id"], (v.get("build") or {}).get("method"), (v.get("build") or {}).get("step"),
             (v.get("build") or {}).get("nativeTried", "?"), (v.get("build") or {}).get("reason", "?"))
            for v in layout.get("visuals", []) if ((v.get("build") or {}).get("step") or 1) > 1]


def short_list(root, layout, plan, mode=None, data_class=None, model=None):
    """The plain short list shown beside the picture (Markdown)."""
    from . import status as ST
    lines = ["# Plan", ""]
    pages = layout.get("pages", {})
    for pk, page in pages.items():
        purpose = plan.get("purposes", {}).get(pk) or "(say what this page should help people decide)"
        lines.append(f"Page {page.get('displayName', pk)}: \"{purpose}\"")
    lines += ["", "| KPI | Measure | Compared with |", "| --- | --- | --- |"]
    ks = kpis(layout)
    lines += [f"| {lab} | {m} | {cmp} |" for _, lab, m, cmp in ks] or ["| (no KPI cards) | | |"]
    lines += ["", "Assumptions (say \"change ...\" to change any):"]
    lines += [f"- {a}" for a in plan.get("assumptions", [])] or ["- none"]
    fb = fallbacks(layout)
    if fb:
        lines += ["", "Fallbacks (OK on the plan approves them):"]
        lines += [f"- {vid}: {reason} (native option tried: {tried})" for vid, _, _, tried, reason in fb]
    st = ST.read(root)
    mode = mode or st.get("mode")
    lines += ["", f"Build: {ST.MODE_WORDS.get(mode, 'guided build (the default)')}   "
                  f"Data: {data_class or st.get('dataClass', 'restricted')}   "
                  f"Model: {model or st.get('pack') or 'the model you dropped'}"]
    return "\n".join(lines) + "\n"


def picture(layout_path, out_folder, tokens=None, theme=None, shoot=None, notes=None):
    """Draw a layout as one PNG per page; returns the PNG paths. `shoot` (tests) replaces the Edge screenshot.

    Every path is absolute before Edge sees it: Edge resolves a relative --screenshot path against its own folder, so
    with `--in <project>` the picture was written elsewhere and the wait timed out (walkthrough fix 3). If the browser
    still can't draw a page, a simple preview (the boxes, from layout.json) is written instead and the plain reason is
    added to `notes`: never a silent failure."""
    from . import progress as PR
    layout_path = pathlib.Path(layout_path).resolve()
    out_folder = pathlib.Path(out_folder).resolve()
    out_folder.mkdir(parents=True, exist_ok=True)
    html = out_folder / "plan.html"
    tokens = tokens or _find_up(layout_path, "design/tokens.json") or KIT / "design" / "tokens.json"
    args = [sys.executable, str(SCRIPTS / "gen_wireframe_hf.py"), "--layout", str(layout_path),
            "--tokens", str(tokens), "--data", "example", "--out", str(html), "--vega", "offline"]
    theme = theme or _first_theme(layout_path)
    if theme:
        args += ["--theme", str(theme)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise PlanError("the plan picture couldn't be drawn: " + (r.stderr or r.stdout).strip().splitlines()[-1])
    layout = load(layout_path, {})
    pngs = []
    page_html = html.read_text(encoding="utf-8")
    for i, (pk, page) in enumerate(layout.get("pages", {}).items(), 1):
        png = out_folder / f"page-{i}.png"
        h = int(page.get("height") or 1080)
        try:
            with PR.still("drawing the plan picture"):
                if shoot:
                    shoot(page_html, png, 1920, h, f"#shot&labels=off&page={i}")
                else:
                    sys.path.insert(0, str(SCRIPTS))
                    import edge_page
                    edge_page.screenshot(page_html, png, 1920, h, hash_=f"#shot&labels=off&page={i}")
        except (SystemExit, RuntimeError, OSError, FileNotFoundError) as e:
            why = _plain_draw_error(e)
            boxes_png(layout, pk, png, load(tokens, {}) or {}, h)
            if notes is not None:
                notes.append(f"The full plan picture couldn't be drawn ({why}), so this is a simpler preview: the "
                             "boxes and their places, without colours or sample shapes.")
        pngs.append(png)
    return pngs


def _plain_draw_error(e):
    t = str(getattr(e, "code", None) or e).lower()
    if "didn't write" in t or "within" in t or "post" in t:
        return "the hidden browser that draws it didn't finish in time"
    if isinstance(e, FileNotFoundError) or "no such file" in t or "cannot find" in t:
        return "Microsoft Edge wasn't found on this computer"
    return "the hidden browser that draws it stopped"


def _hex(c, default):
    c = str(c or default).lstrip("#")
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return _hex(default, "#FFFFFF")


def boxes_png(layout, page_key, png, tokens=None, height=1080, scale=0.5):
    """A simple preview of one page without a browser: the page background, each visual's box with a border, the
    title band darker. Standard library only (zlib), so it always works."""
    import struct, zlib
    colors = (tokens or {}).get("colors", tokens or {})
    W, H = int(1920 * scale), int(height * scale)
    bg, card, border, text = (_hex(colors.get("background"), "#F3F5F8"), _hex(colors.get("card"), "#FFFFFF"),
                              _hex(colors.get("border"), "#D0D7E2"), _hex(colors.get("text"), "#1D2733"))
    px = [bytearray(bytes(bg) * W) for _ in range(H)]

    def rect(x, y, w, h, col):
        x0, y0 = max(0, int(x * scale)), max(0, int(y * scale))
        x1, y1 = min(W, int((x + w) * scale)), min(H, int((y + h) * scale))
        for yy in range(y0, y1):
            row = px[yy]
            row[x0 * 3:x1 * 3] = bytes(col) * (x1 - x0)

    for v in layout.get("visuals", []):
        if v.get("page") != page_key or not all(k in v for k in ("x", "y", "w", "h")):
            continue
        if v.get("type") in ("textbox",):
            rect(v["x"], v["y"] + v["h"] * 0.3, min(v["w"], 420), v["h"] * 0.4, text)
            continue
        rect(v["x"], v["y"], v["w"], v["h"], border)
        rect(v["x"] + 2, v["y"] + 2, v["w"] - 4, v["h"] - 4, card)
        rect(v["x"] + 16, v["y"] + 14, min(220, v["w"] - 32), 10, border)        # where the title goes
    raw = b"".join(b"\x00" + bytes(r) for r in px)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    pathlib.Path(png).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(png).write_bytes(data)
    return png


def _find_up(start, rel):
    for p in pathlib.Path(start).parents:
        if (p / rel).exists():
            return p / rel
    return None


def _first_theme(layout_path):
    for p in pathlib.Path(layout_path).parents:
        found = sorted((p / "design" / "themes").glob("*.json"))
        if found:
            return found[0]
    return None


def show(root, layout=None, purposes=None, assumptions=None, shoot=None, notes=None, measure=None):
    """Draw the plan picture and write the short list; returns (pngs, list text, hash). `notes` collects plain
    lines about the drawing (a simpler preview, and why)."""
    root = pathlib.Path(root)
    lf = layout_file(root, layout)
    lay = load(lf)
    if not lay:
        raise PlanError("there is no layout to show yet")
    plan = load(plan_file(root), {}) or {}
    if purposes:
        plan.setdefault("purposes", {}).update(purposes)
    if assumptions:
        plan["assumptions"] = list(dict.fromkeys(assumptions))     # the whole list each time: no old ones pile up
    save(plan_file(root), plan)
    out = root / PLAN_DIR
    pngs = picture(lf, out, shoot=shoot, notes=notes)
    faint = contrast(out / "plan.html", measure=measure)
    text = short_list(root, lay, plan)
    if faint:
        text += "\nToo faint to read on the picture (fixed before the build, so the plan doesn't change after OK):\n" \
                + "\n".join(f"- {x}" for x in faint) + "\n"
    (out / "plan.md").write_text(text, encoding="utf-8")
    if notes is not None:
        notes.extend(f"Contrast: {x}" for x in faint)
    return pngs, text, plan_hash(lay, plan)


def contrast(html, measure=None):
    """WCAG AA on the plan picture itself (check_contrast.py), so a faint text is caught before the OK, not after it
    (walkthrough fix 7). Plain lines, one per failing text; [] when all pass or Edge isn't there (not checked)."""
    from . import progress as PR
    try:
        if measure is None:
            sys.path.insert(0, str(SCRIPTS))
            import check_contrast, edge_page
            if not edge_page.available():
                return []
            measure = check_contrast.measure
        with PR.still("checking the picture's text contrast"):
            rows = measure(pathlib.Path(html).read_text(encoding="utf-8"))
    except (SystemExit, RuntimeError, OSError):
        return []
    out = []
    for r in rows:
        if r.get("ratio", 99) < r.get("need", 4.5):
            out.append(f"\"{r.get('text', '')}\" ({r.get('id') or 'the page'}): {r['ratio']:.1f}:1, needs "
                       f"{r['need']:g}:1")
    return out


def approve(root, layout=None):
    """The person said OK: record the hash, write the page purposes into spec.md, mark the plan stage done."""
    from . import status as ST
    root = pathlib.Path(root)
    lay = load(layout_file(root, layout))
    plan = load(plan_file(root), {}) or {}
    if not lay:
        raise PlanError("there is no plan to approve yet")
    missing = [pk for pk in lay.get("pages", {}) if not plan.get("purposes", {}).get(pk)]
    if missing:
        raise PlanError(f"{len(missing)} page(s) have no purpose yet: ask what each should help people decide")
    if not lay.get("theme") and (root / "design" / "themes" / "pbip-polish.json").exists():
        lay["theme"] = "design/themes/pbip-polish.json"         # the theme is part of every plan (v1.7 live fix 6)
        save(layout_file(root, layout), lay)
    h = plan_hash(lay, plan)
    plan["approved"] = h
    plan["approvedStructure"] = structure(lay)
    save(plan_file(root), plan)
    keep_approved(root)
    write_purpose(root, lay, plan)
    ST.update(root, done="plan", planHash=h)
    for s in ("start", "page purpose"):          # an approved plan means the start is done too
        ST.update(root, done=s)
    return h


def keep_approved(root):
    """Keep the approved preview (two renderers, v1.7): design/plan/approved.html and approved-page-<n>.png, which the
    Desktop screenshot after the build is compared with (`pbik plan compare`); a later redraw doesn't touch them."""
    import shutil
    d = pathlib.Path(root) / PLAN_DIR
    if (d / "plan.html").exists():
        shutil.copy2(d / "plan.html", d / "approved.html")
    for png in sorted(d.glob("page-*.png")):
        shutil.copy2(png, d / f"approved-{png.name}")


def compare(root=".", desktop=True, assume_saved=False, run=None):
    """The real Desktop screenshot of the built report against the approved preview (fidelity_check.py, numbers not
    compared: the preview's are examples). Returns (exit code, plain lines)."""
    from . import progress as PR
    root = pathlib.Path(root).resolve()
    approved = root / PLAN_DIR / "approved.html"
    if not approved.exists():
        raise PlanError("there is no approved plan picture to compare with yet")
    args = [sys.executable, str(SCRIPTS / "fidelity_check.py"), "--project", str(root), "--wireframe", str(approved),
            "--out", str(root / "design" / "reviews" / "fidelity"), "--example"]
    if not desktop:
        args.append("--no-desktop")
    if assume_saved:
        args.append("--assume-saved")
    with PR.still("comparing the built page with the approved picture"):
        r = (run or subprocess.run)(args, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "").splitlines()
    diffs = [ln.strip() for ln in out if ln.startswith("  P")]
    lines = []
    if r.returncode == 0:
        lines.append("The built page matches the approved picture: every visual where it was approved, of the same "
                     "kind, with the same titles (the numbers are your model's, not the picture's examples).")
    elif r.returncode == 1:
        lines.append(f"{len(diffs)} difference(s) from the approved picture; side by side in the fidelity review:")
        lines += [f"- {d}" for d in diffs[:12]]
    else:
        lines.append("Not compared: " + (out[0] if out else "Power BI Desktop couldn't be checked") +
                     " (the files were compared instead when Desktop isn't there)")
    return r.returncode, lines


def changed_since_approval(root, layout=None):
    """True when the layout or plan changed after the person's OK (or there was no OK)."""
    lay = load(layout_file(root, layout))
    plan = load(plan_file(root), {}) or {}
    return not lay or plan.get("approved") != plan_hash(lay, plan)


def changes_since_approval(root, layout=None):
    """Plain lines saying what changed in what the person approved (empty when nothing did)."""
    lay = load(layout_file(root, layout))
    plan = load(plan_file(root), {}) or {}
    if not lay or not plan.get("approved"):
        return ["the plan wasn't approved yet"]
    if plan.get("approved") == plan_hash(lay, plan):
        return []
    lines = what_changed(plan.get("approvedStructure") or {}, structure(lay))
    return lines or ["the page purposes changed"]


MAIN_FLOW = "<!-- pbik main flow: the plan list (design/plan/plan.md) is the design spec -->"


def _section(text, head, body):
    """Replace or add a `## head` section."""
    block = f"## {head}\n\n" + body.rstrip("\n") + "\n"
    if f"## {head}" in text:
        before, rest = text.split(f"## {head}", 1)
        nxt = rest.find("\n## ")
        return before + block + (rest[nxt + 1:] if nxt >= 0 else "")
    return text.rstrip("\n") + "\n\n" + block


def write_purpose(root, layout, plan):
    """design/specs/spec.md in the main flow: Page purpose (for the wrap-up and the numbers audit), every visual by ID
    and the fallback register, so the ID checks have what they read; the plan list stands in for the /plan-only
    sections (design ambition, pattern choices), which audit_ids.py then doesn't ask for (walkthrough fix 6)."""
    f = pathlib.Path(root) / "design" / "specs" / "spec.md"
    text = f.read_text(encoding="utf-8") if f.exists() else "# Spec\n"
    if not f.exists() or MAIN_FLOW in text:
        if MAIN_FLOW not in text:
            text = text.rstrip("\n") + "\n\n" + MAIN_FLOW + "\n"
        vis = [f"- {v['id']}: {_plain_type(v)}" + (f", {_title(v)}" if _title(v) else "")
               for v in layout.get("visuals", [])]
        text = _section(text, "Visuals", "\n".join(vis) or "- none")
        fb = fallbacks(layout)
        text = _section(text, "Fallback register", "\n".join(
            f"- {vid}: {method} (step {step}); native option tried: {tried}; why: {reason}"
            for vid, method, step, tried, reason in fb) or "- none: every visual is native")
    text = _section(text, "Page purpose", "\n".join(
        f"- {page.get('displayName', pk)} ({pk}): {plan['purposes'][pk]}" for pk, page in layout["pages"].items()))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def _title(v):
    c = v.get("container")
    t = c.get("title") if isinstance(c, dict) else None
    return t if isinstance(t, str) else ""


def _plain_type(v):
    return {"cardVisual": "KPI card", "card": "KPI card", "lineChart": "line chart", "barChart": "bar chart",
            "clusteredBarChart": "bar chart", "columnChart": "column chart", "clusteredColumnChart": "column chart",
            "tableEx": "table", "pivotTable": "matrix", "slicer": "filter", "advancedSlicerVisual": "button filter",
            "textbox": "text", "shape": "shape", "image": "picture", "actionButton": "button"}.get(
        v.get("type"), v.get("type", "visual"))


def open_beside(files, run=None):
    """Open pictures beside the chat: in VS Code (Copilot, Claude Code in VS Code) as editor tabs through `code`, else
    in the default image viewer. Returns how ("vscode" or "viewer"). The Claude desktop app shows them in the chat."""
    import os, shutil, subprocess as sp
    files = [str(pathlib.Path(f).resolve()) for f in files]
    code = shutil.which("code") or shutil.which("code.cmd")
    if code and (os.environ.get("TERM_PROGRAM") == "vscode" or os.environ.get("VSCODE_PID")
                 or os.environ.get("PBIK_OPEN") == "vscode"):
        (run or sp.run)([code, "--reuse-window", *files])
        return "vscode"
    for f in files:
        if run:
            run(["open", f])
        elif hasattr(os, "startfile"):
            os.startfile(f)                                           # noqa: S606
    return "viewer"
