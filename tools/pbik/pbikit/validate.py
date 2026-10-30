"""pbik validate: schema checks plus the kit's rules, read-only.

Kit rules (errors unless noted):
- visual IDs: every visual folder is '<P<n>-V<nn>>_<name>' with a matching visual name; no ID used twice; with
  --layout, every layout ID has a folder and no folder has an ID outside the layout;
- buttons: a page-navigation target must be a page name (id), not a display name;
- groups: a visual's parentGroupName names a group (visualGroup) on the same page;
- pages.json: every pageOrder entry (and activePageName) has a page folder, and every page folder is in pageOrder;
- SVG measures (model and report extensions): '%' inside the SVG text must be written as %25;
- visuals inside the page (x, y >= 0, x + width <= page width, y + height <= page height);
- filter values: a number written as text ('2024') on a numeric column never matches;
- bindings: every field a report file uses exists in the model's TMDL (or in reportExtensions.json);
- bookmarks: a button pointing to a missing bookmark; a bookmark listing a visual that isn't on its page; a bookmark
  that would hide or show visuals on a different page than the button that applies it (when it doesn't switch page);
- settings catalog (warnings, pbikit/catalog.py): a property, value type or selector pbik wrote (the `owned` list in
  visual-map.json next to --layout; without it, every property of an ID'd visual) that no Desktop-saved file in
  the catalog (tools/pbik/catalogs/home.json, or the one project.json `catalog` names) has: Desktop may ignore or
  rewrite it; another machine's catalog
  (`pbik catalog refresh --name work`);
- target Desktop (project.json `targetDesktop`, pbikit/versions.py): a file whose $schema version is newer than the
  target Desktop's release supports is an error (that Desktop may not open the report);
- accessibility (warnings, pbikit/a11y.py, CLAUDE.md "Accessibility"): alt text on data visuals and images, WCAG AA
  text contrast against what is behind the text, a minimum font size (tokens a11y.minFontPt, default 10pt), and tab
  order in reading order;
- button slicers (warnings, pbikit/slicerfit.py): no rowCount / columnCount, more items than tiles, or a label wider
  than its tile. Items from the open Desktop model with --port (N or auto), else the layout.json `items` hint.
Exit 1 on errors. Without jsonschema, or with schemas not cached, schema checks are skipped with a warning.
"""
import json, pathlib, re

from . import a11y, catalog as CAT, schemas, slicerfit, tmdl, versions
from . import deneb as DN
from .objects import load
from .report import ID_RE, Report

TOL = 0.5


class Findings:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def walk_fields(node, aliases=None, path=""):
    """Yield (kind, entity, schema, property, path) for every field reference in a PBIR JSON tree."""
    aliases = dict(aliases or {})
    if isinstance(node, dict):
        if isinstance(node.get("From"), list):
            for fr in node["From"]:
                if isinstance(fr, dict) and "Entity" in fr:
                    aliases[fr.get("Name")] = (fr["Entity"], fr.get("Schema"))
                elif isinstance(fr, dict):
                    aliases[fr.get("Name")] = None       # subquery
        for kind in ("Measure", "Column"):
            if kind in node and isinstance(node[kind], dict) and "Property" in node[kind]:
                ref = node[kind].get("Expression", {}).get("SourceRef", {})
                if "Entity" in ref:
                    yield kind, ref["Entity"], ref.get("Schema"), node[kind]["Property"], path
                elif "Source" in ref and aliases.get(ref["Source"]):
                    ent, sch = aliases[ref["Source"]]
                    yield kind, ent, sch, node[kind]["Property"], path
        for k, v in node.items():
            yield from walk_fields(v, aliases, f"{path}/{k}")
    elif isinstance(node, list):
        for k, v in enumerate(node):
            yield from walk_fields(v, aliases, f"{path}/{k}")


def walk_in_filters(node, aliases=None):
    """Yield (entity, column, [literal values]) for every In condition with value tuples."""
    aliases = dict(aliases or {})
    if isinstance(node, dict):
        if isinstance(node.get("From"), list):
            for fr in node["From"]:
                if isinstance(fr, dict) and "Entity" in fr:
                    aliases[fr.get("Name")] = fr["Entity"]
        cond = node.get("In")
        if isinstance(cond, dict) and cond.get("Values"):
            for k, e in enumerate(cond.get("Expressions", [])):
                col = e.get("Column") if isinstance(e, dict) else None
                if not col:
                    continue
                ref = col.get("Expression", {}).get("SourceRef", {})
                ent = ref.get("Entity") or aliases.get(ref.get("Source"))
                vals = [t[k].get("Literal", {}).get("Value") for t in cond["Values"] if len(t) > k and isinstance(t[k], dict)]
                yield ent, col.get("Property"), vals
        cmp_ = node.get("Comparison")
        if isinstance(cmp_, dict) and isinstance(cmp_.get("Left"), dict) and "Column" in cmp_["Left"]:
            col = cmp_["Left"]["Column"]
            ref = col.get("Expression", {}).get("SourceRef", {})
            ent = ref.get("Entity") or aliases.get(ref.get("Source"))
            lit = cmp_.get("Right", {}).get("Literal", {}).get("Value")
            if lit is not None:
                yield ent, col.get("Property"), [lit]
        for v in node.values():
            yield from walk_in_filters(v, aliases)
    elif isinstance(node, list):
        for v in node:
            yield from walk_in_filters(v, aliases)


def raw_percent(text):
    """Positions of '%' not followed by two hex digits."""
    return [m.start() for m in re.finditer(r"%(?![0-9A-Fa-f]{2})", text)]


def svg_issues(name, expr):
    _, strings = tmdl.strip_dax(expr or "")
    if "DaxLib.SVG." in (expr or "") and any("%23" in s_ for s_ in strings):
        # DaxLib.SVG writes a raw % (width='100%') so Power BI doesn't decode the URI: a %23 colour draws nothing
        # (a card and a table in Desktop, v0.4.1); its colours are raw #
        return [f"{name}: passes a %23 colour to DaxLib.SVG, which draws nothing in Desktop; pass \"#RRGGBB\""]
    if not any("svg" in s_.lower() for s_ in strings):
        return []
    out = []
    for s_ in strings:
        for pos in raw_percent(s_):
            out.append(f"{name}: raw '%' in SVG text ...{s_[max(0, pos - 25):pos + 10]}... (write %25)")
    return out


def check_slicers(fd, slicers, lay, port, report_dir):
    if not slicers:
        return
    hints = {v["id"]: v["items"] for v in (lay or {}).get("visuals", []) if "items" in v}
    if port == "auto":
        port = slicerfit.discover_port()
        if port is None:
            fd.warn("slicers", "--port auto: no Desktop workspace port found; using layout.json items hints")
    script = slicerfit.find_run_dax(report_dir) if port else None
    cache, checked = {}, 0
    for where, vid, d in slicers:
        items, col = None, slicerfit.slicer_column(d)
        if port and col:
            if col not in cache:
                try:
                    cache[col] = slicerfit.dax_values(*col, int(port), script)
                except RuntimeError as e:
                    cache[col] = None
                    fd.warn("slicers", f"{col[0]}[{col[1]}]: item count from Desktop (port {port}) failed: {e}; "
                                       f"using layout.json items hints")
            items = cache[col]
        if items is None and vid in hints:
            items = hints[vid]
        if items is None:
            continue
        checked += 1
        for msg in slicerfit.fit_issues(slicerfit.geometry(d), items):
            fd.warn(where, f"button slicer: {msg}")
    if checked < len(slicers):
        print(f"note    {len(slicers) - checked} of {len(slicers)} button slicer(s) not fit-checked "
              f"(pass --port auto with Desktop open, or add `items` to layout.json)")


def page_background(pd):
    for e in pd.get("objects", {}).get("background", []):
        return a11y._hex(e.get("properties", {}).get("color"))
    return None


def check_catalog(fd, rep, pages, layout, catalog_path):
    cat = CAT.load_catalog(catalog_path)
    if cat is None:
        fd.warn("catalog", f"no settings catalog at {catalog_path or CAT.catalog_path()}: run pbik catalog refresh --name <name>")
        return
    owned = None
    if layout:
        mf = pathlib.Path(layout).parent / "visual-map.json"
        if mf.exists():
            owned = load(mf).get("owned", {})
    hits = {}
    for _, pd, pfolder in pages:
        for d, f in rep.visuals(pfolder):
            m = ID_RE.match(f.parent.name)
            vis = d.get("visual")
            if not m or not vis:
                continue
            vid, vt = m.group(1), vis.get("visualType")
            if owned is not None:
                items = [(w, k, json.loads(sk) if sk else None, pr) for w, k, sk, pr in owned.get(vid, [])
                         if w in ("objects", "visualContainerObjects")]
            else:
                items = [(w, k, e.get("selector"), pr) for w in ("objects", "visualContainerObjects")
                         for k, lst in (vis.get(w) or {}).items() for e in lst for pr in (e.get("properties") or [None])]
            for where, key, sel, prop in items:
                e = next((x for x in (vis.get(where) or {}).get(key, []) if x.get("selector") == sel), None)
                if e is None:
                    continue
                val = (e.get("properties") or {}).get(prop) if prop else None
                if prop and val is None:
                    continue
                why = CAT.check_entry(cat, vt, where, key, prop, val, sel)
                if why:
                    hits.setdefault(why, []).append(vid)
    for why, vids in sorted(hits.items()):
        ids = sorted(set(vids))
        fd.warn("catalog", f"{why} ({', '.join(ids[:6])}{' ...' if len(ids) > 6 else ''})")


def check_deneb(fd, rep, denebs, lay, project=None):
    if denebs and (versions.target_for(rep.path.parent, project)[1] or {}).get("customVisuals") is False:
        fd.warn("project.json", f"customVisuals is false but {len(denebs)} Deneb visual(s) are built: rerun pbik build "
                "(it builds their fallbacks)")
    if denebs and DN.TYPE not in load(rep.defn / "report.json").get("publicCustomVisuals", []):
        fd.err("report.json", f"{len(denebs)} Deneb visual(s) but publicCustomVisuals doesn't list {DN.TYPE}")
    for where, d in denebs:
        vis = d.get("visual", {})
        spec_lit = next((e.get("properties", {}).get("jsonSpec") for e in vis.get("objects", {}).get("vega", [])
                         if "jsonSpec" in e.get("properties", {})), None)
        txt = (spec_lit or {}).get("expr", {}).get("Literal", {}).get("Value") if isinstance(spec_lit, dict) else None
        if not isinstance(txt, str) or not txt.startswith("'"):
            fd.err(where, "Deneb visual without a spec (vega.jsonSpec)")
            continue
        try:
            spec = json.loads(txt[1:-1].replace("''", "'"))
        except json.JSONDecodeError as e:
            fd.err(where, f"Deneb spec is not valid JSON: {e}")
            continue
        projs = vis.get("query", {}).get("queryState", {}).get("dataset", {}).get("projections", [])
        names = [p.get("nativeQueryRef") or p.get("queryRef", "").split(".")[-1] for p in projs]
        errs, warns = DN.spec_issues(spec, names)
        for e in errs:
            fd.err(where, f"Deneb spec: {e}")
        for w in warns:
            fd.warn(where, f"Deneb spec: {w}")
    for v in (lay or {}).get("visuals", []):
        if not DN.is_deneb(v):
            continue
        fb = v.get("fallback")
        if not isinstance(fb, dict) or not fb.get("type"):
            fd.err(v["id"], "Deneb visual without a `fallback` in layout.json (a native or SVG visual)")
            continue
        own = DN.title_issue(v)
        if own:
            fd.err(v["id"], own)
        method = (fb.get("build") or {}).get("method", "native")
        if DN.is_deneb(fb) or method not in DN.FALLBACK_METHODS:
            fd.err(v["id"], f"the fallback must be native or SVG (it is {fb.get('type')}, {method})")


def check_target(fd, rep, files, rel):
    t = rep.target
    if not t.pinned:
        return
    for f in files:
        try:
            m = versions.SCHEMA_RE.search(load(f).get("$schema") or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        if not m:
            continue
        cap = t.too_new(m.group(1), m.group(2))
        if cap:
            fd.err(rel(f), f"{m.group(1)} {m.group(2)} is newer than target Desktop {t.desktop} supports ("
                           + (f"{cap}, {t.note}" if cap != "none" else f"none released by {t.month}")
                           + "): pbik build lowers the files it writes and report.json; save any other file in that Desktop")


def validate(report_path, layout=None, strict_schema=False, port=None, catalog=None, use_catalog=True,
             use_a11y=True, project=None):
    rep = Report(report_path)
    rep.project = project
    fd = Findings()
    model = rep.model()
    ext = rep.extensions()
    checker = schemas.Checker()
    root = rep.path.parent

    def rel(f):
        return str(f.relative_to(root)).replace("\\", "/")

    # ---- schema checks
    files = sorted(rep.defn.rglob("*.json")) + [f for f in (rep.path / "definition.pbir",) if f.exists()]
    if checker.available:
        for f in files:
            try:
                doc = load(f)
            except json.JSONDecodeError as e:
                fd.err(rel(f), f"not valid JSON: {e}")
                continue
            res = checker.check(doc)
            for e in res or []:
                fd.err(rel(f), f"schema: {e}")
        if checker.missing:
            fd.warn("schemas", f"{len(checker.missing)} schema(s) not cached, those files were not schema-checked: "
                               f"run `pbik schemas fetch {rep.path.name}` (first: {sorted(checker.missing)[0]})")
    else:
        fd.warn("schemas", f"schema checks skipped: {checker.reason}")
    check_target(fd, rep, files, rel)

    # ---- pages and visuals
    pages = rep.pages()
    page_names = {name for name, _, _ in pages}
    display = {d.get("displayName"): name for name, d, _ in pages}
    ids = {}
    names_on = {}                 # page name -> {visual name}
    links = []                    # (page name, where, bookmark id) for Bookmark buttons
    slicers = []                  # (where, visual ID, visual.json) for button slicers
    denebs = []                   # (where, visual.json) for Deneb visuals
    for name, pd, pfolder in pages:
        pw, ph = pd.get("width", 1280), pd.get("height", 720)
        for d, f in rep.visuals(pfolder):
            folder = f.parent.name
            where = f"{pd.get('displayName')}/{folder}"
            names_on.setdefault(name, set()).add(d.get("name", folder))
            m = ID_RE.match(folder)
            if not m:
                fd.err(where, "visual has no ID (folder must be '<P<n>-V<nn>>_<name>')")
            else:
                ids.setdefault(m.group(1), []).append(where)
            if d.get("name") != folder:
                fd.warn(where, f"visual name {d.get('name')!r} differs from its folder")
            pos = d.get("position", {})
            x, y, w, h = (pos.get(k, 0) for k in ("x", "y", "width", "height"))
            if not all(isinstance(q, (int, float)) for q in (x, y, w, h)):
                fd.err(where, f"position is not numeric: {pos}")
            elif x < -TOL or y < -TOL or x + w > pw + TOL or y + h > ph + TOL:
                fd.err(where, f"off the page: x {x}, y {y}, {w}x{h} on a {pw}x{ph} page")
            for oname, entries in d.get("visual", {}).get("objects", {}).items():
                for e in entries:
                    for prop, val in e.get("properties", {}).items():
                        lit = val.get("expr", {}).get("Literal", {}).get("Value") if isinstance(val, dict) else None
                        if re.search(r"size$", prop, re.I) and isinstance(lit, str) and lit.startswith("'"):
                            fd.err(where, f"{oname}.{prop} is text ({lit}); a size must be a number such as 27D")
            if d.get("visual", {}).get("visualType") == "advancedSlicerVisual":
                slicers.append((where, m.group(1) if m else None, d))
            if d.get("visual", {}).get("visualType") == DN.TYPE:
                denebs.append((where, d))
            if d.get("visual", {}).get("visualType") == "actionButton":
                for e in d["visual"].get("objects", {}).get("text", []):
                    extra = [p for p in e.get("properties", {}) if p != "show"]
                    if extra and e.get("selector") != {"id": "default"}:
                        fd.warn(where, f"button text {extra} is not on selector {{id: default}}; Desktop ignores it")
            for lk in d.get("visual", {}).get("visualContainerObjects", {}).get("visualLink", []):
                p = lk.get("properties", {})
                typ = p.get("type", {}).get("expr", {}).get("Literal", {}).get("Value", "")
                tgt = p.get("navigationSection", {}).get("expr", {}).get("Literal", {}).get("Value")
                bm = p.get("bookmark", {}).get("expr", {}).get("Literal", {}).get("Value")
                if "Bookmark" in typ and bm:
                    links.append((name, where, bm.strip("'")))
                if "PageNavigation" in typ and tgt:
                    t = tgt.strip("'")
                    if t not in page_names:
                        hint = f" (that is the display name of page {display[t]})" if t in display else ""
                        fd.err(where, f"button targets {t!r}, which is not a page name{hint}")
    meta = rep.pages_meta()
    order = meta.get("pageOrder", [])
    for pn in order:
        if pn not in page_names:
            fd.err("pages.json", f"pageOrder lists page {pn}, which has no page folder")
    for pn, pd, _ in pages:
        if pn not in order:
            fd.err("pages.json", f"page {pd.get('displayName')!r} ({pn}) has a folder but is not in pageOrder")
    act = meta.get("activePageName")
    if act and act not in page_names:
        fd.err("pages.json", f"activePageName {act} has no page folder")
    for name, pd, pfolder in pages:                 # a group member's parentGroupName names a group on its page
        groups = {d.get("name") for d, _ in rep.visuals(pfolder) if "visualGroup" in d}
        for d, f in rep.visuals(pfolder):
            pg = d.get("parentGroupName")
            if pg and pg not in groups:
                fd.err(f"{pd.get('displayName')}/{f.parent.name}", f"parentGroupName {pg} is not a group on this page")
    for vid, wheres in sorted(ids.items()):
        if len(wheres) > 1:
            fd.err(vid, f"duplicate visual ID: {wheres}")

    # ---- bookmarks
    bdir = rep.defn / "bookmarks"
    books = {}
    for f in sorted(bdir.glob("*.bookmark.json")) if bdir.is_dir() else []:
        try:
            books[f.name[:-len(".bookmark.json")]] = load(f)
        except json.JSONDecodeError:
            continue                                  # reported by the schema pass
    page_disp = {n: d.get("displayName") for n, d, _ in pages}
    where_is = {}
    for pn, vs in names_on.items():
        for vn in vs:
            where_is.setdefault(vn, set()).add(pn)
    for bid, bd in books.items():
        label = f"bookmark {bd.get('displayName', bid)!r} [{bid}]"
        es = bd.get("explorationState", {})
        act = es.get("activeSection")
        if act and act not in page_names:
            fd.err(label, f"its page {act} is not in the report")
        for sec, sv in es.get("sections", {}).items():
            if sec not in page_names:
                fd.err(label, f"has a section for page {sec}, which is not in the report")
                continue
            for vn in sv.get("visualContainers", {}):
                if vn in names_on.get(sec, set()):
                    continue
                other = sorted(where_is.get(vn, set()) - {sec})
                if other:
                    fd.err(label, f"would hide or show {vn}, which is on page {page_disp.get(other[0])!r}, "
                                  f"not on its page {page_disp.get(sec)!r}")
                else:
                    fd.err(label, f"lists {vn}, which is not a visual on its page {page_disp.get(sec)!r}")
    for pn, where, bid in links:
        bd = books.get(bid)
        if bd is None:
            fd.err(where, f"button applies bookmark {bid!r}, which doesn't exist")
            continue
        es = bd.get("explorationState", {})
        secs = set(es.get("sections", {}))
        stays = bd.get("options", {}).get("suppressActiveSection", False)
        if secs and pn not in secs and stays:
            fd.err(where, f"button applies bookmark {bd.get('displayName', bid)!r}, which hides or shows visuals on "
                          f"page {page_disp.get(sorted(secs)[0])!r}, not on this page")
    mf = bdir / "bookmarks.json"
    if mf.exists():
        listed = set()
        for it in load(mf).get("items", []):
            listed.update(it.get("children", [])) if "children" in it else listed.add(it.get("name"))
        for bid in sorted(listed - set(books)):
            fd.err("bookmarks.json", f"lists bookmark {bid}, which has no .bookmark.json file")
        for bid in sorted(set(books) - listed):
            fd.warn("bookmarks.json", f"bookmark {bid} has a file but isn't listed, so Desktop won't show it")
    if layout:
        lay = load(layout)
        lids = {v["id"] for v in lay.get("visuals", []) if (v.get("build") or {}).get("method") != "page-background"}
        lay_pages = {p.get("displayName") for p in lay.get("pages", {}).values()}
        on_lay_pages = {vid for vid, wheres in ids.items() if any(w.split("/", 1)[0] in lay_pages for w in wheres)}
        for vid in sorted(lids - set(ids)):
            fd.err(vid, "in layout.json but has no visual folder (run pbik build)")
        for vid in sorted(on_lay_pages - lids):
            fd.err(vid, "has a visual folder but is not in layout.json" +
                   (" (retired)" if vid in lay.get("retired", []) else ""))

    # ---- Deneb visuals: a valid Vega-Lite spec over the dataset, registered in report.json, a fallback in layout.json
    check_deneb(fd, rep, denebs, load(layout) if layout else None, project)

    # ---- settings catalog
    if use_catalog:
        if not catalog:
            proj = versions.target_for(rep.path.parent, project)[1] or {}
            catalog = CAT.catalog_path(proj.get("catalog")) if proj.get("catalog") else None
        check_catalog(fd, rep, pages, layout, catalog)

    # ---- accessibility
    if use_a11y:
        min_pt = 10
        if layout:
            tf = pathlib.Path(layout).resolve().parent.parent / "tokens.json"
            if tf.exists():
                min_pt = load(tf).get("a11y", {}).get("minFontPt", 10)
        a11y.check(fd, pages, rep, page_background, min_pt)

    # ---- button slicer fit
    check_slicers(fd, slicers, load(layout) if layout else None, port, rep.path)

    # ---- fields and filter values
    if model is None:
        fd.warn("model", "no semantic model found next to the report: bindings and filter types not checked")
    for f in files:
        try:
            doc = load(f)
        except json.JSONDecodeError:
            continue
        if f.name == "reportExtensions.json":
            continue
        if model:
            seen = set()
            for kind, ent, sch, prop, path in walk_fields(doc):
                key = (kind, ent, sch, prop)
                if key in seen:
                    continue
                seen.add(key)
                if sch == "extension":
                    if (ent, prop) not in ext:
                        fd.err(rel(f), f"binds extension measure {ent}[{prop}], not in reportExtensions.json")
                elif kind == "Measure":
                    if ent not in model.tables:
                        fd.err(rel(f), f"binds [{prop}] in table {ent!r}, which is not in the model")
                    elif prop not in model.tables[ent].measures:
                        alt = model.measure_home(prop)
                        if not (prop in model.tables[ent].columns):
                            fd.err(rel(f), f"binds measure {ent}[{prop}], not in the model's TMDL"
                                           + (f" (it is in {alt})" if alt else ""))
                else:
                    if ent not in model.tables:
                        fd.err(rel(f), f"binds {ent}[{prop}]: table {ent!r} is not in the model")
                    elif not model.has_field(ent, prop):
                        fd.err(rel(f), f"binds column {ent}[{prop}], not in the model's TMDL")
            for ent, col, vals in walk_in_filters(doc):
                dt = model.column_type(ent, col)
                if dt in tmdl.NUMERIC:
                    texts = [v for v in vals if isinstance(v, str) and v.startswith("'")]
                    if texts:
                        fd.err(rel(f), f"filter on {ent}[{col}] ({dt}) has text values {texts[:3]}: "
                                       f"write numbers as {texts[0].strip(chr(39))}{'L' if dt == 'int64' else 'D'}")

    # ---- SVG measures
    if model:
        for mm in model.all_measures():
            for msg in svg_issues(f"model {mm.table}[{mm.name}]", mm.expression):
                fd.err("svg", msg)
    for (t, nme), mm in ext.items():
        for msg in svg_issues(f"extension {t}[{nme}]", mm.get("expression", "")):
            fd.err("svg", msg)
        if mm.get("dataCategory") == "ImageUrl" and mm.get("dataType") != "Text":
            fd.err("reportExtensions.json", f"{t}[{nme}] is ImageUrl but dataType is {mm.get('dataType')!r} (needs Text)")
        if model and model.measure_home(nme):
            fd.err("reportExtensions.json", f"{t}[{nme}] has the same name as a model measure")
        refs = sorted(o for (_, o) in ext if o != nme and re.search(r"\[" + re.escape(o) + r"\]", mm.get("expression", "")))
        if refs:
            fd.err("reportExtensions.json", f"{t}[{nme}] references extension measure(s) {refs}: visuals using it fail "
                                            "in Desktop (\"Error fetching data\"); make it self-contained")

    # ---- report
    for e in fd.errors:
        print(f"error   {e}")
    for w in fd.warnings:
        print(f"warning {w}")
    nvis = sum(len(rep.visuals(p[2])) for p in pages)
    print(f"\n{rep.path.name}: {len(pages)} page(s), {nvis} visual(s): {len(fd.errors)} error(s), "
          f"{len(fd.warnings)} warning(s)")
    return fd
