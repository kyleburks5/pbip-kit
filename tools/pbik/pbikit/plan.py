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


def plan_hash(layout, plan):
    """What the person approves: the layout (positions, types, fields) and the plan's purposes and assumptions."""
    keep = {k: v for k, v in layout.items() if not k.startswith("_")}
    body = json.dumps([keep, plan.get("purposes", {}), plan.get("assumptions", [])], sort_keys=True)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


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
        refs = [_plain_field(r.get("field", r)) if isinstance(r, dict) else str(r)
                for r in v.get("referenceLabels", []) or []]
        label = (v.get("container") or {}).get("title") or fields[0].split("[")[-1].rstrip("]")
        out.append((v["page"], label, fields[0], ", ".join(refs) or "nothing yet: every headline number needs a "
                                                                      "comparison"))
    return out


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


def picture(layout_path, out_folder, tokens=None, theme=None, shoot=None):
    """Draw a layout as one PNG per page; returns the PNG paths. `shoot` (tests) replaces the Edge screenshot."""
    layout_path = pathlib.Path(layout_path).resolve()
    out_folder = pathlib.Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)
    html = out_folder / "plan.html"
    tokens = tokens or _find_up(layout_path, "design/tokens.json") or KIT / "design" / "tokens.json"
    args = [sys.executable, str(SCRIPTS / "gen_wireframe_hf.py"), "--layout", str(layout_path),
            "--tokens", str(tokens), "--data", "none", "--out", str(html), "--vega", "offline"]
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
        if shoot:
            shoot(page_html, png, 1920, h, f"#shot&labels=off&page={i}")
        else:
            sys.path.insert(0, str(SCRIPTS))
            import edge_page
            edge_page.screenshot(page_html, png, 1920, h, hash_=f"#shot&labels=off&page={i}")
        pngs.append(png)
    return pngs


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


def show(root, layout=None, purposes=None, assumptions=None, shoot=None):
    """Draw the plan picture and write the short list; returns (pngs, list text, hash)."""
    root = pathlib.Path(root)
    lf = layout_file(root, layout)
    lay = load(lf)
    if not lay:
        raise PlanError("there is no layout to show yet")
    plan = load(plan_file(root), {}) or {}
    if purposes:
        plan.setdefault("purposes", {}).update(purposes)
    if assumptions:
        plan["assumptions"] = list(dict.fromkeys(plan.get("assumptions", []) + list(assumptions)))
    save(plan_file(root), plan)
    out = root / PLAN_DIR
    pngs = picture(lf, out, shoot=shoot)
    text = short_list(root, lay, plan)
    (out / "plan.md").write_text(text, encoding="utf-8")
    return pngs, text, plan_hash(lay, plan)


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
    h = plan_hash(lay, plan)
    plan["approved"] = h
    save(plan_file(root), plan)
    write_purpose(root, lay, plan)
    ST.update(root, done="plan", planHash=h)
    for s in ("page purpose",):
        ST.update(root, done=s)
    return h


def changed_since_approval(root, layout=None):
    """True when the layout or plan changed after the person's OK (or there was no OK)."""
    lay = load(layout_file(root, layout))
    plan = load(plan_file(root), {}) or {}
    return not lay or plan.get("approved") != plan_hash(lay, plan)


def write_purpose(root, layout, plan):
    """The "Page purpose" section of design/specs/spec.md (kept for the wrap-up and the numbers audit)."""
    f = pathlib.Path(root) / "design" / "specs" / "spec.md"
    text = f.read_text(encoding="utf-8") if f.exists() else "# Spec\n"
    section = ["## Page purpose", ""] + [
        f"- {page.get('displayName', pk)} ({pk}): {plan['purposes'][pk]}" for pk, page in layout["pages"].items()]
    block = "\n".join(section) + "\n"
    if "## Page purpose" in text:
        head, rest = text.split("## Page purpose", 1)
        nxt = rest.find("\n## ")
        text = head + block + (rest[nxt + 1:] if nxt >= 0 else "")
    else:
        text = text.rstrip("\n") + "\n\n" + block
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


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
