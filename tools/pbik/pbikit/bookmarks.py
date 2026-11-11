"""Bookmarks from layout.json (pbik build), in the shape Power BI Desktop saved them in Rep 5.

Per page in layout.json:
    "bookmarks": [{"name": "filters-open", "displayName": "Overview · Filters open",
                   "show": ["P1-V08", ...], "hide": ["P1-V30", ...], "targets": [...],
                   "data": false, "display": true, "changesPage": false}],
    "bookmarkGroups": [{"name": "pane", "displayName": "Filter pane", "bookmarks": ["filters-open", "filters-closed"]}]

- targets = show + hide (+ `targets`): the bookmark applies only to them (applyOnlyToTargetVisuals);
- data false (default): display only (suppressData), so filters and slicer selections are not changed; data true
  captures data, which with nothing saved clears the targets' selections (Rep 5 "Filters cleared");
- display false: data only (suppressDisplay); changesPage false (default): applying it doesn't switch page
  (suppressActiveSection);
- a hidden visual is written as singleVisual.display.mode "hidden" in its page's section (explorationState).
Names are stable: bookmark = 20 hex from (page key, name), group = from (group name). Bookmarks and groups pbik wrote
are listed in the ID map; one that leaves the layout is removed only with --prune; bookmarks made in Desktop are
never touched. bookmarksMetadata items follow the public schema: {name} or a group {name, displayName, children}.
"""
from .objects import load
from .report import stable_name

DEFAULT_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/2.1.0/schema.json"
META_SCHEMA = ("https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmarksMetadata/1.0.0/"
               "schema.json")


def bookmark_id(page_key, name):
    return stable_name("bookmark", page_key, name)


def group_id(name):
    return stable_name("bookmark-group", name)


def ids(layout):
    """{(page key, layout name): bookmark id} for every bookmark in the layout."""
    return {(k, b["name"]): bookmark_id(k, b["name"])
            for k, p in layout.get("pages", {}).items() for b in p.get("bookmarks", [])}


def resolve(layout, page_key, ref, existing):
    """A button's bookmark reference -> bookmark id: a layout name on the same page, '<page key>/<name>' for another
    page, or the id of a bookmark already in the report (made in Desktop). None if nothing matches."""
    table = ids(layout)
    if "/" in ref:
        pk, _, nm = ref.partition("/")
        return table.get((pk, nm))
    if (page_key, ref) in table:
        return table[(page_key, ref)]
    return ref if ref in existing else None


def check(layout):
    """Layout errors: unknown or off-page visual IDs, duplicate names, group members that don't exist."""
    errors = []
    page_of = {v["id"]: v.get("page") for v in layout.get("visuals", [])}
    all_names = set()
    for k, p in layout.get("pages", {}).items():
        names = [b.get("name") for b in p.get("bookmarks", [])]
        for n in {x for x in names if names.count(x) > 1}:
            errors.append(f"page {k}: bookmark {n!r} is listed twice")
        for b in p.get("bookmarks", []):
            if not b.get("name"):
                errors.append(f"page {k}: a bookmark has no name")
                continue
            all_names.add((k, b["name"]))
            for vid in (list(b.get("show", [])) + list(b.get("hide", [])) + list(b.get("targets", [])) +
                        list(b.get("select") or {}) + list(b.get("sort") or {}) + display_ids(b)):
                if vid not in page_of:
                    errors.append(f"page {k}: bookmark {b['name']!r} lists {vid}, which is not in layout.json")
                elif page_of[vid] != k:
                    errors.append(f"page {k}: bookmark {b['name']!r} lists {vid}, which is on page {page_of[vid]}")
            both = set(b.get("show", [])) & set(b.get("hide", []))
            if both:
                errors.append(f"page {k}: bookmark {b['name']!r} both shows and hides {sorted(both)}")
            if b.get("elevate"):
                errors.append(f"page {k}: bookmark {b['name']!r}: elevate isn't supported: Desktop dropped the "
                              "elevation mode on save (pbik-smoke-bulk, 2026-11-11)")
            fid, tbl = focus_of(b)
            if b.get("focus") and not fid:
                errors.append(f"page {k}: bookmark {b['name']!r}: focus needs a visual ID")
            if tbl not in (None, "accessible", "normal"):
                errors.append(f"page {k}: bookmark {b['name']!r}: focus table {tbl!r} (accessible, normal)")
            modes = [set(b.get("hide", [])), set(b.get("spotlight") or []), set(b.get("elevate") or []),
                     {fid} if fid else set()]
            clash = set().union(*[m & n for i_, m in enumerate(modes) for n in modes[i_ + 1:]])
            if clash:
                errors.append(f"page {k}: bookmark {b['name']!r} gives {sorted(clash)} two display modes")
            if (b.get("select") or b.get("sort")) and b.get("data") is False:
                errors.append(f"page {k}: bookmark {b['name']!r} saves a selection or sort, which needs data")
            if b.get("data") is False and b.get("display") is False:
                errors.append(f"page {k}: bookmark {b['name']!r} captures neither data nor display")
    groups = [g.get("name") for p in layout.get("pages", {}).values() for g in p.get("bookmarkGroups", [])]
    for n in {x for x in groups if groups.count(x) > 1}:
        errors.append(f"bookmark group {n!r} is defined twice")
    seen = {}
    for k, p in layout.get("pages", {}).items():
        for g in p.get("bookmarkGroups", []):
            for m in g.get("bookmarks", []):
                key = (m.partition("/")[0], m.partition("/")[2]) if "/" in m else (k, m)
                if key not in all_names:
                    errors.append(f"bookmark group {g.get('name')!r}: no bookmark {m!r}")
                elif key in seen:
                    errors.append(f"bookmark {m!r} is in two groups ({seen[key]}, {g.get('name')})")
                else:
                    seen[key] = g.get("name")
    return errors


def focus_of(b):
    """bookmark `focus`: "ID" or {visual: ID, table: accessible / normal} -> (ID, dataTable or None)."""
    f = b.get("focus")
    if not f:
        return None, None
    return (f, None) if isinstance(f, str) else (f.get("visual"), f.get("table"))


def display_ids(b):
    return list(b.get("spotlight") or []) + ([focus_of(b)[0]] if b.get("focus") else [])


def bookmark_doc(rep, b, page_name, vnames, vtypes):
    show, hide = list(b.get("show", [])), list(b.get("hide", []))
    targets = list(dict.fromkeys(show + hide + list(b.get("targets", [])) + list(b.get("select") or {}) +
                                 list(b.get("sort") or {}) + display_ids(b)))
    containers, groups = {}, {}
    for vid in targets:
        if vtypes[vid] == "group":            # groups: visualContainerGroups {name: {isHidden}}, as Desktop saved Rep 7
            groups[vnames[vid]] = {"isHidden": vid in hide}
            continue
        sv = {"visualType": vtypes[vid], "objects": {}}
        if vid in (b.get("_select") or {}):          # roadmap gap 5: the slicer selection this bookmark saves
            sv["objects"] = {"merge": {"general": [{"properties": {"filter": {"filter": b["_select"][vid]}}}]}}
        if vid in (b.get("_sort") or {}):
            sv["orderBy"] = b["_sort"][vid]
        if vid in hide:
            sv["display"] = {"mode": "hidden"}
        elif vid in (b.get("spotlight") or []):      # roadmap gap 28 (UNVERIFIED in Desktop)
            sv["display"] = {"mode": "spotlight"}
        elif vid == focus_of(b)[0]:
            sv["display"] = {"mode": "maximize"}
            if focus_of(b)[1]:
                sv["display"]["maximizedOptions"] = {"dataTable": focus_of(b)[1]}
        containers[vnames[vid]] = {"singleVisual": sv}
    section = {"visualContainers": containers}
    if groups:
        section["visualContainerGroups"] = groups
    options = {}
    if targets:
        options["applyOnlyToTargetVisuals"] = True
        options["targetVisualNames"] = [vnames[v] for v in targets]
    if not b.get("changesPage", False):
        options["suppressActiveSection"] = True
    if not b.get("data", bool(b.get("select") or b.get("sort"))):
        options["suppressData"] = True
    if b.get("display", True) is False:
        options["suppressDisplay"] = True
    return {"$schema": rep.schema_version("bookmark"),
            "displayName": b.get("displayName", b["name"]), "name": None,
            "options": options,
            "explorationState": {"version": "1.0", "activeSection": page_name,
                                 "sections": {page_name: section}}}


def write(rep, layout, page_ids, vnames, vtypes, old_map, prune, log):
    """Write the layout's bookmarks and groups; return the ID-map entry {"bookmarks": [...], "groups": [...]}."""
    bdir = rep.defn / "bookmarks"
    wanted, groups = [], []
    for k, p in layout.get("pages", {}).items():
        for b in p.get("bookmarks", []):
            bid = bookmark_id(k, b["name"])
            doc = bookmark_doc(rep, b, page_ids[k], vnames, vtypes)
            doc["name"] = bid
            wanted.append((bid, doc))
        for g in p.get("bookmarkGroups", []):
            members = [bookmark_id(*(m.split("/", 1) if "/" in m else (k, m))) for m in g.get("bookmarks", [])]
            groups.append({"name": group_id(g["name"]), "displayName": g.get("displayName", g["name"]),
                           "children": members})
    old = (old_map or {}).get("bookmarks", {})
    old_b, old_g = set(old.get("bookmarks", [])), set(old.get("groups", []))
    if not wanted and not groups and not old_b and not old_g:
        return {"bookmarks": [], "groups": []}
    bdir.mkdir(exist_ok=True)
    for bid, doc in wanted:
        rep.write(bdir / f"{bid}.bookmark.json", doc)
    mf = bdir / "bookmarks.json"
    meta = load(mf) if mf.exists() else {"$schema": META_SCHEMA, "items": []}
    items = meta.setdefault("items", [])
    want_ids = [bid for bid, _ in wanted]
    grouped = {c for g in groups for c in g["children"]}
    gone_b = (old_b - set(want_ids))
    gone_g = (old_g - {g["name"] for g in groups})
    if gone_b or gone_g:
        if prune:
            for bid in sorted(gone_b):
                f = bdir / f"{bid}.bookmark.json"
                if f.exists():
                    f.unlink()
                    rep.changed.append(str(f.relative_to(rep.path.parent)).replace("\\", "/") + " (removed)")
        else:
            for bid in sorted(gone_b):
                log.append(f"bookmark {bid} is no longer in layout.json (kept; --prune removes it)")
            want_ids = want_ids + sorted(gone_b)      # keep it listed until pruned
    keep_old_groups = set() if prune else gone_g

    def strip(lst):
        """Remove pbik's own entries (and pbik's members inside Desktop groups stay as they are)."""
        out = []
        for it in lst:
            if "children" in it:
                if it["name"] in old_g or it["name"] in {g["name"] for g in groups}:
                    if it["name"] in keep_old_groups:
                        out.append(it)
                    continue
                out.append(it)
            elif it["name"] in set(want_ids) | old_b:
                continue
            else:
                out.append(it)
        return out

    positions = {}                                # keep pbik items where they already sit
    for n_, it in enumerate(items):
        positions.setdefault(it.get("name"), n_)
    new_items = strip(items)
    mine = [{"name": bid} for bid in want_ids if bid not in grouped] + groups
    mine.sort(key=lambda it: positions.get(it["name"], 10 ** 6))
    for it in mine:
        pos = positions.get(it["name"])
        if pos is None or pos > len(new_items):
            new_items.append(it)
        else:
            new_items.insert(min(pos, len(new_items)), it)
    meta["items"] = new_items
    rep.write(mf, meta)
    return {"bookmarks": [bid for bid, _ in wanted] + ([] if prune else sorted(gone_b)),
            "groups": [g["name"] for g in groups] + sorted(keep_old_groups)}
