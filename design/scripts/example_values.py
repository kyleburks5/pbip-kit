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
    if PCT.search(name or ""):
        return "+0.0%;-0.0%;0.0%" if re.search(r"\bvs\b|growth|change", name, re.I) else "0.0%"
    if AVG.search(name or ""):
        return "#,0.00"
    return "#,0"


CMP_WORDS = re.compile(r"\bvs\b|change|growth|variance|\bdiff|delta|\byoy\b", re.I)
LY = re.compile(r"\b(LY|PY|last year|prior|previous)\b", re.I)
SMALL = re.compile(r"return|refund|cost|discount|claim", re.I)


def _key(name):
    """The measure a name stands for: last-year versions share their base measure's numbers."""
    key = LY.sub("", name or "").strip(" _-[]").lower()
    return re.sub(r"^(fact|total|sum of)\s+", "", key)


def value_for(name, rnd=None):
    """A total for a measure, the same for the same measure name in every visual."""
    rnd = random.Random("total/" + _key(name))
    if PCT.search(name or ""):
        return round(rnd.uniform(-0.08, 0.12) if re.search(r"\bvs\b|growth|change", name, re.I)
                     else rnd.uniform(0.08, 0.35), 4)
    if AVG.search(name or ""):
        return round(rnd.uniform(20, 90), 2)
    scale = 0.12 if SMALL.search(name or "") else 1
    if COUNT.search(name or ""):
        return float(round(rnd.randint(8_000, 40_000) * scale))
    v = float(round(rnd.randint(900_000, 2_400_000) * scale))
    return round(v * 0.88) if LY.search(name or "") else v


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


def for_visual(v, measures=None):
    """The wireframe data entry (as wireframe_data.py writes it) for one visual, with example values."""
    groups, values, names = [], [], []
    for role, b in (v.get("bindings") or {}).items():
        for it in b if isinstance(b, list) else [b]:
            it = it if isinstance(it, dict) else {"field": it}
            fld = it.get("field") or it.get("fieldParameter") or ""
            label = it.get("displayName") or re.sub(r"^.*\[|\]\)?$", "", fld)
            if is_measure(fld, role, measures):
                values.append(label)
                names.append(re.sub(r"^.*\[|\]\)?$", "", fld) or label)
            else:
                groups.append(label)
    if not values and not groups:
        return None
    t = v.get("type", "")
    one = t in ("cardVisual", "card", "kpi", "gauge") or not groups
    rows = []
    if one:
        rows.append([value_for(x) for x in names])
    else:
        cats = categories(groups[0], 12 if "month" in groups[0].lower() else 6)
        for c in cats:
            row = [c] + [None] * (len(groups) - 1)
            for x in names:
                total = value_for(x)
                if PCT.search(x) or AVG.search(x):
                    val = total * random.Random(f"{_key(x)}/{c}").uniform(0.8, 1.2)
                else:
                    val = total * share(c, len(cats), x)
                row.append(round(val, 4 if PCT.search(x) else 2))
            rows.append(row)
        if t in ("barChart", "clusteredBarChart", "columnChart", "clusteredColumnChart", "tableEx") and values \
                and "month" not in groups[0].lower():
            rows.sort(key=lambda r: -(r[len(groups)] or 0))           # ranked, as the plan usually asks
    out = {"groups": [] if one else groups, "values": values, "formats": [fmt_for(x) for x in names],
           "cat": 0, "leg": None, "rows": rows, "counts": [99] * len(rows), "hidden": 0, "total": len(rows),
           "example": True}
    rl = v.get("referenceLabels")
    if isinstance(rl, dict) and rl.get("labels"):
        out["refs"], out["refDetails"] = [], []
        for lab in rl["labels"]:
            name = re.sub(r"^.*\[|\]$", "", str(lab.get("value", "")))
            out["refs"].append(format_value(value_for(name), fmt_for(name)))
            det = re.sub(r"^.*\[|\]$", "", str(lab.get("detail", "") or ""))
            if det:                               # the change beside it: ▲ / ▼, green or red when coloured
                x = value_for(det)
                text = ("▲ " if x >= 0 else "▼ ") + format_value(abs(x), "0.0%") if PCT.search(det) or \
                    CMP_WORDS.search(det) else format_value(x, fmt_for(det))
                out["refDetails"].append({"text": text, "good": x >= 0 if lab.get("detailColor") else None})
            else:
                out["refDetails"].append(None)
    return out


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
    vis = {}
    for v in layout.get("visuals", []):
        e = for_visual(v, measures)
        if e:
            vis[v["id"]] = e
    return {"visuals": vis, "example": True,
            "privacy": ["example values (made up from a seed per visual, no data read): passed"]}
