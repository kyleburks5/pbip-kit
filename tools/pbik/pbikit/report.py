"""A PBIR report folder on disk: pages, visuals, the linked semantic model and report extension measures.

Layout follows Microsoft's PBIR docs: <Name>.Report/definition/{report.json, pages/pages.json,
pages/<page name>/page.json, pages/<page name>/visuals/<visual name>/visual.json, reportExtensions.json}, and
definition.pbir, whose datasetReference.byPath points at the semantic model folder.
"""
import hashlib, json, pathlib, re, sys

from . import tmdl, versions
from .objects import load, save

ID_RE = re.compile(r"^(P\d+-V\d{2,})_(.+)$")
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/{}/{}/schema.json"
DEFAULT_VERSIONS = {"page": "2.1.0", "visualContainer": "2.13.0", "pagesMetadata": "1.1.0", "reportExtension": "1.0.0",
                    "bookmark": "2.1.0", "bookmarksMetadata": "1.0.0"}


def fail(msg, code=2):
    print(f"pbik: {msg}", file=sys.stderr)
    sys.exit(code)


def stable_name(*parts, length=20):
    """Deterministic hex name (pages, filters): the same input gives the same name on every run."""
    return hashlib.sha1("/".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:length]


class Report:
    def __init__(self, path):
        p = pathlib.Path(path).resolve()
        if p.suffix.lower() == ".pbip":
            p = p.with_suffix(".Report")
        if not (p / "definition").is_dir():
            fail(f"{path} is not a PBIR report folder (no definition/ inside)")
        self.path = p
        self.defn = p / "definition"
        self.changed = []         # files written this run
        self._model = None
        self._ext = None
        self._target = None
        self.project = None       # project.json path (default: <project>/design/specs/project.json)

    @property
    def target(self):
        """The target Desktop (project.json targetDesktop; "latest" without one): pbik caps $schema versions to it."""
        if self._target is None:
            self._target = versions.target_for(self.path.parent, self.project)[0]
        return self._target

    # ------------------------------------------------------------ writing
    def write(self, f, d):
        if isinstance(d, dict) and d.get("$schema"):
            d["$schema"] = versions.capped_url(d["$schema"], self.target)
        if save(f, d):
            rel = str(pathlib.Path(f).relative_to(self.path.parent)).replace("\\", "/")
            if rel not in self.changed:
                self.changed.append(rel)
            return True
        return False

    def schema_version(self, kind):
        """Newest $schema version of this kind already in the report (so new files match what Desktop saved)."""
        found = []
        for f in self.defn.rglob("*.json"):
            try:
                m = re.search(rf"/definition/{kind}/(\d+)\.(\d+)\.(\d+)/schema\.json", f.read_text(encoding="utf-8")[:400])
            except OSError:
                continue
            if m:
                found.append(tuple(int(x) for x in m.groups()))
        v = max(found) if found else tuple(int(x) for x in DEFAULT_VERSIONS[kind].split("."))
        return versions.capped_url(SCHEMA.format(kind, ".".join(map(str, v))), self.target)

    # ------------------------------------------------------------ pages
    def pages_meta(self):
        f = self.defn / "pages" / "pages.json"
        return load(f) if f.exists() else {"$schema": self.schema_version("pagesMetadata"), "pageOrder": []}

    def pages(self):
        """[(page name, page.json dict, folder)] in page order (pages missing from pageOrder last)."""
        order = self.pages_meta().get("pageOrder", [])
        found = {}
        for f in (self.defn / "pages").glob("*/page.json"):
            d = load(f)
            found[d.get("name", f.parent.name)] = (d, f.parent)
        names = [x for x in order if x in found] + sorted(x for x in found if x not in order)
        return [(name, found[name][0], found[name][1]) for name in names]

    def page_by(self, key):
        """Find a page by name (id) or display name."""
        for name, d, folder in self.pages():
            if key in (name, d.get("displayName")):
                return name, d, folder
        return None

    # ------------------------------------------------------------ visuals
    def visuals(self, page_folder=None):
        """[(visual dict, file)] on one page or all pages."""
        folders = [page_folder] if page_folder else [p[2] for p in self.pages()]
        out = []
        for pf in folders:
            for f in sorted((pf / "visuals").glob("*/visual.json")):
                out.append((load(f), f))
        return out

    def visual_by_id(self, vid):
        """All visual folders whose name starts with '<vid>_' (more than one is a duplicate ID)."""
        return [f for f in self.defn.glob(f"pages/*/visuals/{vid}_*/visual.json")]

    # ------------------------------------------------------------ model
    def model_folder(self):
        f = self.path / "definition.pbir"
        if f.exists():
            ref = load(f).get("datasetReference", {}).get("byPath", {}).get("path")
            if ref:
                p = (self.path / ref).resolve()
                if p.exists():
                    return p
        guess = self.path.with_name(self.path.name[:-len(".Report")] + ".SemanticModel")
        return guess if guess.exists() else None

    def model(self):
        if self._model is None:
            mf = self.model_folder()
            self._model = tmdl.load(mf) if mf else False
        return self._model or None

    # ------------------------------------------------------------ report extensions
    def ext_file(self):
        return self.defn / "reportExtensions.json"

    def extensions(self):
        """{(table, measure): measure dict} from reportExtensions.json."""
        if self._ext is None:
            f = self.ext_file()
            self._ext = {}
            if f.exists():
                for ent in load(f).get("entities", []):
                    for m in ent.get("measures", []):
                        self._ext[(ent["name"], m["name"])] = m
        return self._ext

    def reset_cache(self):
        self._ext = None
