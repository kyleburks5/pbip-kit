"""Features pbik writes that no Desktop save has confirmed yet: "UNVERIFIED in Desktop" (roadmap batch 2).

Each feature here was built from Microsoft's PBIR schema only (design/reviews/pbik-roadmap-batch2.md). So that a wrong
form can't break a report silently:
- `pbik build` prints one warning per unverified feature the layout uses, and checks the JSON it writes for it against
  the cached schema (schemaprops.tree_issues: a warning; `--strict` an error, nothing written);
- `pbik validate` lists every unverified feature it finds in the report files (warnings), next to its schema pass.
When a Desktop save and `pbik roundtrip` confirm a feature, remove it from FEATURES (and say so in the batch notes).
"""
import json

FEATURES = {}      # key -> (gap, label, detect(kind, doc) -> bool); kind: report, page, visual, bookmark, mobile, pages


def feature(key, gap, label, detect):
    FEATURES[key] = (gap, label, detect)


def message(key):
    gap, label, _ = FEATURES[key]
    return (f"UNVERIFIED in Desktop (roadmap gap {gap}): {label}. Built from Microsoft's schema only: open and save the "
            "report in Desktop, then run `pbik roundtrip` (design/reviews/pbik-roadmap-batch2.md, Desktop checklist)")


def _has(doc, *path):
    cur = doc
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return False
        cur = cur[p]
    return bool(cur) or cur is False or cur == 0


def scan(rep):
    """{key: [where]} for every unverified feature found in the report's files."""
    from .objects import load
    docs = []
    rf = rep.defn / "report.json"
    if rf.exists():
        docs.append(("report", "report.json", load(rf)))
    pm = rep.defn / "pages" / "pages.json"
    if pm.exists():
        docs.append(("pages", "pages.json", load(pm)))
    for name, pd, folder in rep.pages():
        docs.append(("page", f"page {pd.get('displayName')}", pd))
        for d, f in rep.visuals(folder):
            docs.append(("visual", f.parent.name, d))
            mf = f.parent / "mobile.json"
            if mf.exists():
                docs.append(("mobile", f.parent.name, load(mf)))
    bdir = rep.defn / "bookmarks"
    for f in sorted(bdir.glob("*.bookmark.json")) if bdir.is_dir() else []:
        try:
            docs.append(("bookmark", f"bookmark {f.name}", load(f)))
        except json.JSONDecodeError:
            continue
    out = {}
    for kind, where, doc in docs:
        for key, (_, _, detect) in FEATURES.items():
            try:
                hit = detect(kind, doc)
            except (AttributeError, TypeError, KeyError):
                hit = False
            if hit:
                out.setdefault(key, []).append(where)
    return out


def check(fd, rep):
    for key, wheres in sorted(scan(rep).items(), key=lambda kv: FEATURES[kv[0]][0]):
        fd.warn("unverified", f"{message(key)}; in {len(wheres)} file(s): {', '.join(wheres[:5])}"
                              f"{' ...' if len(wheres) > 5 else ''}")


# ---------------------------------------------------------------- the features (one block per gap)
def _pbik_annotations(kind, doc):
    return kind in ("report", "page", "visual") and any(
        isinstance(a, dict) for a in (doc.get("annotations") or []))


feature("landing", 12, "the landing page (pages.json landingPageName, layout page `landing`)",
        lambda kind, doc: kind == "pages" and bool(doc.get("landingPageName")))
feature("page-props", 12, "page settings through page `props` (pageSize, displayArea, pageInformation, outspace, "
        "pageRefresh, personalizeVisual)",
        lambda kind, doc: kind == "page" and bool(set(doc.get("objects") or {}) & {
            "pageSize", "displayArea", "pageInformation", "outspace", "pageRefresh", "personalizeVisual"}))
def _members_other(kind, doc):
    if kind != "visual":
        return False
    for obj, entries in ((doc.get("visual") or {}).get("objects") or {}).items():
        for e in entries:
            if "scopeId" in json.dumps(e.get("selector") or {}) and (obj, set(e.get("properties") or {})) != (
                    "dataPoint", {"fill"}):
                return True
    return False


feature("members", 2, "per-member formatting on objects other than dataPoint.fill (layout `members`)", _members_other)


def _new_filters(kind, doc):
    fc = doc.get("filterConfig") or {}
    mine = [f for f in fc.get("filters", []) if str(f.get("name", "")).startswith("pbik_")]
    if fc.get("filterSortOrder") or (kind == "report" and mine):
        return True
    for f in mine:
        if f.get("type") in ("Range", "RelativeDate") or "displayName" in f or "ordinal" in f:
            return True
        txt = json.dumps(f.get("filter", {}))
        if f.get("type") == "Advanced" and ('"Contains"' in txt or '"StartsWith"' in txt or '"null"' in txt):
            return True
    return False


feature("filters", 4, "filter types Range, RelativeDate and Advanced text conditions, report-level filters, filter "
        "displayName / ordinal and filterSortOrder", _new_filters)
feature("annotations", 13, "annotations on report.json, pages and visuals (layout `annotate`, `annotations`)",
        _pbik_annotations)
