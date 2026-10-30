"""Deneb visuals (visual-method ladder step 3): layout.json `type: "deneb"` -> the PBIR form Desktop saved.

Learned from one Deneb visual Power BI Desktop saved on the Patterns page (..\\pbip-patterns, page
Patterns, visual cdf624ae768e435e8035, 2026-10-24), never from Deneb's or Desktop's program code:
- visual.visualType is the AppSource visual's GUID name below, also listed in report.json `publicCustomVisuals`;
- the fields are one role, `dataset` (columns and measures, as any projection);
- objects.vega[0].properties.jsonSpec: the spec as one string literal (Desktop kept CRLF line breaks in it);
- objects.stateManagement[0].properties: supportFieldConfiguration (a JSON string, one entry per field by its name:
  highlight / highlightStatus / highlightComparator / names false, format and formatted true for the measures and false
  for the column), denebMetaVersion '2', consolidateFieldParameters false, viewportHeight / viewportWidth (the visual's
  size in whole pixels, as D numbers).
No provider property was saved (the spec is Vega-Lite), and no config: pbik writes Vega-Lite specs only, and nothing
it hasn't seen saved.

layout.json:
    {"id": "P1-V05", "type": "deneb", "bindings": {"dataset": ["Region[Region]", "[Value]"]},
     "deneb": {"spec": {...Vega-Lite...} or "design/deneb/P1-V05.vl.json"},
     "fallback": {"type": "clusteredBarChart", "bindings": {...}, "props": {...},
                  "build": {"method": "native", "step": 1, "reason": "..."}},
     "build": {"method": "deneb", "step": 3, "nativeTried": "...", "reason": "...", "register": "F3"}}
The fallback takes the visual's ID, name, page, box, z, container (not its title or subtitle: the fallback sets its
own when the Deneb visual has one), tab order and filters; its own keys replace the rest.
`pbik build --no-custom-visuals` builds every fallback instead (same ID and folder).
"""
import json, pathlib

TYPE = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"
KEEP = ("id", "name", "page", "x", "y", "w", "h", "z", "cols", "tabOrder", "hidden", "container", "pattern", "filters")
SPEC_ROOTS = ("mark", "layer", "facet", "repeat", "concat", "hconcat", "vconcat")
FALLBACK_METHODS = {"native", "svg-measure", "svg", "image"}


OWN_TEXT = ("title", "subtitle")       # the fallback says what it draws; the Deneb visual's words don't carry over


def title_issue(v):
    """A Deneb visual with a title or subtitle needs its fallback's own (fallback.container.title / subtitle)."""
    c, fc = v.get("container"), (v.get("fallback") or {}).get("container")
    missing = [k for k in OWN_TEXT if isinstance(c, dict) and c.get(k) not in (None, False)
               and not (isinstance(fc, dict) and k in fc)]
    return (f"the fallback needs its own container {' and '.join(missing)} (the Deneb visual's describes the Deneb "
            "chart; use false for none)") if missing else None


class DenebError(Exception):
    pass


def is_deneb(v):
    return v.get("type") in ("deneb", TYPE)


def load_spec(v, root):
    """The Vega-Lite spec of a layout visual: `deneb.spec` inline, or a JSON file path from the project root."""
    spec = (v.get("deneb") or {}).get("spec")
    if isinstance(spec, str):
        f = pathlib.Path(root) / spec
        if not f.exists():
            raise DenebError(f"deneb.spec file {spec} not found")
        try:
            spec = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise DenebError(f"deneb.spec file {spec} is not valid JSON: {e}")
    if spec is None:
        raise DenebError("no deneb.spec (a Vega-Lite spec, inline or a file)")
    return spec


def _walk(node, path=()):
    if isinstance(node, dict):
        for k, x in node.items():
            yield path + (k,), k, x
            yield from _walk(x, path + (k,))
    elif isinstance(node, list):
        for k, x in enumerate(node):
            yield from _walk(x, path + (k,))


def spec_issues(spec, fields=None):
    """(errors, warnings) for a Vega-Lite spec: valid shape, no external data or images, fields in the dataset."""
    errs, warns = [], []
    if not isinstance(spec, dict):
        return [f"the spec is not a JSON object ({type(spec).__name__})"], warns
    if (spec.get("deneb") or {}).get("provider") not in (None, "vegaLite") or "signals" in spec or "marks" in spec:
        errs.append("the spec looks like Vega, not Vega-Lite: pbik writes Vega-Lite only (the form Desktop saved)")
    if not any(k in spec for k in SPEC_ROOTS):
        errs.append(f"the spec has none of {', '.join(SPEC_ROOTS)}: nothing to draw")
    data = spec.get("data")
    if data is not None and data != {"name": "dataset"}:
        warns.append(f"data is {json.dumps(data)}; Deneb provides the visual's fields as {{\"name\": \"dataset\"}}")
    for path, k, x in _walk(spec):
        if k == "url":
            errs.append(f"{'.'.join(map(str, path))}: a url loads data or images from outside the model "
                        "(aggregates only, docs/it-security.md); use the dataset")
        if k == "values" and len(path) >= 2 and path[-2] == "data":
            warns.append(f"{'.'.join(map(str, path))}: inline data values in the spec; the visual should draw the dataset")
    if fields is not None:
        known = set(fields)
        derived = set()                     # fields a transform makes (`as`)
        for _, k, x in _walk(spec):
            if k == "as":
                derived.update([x] if isinstance(x, str) else [a for a in x if isinstance(a, str)]
                               if isinstance(x, list) else [])
        missing = set()
        for path, k, x in _walk(spec):
            if k == "field" and isinstance(x, str) and "encoding" in path:
                name = x.replace("\\.", ".").replace("\\[", "[").replace("\\]", "]")
                if name not in known and name not in derived and not name.startswith("__"):
                    missing.add(x)
        if missing:
            warns.append(f"the spec uses field(s) {sorted(missing)} that aren't in the dataset {sorted(known)}")
    return errs, warns


def spec_text(spec):
    """The spec as Desktop stores it: indented JSON with CRLF line breaks, in one string literal."""
    return json.dumps(spec, indent=2, ensure_ascii=False).replace("\n", "\r\n")


def field_config(projections):
    """stateManagement.supportFieldConfiguration, as Desktop saved it: per field name, format/formatted true for
    measures."""
    out = {}
    for p in projections:
        name = p.get("nativeQueryRef") or p.get("queryRef", "").split(".")[-1]
        meas = "Measure" in p.get("field", {})
        out[name] = {"highlight": False, "highlightStatus": False, "highlightComparator": False, "format": meas,
                     "formatted": meas, "names": False}
    return json.dumps(out, separators=(",", ":"))


def resolve(visuals, no_custom, root):
    """Layout visuals for the build: a Deneb visual becomes the GUID-typed visual (with its spec), or its fallback.
    Each carries `_swapFrom`, the type it may replace on disk (switching between the two keeps the ID and folder)."""
    out, errors = [], []
    for v in visuals:
        if not is_deneb(v):
            out.append(v)
            continue
        fb = v.get("fallback")
        if not isinstance(fb, dict) or not fb.get("type"):
            errors.append(f"{v['id']}: a Deneb visual needs a `fallback` (a native or SVG visual: type, bindings, ...)")
            continue
        if is_deneb(fb):
            errors.append(f"{v['id']}: the fallback is a Deneb visual; it must be native or SVG")
            continue
        try:
            spec = load_spec(v, root)
        except DenebError as e:
            errors.append(f"{v['id']}: {e}")
            continue
        errors.extend(f"{v['id']}: Deneb spec: {e}" for e in spec_issues(spec)[0])
        own = title_issue(v)
        if own:
            errors.append(f"{v['id']}: {own}")
            continue
        if no_custom:
            w = {k: v[k] for k in KEEP if k in v}
            w.update({k: x for k, x in fb.items() if k != "container"})
            if isinstance(v.get("container"), dict) and isinstance(fb.get("container"), dict):
                base = {k: x for k, x in v["container"].items() if k not in OWN_TEXT}   # never the Deneb title
                w["container"] = {**base, **fb["container"]}
            elif "container" in fb:
                w["container"] = fb["container"]
            w["_swapFrom"] = TYPE
            out.append(w)
        else:
            out.append({**v, "type": TYPE, "_deneb": spec, "_swapFrom": fb["type"]})
    return out, errors
