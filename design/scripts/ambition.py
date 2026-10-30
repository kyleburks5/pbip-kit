"""Design ambition checks (/plan step 1, before choosing visuals): the spec records, per key number, its baseline,
what normal looks like, the exceptions and anything partial or stale; every headline number has a comparison.

- spec.md has a "Design ambition" section, with a table row (or line) per key number naming all four:
  baseline, normal, exceptions, partial / stale;
- every headline visual (a card, KPI or gauge with bindings, except a `freshness-line`) shows a comparison:
  reference labels, a second value binding (KPI target, gauge target), or a `comparison` key in layout.json naming
  the visual that carries it (for example a range band next to the card).
audit_ids.py calls issues().
"""
import re

HEADLINE = {"cardVisual", "card", "kpi", "gauge", "multiRowCard"}
PARTS = ("baseline", "normal", "exception", "partial")


def headline_issues(visuals):
    out = []
    for v in visuals:
        if v.get("type") not in HEADLINE or not v.get("bindings") or v.get("pattern") == "freshness-line":
            continue
        values = [x for k, b in v["bindings"].items() for x in (b if isinstance(b, list) else [b])]
        has_ref = bool((v.get("referenceLabels") or {}).get("labels"))
        two = len(values) > 1 and v["type"] in ("kpi", "gauge")
        if not (has_ref or two or v.get("comparison")):
            out.append(f"layout: {v.get('id')} is a headline number without a comparison (reference labels, a "
                       "target binding, or `comparison` naming the visual that carries it)")
    return out


def spec_issues(spec_text):
    m = re.search(r"^#+\s*Design ambition\b(.*?)(?=^#{1,2}\s|\Z)", spec_text, re.S | re.M | re.I)
    if not m:
        return ["spec: no \"Design ambition\" section (baseline, normal, exceptions, partial or stale per key number)"]
    body = m.group(1).lower()
    missing = [p for p in PARTS if p not in body]
    return [f"spec: the Design ambition section doesn't cover: {', '.join(missing)}"] if missing else []


def issues(visuals, spec_text=None):
    return headline_issues(visuals) + (spec_issues(spec_text) if spec_text is not None else [])
