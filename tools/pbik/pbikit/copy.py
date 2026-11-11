"""pbik copy page: copy a page (and the bookmarks that belong to it) from one PBIR report into another (roadmap gap 17).

    pbik copy page <from Report> <page> <to Report> --key P5 [--as "New name"] [--bookmarks]

What changes on the way (Microsoft Learn, "Power BI Desktop project report folder", PBIR format scenarios and Common
PBIR errors: a copied page's pageBinding.name must stay unique; a copied bookmark keeps its config only when its
visuals come with it):
- the page gets a new name (the 20 hex `pbik build` gives layout page <key>), so a later layout entry with this key
  and display name takes it over; it is appended to pageOrder;
- visual IDs move to the new page number (P2-V04_x -> P5-V04_x): folder, visual `name`, parentGroupName,
  visualInteractions; folders without an ID keep their name (`pbik validate` will list them);
- filter names (page and visual) and the pageBinding name and parameter names are renamed (stable from the new page),
  and parameters' boundFilter follow;
- with --bookmarks, every bookmark whose sections are only the copied page comes too, with its visual names, targets,
  groups and active section rewritten, and is listed in bookmarks.json.
Fields aren't changed: `pbik validate` on the target reports any field its model lacks. Nothing else is touched.
"""
import json, pathlib, re, shutil

from .objects import load
from .report import ID_RE, Report, fail, stable_name


def _ren(text, mapping):
    """Replace whole JSON string values found in mapping (visual, filter, bookmark names), also as PBIR text literals
    ("'name'", how a button holds a bookmark id or a page name)."""
    def one(m):
        s = json.loads(m.group(0))
        if s in mapping:
            return json.dumps(mapping[s])
        if len(s) > 2 and s[0] == s[-1] == "'" and s[1:-1] in mapping:
            return json.dumps(f"'{mapping[s[1:-1]]}'")
        return m.group(0)
    return re.sub(r'"(?:[^"\\]|\\.)*"', one, text)


def copy_page(src_report, page, dst_report, key, as_name=None, bookmarks=False):
    src, dst = Report(src_report), Report(dst_report)
    hit = src.page_by(page)
    if not hit:
        fail(f"no page {page!r} in {src.path.name}")
    if not re.fullmatch(r"P\d+", key or ""):
        fail(f"--key {key!r}: the layout page key the copy will have (P<n>)")
    old_name, pd, folder = hit
    display = as_name or pd.get("displayName")
    new_name = stable_name("page", key, display)
    if (dst.defn / "pages" / new_name).exists() or dst.page_by(display):
        fail(f"{dst.path.name} already has a page {display!r} ({new_name}); pass --as with another name")
    n = key[1:]
    mapping = {old_name: new_name}
    renamed = []
    for vf in sorted((folder / "visuals").glob("*")):
        m = ID_RE.match(vf.name)
        if m:
            new_v = re.sub(r"^P\d+-", f"P{n}-", vf.name)
            mapping[vf.name] = new_v
            mapping[m.group(1)] = new_v.split("_", 1)[0]          # the pbik.id annotation follows the new ID
            renamed.append((vf.name, new_v))
    old_key = re.match(r"P\d+", renamed[0][0]).group(0) if renamed else None
    if old_key:
        mapping[old_key] = key                                    # and pbik.page
    if bookmarks:                                                 # buttons applying them point at the copies
        for bid, _ in page_bookmarks(src, old_name):
            mapping[bid] = stable_name("bookmark-copy", new_name, bid)
    for f in [folder / "page.json"] + sorted(folder.glob("visuals/*/visual.json")):
        for flt in (load(f).get("filterConfig") or {}).get("filters", []):
            nm = flt.get("name", "")
            if nm and nm not in mapping:
                mapping[nm] = ("pbik_" + stable_name("copy", new_name, nm, length=16)) if nm.startswith("pbik_") \
                    else stable_name("copy", new_name, nm)
    binding = pd.get("pageBinding") or {}
    if binding.get("name"):
        mapping[binding["name"]] = stable_name("binding", new_name, binding["name"])
        for p in binding.get("parameters") or []:
            if p.get("name"):
                mapping[p["name"]] = stable_name("param", new_name, p["name"])
    out = dst.defn / "pages" / new_name
    shutil.copytree(folder, out)
    for old_v, new_v in renamed:
        (out / "visuals" / old_v).rename(out / "visuals" / new_v)
    for f in [out / "page.json"] + sorted(out.glob("visuals/*/*.json")):
        text = _ren(f.read_text(encoding="utf-8"), mapping)
        if f.name == "page.json":
            d = json.loads(text)
            d["name"], d["displayName"] = new_name, display
            text = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
        f.write_text(text, encoding="utf-8")
    meta = dst.pages_meta()
    meta.setdefault("pageOrder", []).append(new_name)
    dst.write(dst.defn / "pages" / "pages.json", meta)
    print(f"copied page {pd.get('displayName')!r} -> {display!r} ({new_name}) in {dst.path.name}: "
          f"{len(renamed)} visual(s) renumbered to P{n}")
    nav = []
    dst_pages = {x[0] for x in dst.pages()}
    for f in sorted(out.glob("visuals/*/visual.json")):
        for e in (load(f).get("visual", {}).get("visualContainerObjects", {}).get("visualLink") or []):
            for prop in ("navigationSection", "drillthroughSection"):
                tgt = (((e.get("properties") or {}).get(prop) or {}).get("expr", {}).get("Literal", {}).get("Value") or "")
                if tgt and tgt.strip("'") not in dst_pages:
                    nav.append(f"{f.parent.name} -> {tgt}")
    for x in nav:
        print(f"warning: {x}: the target page isn't in {dst.path.name}; repoint the button")
    if bookmarks:
        copy_bookmarks(src, dst, old_name, new_name, mapping)
    print("next: add the page and its visuals to layout.json (key " + key + ") if pbik should own them, then "
          "`pbik validate` (fields the target model lacks are errors)")
    return new_name


def page_bookmarks(rep, page_name):
    """[(bookmark name, doc)] whose sections are this page alone."""
    bdir = rep.defn / "bookmarks"
    out = []
    for f in sorted(bdir.glob("*.bookmark.json")) if bdir.is_dir() else []:
        bd = load(f)
        if set((bd.get("explorationState") or {}).get("sections") or {}) == {page_name}:
            out.append((bd.get("name") or f.name[:-len(".bookmark.json")], bd))
    return out


def copy_bookmarks(src, dst, old_name, new_name, mapping):
    ddir = dst.defn / "bookmarks"
    copied = []
    for old_bid, bd in page_bookmarks(src, old_name):
        bid = mapping[old_bid]
        bd = json.loads(_ren(json.dumps(bd), mapping))
        bd["name"] = bid
        ddir.mkdir(exist_ok=True)
        dst.write(ddir / f"{bid}.bookmark.json", bd)
        copied.append((bid, bd.get("displayName")))
    if not copied:
        print("no bookmark belongs to that page alone: none copied")
        return
    mf = ddir / "bookmarks.json"
    meta = load(mf) if mf.exists() else {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                                                    "definition/bookmarksMetadata/1.0.0/schema.json", "items": []}
    have = {it.get("name") for it in meta.get("items", [])}
    meta.setdefault("items", []).extend({"name": b} for b, _ in copied if b not in have)
    dst.write(mf, meta)
    print(f"copied {len(copied)} bookmark(s): {', '.join(str(d) for _, d in copied)}")
