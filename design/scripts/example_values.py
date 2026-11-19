"""Example values for the fast HTML preview (the plan picture and quick changes): made up, never read from data.

    gen_wireframe_hf.py --data example

Two renderers (v1.7 walkthrough): this preview, drawn from layout.json, tokens, the theme and the templates' look with
believable example numbers, is what the person approves; after the build, a real Power BI Desktop screenshot is
compared against it (design/scripts/fidelity_check.py, `pbik plan compare`). Nothing here touches a model: the values
come from a seed per visual, so the same layout always draws the same picture. Formats follow the measure's name
(share, rate, % and "vs" as percentages, averages with two decimals, everything else whole numbers with thousands
separators); categories follow the field's name (months in calendar order, years, then "<Name> 1..n").
"""
import json, pathlib, random, re

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PCT = re.compile(r"%|share|rate|ratio|pct|percent|\bvs\b|growth|change", re.I)
AVG = re.compile(r"\bavg\b|average|mean|per\b", re.I)
COUNT = re.compile(r"qty|quantity|count|units|orders?$|number|visits|tickets", re.I)
MEASURE_TABLE = re.compile(r"^_|measure", re.I)
DAYS = re.compile(r"days|hours|duration|\btime\b", re.I)
SPLY = re.compile(r"^\s*CALCULATE\s*\(\s*\[([^\]]+)\]\s*,\s*(SAMEPERIODLASTYEAR|DATEADD|PARALLELPERIOD|PREVIOUSYEAR)", re.I)
MODEL = {}           # measure name -> {formatString, expression}: the model contract and planned measures (v1.11.2)


def load_model(root):
    """What the model says about its measures (format, expression), so the example values follow the model rather
    than the measure's name: a 0.0% format is a rate, CALCULATE ( [X], SAMEPERIODLASTYEAR ... ) is X last year."""
    MODEL.clear()
    for p in [pathlib.Path(root), *pathlib.Path(root).parents][:4]:
        spec = p / "design" / "specs"
        if (spec / "contract.json").exists():
            try:
                c = json.loads((spec / "contract.json").read_text(encoding="utf-8"))
                for t in (c.get("tables") or {}).values():
                    MODEL.update({k: v for k, v in (t.get("measures") or {}).items() if isinstance(v, dict)})
                g = json.loads((spec / "generate.json").read_text(encoding="utf-8")) if (spec / "generate.json").exists() else {}
                MODEL.update({k: v for k, v in (g.get("plannedMeasures") or {}).items() if isinstance(v, dict)})
            except (OSError, ValueError):
                pass
            return


def is_pct(name):
    f = (MODEL.get(name) or {}).get("formatString")
    return "%" in f if f else bool(PCT.search(name or ""))


def ly_base(name):
    """The measure a last-year measure shifts, from its DAX when the model has it, else from its name."""
    m = SPLY.match((MODEL.get(name) or {}).get("expression", ""))
    if m:
        return m.group(1)
    if LY.search(name or ""):
        base = LY.sub("", name).strip(" _-")
        return base if base else None
    return None


def contract_measures(root):
    """Measure names from design/specs/contract.json (the approved model contract), if the project has one."""
    for p in [pathlib.Path(root), *pathlib.Path(root).parents][:4]:
        f = p / "design" / "specs" / "contract.json"
        if f.exists():
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                return set()
            tabs = c.get("tables") or {}
            items = tabs.items() if isinstance(tabs, dict) else ((t.get("name"), t) for t in tabs)
            return {m for _, t in items for m in (t.get("measures") or {})}
    return set()


def is_measure(field, role=None, measures=None):
    """A bound field is a measure when the model contract says so, it is written [Name], or its table is a measure
    table (_Measures); a Data or Y binding without a table is one too. Columns keep their table: T[C]."""
    f = str(field or "")
    m = re.match(r"^'?([^'\[]*)'?\[(.+)\]$", f)
    if not m:
        return "(" in f
    table, name = m.group(1), m.group(2)
    if measures and name in measures:
        return True
    if not table:
        return True
    return bool(MEASURE_TABLE.search(table))


def fmt_for(name):
    f = (MODEL.get(name) or {}).get("formatString")
    if f and f not in ("0", "General"):
        return f
    if is_pct(name):
        return "+0.0%;-0.0%;0.0%" if re.search(r"\bvs\b|growth|change", name, re.I) else "0.0%"
    if AVG.search(name or ""):
        return "#,0.00"
    return "#,0"


CMP_WORDS = re.compile(r"\bvs\b|change|growth|variance|\bdiff|delta|\byoy\b", re.I)
LY = re.compile(r"\b(LY|PY|last year|prior|previous)\b", re.I)
SMALL = re.compile(r"return|refund|cost|discount|claim|breach|late|overdue|fail|error|backlog", re.I)


def _key(name):
    """The measure a name stands for: last-year versions share their base measure's numbers."""
    key = LY.sub("", name or "").strip(" _-[]").lower()
    return re.sub(r"^(fact|total|sum of)\s+", "", key)


def value_for(name, rnd=None):
    """A total for a measure, the same for the same measure name in every visual. A last-year version is its base
    measure's value moved by a seeded amount (v1.11.2: never equal to this year, so the change shown agrees)."""
    src = ly_base(name)
    if src and src in MODEL and src != name:      # the model says which measure it shifts: follow that one
        base = value_for(src)
        name_kind = src
    else:
        base = _base_value(name)
        name_kind = name
    if not src or not isinstance(base, (int, float)):
        return base
    r = random.Random("ly/" + _key(name))
    if is_pct(name_kind):
        return round(base - r.uniform(-0.012, 0.025), 4)
    v = base * r.uniform(0.86, 1.04)
    return round(v, 2) if AVG.search(name or "") else float(round(v))


def change_text(cur, ly, pct_points=False):
    """(text, sign) for the change from last year to this year, computed from the two shown values."""
    if cur is None or ly is None:
        return "", 0
    x = (cur - ly) if pct_points else ((cur - ly) / ly if ly else 0)
    if abs(x) < 0.0005:
        return "no change", 0
    txt = f"{abs(x) * 100:.1f} pts" if pct_points else format_value(abs(x), "0.0%")
    return ("▲ " if x > 0 else "▼ ") + txt, (1 if x > 0 else -1)


def _base_value(name):
    rnd = random.Random("total/" + _key(name))
    if is_pct(name):
        return round(rnd.uniform(-0.08, 0.12) if re.search(r"\bvs\b|growth|change", name, re.I)
                     else rnd.uniform(0.08, 0.35), 4)
    if DAYS.search(name or ""):                  # days to resolve, SLA days: a few, not thousands
        return round(rnd.uniform(2, 12), 2 if AVG.search(name or "") else 0)
    if AVG.search(name or ""):
        return round(rnd.uniform(20, 90), 2)
    scale = 0.12 if SMALL.search(name or "") else 1
    if COUNT.search(name or ""):
        return float(round(rnd.randint(8_000, 40_000) * scale))
    return float(round(rnd.randint(900_000, 2_400_000) * scale))


def share(category, n_cats, name):
    """The part of a total that one category holds (weights seeded by the category, summing to 1 over the categories)."""
    return random.Random("w/" + str(category)).uniform(0.6, 1.4) / n_cats


def categories(label, n=6):
    low = (label or "").lower()
    if "month" in low or low in ("date", "period"):
        return MONTHS[:max(n, 12)][:12]
    if "year" in low:
        return [str(2021 + i) for i in range(min(n, 5))]
    if "quarter" in low:
        return ["Q1", "Q2", "Q3", "Q4"]
    base = re.sub(r"\s*(name|key|label)$", "", label or "Item", flags=re.I).strip() or "Item"
    return [f"{base} {i + 1}" for i in range(n)]


def for_visual(v, measures=None, colors=None):
    """The wireframe data entry (as wireframe_data.py writes it) for one visual, with example values."""
    groups, values, names, group_roles = [], [], [], []
    for role, b in (v.get("bindings") or {}).items():
        if role in ("Tooltips", "Details") and v.get("type") != "scatterChart":             # tooltip fields aren't drawn; details are the points, not a series
            continue
        for it in b if isinstance(b, list) else [b]:
            it = it if isinstance(it, dict) else {"field": it}
            fld = it.get("field") or it.get("fieldParameter") or ""
            label = it.get("displayName") or re.sub(r"^.*\[|\]\)?$", "", fld)
            if is_measure(fld, role, measures):
                values.append(label)
                names.append(re.sub(r"^.*\[|\]\)?$", "", fld) or label)
            else:
                groups.append(label)
                group_roles.append(role)
    if not values and not groups:
        return None
    t = v.get("type", "")
    one = t in ("cardVisual", "card", "kpi", "gauge") or not groups
    rows = []
    if one:
        rows.append([value_for(x) for x in names])
    else:
        cats = categories(groups[0], 12 if "month" in groups[0].lower() else 6)
        # a legend / matrix column field splits each category into members (stacked columns, a matrix's columns)
        leg = next((i for i, r in enumerate(group_roles) if r in ("Series", "Legend", "Columns") and i > 0), None)
        members = categories(groups[leg], 4) if leg is not None else [None]
        for c, mem in ((c, m) for c in cats for m in members):
            row = [c] + [None] * (len(groups) - 1)
            if leg is not None:
                row[leg] = mem
            for x in names:
                total = value_for(x)
                if is_pct(x) or AVG.search(x) or DAYS.search(x):
                    val = total * random.Random(f"{_key(x)}/{c}").uniform(0.8, 1.2)
                else:
                    val = total * share(c, len(cats), x) * (share(mem, len(members), x) if mem else 1)
                row.append(round(val, 4 if is_pct(x) else 2))
            rows.append(row)
        if t in ("barChart", "clusteredBarChart", "columnChart", "clusteredColumnChart", "tableEx") and values \
                and "month" not in groups[0].lower() and leg is None:
            rows.sort(key=lambda r: -(r[len(groups)] or 0))           # ranked, as the plan usually asks
    out = {"groups": [] if one else groups, "values": values, "formats": [fmt_for(x) for x in names],
           "cat": 0, "leg": None if one else leg, "rows": rows, "counts": [99] * len(rows), "hidden": 0, "total": len(rows),
           "example": True}
    colors = colors or {}
    for c in v.get("cf", []) or []:              # a "vs" column coloured by direction, as the colour measure does
        if c.get("type") != "measure" or c.get("property") != "fontColor" or one:
            continue
        tgt = re.sub(r"^.*\[|\]$", "", str(c.get("target") or ""))
        if tgt not in names:
            continue
        k = len(groups) + names.index(tgt)
        lower = bool(c.get("lowerIsBetter"))
        good, bad = colors.get("good", "#197982"), colors.get("bad", "#B94642")
        out["fonts"] = [None if r[k] is None else (good if (r[k] >= 0) != lower else bad) for r in rows]
        out["fontTarget"] = values[names.index(tgt)]
    rl = v.get("referenceLabels")
    if isinstance(rl, dict) and rl.get("labels"):
        out["refs"], out["refDetails"] = [], []
        for lab in rl["labels"]:
            name = re.sub(r"^.*\[|\]$", "", str(lab.get("value", "")))
            out["refs"].append(format_value(value_for(name), fmt_for(name)))
            det = re.sub(r"^.*\[|\]$", "", str(lab.get("detail", "") or ""))
            if det:                               # the change beside it, computed from the two values shown
                cur = value_for(names[0]) if names else None
                ly = value_for(name)
                if ly_base(name) and isinstance(cur, (int, float)) and isinstance(ly, (int, float)):
                    text, sign = change_text(cur, ly, pct_points=is_pct(names[0]))   # a rate moves in points
                elif CMP_WORDS.search(det) and isinstance(cur, (int, float)) and isinstance(ly, (int, float)):
                    # against a target or threshold (the SLA, a budget): the difference in the card's own units
                    x = cur - ly
                    sign = 1 if x > 0 else -1 if x < 0 else 0
                    shown = f"{abs(x) * 100:.1f} pts" if is_pct(names[0]) else format_value(abs(x), fmt_for(names[0]).lstrip("+"))
                    text = "no change" if sign == 0 else ("▲ " if sign > 0 else "▼ ") + shown
                else:
                    x = value_for(det)
                    text = ("▲ " if x >= 0 else "▼ ") + format_value(abs(x), "0.0%") if PCT.search(det) or \
                        CMP_WORDS.search(det) else format_value(x, fmt_for(det))
                    sign = 1 if x > 0 else -1 if x < 0 else 0
                good = None if sign == 0 else (sign > 0) != bool(lab.get("lowerIsBetter"))   # a fall is good for costs
                out["refDetails"].append({"text": text, "good": good if lab.get("detailColor") else None})
            else:
                out["refDetails"].append(None)
    # one accent (dark glass rule): a cf colour measure with `emphasis: "top"` paints the top item in the accent, the
    # rest muted; the rows are ranked, so the top item is the first
    for c in v.get("cf", []) or []:
        if c.get("emphasis") in ("top", "last") and rows and not one:
            pick = 0 if c["emphasis"] == "top" else len(rows) - 1
            out["colours"] = [colors.get(c.get("accent", "brand"), "#F2A541") if i == pick else colors.get(c.get("muted", "second"), "#8C9BB2")
                              for i in range(len(rows))]
    rls = [r for r in v.get("referenceLines") or [] if isinstance(r.get("value"), (int, float, str))]
    if rls:                                       # a measure line ("[SLA Days]") at that measure's example value
        val = lambda x: x if isinstance(x, (int, float)) else value_for(re.sub(r"^.*\[|\]$", "", x))
        out["refLines"] = [{"axis": r.get("axis", "value"), "label": r.get("label", ""), "value": val(r["value"])} for r in rls]
    if v.get("preview"):                          # a sentence for the plan picture, its numbers from these values
        out["preview"] = preview_text(v["preview"])
    return out


def preview_text(tpl):
    """`{value:[M]}` the example value of M; `{change:[M]|[M PY]}` the change between two; `{top:Field|[M]}` the
    member with the most of M (the first bar), `{top:Field}` the first member."""
    def sub(m):
        kind, arg = m.group(1), m.group(2)
        if kind == "value":
            n = arg.strip("[]")
            return format_value(value_for(n), fmt_for(n))
        if kind == "change":
            a, b = (x.strip().strip("[]") for x in arg.split("|"))
            ca, cb = value_for(a), value_for(b)
            t, sign = change_text(ca, cb, pct_points=bool(PCT.search(a)))
            return t.replace("▲ ", "up ").replace("▼ ", "down ") if t else ""
        if kind == "top":                      # {top:Field|[Measure]}: the member the ranked bars show first
            fld, _, msr = arg.partition("|")
            cats = categories(re.sub(r"^.*\[|\]$", "", fld), 6)
            return max(cats, key=lambda c: share(c, len(cats), msr)) if msr else cats[0]
        return m.group(0)
    return re.sub(r"\{(value|change|top):([^}]+)\}", sub, tpl)


def format_value(x, fmt):
    if "%" in fmt:
        s = f"{abs(x) * 100:.1f}%"
        return ("+" if x >= 0 else "-") + s if fmt.startswith("+") else s
    if "0.00" in fmt:
        return f"{x:,.2f}"
    return f"{x:,.0f}"


def data_for(layout, root=None):
    """The whole wireframe data document: {"visuals": {id: entry}, "privacy": [...], "example": true}."""
    measures = contract_measures(root or layout.get("_root") or ".")
    load_model(root or layout.get("_root") or ".")
    colors = {}
    try:
        import json as _json, pathlib as _p
        colors = _json.loads((_p.Path(root or layout.get("_root") or ".") / "design" / "tokens.json")
                             .read_text(encoding="utf-8")).get("colors", {})
    except (OSError, ValueError):
        pass
    vis = {}
    for v in layout.get("visuals", []):
        e = for_visual(v, measures, colors)
        if e:
            vis[v["id"]] = e
    return {"visuals": vis, "example": True,
            "privacy": ["example values (made up from a seed per visual, no data read): passed"]}
