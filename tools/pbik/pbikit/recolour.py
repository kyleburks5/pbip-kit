"""Template colours to the current palette (pbik build, when tokens.json has theme.recolourTemplates).

The templates were drawn in one palette (design/templates/palette.json lists its colours). Each literal colour in a
template visual is looked up there by where it sits (text, line, shadow or fill) and replaced with the tokens.json
colour of that name, so a theme made by gen_tokens.py reaches what the templates bake in. A colour the palette doesn't
list, or a name the tokens don't have, stays as it is. Only new visuals (and --reset) start from a template: a theme
change on visuals already built reaches them through layout props and the theme, or a --reset.
"""
import json, pathlib, re

TEXT = re.compile(r"(font|label|title|value|detail|text)color$|^color$", re.I)
LINE = re.compile(r"(line|outline|border|gridline|stroke)color$|^lineColor$", re.I)
LIT = re.compile(r"'(#[0-9A-Fa-f]{6})'")
# objects whose plain `color` is a fill, never text (walkthrough fix 2: the container background's `color` matched the
# text rule, so a white card background became the "text on dark" colour, near-black on a light theme)
FILL_OBJECTS = {"background", "fill", "fillCustom", "dataPoint", "plotArea", "visualHeader", "visualTooltip",
                "values", "rowHeaders", "columnHeaders", "total", "subTotals", "grid", "shape", "pill", "accentBar",
                "spacing"}


def load_palette(templates):
    f = pathlib.Path(templates) / "palette.json"
    if not f.exists():
        return {}
    return {k.upper(): v for k, v in json.loads(f.read_text(encoding="utf-8")).get("colors", {}).items()}


def category(obj, prop):
    if obj == "dropShadow" or prop.lower().startswith("shadow"):
        return "shadow"
    if obj in ("border", "outline") or LINE.search(prop):
        return "line"
    pl = prop.lower()
    if obj in FILL_OBJECTS and (pl in ("color", "fill", "fillcolor") or "back" in pl):
        return "fill"
    if obj in ("labels", "legend", "categoryAxis", "valueAxis", "title", "subTitle", "header", "items",
               "columnHeaders", "rowHeaders") and prop.lower().endswith("color") and "back" not in prop.lower() \
            and "grid" not in prop.lower():
        return "text"
    if (TEXT.search(prop) or "fontcolor" in pl) and "back" not in pl and "fill" not in pl:
        return "text"
    return "fill"


def apply(d, palette, colour):
    """Recolour the visual dict d in place. colour(name) -> hex (raises for an unknown name). Returns
    [(object.property, old, new)]."""
    changed = []
    vis = d.get("visual", {})

    def walk(node, obj, prop):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "Value" and isinstance(v, str):
                    m = LIT.fullmatch(v)
                    if m:
                        old = m.group(1).upper()
                        name = (palette.get(old) or {}).get(category(obj, prop))
                        if name:
                            try:
                                new = colour(name)
                            except Exception:
                                new = None
                            if isinstance(new, str) and new.upper() != old:
                                node[k] = f"'{new.upper()}'"
                                changed.append((f"{obj}.{prop}", old, new.upper()))
                else:
                    walk(v, obj, prop)
        elif isinstance(node, list):
            for v in node:
                walk(v, obj, prop)

    for where in ("objects", "visualContainerObjects"):
        for obj, entries in (vis.get(where) or {}).items():
            for e in entries if isinstance(entries, list) else []:
                for prop, v in (e.get("properties") or {}).items():
                    walk(v, obj, prop)
    return changed
