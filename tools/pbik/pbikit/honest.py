"""Honest data settings (docs/patterns/honest-data.md): the small-sample threshold and what happens below it.

design/specs/project.json `honestData`: {"minSample": 11, "mode": "fade" | "suppress"}. Defaults: minSample 11 (the
usual small-cell rule), mode "suppress" when the project's catalog is "work" (privacy mode on by default at work),
else "fade". `pbik build` writes them into every kit custom visual that declares the hidden `honest` object; native
visuals use the same numbers through the pattern's DAX (the threshold as a measure or a what-if value)."""
import json, pathlib

DEFAULT_MIN = 11
MODES = ("fade", "suppress")


def project_file(project="."):
    return pathlib.Path(project).resolve() / "design" / "specs" / "project.json"


def settings(project="."):
    """{"minSample": int, "mode": "fade" | "suppress", "source": "project" | "default"}."""
    f = project_file(project)
    try:
        doc = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        doc = {}
    hd = doc.get("honestData") if isinstance(doc.get("honestData"), dict) else {}
    work = str(doc.get("catalog", "")).lower() == "work"
    n = hd.get("minSample", DEFAULT_MIN)
    try:
        n = max(0, int(n))
    except (TypeError, ValueError):
        n = DEFAULT_MIN
    mode = hd.get("mode") if hd.get("mode") in MODES else ("suppress" if work else "fade")
    return {"minSample": n, "mode": mode, "source": "project" if hd else "default"}


def errors(project="."):
    """Problems in project.json `honestData` (validate reports them)."""
    f = project_file(project)
    try:
        hd = (json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}).get("honestData")
    except (OSError, ValueError):
        return []
    out = []
    if hd is None:
        return out
    if not isinstance(hd, dict):
        return ["project.json honestData must be an object: {\"minSample\": 11, \"mode\": \"fade\" or \"suppress\"}"]
    if "mode" in hd and hd["mode"] not in MODES:
        out.append(f"project.json honestData.mode {hd['mode']!r}: use fade or suppress")
    if "minSample" in hd and (not isinstance(hd["minSample"], int) or hd["minSample"] < 0):
        out.append(f"project.json honestData.minSample {hd['minSample']!r}: a whole number, 0 or more")
    return out


def has_honest_object(src):
    """Does the kit visual in folder `src` declare the hidden `honest` object (capabilities.json)?"""
    try:
        caps = json.loads((pathlib.Path(src) / "capabilities.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return "honest" in (caps.get("objects") or {})


def props_for(visual, src, project="."):
    """The props to add to a kit visual's layout entry: the project's settings unless the layout sets its own."""
    if not has_honest_object(src):
        return {}
    have = {k.split("@", 1)[0] for k in (visual.get("props") or {})}
    st = settings(project)
    out = {}
    if "honest.minSample" not in have:
        out["honest.minSample@none"] = st["minSample"]
    if "honest.mode" not in have:
        out["honest.mode@none"] = st["mode"]
    return out
