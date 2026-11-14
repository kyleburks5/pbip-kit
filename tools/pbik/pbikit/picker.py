"""Desktop as the model picker for bind live (docs/design/phase1-usability.md, section 5).

The agent runs `pbik bind picker`: it makes the "Live pick" folder inside the Reference folder (git-ignored, never read
as a layout input) and names it; it never opens File Explorer. The person, in Power BI Desktop: File > New, Get data >
Power BI semantic models, picks the model, File > Save as, type Power BI project (.pbip), into that folder, and
closes. `pbik bind picker --scan` finds the newest Desktop-saved report
there (and in project.json `pickerFolders`, saved in the last day) and says which model it connects to; the
*Connect to the live model* task reads it (gate prepare bind-live --from picked). No typed names or IDs.
"""
import os, pathlib, time

from . import dataclass_ as DC
from .objects import load

FOLDER = pathlib.Path("Reference") / "Live pick"
OLD_FOLDER = pathlib.Path("design") / "reference" / "live"
RECENT = 24 * 3600


class PickError(Exception):
    pass


def folder(root):
    return pathlib.Path(root) / FOLDER


def prepare(root, open_folder=False):
    """Make the folder. `open_folder` is ignored: the kit never opens File Explorer (v1.7 live walkthrough fix 14)."""
    d = folder(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gitignore").write_text("*\n", encoding="utf-8")
    return d


def candidates(root, now=None):
    """[(mtime, definition.pbir)] of Desktop-saved live reports, newest first."""
    now = now or time.time()
    places = [(folder(root), None), (pathlib.Path(root) / OLD_FOLDER, None)] + [(pathlib.Path(os.path.expandvars(os.path.expanduser(p))), RECENT)
                                       for p in DC.read_project(root).get("pickerFolders", [])]
    out = []
    for base, max_age in places:
        if not base.is_dir():
            continue
        for f in base.rglob("definition.pbir"):
            try:
                bc = load(f).get("datasetReference", {}).get("byConnection")
            except (OSError, ValueError):
                continue
            age = now - f.stat().st_mtime
            if bc and (max_age is None or age <= max_age):
                out.append((f.stat().st_mtime, f))
    return sorted(out, reverse=True)


def picked(root):
    """(workspace, model, id, report folder) of the newest pick."""
    from . import bind as BD
    found = candidates(root)
    if not found:
        raise PickError("no model picked yet: in Power BI Desktop, connect a new report to the published model and "
                        "save it as a Power BI project in the folder that opened")
    f = found[0][1]
    ws, model, mid, _ = BD.from_report(f.parent)
    return ws, model, mid, f.parent
