"""Helpers for design/scripts/smoke.py, on top of pbik (tools/pbik). Reps build from layout.json alone (pbik 0.6).

    from pbik_helpers import *
    P = Project()                       # the one *.Report in the root, layout.json, tokens.json
    P.build()                           # pbik build: pages, visuals, bindings, filters, cf, ... and visual-map.json
    P.patch("P1-V05", lambda d: label_above_bars(d, ...))
    P.validate()                        # pbik validate --layout

Two layers:
- pure JSON builders (L, s, n, i, b, lit, solid, measure, column, put, chrome_off, ref_labels, ...): no files touched;
- Project: pbik calls and visual files by ID ("<id>_<name>" folders).
Field notation in layout.json: '[Measure]', 'Table[Column]', 'First(Table[Column])' / 'Min(Table[Column])'.
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PBIK = ROOT / "tools" / "pbik" / "pbik.py"
sys.path.insert(0, str(PBIK.parent))
sys.stdout.reconfigure(encoding="utf-8")

from pbikit.objects import *  # noqa: E402,F401,F403  (the pure builders)
from pbikit.objects import load, save  # noqa: E402


def pbik(*args, check=True):
    """Run pbik with this Python; print its output; stop the build on failure unless check=False."""
    r = subprocess.run([sys.executable, str(PBIK), *map(str, args)], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8")
    out = (r.stdout + r.stderr).strip()
    if out:
        print(out)
    if check and r.returncode != 0:
        sys.exit(f"pbik failed ({r.returncode}): {' '.join(map(str, args))}")
    return r


class Project:
    """One report in the project root, driven from design/specs/layout.json and design/tokens.json.
    Visual folders are '<id>_<name>' (P1-V13_kpi-cards): the ID ties layout, wireframe, spec, review and files."""


    def __init__(self, report=None, layout=None):
        self.root = ROOT
        self.tokens = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
        self.layout_path = pathlib.Path(layout) if layout else ROOT / "design" / "specs" / "layout.json"
        self.layout = load(self.layout_path) if self.layout_path.exists() else {"pages": {}, "visuals": []}
        self.V = {v["id"]: v for v in self.layout["visuals"]}
        self.report = report or self._find_report()

    def _find_report(self):
        reports = sorted(p.name for p in ROOT.glob("*.Report"))
        if len(reports) != 1:
            sys.exit(f"Expected one *.Report folder in {ROOT}, found {reports}: pass Project(report=...).")
        return reports[0]

    # pbik
    def build(self, prune=False, map_path=None, templates=None):
        args = ["build", self.report, self.layout_path, "--tokens", ROOT / "design" / "tokens.json"]
        if prune:
            args.append("--prune")
        if map_path:
            args += ["--map", map_path]
        if templates:
            args += ["--templates", templates]
        return pbik(*args)

    def validate(self, check=False, port=None):
        return pbik("validate", self.report, "--layout", self.layout_path, *(["--port", port] if port else []),
                    check=check)

    # pages
    def page_name(self, vid):
        """Page display name of a visual: layout.pages[<page key>].displayName."""
        return self.layout["pages"][self.V[vid]["page"]]["displayName"]

    def page_dir(self, display_name):
        for f in ROOT.glob(f"{self.report}/definition/pages/*/page.json"):
            if json.loads(f.read_text(encoding="utf-8")).get("displayName") == display_name:
                return f.parent
        return None

    # visuals
    def vname(self, vid):
        return f"{vid}_{self.V[vid]['name']}"

    def vfile(self, vid):
        pdir = self.page_dir(self.page_name(vid))
        f = pdir / "visuals" / self.vname(vid) / "visual.json" if pdir else None
        return f if f and f.exists() else None

    def patch(self, vid, fn):
        f = self.vfile(vid)
        if f is None:
            sys.exit(f"{vid}: no visual.json (run P.build() first)")
        d = load(f)
        fn(d)
        save(f, d)

