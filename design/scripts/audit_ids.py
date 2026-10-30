"""Visual ID audit: every visual has one stable ID (P<page>-V<nn>) that the layout, wireframe, spec, review, fix,
visual-map and report folders all agree on. Rules: design/reference/layout-schema.md.

Checks (read-only):
- layout.json: each ID matches P<n>-V<nn>, is unique, its page prefix matches its page key, and is not in `retired`;
  each visual has build.method; a non-native method has build.nativeTried and build.reason; build.step matches
  the method on the visual-method ladder and build.reason is set (ladder.py); a step-4 custom visual has
  build.itCheck; every headline number (card, KPI, gauge) has a comparison (ambition.py);
- report: each layout ID has exactly one folder "<id>_<name>"; no ID-like folder outside the layout;
- wireframe (design/wireframes/wireframe.html): each layout ID appears as data-id="<id>"; no unknown data-id;
- spec (design/specs/spec.md): each layout ID is mentioned; no unknown ID; every non-native ID has a row in the
  "Fallback register" section; a "Design ambition" section covers baseline, normal, exceptions and partial / stale;
- visual-map.json (written by build.py): the same IDs; an ID whose name changed since the map was written was reused;
- review.md: every ID it names exists (or is retired).
Files not created yet (before /plan or /build) are skipped with a note.
Usage: python design/scripts/audit_ids.py          (exit 1 on any issue)
"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ambition, ladder  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPECS = ROOT / "design" / "specs"
ID_RE = re.compile(r"\bP\d+-V\d{2,}\b")
issues, notes = [], []

lay_f = SPECS / "layout.json"
if not lay_f.exists():
    sys.exit("design/specs/layout.json not found: run /plan first.")
LAY = json.loads(lay_f.read_text(encoding="utf-8"))
VIS = LAY.get("visuals", [])
RETIRED = set(LAY.get("retired", []))
ALL_IDS = [v.get("id") for v in VIS]
IDS = list(dict.fromkeys(ALL_IDS))   # unique, in layout order
ID_SET = set(IDS)
NAME = {v.get("id"): v.get("name") for v in VIS}

# layout.json
for vid in sorted({x for x in ALL_IDS if ALL_IDS.count(x) > 1}):
    issues.append(f"layout: {vid} used by {ALL_IDS.count(vid)} visuals")
for v in VIS:
    vid = v.get("id") or "(no id)"
    if not re.fullmatch(r"P\d+-V\d{2,}", vid):
        issues.append(f"layout: bad id {vid!r} ({v.get('name')}); format P<page>-V<nn>")
    elif v.get("page") and not vid.startswith(f"{v['page']}-"):
        issues.append(f"layout: {vid} is on page {v['page']}; the prefix must match")
    if vid in RETIRED:
        issues.append(f"layout: {vid} is retired and must not be reused")
    method = (v.get("build") or {}).get("method")
    if not method:
        issues.append(f"layout: {vid} has no build.method")
    elif method not in ("native", "page-background") and not ((v["build"].get("nativeTried")) and v["build"].get("reason")):
        issues.append(f"layout: {vid} is {method} but has no build.nativeTried / build.reason")
    issues.extend(ladder.issues(v))
issues.extend(ambition.headline_issues(VIS))

# report folders
reports = sorted(ROOT.glob("*.Report"))
if reports:
    seen = {}
    for d in reports[0].glob("definition/pages/*/visuals/*"):
        m = re.match(r"(P\d+-V\d{2,})_(.+)$", d.name)
        if m:
            seen.setdefault(m.group(1), []).append(m.group(2))
    for vid in IDS:
        names = seen.get(vid, [])
        page_bg = (next(v for v in VIS if v.get("id") == vid).get("build") or {}).get("method") == "page-background"
        if not names and not page_bg:
            notes.append(f"report: {vid} not built yet")
        elif len(names) > 1:
            issues.append(f"report: {vid} has {len(names)} folders {names}")
        elif names and names[0] != NAME[vid]:
            issues.append(f"report: folder {vid}_{names[0]} vs layout name {NAME[vid]}")
    for vid in sorted(set(seen) - ID_SET):
        issues.append(f"report: folder {vid}_{seen[vid][0]} is not in layout.json" + (" (retired)" if vid in RETIRED else ""))
else:
    notes.append("report: no *.Report folder yet")

# wireframe
wf = ROOT / "design" / "wireframes" / "wireframe.html"
if wf.exists():
    found = re.findall(r'data-id="([^"]+)"', wf.read_text(encoding="utf-8"))
    for vid in IDS:
        if vid not in found:
            issues.append(f"wireframe: {vid} has no data-id element")
    for vid in sorted(set(found) - ID_SET):
        issues.append(f"wireframe: data-id {vid} is not in layout.json")
else:
    notes.append("wireframe: not generated yet")

# spec
spec = SPECS / "spec.md"
if spec.exists():
    text = spec.read_text(encoding="utf-8")
    named = set(ID_RE.findall(text))
    for vid in IDS:
        if vid not in named:
            issues.append(f"spec: {vid} is not mentioned")
    for vid in sorted(named - ID_SET - RETIRED):
        issues.append(f"spec: {vid} is not in layout.json")
    m = re.search(r"^#+[^\n]*fallback register[^\n]*\n(.*?)(?=^#+ |\Z)", text, re.I | re.M | re.S)
    register = set(ID_RE.findall(m.group(1))) if m else set()
    if not m:
        issues.append("spec: no 'Fallback register' section")
    for v in VIS:
        if (v.get("build") or {}).get("method") not in (None, "native", "page-background") and v["id"] not in register:
            issues.append(f"spec: {v['id']} ({v['build']['method']}) has no fallback register row")
    issues.extend(ambition.spec_issues(text))
else:
    notes.append("spec: not written yet")

# visual map
vm = SPECS / "visual-map.json"
if vm.exists():
    m = json.loads(vm.read_text(encoding="utf-8")).get("visuals", {})
    for vid in IDS:
        if vid not in m:
            issues.append(f"visual-map: {vid} missing (re-run build.py)")
        elif m[vid]["name"] != NAME[vid]:
            issues.append(f"visual-map: {vid} was {m[vid]['name']!r}, now {NAME[vid]!r}: an ID was reused; "
                          "give the new visual a new ID and add the old one to `retired`")
    for vid in sorted(set(m) - ID_SET):
        issues.append(f"visual-map: {vid} is not in layout.json (add it to `retired` if it was removed)"
                      if vid not in RETIRED else f"visual-map: {vid} is retired but still mapped (re-run build.py)")
else:
    notes.append("visual-map: not written yet (build.py writes it)")

# review
rv = ROOT / "design" / "reviews" / "review.md"
if rv.exists():
    for vid in sorted(set(ID_RE.findall(rv.read_text(encoding="utf-8"))) - ID_SET - RETIRED):
        issues.append(f"review: {vid} is not in layout.json")

print(f"{len(IDS)} visual IDs in layout.json, {len(RETIRED)} retired.")
for x in notes:
    print("note:", x)
print("\nISSUES:" if issues else "No ID issues.")
for x in issues:
    print(" -", x)
sys.exit(1 if issues else 0)
