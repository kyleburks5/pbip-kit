"""Field references inside PBIR objects, checked against a model: used when a template (or a visual copied from another
report) carries formatting bound to fields the target model doesn't have.

A field is (kind, entity, property, schema): kind Measure or Column; schema "extension" for report extension measures.
Selectors name fields as metadata strings ('_Measures.Headcount', 'Sum(DataTable.Salary)').
"""
import re

META = re.compile(r"^(?:[A-Za-z]+\()?(.+?)\.(.+?)\)?$")


def field_ok(model, ext, kind, ent, prop, schema=None):
    if schema == "extension":
        return (ent, prop) in (ext or {})
    if model is None:
        return True                                  # nothing to check against
    if ent not in model.tables:
        return False
    if kind == "Measure":
        return prop in model.tables[ent].measures or model.has_field(ent, prop)
    return model.has_field(ent, prop)


def refs_in(node):
    """(kind, entity, property, schema) of every field reference under node (SourceRef by Entity)."""
    if isinstance(node, dict):
        for kind in ("Measure", "Column"):
            x = node.get(kind)
            if isinstance(x, dict) and "Property" in x:
                sr = x.get("Expression", {}).get("SourceRef", {})
                if "Entity" in sr:
                    yield kind, sr["Entity"], x["Property"], sr.get("Schema")
        for v in node.values():
            yield from refs_in(v)
    elif isinstance(node, list):
        for v in node:
            yield from refs_in(v)


def meta_ok(model, ext, text):
    m = META.match(text or "")
    return bool(m) and field_ok(model, ext, "Measure", m.group(1), m.group(2))


def clean_objects(objs, model, ext, dropped, where):
    """Drop entries whose selector names a missing field and properties bound to a missing field, in place.
    An entry Desktop saved with no properties stays; one emptied here goes."""
    for key in list(objs):
        keep = []
        for e in objs[key]:
            sel = e.get("selector") or {}
            if isinstance(sel.get("metadata"), str) and not meta_ok(model, ext, sel["metadata"]):
                dropped.append(f"{where}.{key}@{sel['metadata']}")
                continue
            if any(not field_ok(model, ext, *r) for r in refs_in(sel)):
                dropped.append(f"{where}.{key}@selector")
                continue
            props = e.get("properties", {})
            had = bool(props)
            for prop in list(props):
                if any(not field_ok(model, ext, *r) for r in refs_in(props[prop])):
                    dropped.append(f"{where}.{key}.{prop}")
                    del props[prop]
            if props or not had:
                keep.append(e)
        if keep:
            objs[key] = keep
        else:
            del objs[key]


def clean_visual(d, model, ext):
    """Objects, container objects and filters of a visual.json, against the model. Returns what was dropped."""
    dropped = []
    vis = d.get("visual", {})
    for where in ("objects", "visualContainerObjects"):
        if where in vis:
            clean_objects(vis[where], model, ext, dropped, where)
    fc = d.get("filterConfig", {}).get("filters")
    if fc:
        keep = [f for f in fc if all(field_ok(model, ext, *r) for r in refs_in(f))]
        if len(keep) < len(fc):
            dropped.append(f"{len(fc) - len(keep)} filter(s)")
            d["filterConfig"]["filters"] = keep
            if not keep:
                d["filterConfig"].pop("filters")
                if not d["filterConfig"]:
                    d.pop("filterConfig")
    return dropped


# content a template must not carry into a new visual: the layout sets it (text, title, bindings, images, actions)
CONTENT = {("visualContainerObjects", "title", "text"), ("visualContainerObjects", "subTitle", "text"),
           ("objects", "general", "paragraphs"), ("objects", "general", "imageUrl"), ("objects", "general", "filter"),
           ("objects", "text", "text"), ("objects", "header", "text")}
CONTENT_OBJECTS = {("visualContainerObjects", "visualLink")}
# a reference line bound to a field goes whole: without its value it draws at 0 under the template's old label
# ("Company: 0" over a top-5 chart, Rep 9); layout.json `referenceLines` writes the report's own
WHOLE_ENTRY = {"xAxisReferenceLine", "y1AxisReferenceLine", "y2AxisReferenceLine"}


def _drop(objs, where, keep_entry, keep_prop):
    for key in list(objs):
        if (where, key) in CONTENT_OBJECTS:
            del objs[key]
            continue
        kept = []
        for e in objs[key]:
            if not keep_entry(e.get("selector") or {}):
                continue
            props = e.get("properties", {})
            if key in WHOLE_ENTRY and not all(keep_prop(v) for v in props.values()):
                continue
            had = bool(props)
            for prop in list(props):
                if (where, key, prop) in CONTENT or not keep_prop(props[prop]):
                    del props[prop]
            if props or not had:
                kept.append(e)
        if kept:
            objs[key] = kept
        else:
            del objs[key]


def formatting_only(d, model, ext):
    """A visual.json from a template, before pbik applies the layout: keep its formatting, drop its content.
    Dropped: every property or entry bound to a field (a measure colour, a series colour on a metadata selector,
    reference labels, a slicer's default selection; the layout's bindings, cf, props and referenceLabels set those),
    a whole reference line whose value or any setting is bound to a field (layout `referenceLines` sets them),
    the literal content (title / subtitle text, text box paragraphs, button and slicer header text, an image's
    registered file, the button action). Template filters stay when this model has their fields (README).
    Returns the template filters dropped because their fields are missing."""
    vis = d.get("visual", {})
    no_fields = lambda node: not any(True for _ in refs_in(node))                      # noqa: E731
    keep_entry = lambda sel: not isinstance(sel.get("metadata"), str) and no_fields(sel)   # noqa: E731
    for where in ("objects", "visualContainerObjects"):
        if where in vis:
            _drop(vis[where], where, keep_entry, no_fields)
            if not vis[where]:
                del vis[where]
    dropped = []
    fc = d.get("filterConfig", {}).get("filters")
    if fc:
        keep = [f for f in fc if all(field_ok(model, ext, *r) for r in refs_in(f))]
        if len(keep) < len(fc):
            dropped.append(f"{len(fc) - len(keep)} filter(s)")
            d["filterConfig"]["filters"] = keep
            if not keep:
                d["filterConfig"].pop("filters")
                if not d["filterConfig"]:
                    d.pop("filterConfig")
    return dropped
