"""Button slicer fit (pbik validate, warnings): can the slicer show every item, with its text, without scrolling?

The new button slicer (advancedSlicerVisual) lays its items out in `layout.rowCount` x `layout.columnCount` tiles
(`columnPadding` / `rowPadding` between them). Without both counts Desktop picks its own tile width and scrolls the rest
(smoke 2026-10-18: a 600px slicer showed 3 of 4 location buttons). Checks, per button slicer:
- no rowCount / columnCount set;
- more items than tiles (the rest scroll);
- the longest label is wider than a tile at the slicer's font size, inside its padding (the text clips).
Items come from the open Desktop model (`--port`, a DAX VALUES query through .claude/scripts/run-dax.ps1) or, when
Desktop isn't reachable, from the visual's `items` hint in layout.json (a count, or the list of labels).
Label widths are estimates for Segoe UI (no font metrics), so a warning means "check it in Desktop".
"""
import math, os, pathlib, re, shutil, socket, subprocess, tempfile

PT_PX = 96 / 72
DEFAULT_FONT_PT = 10
DEFAULT_MARGIN = 8        # padding "Normal" (left and right) when it isn't Custom
DEFAULT_GAP = 4
SEP = " ¦ "


def lit(v):
    """Number from a PBIR literal ('8L', '2D', '11D', 8) or None."""
    if isinstance(v, dict):
        v = v.get("expr", {}).get("Literal", {}).get("Value")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.fullmatch(r"(-?\d+(?:\.\d+)?)[LDM]?", v.strip())
        if m:
            return float(m.group(1))
    return None


def _props(objs, key, selector=None):
    out = {}
    for e in objs.get(key, []):
        if e.get("selector") is None or e.get("selector") == selector:
            out.update(e.get("properties", {}))
    return out


def text_px(label, font_pt):
    """Rough Segoe UI width: 0.55 em per lower-case letter or digit, 0.68 em per capital, 0.3 em per space."""
    em = font_pt * PT_PX
    w = 0.0
    for ch in str(label):
        w += 0.3 if ch == " " else 0.68 if ch.isupper() else 0.55
    return w * em


def geometry(d):
    """The slicer's grid from its visual.json: {w, h, rows, cols, colGap, rowGap, fontPt, margin}."""
    vis = d.get("visual", {})
    objs = vis.get("objects", {})
    pos = d.get("position", {})
    lay = _props(objs, "layout")
    pad = _props(objs, "padding", {"id": "default"})
    val = _props(objs, "value", {"id": "default"})
    cpad = _props(vis.get("visualContainerObjects", {}), "padding")
    custom = str(pad.get("paddingSelection", {}).get("expr", {}).get("Literal", {}).get("Value", "")).strip("'") == "Custom"
    margin = ((lit(pad.get("leftMargin")) or 0) + (lit(pad.get("rightMargin")) or 0)) if custom else 2 * DEFAULT_MARGIN
    inner_w = pos.get("width", 0) - (lit(cpad.get("left")) or 0) - (lit(cpad.get("right")) or 0)
    return {"w": inner_w, "h": pos.get("height", 0),
            "rows": lit(lay.get("rowCount")), "cols": lit(lay.get("columnCount")),
            "colGap": lit(lay.get("columnPadding")) if lit(lay.get("columnPadding")) is not None else DEFAULT_GAP,
            "rowGap": lit(lay.get("rowPadding")) if lit(lay.get("rowPadding")) is not None else DEFAULT_GAP,
            "fontPt": lit(val.get("fontSize")) or DEFAULT_FONT_PT, "margin": margin}


def fit_issues(g, items):
    """Messages for a slicer with geometry g and items (a count or a list of labels)."""
    labels = items if isinstance(items, list) else None
    count = len(labels) if labels is not None else int(items)
    out = []
    if not (g["rows"] and g["cols"]):
        return [f"{count} item(s) but no layout.rowCount / columnCount: Desktop picks its own tile width and may "
                f"scroll (set both)"]
    rows, cols = int(g["rows"]), int(g["cols"])
    if count > rows * cols:
        out.append(f"{count} item(s) in a {rows}x{cols} grid: {count - rows * cols} scroll out of view")
    if labels:
        tile = (g["w"] - (cols - 1) * g["colGap"]) / cols - g["margin"]
        longest = max(labels, key=lambda x: text_px(x, g["fontPt"]))
        need = text_px(longest, g["fontPt"])
        if need > tile:
            out.append(f"{longest!r} needs ~{math.ceil(need)}px at {g['fontPt']:g}pt; each of {cols} tile(s) has "
                       f"~{max(0, math.floor(tile))}px inside its padding: the text clips (widen it or wrap onto rows)")
    return out


def slicer_column(d):
    """(table, column) of the slicer's Values field, or None."""
    for role in d.get("visual", {}).get("query", {}).get("queryState", {}).values():
        for p in role.get("projections", []):
            col = p.get("field", {}).get("Column")
            if col:
                ent = col.get("Expression", {}).get("SourceRef", {}).get("Entity")
                if ent:
                    return ent, col.get("Property")
    return None


# ---- items from the open Desktop model

DESKTOP_FIRST = "Open the report in Desktop first"


def port_answers(port, timeout=0.5):
    """True when something listens on localhost:port (a closed Desktop leaves its port file behind)."""
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def desktop_running():
    """True when a PBIDesktop.exe process runs (Windows; elsewhere None: not checked)."""
    if os.name != "nt":
        return None
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq PBIDesktop.exe", "/NH"], capture_output=True, text=True,
                       errors="replace")
    return "PBIDesktop.exe" in (r.stdout or "")


def _port_files(roots=None):
    roots = roots or [pathlib.Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Microsoft" / "Power BI Desktop Store App",
                      pathlib.Path(os.environ.get("LOCALAPPDATA", "~")).expanduser() / "Microsoft" / "Power BI Desktop"]
    files = [f for r in roots for f in pathlib.Path(r).glob("AnalysisServicesWorkspaces/*/Data/msmdsrv.port.txt")]
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def _read_port(f):
    raw = f.read_bytes()
    text = raw.decode("utf-16-le" if b"\x00" in raw else "utf-8", errors="ignore").strip("\ufeff\x00 \r\n")
    return int(text) if text.isdigit() else None


def discover_port(roots=None, answers=port_answers):
    """Port of the newest Desktop Analysis Services workspace that answers, or None. Port files left by a closed
    Desktop (nothing listens on them any more) are skipped."""
    for f in _port_files(roots):
        port = _read_port(f)
        if port and answers(port):
            return port
    return None


def require_port(port=None, roots=None, answers=port_answers, running=desktop_running):
    """The port to query: the given one if it answers, else the newest live workspace. Raises RuntimeError
    ("Open the report in Desktop first") when Desktop isn't running or no workspace answers."""
    if running() is False:
        raise RuntimeError(f"{DESKTOP_FIRST}: Power BI Desktop isn't running")
    if port not in (None, "auto"):
        if answers(int(port)):
            return int(port)
        raise RuntimeError(f"{DESKTOP_FIRST}: nothing answers on port {port} (Desktop closed or reopened?)")
    found = discover_port(roots, answers)
    if not found:
        raise RuntimeError(f"{DESKTOP_FIRST}: no open Desktop model answers (only port files of a closed Desktop)")
    return found


def find_run_dax(*starts):
    for s in [*starts, pathlib.Path.cwd()]:
        p = pathlib.Path(s).resolve()
        for d in [p, *p.parents]:
            f = d / ".claude" / "scripts" / "run-dax.ps1"
            if f.exists():
                return f
    return None


def dax_values(table, column, port, script):
    """Distinct values of table[column] from the open model; raises RuntimeError when the query can't run."""
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps or not script:
        raise RuntimeError("PowerShell or .claude/scripts/run-dax.ps1 not found")
    q = pathlib.Path(tempfile.gettempdir()) / "pbik_slicer_items.dax"
    t, c = table.replace("'", "''"), column.replace("]", "]]")
    # SELECTCOLUMNS, not VALUES: a field parameter's display column is part of a composite key
    q.write_text(f"EVALUATE DISTINCT ( SELECTCOLUMNS ( '{t}', \"v\", '{t}'[{c}] ) )\n", encoding="utf-8")
    r = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-File", str(q),
                        "-Port", str(port)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    if r.returncode or out.startswith("ERROR") or (r.stderr or "").strip() and not out:
        raise RuntimeError((out or r.stderr or "").strip().splitlines()[0][:200])
    return [ln.split(SEP)[0] for ln in out.splitlines() if ln != "----"]
