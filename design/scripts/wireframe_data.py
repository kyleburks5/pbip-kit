"""Aggregate numbers for the high-fidelity wireframe, from each visual's own bindings (read-only; docs/it-security.md).

    python design/scripts/wireframe_data.py --port <Desktop port>         writes design/wireframes/wireframe-data.json
    python design/scripts/wireframe_data.py --dry-run                      prints the queries, runs nothing

For every visual in design/specs/layout.json with bindings, one DAX query at the visual's own grain:
SUMMARIZECOLUMNS over the visual's columns (with their sort-by columns), its measures and aggregations, the privacy
count, and the default state: the visual's and page's categorical filters and the `selection` of the slicers on its
page (and of slicers synced to it). Cards and other visuals without columns get one row.

Privacy (layout.json `privacy`, required to fetch anything):
    "privacy": {"count": "[Group Size]", "minGroup": 5, "identifiers": ["DataTable[EmployeeID]"], "maxRows": 500}
- count: a measure (or DAX) giving the number of people behind each row; every query returns it as __n;
- a row (or a card) whose count is under minGroup is hidden. If a visual hides exactly one of its rows, the smallest
  remaining row is hidden too, so the hidden one can't be worked out from a total (secondary suppression);
- the save fails, writing nothing, when: a visual groups by an identifier column (privacy.identifiers, or a column
  named like an id, key, e-mail, phone, birth date or address), a query returns more than maxRows rows (looks
  row-level), a row survives without a count, or anything hidden is still in the data.
The output holds per visual: the group and value labels, the measures' format strings, the rows, and how many rows
were hidden; plus the queries and the privacy report, so the wireframe file says how its numbers were made.
Also per visual, when layout.json asks for them: `colours` (one per row) from a `cf` measure on dataPoint.fill
(perPoint or target), and `refLines` (axis, label, value) from `referenceLines` (a measure is evaluated under the
visual's filters).
Also per row, when layout.json asks for them: `labels` (series -> one per row) from a measure on the data labels
(`cf` labels.dynamicLabelValue, or the props form Desktop saves), `backs` and `fonts` from `cf` measures on a table's
or matrix's values.backColor / fontColor, and `images` from a `cf` image measure (the SVG text a DaxLib.SVG measure
returns, which the wireframe draws as Power BI does). Per visual: `axis` (start, end, secStart, secEnd) from `cf`
measures on valueAxis, and `titles` from container title / subtitle measures. Report extension measures (the report's
reportExtensions.json) are defined query-scoped, so `img` measures evaluate. `levels` lists each group's members in
their sort order (a matrix's columns).
A Top N filter (`filters` type TopN: field, by, n, direction) is evaluated in the query: a DEFINE VAR keeps the top
(or bottom) n members of its field by its measure under the visual's other filters, so the ranking measure need not be
one the visual shows, and a visual with more groups (matrix columns, line series) keeps every row of those members.
    --define <file.dax>   MEASURE definitions run query-scoped (measures proposed at /plan, not yet in the model);
                          `// format [Measure] = <format string>` lines give their formats (e.g. 0"×", 0%)
"""
import argparse, datetime, json, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pbik"))

from pbikit import tmdl  # noqa: E402

SEP = " ¦ "
CAT_ROLES = ("Category", "Axis", "Rows", "X", "Details", "Group")
LEG_ROLES = ("Legend", "Series", "Columns", "SmallMultiples")
ID_WORDS = re.compile(r"(?i)(?:^|[\s_-])(?:id|key|guid|uuid|e-?mail|phone|mobile|ssn|social security( number)?|"
                      r"birth ?date|date of birth|dob|address|street|post ?code|zip ?code|passport( number)?)$")
ID_CAMEL = re.compile(r"[a-z](?:ID|Id|Key|Guid|Email|Phone|Ssn|Dob)$")      # EmployeeID, CustomerKey, userEmail


def looks_like_identifier(column):
    return bool(ID_WORDS.search(column) or ID_CAMEL.search(column))
NOTATION = re.compile(r"^(?:(?P<agg>[A-Za-z]+)\()?(?:(?P<tbl>'(?:[^']|'')+'|[A-Za-z_][\w ]*?))?\[(?P<name>[^\]]+)\]\)?$")


class PrivacyError(Exception):
    pass


DEFS = {"text": "", "names": set(), "formats": {}}    # --define: query-scoped MEASURE definitions
EXT = {}                                              # report extension measures: name -> (entity, expression)


def load_extensions(root):
    """The report extension measures of the project at root (*.Report/definition/reportExtensions.json)."""
    EXT.clear()
    for f in sorted(pathlib.Path(root).glob("*.Report/definition/reportExtensions.json")):
        for ent in json.loads(f.read_text(encoding="utf-8")).get("entities", []):
            for m in ent.get("measures", []):
                EXT[m["name"]] = (ent["name"], m.get("expression", ""))
    return EXT
FORMAT_LINE = re.compile(r"(?m)^\s*//\s*format\s+(?:'(?:[^']|'')+'|[\w ]+?)?\[([^\]]+)\]\s*=\s*(.+?)\s*$")


def load_defines(path):
    """MEASURE definitions, and their format strings from `// format [Measure] = <format string>` comment lines."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    DEFS["text"] = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("//"))
    DEFS["names"] = set(re.findall(r"(?im)^\s*MEASURE\s+(?:'(?:[^']|'')+'|[\w ]+?)?\[([^\]]+)\]", text))
    DEFS["formats"] = dict(FORMAT_LINE.findall(text))


def with_defines(dax):
    if not DEFS["text"]:
        return dax
    if re.match(r"\s*DEFINE\b", dax, re.I):
        return re.sub(r"^\s*DEFINE\b", lambda m: "DEFINE\n" + DEFS["text"] + "\n", dax, count=1, flags=re.I)
    return "DEFINE\n" + DEFS["text"] + "\n" + dax


def known_measure(model, name):
    """(known, format string): in the model's TMDL, or defined with --define (its `// format` line wins)."""
    if name in DEFS["formats"] and (name in DEFS["names"] or (model and model.measure_home(name))):
        return True, DEFS["formats"][name]
    if model:
        home = model.measure_home(name)
        mm = model.tables[home[0]].measures.get(name) if home else None
        if mm is not None:
            return True, mm.format_string
    return name in DEFS["names"], None


def measure_dax(model, text, defines):
    """DAX for a field reference, or None for a measure that is neither in the model, --define nor the report's
    extension measures (an extension measure is added to `defines`, so the query defines it)."""
    try:
        kind, tbl, name, agg = parse(text)
    except ValueError:
        return None
    if kind != "measure":
        return dax_ref(kind, tbl, name, agg)
    if known_measure(model, name)[0] or not (model or DEFS["names"]):
        return f"[{name}]"
    if name in EXT:
        ent, expr = EXT[name]
        d = f"MEASURE '{ent.replace(chr(39), chr(39) * 2)}'[{name}] = {expr}"
        if d not in defines:
            defines.append(d)
        return f"[{name}]"
    return None


def one_line(dax):
    """Text measures (SVG) on one line: run-dax.ps1 prints one row per line."""
    return f'SUBSTITUTE ( SUBSTITUTE ( {dax}, UNICHAR ( 13 ), "" ), UNICHAR ( 10 ), " " )'


def selector_measure(sel):
    """The measure a Desktop-saved props selector names: {"metadata": "Table.Measure"} -> "Measure"."""
    try:
        meta = json.loads(sel).get("metadata")
    except (ValueError, AttributeError):
        return None
    return meta.split(".", 1)[1] if isinstance(meta, str) and "." in meta else None


def parse(text):
    """Layout notation -> (kind, table, name, agg): kind measure / column / aggregation."""
    m = NOTATION.match(text.strip())
    if not m:
        raise ValueError(f"field {text!r}: write [Measure], Table[Column] or Sum(Table[Column])")
    tbl = (m.group("tbl") or "").strip()
    tbl = tbl[1:-1].replace("''", "'") if tbl.startswith("'") else tbl
    if m.group("agg"):
        return "aggregation", tbl, m.group("name"), m.group("agg").upper()
    return ("column" if tbl else "measure"), tbl, m.group("name"), None


def dax_ref(kind, tbl, name, agg=None):
    col = f"'{tbl.replace(chr(39), chr(39) * 2)}'[{name}]"
    if kind == "measure":
        return f"[{name}]"
    if kind == "aggregation":
        fn = {"SUM": "SUM", "MIN": "MIN", "MAX": "MAX", "AVG": "AVERAGE", "AVERAGE": "AVERAGE",
              "COUNT": "COUNTA", "COUNTNONNULL": "COUNTA", "FIRST": "MIN", "LAST": "MAX"}.get(agg, agg)
        return f"{fn} ( {col} )"
    return col


def literal(model, tbl, col, v):
    dt = model.column_type(tbl, col) if model else None
    if dt in tmdl.NUMERIC and not isinstance(v, str):
        return str(v)
    if dt in tmdl.NUMERIC and isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v):
        return v
    return '"' + str(v).replace('"', '""') + '"'


def items(binding):
    for it in binding if isinstance(binding, list) else [binding]:
        yield it if isinstance(it, dict) else {"field": it}


# ---------------------------------------------------------------- queries
def selections(layout):
    """Default slicer selections per page key: [(field, values)], plus synced slicers' selections on other pages."""
    by_page, by_group = {}, {}
    for v in layout.get("visuals", []):
        sel = v.get("selection")
        if sel and sel.get("field"):
            vals = sel["values"] if isinstance(sel.get("values"), list) else [sel.get("value")]
            by_page.setdefault(v["page"], []).append((sel["field"], vals))
            g = v.get("sync")
            g = g.get("group") if isinstance(g, dict) else g
            if g:
                by_group[g] = (sel["field"], vals)
    for v in layout.get("visuals", []):
        g = v.get("sync")
        g = g.get("group") if isinstance(g, dict) else g
        if g in by_group and by_group[g] not in by_page.get(v["page"], []):
            by_page.setdefault(v["page"], []).append(by_group[g])
    return by_page


def filter_args(model, specs):
    out = []
    for f in specs or []:
        if str(f.get("type", "Categorical")).lower() != "categorical" or not f.get("values"):
            continue
        kind, tbl, name, _ = parse(f["field"])
        if kind != "column":
            continue
        col = dax_ref("column", tbl, name)
        vals = ", ".join(literal(model, tbl, name, x) for x in f["values"])
        if f.get("invert"):
            out.append(f"FILTER ( ALL ( {col} ), NOT {col} IN {{ {vals} }} )")
        else:
            out.append(f"TREATAS ( {{ {vals} }}, {col} )")
    return out


def visual_query(v, layout, model, privacy, sels):
    """{dax, groups: [{label, ref, sortBy}], values: [{label, field, format}], cat, leg} or None (nothing bound)."""
    b = v.get("bindings") or {}
    if not b:
        return None
    groups, values, defines = [], [], []
    for role, binding in b.items():
        for it in items(binding):
            if "field" not in it:
                continue                         # field parameters: drawn as placeholders
            try:
                kind, tbl, name, agg = parse(it["field"])
            except ValueError:
                continue
            label = it.get("displayName") or name
            if kind == "column":
                if any(g["field"] == it["field"] for g in groups):
                    continue
                c = model.tables.get(tbl).columns.get(name) if model and tbl in model.tables else None
                sort_by = c.sort_by if c is not None and c.sort_by else None
                groups.append({"label": label, "field": it["field"], "ref": dax_ref(kind, tbl, name), "role": role,
                               "table": tbl, "column": name,
                               "sortBy": dax_ref("column", tbl, sort_by) if sort_by else None})
            else:
                fmt, ref = None, dax_ref(kind, tbl, name, agg)
                if kind == "measure" and (model or DEFS["names"]):
                    ok, fmt = known_measure(model, name)
                    if not ok:
                        ref = measure_dax(model, it["field"], defines)    # a report extension measure
                        if not ref:
                            continue             # unknown: drawn without numbers
                        ref = one_line(ref)      # extension measures are text (images, colours)
                values.append({"label": label, "field": it["field"], "ref": ref, "role": role, "format": fmt})
    if not groups and not values:
        return None
    filt = filter_args(model, (layout.get("pages", {}).get(v["page"], {}).get("filters") or []) + (v.get("filters") or []))
    own = {g["field"] for g in groups}
    for field, vals in sels.get(v["page"], []):
        if field in own:
            continue                             # a slicer doesn't filter itself
        filt += filter_args(model, [{"field": field, "values": vals}])
    cols = [g["ref"] for g in groups] + [g["sortBy"] for g in groups if g["sortBy"]]
    meas = [f'"__n", {privacy["count"]}'] + [f'"v{k}", {x["ref"]}' for k, x in enumerate(values)]
    label_of = {x["field"]: x["label"] for x in values}
    colour, extras, row_items, targets = None, [], [], {}    # extras: per-row columns after the values;
    #                                                           row_items: one per visual
    for c in v.get("cf") or []:
        typ, obj, prp, m = c.get("type"), c.get("object"), c.get("property"), c.get("measure")
        ref = measure_dax(model, m, defines) if m else None
        if not ref:
            continue
        if typ == "measure" and obj == "dataPoint" and prp == "fill" and (c.get("perPoint") or c.get("target")) \
                and groups:              # per-point colour from a measure (e.g. bars inside / past the SLA)
            colour = colour or ref
        elif typ == "measure" and obj == "values" and prp in ("backColor", "fontColor"):
            extras.append(("back" if prp == "backColor" else "font", ref))
            if c.get("target") in label_of:      # the column it colours (a table); none: every value
                targets["back" if prp == "backColor" else "font"] = label_of[c["target"]]
        elif typ == "measure" and obj == "labels" and prp == "dynamicLabelValue":
            extras.append(("label:" + label_of.get(c.get("target"), "*"), ref))
        elif typ == "measure" and obj == "valueAxis" and prp in ("start", "end", "secStart", "secEnd"):
            row_items.append(("axis", prp, ref))
        elif typ == "image":
            extras.append(("image", one_line(ref)))
    for k, val in (v.get("props") or {}).items():  # labels.dynamicLabelValue as Desktop saves it (per series)
        if not k.startswith("labels.dynamicLabelValue@{"):
            continue
        mm = re.search(r'"Property":\s*"([^"]+)"', json.dumps(val))
        ref = measure_dax(model, f"[{mm.group(1)}]", defines) if mm else None
        if ref:
            target = selector_measure(k.split("@", 1)[1])
            extras.append(("label:" + (label_of.get(f"[{target}]", "*") if target else "*"), ref))
    cont = v.get("container") if isinstance(v.get("container"), dict) else {}
    for key in ("title", "subtitle"):          # titles from a measure: evaluated, so the wireframe shows the text
        tv = cont.get(key)
        ref = measure_dax(model, tv["measure"], defines) if isinstance(tv, dict) and tv.get("measure") else None
        if ref:
            row_items.append(("title", key, ref))
    if colour:
        extras.insert(0, ("colour", colour))
    for k, (key, ref) in enumerate(extras):  # IF: no rows without data
        meas.append(f'"{"__colour" if key == "colour" else f"__x{k}"}", IF ( NOT ISBLANK ( {privacy["count"]} ), '
                    f'{ref} )')
    refs = []
    for rl in v.get("referenceLines") or []:
        val = rl.get("value")
        if isinstance(val, str):
            kind, tbl, name, agg = parse(val)
            if kind == "measure" and not known_measure(model, name)[0]:
                continue
            refs.append({"axis": rl.get("axis", "value"), "label": rl.get("label", ""), "ref": dax_ref(kind, tbl, name, agg)})
        elif isinstance(val, (int, float)):
            refs.append({"axis": rl.get("axis", "value"), "label": rl.get("label", ""), "value": val})
    if v["type"] in ("slicer", "advancedSlicerVisual", "listSlicer"):
        meas = [f'"__n", {privacy["count"]}']    # slicers list members (with their counts) only
        values, colour, refs, extras, row_items, defines = [], None, [], [], [], []
    # Top N filters, as Power BI applies them: the top (or bottom) n members of the filter's field by its measure,
    # evaluated in the query under the visual's other filters, so the measure need not be one the visual shows
    top_vars, top = [], None
    for f in v.get("filters") or []:
        if str(f.get("type", "")).lower() != "topn":
            continue
        try:
            fk, ft, fn, _ = parse(f["field"])
            bk, bt, bn, bagg = parse(f.get("by", ""))
        except (KeyError, ValueError):
            continue
        if fk != "column" or (bk == "measure" and (model or DEFS["names"]) and not known_measure(model, bn)[0]):
            continue
        col, n, up = dax_ref("column", ft, fn), int(f.get("n", 5)), f.get("direction", "Top") != "Bottom"
        inner = "SUMMARIZECOLUMNS ( " + ", ".join([col] + filt + [f'"__by", {dax_ref(bk, bt, bn, bagg)}']) + " )"
        top_vars.append(f'VAR __top{len(top_vars)} = SELECTCOLUMNS ( TOPN ( {n}, {inner}, [__by], '
                        f'{"DESC" if up else "ASC"} ), "__k", {col} )')
        filt = filt + [f"TREATAS ( __top{len(top_vars) - 1}, {col} )"]
        top = top or {"n": n, "field": f["field"], "by": f.get("by"), "top": up}
    head = "DEFINE\n" + "\n".join(defines + top_vars) + "\n" if defines or top_vars else ""
    if groups:
        dax = head + "EVALUATE SUMMARIZECOLUMNS ( " + ", ".join(cols + filt + meas) + " )"
    else:
        body = "ROW ( " + ", ".join(meas) + " )"
        dax = head + (f"EVALUATE CALCULATETABLE ( {body}, {', '.join(filt)} )" if filt else f"EVALUATE {body}")
    cat = next((k for k, g in enumerate(groups) if g["role"] in CAT_ROLES), 0 if groups else None)
    leg = next((k for k, g in enumerate(groups) if g["role"] in LEG_ROLES), None)
    q = {"dax": dax, "groups": groups, "values": values, "cat": cat, "leg": leg, "colour": bool(colour),
         "extras": [k for k, _ in extras], "targets": targets}
    srt = v.get("sort") or {}
    srt = (srt[0] if srt else {}) if isinstance(srt, list) else srt
    if v["type"] == "pivotTable" and leg is not None and cat is not None and values \
            and any(x["field"] == srt.get("field") for x in values):     # a matrix sorted by a value: row totals
        x = next(x for x in values if x["field"] == srt.get("field"))
        g = groups[cat]
        q["totalDax"] = head + "EVALUATE SUMMARIZECOLUMNS ( " + ", ".join(
            [g["ref"]] + filt + [f'"__n", {privacy["count"]}', f'"t", {x["ref"]}']) + " )"
    if top and len(groups) == 1 and groups[0]["field"] == top["field"]:     # one row per member: order (and cut ties)
        k = next((k for k, x in enumerate(values) if x["field"] == top["by"]), None)
        if k is not None:
            q["topN"] = {"n": top["n"], "value": k, "top": top["top"]}
        srt = v.get("sort") or {}
        j = next((j for j, x in enumerate(values) if x["field"] == srt.get("field")), None)
        if j is not None:                        # the layout's sort on a shown value orders the kept members
            q["order"] = {"value": j, "desc": str(srt.get("direction", "Descending")).lower().startswith("desc")}
    measured = [r for r in refs if "ref" in r]
    q["rowItems"] = [[kind, key] for kind, key, _ in row_items]
    if measured or row_items:                # one row per visual: reference lines, axis ends, titles
        body = "ROW ( " + ", ".join([f'"__n", {privacy["count"]}'] +       # privacy count first: these values
                                    [f'"r{k}", {r["ref"]}' for k, r in enumerate(measured)] +      # are aggregates
                                    [f'"i{k}", {ref}' for k, (_, _, ref) in enumerate(row_items)]) + " )"
        q["refDax"] = head + (f"EVALUATE CALCULATETABLE ( {body}, {', '.join(filt)} )" if filt else f"EVALUATE {body}")
    q["refs"] = refs
    return q


def queries(layout, model):
    privacy = layout.get("privacy")
    if not privacy or not privacy.get("count"):
        raise PrivacyError("layout.json has no `privacy` with a `count` (the number of people behind a row, e.g. "
                           "\"[Group Size]\"): no data is fetched without it")
    sels = selections(layout)
    out = {}
    for v in layout.get("visuals", []):
        q = visual_query(v, layout, model, privacy, sels)
        if q:
            out[v["id"]] = q
    return out


# ---------------------------------------------------------------- run and shape
def run(dax, port, script=None):
    script = script or ROOT / ".claude" / "scripts" / "run-dax.ps1"
    q = pathlib.Path(tempfile.gettempdir()) / "pbik_wireframe_query.dax"
    q.write_text(dax, encoding="utf-8")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-File", str(q),
                        "-Port", str(port)], capture_output=True, text=True, encoding="utf-8")
    if r.stdout.startswith("ERROR") or (not r.stdout.strip() and r.stderr.strip()):
        raise RuntimeError((r.stdout or r.stderr).strip()[:500])
    return [[None if c == "(blank)" else _num(c) for c in line.split(SEP)]
            for line in r.stdout.splitlines() if line and line != "----"]


def _num(c):
    try:
        return float(c)
    except ValueError:
        return c


def shape(q, raw, privacy):
    """Raw rows (groups, sort-by columns, __n, values) -> visual data with small groups hidden."""
    ng, ns = len(q["groups"]), sum(1 for g in q["groups"] if g["sortBy"])
    ext = q.get("extras") or (["colour"] if q.get("colour") else [])
    rows = []
    for r in raw:
        gvals, sort_vals, n, vals = r[:ng], r[ng:ng + ns], r[ng + ns], r[ng + ns + 1:]
        xs = dict(zip(ext, vals[len(vals) - len(ext):])) if ext else {}
        vals = vals[:len(vals) - len(ext)]
        rows.append({"g": gvals, "s": sort_vals, "n": n, "v": vals, "c": xs.get("colour"), "x": xs})
    min_n = privacy.get("minGroup", 5)
    keep = [r for r in rows if isinstance(r["n"], (int, float)) and r["n"] >= min_n]
    hidden = len(rows) - len(keep)
    if hidden == 1 and len(keep) > 1 and ng:          # secondary suppression: one hidden row could be derived
        smallest = min(keep, key=lambda r: r["n"])
        keep.remove(smallest)
        hidden += 1
    keep.sort(key=lambda r: tuple(_sortable(x) for x in (r["s"] or r["g"])))
    if q.get("topN"):
        t = q["topN"]
        keep.sort(key=lambda r: r["v"][t["value"]] or 0, reverse=t["top"])
        keep = keep[:t["n"]]
    if q.get("order"):
        o = q["order"]
        keep.sort(key=lambda r: r["v"][o["value"]] or 0, reverse=o["desc"])
        keep.sort(key=lambda r: r["v"][o["value"]] is None)                # blanks last
    out = {"groups": [g["label"] for g in q["groups"]], "values": [x["label"] for x in q["values"]],
           "formats": [x["format"] for x in q["values"]], "cat": q["cat"], "leg": q["leg"],
           "rows": [r["g"] + r["v"] for r in keep], "counts": [r["n"] for r in keep], "hidden": hidden,
           "total": len(rows), **({"colours": [r["c"] for r in keep]} if q.get("colour") else {})}
    for key, name in (("back", "backs"), ("font", "fonts"), ("image", "images")):
        if key in ext:
            out[name] = [r["x"].get(key) for r in keep]
    for key, target in (q.get("targets") or {}).items():
        out[key + "Target"] = target
    labels = {k.split(":", 1)[1]: [r["x"].get(k) for r in keep] for k in ext if k.startswith("label:")}
    if labels:
        out["labels"] = labels
    if ng > 1:                                   # each group's members in sort order (a matrix's columns)
        sk = [k for k, g in enumerate(q["groups"]) if g["sortBy"]]
        out["levels"] = []
        for k in range(ng):
            seen = {}
            for r in rows:                       # all rows, so a column with every cell hidden keeps its place
                key = r["s"][sk.index(k)] if k in sk else r["g"][k]
                seen.setdefault(r["g"][k], _sortable(key))
            out["levels"].append(sorted(seen, key=lambda x: seen[x]))
    return out


def _sortable(x):
    return (0, x) if isinstance(x, (int, float)) else (1, str(x))


def check(qs, data, privacy):
    """Raises PrivacyError (nothing is written) if anything could identify an individual. Returns report lines."""
    bad = []
    ident = {i.strip() for i in privacy.get("identifiers", [])}
    max_rows = privacy.get("maxRows", 500)
    min_n = privacy.get("minGroup", 5)
    smallest, groups, hidden = None, 0, 0
    for vid, q in qs.items():
        for g in q["groups"]:
            names = {g["field"], f"{g['table']}[{g['column']}]", f"'{g['table']}'[{g['column']}]"}
            if names & ident or looks_like_identifier(g["column"]):
                bad.append(f"{vid}: groups by {g['field']}, which can identify a person")
        d = data.get(vid)
        if d is None:
            continue
        if d["total"] > max_rows:
            bad.append(f"{vid}: {d['total']} rows (over {max_rows}): looks row-level")
        for n in d["counts"]:
            if not isinstance(n, (int, float)):
                bad.append(f"{vid}: a row has no privacy count")
            elif n < min_n:
                bad.append(f"{vid}: a group of {n:g} is still in the data")
            else:
                smallest = n if smallest is None else min(smallest, n)
        groups += len(d["counts"])
        hidden += d["hidden"]
    if bad:
        raise PrivacyError("privacy check failed, nothing written:\n  " + "\n  ".join(bad))
    return [f"{len(qs)} visual queries; {groups} groups shown, {hidden} hidden (under {min_n}, or hidden so a hidden "
            f"one can't be derived); smallest group shown: {smallest if smallest is not None else '-'}",
            "no identifier columns grouped; privacy check passed"]


def fetch(layout, model, port, runner=None):
    runner = runner or run
    qs = queries(layout, model)
    privacy = layout["privacy"]
    data = {}
    for vid, q in qs.items():
        data[vid] = shape(q, runner(with_defines(q["dax"]), port), privacy)
        if q.get("totalDax"):                    # a matrix's row totals (each over minGroup people)
            data[vid]["rowTotals"] = {str(r[0]): r[2] for r in runner(with_defines(q["totalDax"]), port)
                                      if isinstance(r[1], (int, float)) and r[1] >= privacy.get("minGroup", 5)}
        if q.get("refs") or q.get("rowItems"):
            try:                                 # decoration only: a failed query leaves them without values
                row = runner(with_defines(q["refDax"]), port)[0] if q.get("refDax") else [None]
            except Exception:                    # noqa: BLE001
                row = [None]
            n, vals = row[0], row[1:]
            if q.get("refDax") and not (isinstance(n, (int, float)) and n >= privacy.get("minGroup", 5)):
                vals = []                        # fewer people than minGroup behind them: no value shown
            nm = sum(1 for r in q.get("refs", []) if "value" not in r)
            it = iter(vals[:nm])
            if q.get("refs"):
                data[vid]["refLines"] = [{"axis": r["axis"], "label": r["label"],
                                          "value": r["value"] if "value" in r else next(it, None)} for r in q["refs"]]
            for (kind, key), val in zip(q.get("rowItems", []), vals[nm:]):
                if val is not None:
                    data[vid].setdefault("axis" if kind == "axis" else "titles", {})[key] = val
    report = check(qs, data, privacy)
    return {"_note": "Aggregates for the high-fidelity wireframe (design/scripts/wireframe_data.py). Groups under "
                     f"{privacy.get('minGroup', 5)} hidden.",
            "made": datetime.date.today().isoformat(), "privacy": report,
            "state": {"selections": {k: [[f, v] for f, v in s] for k, s in selections(layout).items()}},
            "queries": {vid: q["dax"] for vid, q in qs.items()}, "visuals": data}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", help="the open Desktop model's port, or 'auto' (the newest Desktop workspace)")
    ap.add_argument("--layout", default=str(ROOT / "design" / "specs" / "layout.json"))
    ap.add_argument("--model", help="the *.SemanticModel folder (default: the one in the project root)")
    ap.add_argument("--out", default=str(ROOT / "design" / "wireframes" / "wireframe-data.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--define", help="file of MEASURE definitions to run query-scoped (proposed measures)")
    a = ap.parse_args(argv)
    if a.define:
        load_defines(a.define)
    layout = json.loads(pathlib.Path(a.layout).read_text(encoding="utf-8"))
    root = pathlib.Path(a.layout).resolve().parents[2]
    mf = pathlib.Path(a.model) if a.model else next(root.glob("*.SemanticModel"), None)
    model = tmdl.load(mf) if mf else None
    load_extensions(root)
    try:
        if a.dry_run:
            for vid, q in queries(layout, model).items():
                print(f"[{vid}] {q['dax']}")
            return 0
        if not a.port:
            ap.error("--port is required (the open Desktop model), or --dry-run")
        port = a.port
        if port == "auto":
            from pbikit import slicerfit
            port = slicerfit.discover_port()
            if not port:
                ap.error("--port auto: no open Desktop model found")
        out = fetch(layout, model, int(port))
    except PrivacyError as e:
        print(f"wireframe_data: {e}", file=sys.stderr)
        return 1
    p = pathlib.Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n".join(out["privacy"]) + f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
