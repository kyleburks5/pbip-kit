"""Power BI Desktop version targets: which PBIR schema versions a Desktop release supports, and the project file.

    pbik schemas support [--refresh]       print (or re-download) tools/pbik/schema-support.json
    pbik schemas lower <Report>            lower every file's $schema to what the target opens
    pbik project show                      the target Desktop, its release month, pinned schema versions, catalog
    pbik project record [--version X]      write the Desktop version on this machine into project.json
    pbik project check [--version X]       installed Desktop against targetDesktop (/build runs it first)

Two Microsoft sources, both public (refresh needs the network; build and validate never go online):
- each PBIR schema's CHANGELOG.md in github.com/microsoft/json-schemas (fabric/item/report/definition/<kind>/):
  `### <version>` then `Released in: <Month Year>`;
- the Power BI Desktop update archive on Microsoft Learn: `<Month Year> update (version 2.<nnn>.<build>.0)`.

A target Desktop version maps to the month of the newest listed release at or below its minor number (2.153 ->
April 2026; an unlisted month in between takes the earlier release, so fewer schema versions, never more). A schema
version is supported when Microsoft released it in that month or before. A target newer than every listed release
(Desktop updates before Learn lists it) is not pinned, like "latest": Desktop then writes versions Microsoft hasn't
published yet (visualContainer 2.14.0 from Desktop 2.159, 2026-10).

Project file (design/specs/project.json):
  {"targetDesktop": "latest" | "2.152.882.0", "catalog": "home", "customVisuals": false (optional),
   "desktop": {"version": "2.159.883.0", "recorded": "2026-10-29"}}     (written by `pbik project record`, at /model)
"""
import datetime, html, json, pathlib, re, subprocess, sys, urllib.request

from .objects import load, save

HERE = pathlib.Path(__file__).resolve().parent
SUPPORT = HERE.parent / "schema-support.json"
CHANGELOG = "https://raw.githubusercontent.com/microsoft/json-schemas/main/fabric/item/report/definition/{}/CHANGELOG.md"
ARCHIVE = "https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-latest-update-archive"
KINDS = ("report", "page", "pagesMetadata", "visualContainer", "bookmark", "bookmarksMetadata", "reportExtension",
         "versionMetadata")
MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"), 1)}
PROJECT = pathlib.Path("design") / "specs" / "project.json"


def vtuple(v):
    return tuple(int(x) for x in str(v).split("."))


def month(text):
    """'September 2026' -> '2026-09' (None if it isn't a month and year)."""
    m = re.fullmatch(r"\s*([A-Za-z]+)\s+(\d{4})\s*", text or "")
    if not m or m.group(1).lower() not in MONTHS:
        return None
    return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"


# ---------------------------------------------------------------- parsing Microsoft's pages
def parse_changelog(text):
    """[(version, 'YYYY-MM')] from a json-schemas CHANGELOG.md, newest first as listed."""
    out, ver = [], None
    for line in text.splitlines():
        h = re.match(r"\s*#{2,4}\s*(\d+\.\d+\.\d+)\s*$", line)
        if h:
            ver = h.group(1)
            continue
        r = re.search(r"Released in:\s*(?:</b>)?\s*([A-Za-z]+\s+\d{4})", line)
        if r and ver:
            m = month(r.group(1))
            if m:
                out.append((ver, m))
            ver = None
    return out


def parse_desktop_archive(page):
    """[('2.156.951.0', '2026-07')] from the Learn update archive (headings that carry a version)."""
    out = {}
    for h in re.findall(r"<h2[^>]*>(.*?)</h2>", page, re.S):
        t = html.unescape(re.sub(r"<[^>]+>", "", h))
        m = re.match(r"\s*([A-Za-z]+\s+\d{4})\s+update\s*\((?:version\s*)?(2\.\d+\.\d+(?:\.\d+)?)\)", t, re.I)
        if m and month(m.group(1)):
            out.setdefault(m.group(2), month(m.group(1)))
    return sorted(out.items(), key=lambda x: vtuple(x[0]), reverse=True)


def _get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def refresh(path=None, get=_get):
    p = pathlib.Path(path) if path else SUPPORT
    kinds, failed = {}, []
    for k in KINDS:
        try:
            rows = parse_changelog(get(CHANGELOG.format(k)))
        except Exception as e:                         # network, 404
            failed.append(f"{k}: {e}")
            continue
        if rows:
            kinds[k] = [{"version": v, "released": m} for v, m in sorted(rows, key=lambda x: vtuple(x[0]))]
    try:
        desk = [{"version": v, "released": m} for v, m in parse_desktop_archive(get(ARCHIVE))]
    except Exception as e:
        failed.append(f"desktop archive: {e}")
        desk = []
    old = load(p) if p.exists() else {}
    out = {"_note": "PBIR schema versions by release month (Microsoft's json-schemas CHANGELOGs) and Power BI Desktop "
                    "releases by month (Microsoft Learn update archive). Written by `pbik schemas support --refresh` "
                    "(pbikit/versions.py); don't edit.",
           "sources": {"schemas": CHANGELOG.format("<kind>"), "desktop": ARCHIVE},
           "kinds": {**old.get("kinds", {}), **kinds},
           "desktop": sorted(desk or old.get("desktop", []), key=lambda d: vtuple(d["version"]), reverse=True)}
    changed = save(p, out)
    print(f"{p}: {len(out['kinds'])} schema kind(s), {len(out['desktop'])} Desktop release(s)"
          + ("" if changed else " (unchanged)"))
    for x in failed:
        print(f"failed: {x}")
    return out, failed


def load_support(path=None):
    p = pathlib.Path(path) if path else SUPPORT
    return load(p) if p.exists() else {"kinds": {}, "desktop": []}


# ---------------------------------------------------------------- targets
class Target:
    """What a target Desktop supports. cap(kind) is the newest schema version it can open, or None (not pinned)."""

    def __init__(self, desktop="latest", support=None):
        self.desktop = str(desktop or "latest")
        self.support = support if support is not None else load_support()
        self.month, self.note = self._resolve()

    def _resolve(self):
        if self.desktop.lower() == "latest":
            return None, "latest: not pinned"
        if not re.fullmatch(r"2\.\d+(\.\d+){0,2}", self.desktop):
            raise ValueError(f"targetDesktop {self.desktop!r}: use a Desktop version (2.152.882.0) or \"latest\"")
        rel = self.support.get("desktop", [])
        if not rel:
            return None, "no Desktop releases in schema-support.json (pbik schemas support --refresh): not pinned"
        minor = vtuple(self.desktop)[1]
        newest = max(vtuple(r["version"])[1] for r in rel)
        if minor > newest:
            return None, (f"newer than every release Microsoft lists (newest 2.{newest}): not pinned, Desktop may "
                          "write schema versions Microsoft hasn't published yet")
        at = [r for r in rel if vtuple(r["version"])[1] <= minor]
        if not at:
            raise ValueError(f"targetDesktop {self.desktop}: older than every release in schema-support.json")
        r = max(at, key=lambda r: vtuple(r["version"]))
        exact = vtuple(r["version"])[1] == minor
        return r["released"], (f"Desktop {r['version']} ({r['released']})" if exact else
                               f"2.{minor} isn't listed: as Desktop {r['version']} ({r['released']}), the release before")

    @property
    def pinned(self):
        return self.month is not None

    def cap(self, kind):
        if not self.pinned:
            return None
        rows = [r for r in self.support.get("kinds", {}).get(kind, []) if r["released"] <= self.month]
        return max((r["version"] for r in rows), key=vtuple, default=None)

    def too_new(self, kind, version):
        """The supported version when `version` is newer than the target opens, else None."""
        c = self.cap(kind)
        if c is None:
            return None if not self.pinned or kind not in self.support.get("kinds", {}) else "none"
        return c if vtuple(version) > vtuple(c) else None


SCHEMA_RE = re.compile(r"/definition/([A-Za-z]+)/(\d+\.\d+\.\d+)/schema\.json$")


def capped_url(url, target):
    """The $schema URL with its version lowered to what the target supports (unchanged when it already does)."""
    m = SCHEMA_RE.search(url or "")
    if not m or target is None:
        return url
    c = target.too_new(m.group(1), m.group(2))
    if c in (None, "none"):
        return url
    return url[:m.start(2)] + c + url[m.end(2):]


def lower(report_path, project=None):
    """Cap the $schema of every definition file to the target (pbik writes the files: a final newline, so they don't
    count as Desktop-saved until that Desktop saves them again). Validate then schema-checks them against the older
    versions: a setting the target's schema doesn't know is an error there."""
    from .report import Report
    rep = Report(report_path)
    rep.project = project
    if not rep.target.pinned:
        print(f"target {rep.target.desktop}: {rep.target.note}; nothing to lower")
        return 0
    for f in sorted(rep.defn.rglob("*.json")):
        d = load(f)
        if isinstance(d, dict) and d.get("$schema") and capped_url(d["$schema"], rep.target) != d["$schema"]:
            rep.write(f, d)
    print(f"target Desktop {rep.target.desktop} ({rep.target.note}): {len(rep.changed)} file(s) lowered")
    for c in rep.changed:
        print(f"  {c}")
    return 0


# ---------------------------------------------------------------- project.json
def project_path(root):
    return pathlib.Path(root) / PROJECT


def load_project(path):
    p = pathlib.Path(path)
    return load(p) if p.exists() else None


def target_for(root=None, project=None, support=None):
    """Target from project.json (explicit path, or <root>/design/specs/project.json); "latest" when there is none."""
    p = pathlib.Path(project) if project else (project_path(root) if root else None)
    d = load_project(p) if p else None
    return Target((d or {}).get("targetDesktop", "latest"), support), d, p


# Microsoft Learn, "Edit Power BI Desktop project files outside Power BI Desktop" (updated 2026-09-29), Prerequisites:
# detecting and reloading external changes needs the August 2026 release or later, with the preview option "Detect and
# reload external PBIP changes" on. Learn gives no version number for August 2026; the last numbered release before it
# is 2.156.951.0 (July 2026, Desktop update archive), so anything up to that build is too old (roadmap gap 23).
RELOAD_LAST_TOO_OLD = "2.156.951.0"
PATH_LIMIT = 260                       # the same page: every project file path under 260 characters


def reload_issue(version):
    """A message when this Desktop is older than the August 2026 release that external reload needs, else None."""
    v = desktop_version(version) if version else None
    if not v:
        return None
    if vtuple(v)[:3] <= vtuple(RELOAD_LAST_TOO_OLD)[:3]:
        return (f"Desktop {v} is older than the August 2026 release that reloading external changes needs (Microsoft "
                "Learn, external editing): `pbik desktop reload` and the Desktop Bridge aren't available; close and "
                "reopen the report instead (.claude/rules/pbik.md)")
    return None


def long_paths(folders, limit=PATH_LIMIT):
    """[(length, path)] of files whose full path is limit characters or more, longest first."""
    out = []
    for folder in folders:
        for f in pathlib.Path(folder).rglob("*"):
            n = len(str(f.resolve()))
            if f.is_file() and n >= limit:
                out.append((n, str(f)))
    return sorted(out, reverse=True)


def desktop_version(text):
    """The leading version number of what Desktop reports: '2.155.756.0 (26.06)+<hash>' (MSI and IT-managed
    installs) -> '2.155.756.0'. None if it doesn't start with one."""
    m = re.match(r"\s*(2\.\d+\.\d+(?:\.\d+)?)(?![\d.])", text or "")
    return m.group(1) if m else None


def detect_desktop():
    """Installed Power BI Desktop version (Store package, then the MSI install), or None."""
    cmds = ["(Get-AppxPackage -Name *PowerBI* | Sort-Object Version -Descending | Select-Object -First 1).Version",
            "(Get-Item \"$env:ProgramFiles\\Microsoft Power BI Desktop\\bin\\PBIDesktop.exe\" -ErrorAction "
            "SilentlyContinue).VersionInfo.ProductVersion"]
    for c in cmds:
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", c], capture_output=True,
                               text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return None
        v = desktop_version(r.stdout)
        if v:
            return v
    return None


def record(path, version=None, today=None):
    p = pathlib.Path(path)
    v = desktop_version(version) if version else detect_desktop()
    if not v:
        raise SystemExit("pbik: couldn't find Power BI Desktop's version: pass --version (Help > About)")
    d = load_project(p) or {"targetDesktop": "latest", "catalog": "home"}
    d["desktop"] = {"version": v, "recorded": today or datetime.date.today().isoformat()}
    save(p, d)
    print(f"{p}: Desktop {v} recorded; targetDesktop {d.get('targetDesktop', 'latest')}")
    return d


def check(path, version=None):
    """Installed Desktop against targetDesktop: 0 when they match, Desktop is older (a warning) or the target is
    "latest"; 5 when Desktop is newer (run /update first); 3 when the version can't be found."""
    d = load_project(path) or {}
    target = str(d.get("targetDesktop", "latest"))
    v = desktop_version(version) if version else detect_desktop()
    if v and reload_issue(v):
        print(f"warning: {reload_issue(v)}")
    if target.lower() == "latest":
        print(f"ok: targetDesktop latest; Desktop {v or '(version not found)'}")
        return 0
    if not v:
        print("pbik: couldn't find Power BI Desktop's version: pass --version (Help > About)", file=sys.stderr)
        return 3
    t = vtuple(target)
    have = vtuple(v)[:len(t)]                 # a target of 2.152 matches every 2.152.x build
    if have > t:
        print(f"Desktop {v} is newer than targetDesktop {target}: run /update first", file=sys.stderr)
        return 5
    if have < t:
        print(f"warning: Desktop {v} is older than targetDesktop {target}: it may not open what pbik writes")
        return 0
    print(f"ok: Desktop {v} matches targetDesktop {target}")
    return 0


def show(path, support=None):
    t, d, p = target_for(project=path, support=support)
    if d is None:
        print(f"no {p}: target latest (not pinned), catalog home")
    print(f"targetDesktop  {t.desktop}  ({t.note})")
    print(f"catalog        {(d or {}).get('catalog', 'home')}")
    if (d or {}).get("customVisuals") is False:
        print("customVisuals  false (pbik build builds each Deneb visual's fallback)")
    if (d or {}).get("desktop"):
        print(f"recorded       Desktop {d['desktop'].get('version')} on {d['desktop'].get('recorded')}")
    kinds = t.support.get("kinds", {})
    for k in KINDS:
        newest = max((r["version"] for r in kinds.get(k, [])), key=vtuple, default="?")
        v = (t.cap(k) or "none released yet") if t.pinned else f"{newest}  (newest published)"
        print(f"  {k:18} {v}")
    return t


def show_support(path=None):
    s = load_support(path)
    for k, rows in sorted(s.get("kinds", {}).items()):
        print(f"{k:18} " + ", ".join(f"{r['version']} ({r['released']})" for r in rows))
    print("Desktop            " + ", ".join(f"{r['version']} ({r['released']})" for r in s.get("desktop", [])[:12])
          + (" ..." if len(s.get("desktop", [])) > 12 else ""))
