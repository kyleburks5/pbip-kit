"""Pure PBIR JSON builders: literals, fields, object lists and the visual patterns proven in Reps 6 and 7.

Carried over from the kit's v0.2 design/scripts helpers (their pure-Python layer). Nothing here touches files.
Every builder writes the JSON shape Power BI Desktop saves, and every patch is idempotent: run twice, same result.
Field notation (layout.json): '[Measure]', 'Table[Column]', 'First(Table[Column])' / 'Min(Table[Column])'.
"""
import json, pathlib, re, uuid

# ---------------------------------------------------------------- PBIR literals and fields
def L(v):
    return {"expr": {"Literal": {"Value": v}}}


def s(text):             # string literal
    return L("'" + str(text).replace("'", "''") + "'")


def n(x):                # decimal literal; a whole number is written 0D, not 0.0D (as Desktop saves)
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return L(f"{x}D")


def i(x):                # integer literal
    return L(f"{int(x)}L")


def b(x):
    return L("true" if x else "false")


def lit(v):
    """Typed literal: bool -> true/false, int -> 2024L, float -> 1.5D, anything else -> quoted text."""
    if isinstance(v, bool):
        return b(v)
    if isinstance(v, int):
        return i(v)
    if isinstance(v, float):
        return n(v)
    return s(v)


def theme_colour(index, percent=0):
    """A theme colour as Desktop saves it. ColorId: 0 = the theme background, 1 = foreground, 2.. = dataColors[0..]
    (Desktop check 2026-10-18: ColorId 3 drew dataColors[1]). Percent -1..1 darkens..lightens."""
    percent = float(percent)
    return {"ThemeDataColor": {"ColorId": int(index), "Percent": int(percent) if percent.is_integer() else percent}}


def colour_expr(c):
    """Hex text or a theme_colour() -> the expression inside a colour property."""
    return c if isinstance(c, dict) and "ThemeDataColor" in c else s(c)["expr"]


def solid(c):
    """Fixed colour: '#hex' (a literal) or theme_colour(...) (ThemeDataColor)."""
    return {"solid": {"color": {"expr": colour_expr(c)}}}


def measure(name, table, schema=None):
    """Model measure, or a report extension measure (schema "extension", as Desktop saves it)."""
    src = {"Schema": schema, "Entity": table} if schema else {"Entity": table}
    return {"Measure": {"Expression": {"SourceRef": src}, "Property": name}}


def column(table, name):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def agg(table, name, fn=3):
    """Aggregation of a column (3 = Min / First), as Desktop saves 'First' on a text column."""
    return {"Aggregation": {"Expression": column(table, name), "Function": fn}}


def ex(field):
    return {"expr": field}


def solid_ex(field):
    """Colour from a measure (fx)."""
    return {"solid": {"color": {"expr": field}}}


def ref(text, measure_table):
    """Layout notation -> PBIR field. '[M]' -> measure in measure_table; a trailing '(note)' is dropped."""
    t = text.strip()
    if not re.match(r"^(First|Min)\(", t):
        t = re.sub(r"\s*\(.*\)\s*$", "", t)
    m = re.fullmatch(r"(First|Min)\(\s*'?([^'\[]+)'?\[([^\]]+)\]\s*\)", t)
    if m:
        return agg(m.group(2), m.group(3))
    m = re.fullmatch(r"'?([^'\[]*)'?\[([^\]]+)\]", t)
    if not m:
        raise ValueError(f"not a field: {text!r}")
    return column(m.group(1), m.group(2)) if m.group(1) else measure(m.group(2), measure_table)


def qref(field):
    """queryRef Desktop uses for a projection."""
    if "Measure" in field:
        return f"{field['Measure']['Expression']['SourceRef']['Entity']}.{field['Measure']['Property']}"
    if "Column" in field:
        return f"{field['Column']['Expression']['SourceRef']['Entity']}.{field['Column']['Property']}"
    if "Percentile" in field:                 # roadmap gap 9 (UNVERIFIED in Desktop)
        p = field["Percentile"]
        c = p["Expression"]["Column"]
        return f"Percentile({c['Expression']['SourceRef']['Entity']}.{c['Property']}, {p['K']:g})"
    c = field["Aggregation"]["Expression"]["Column"]
    fn = AGG_NAMES.get(field["Aggregation"].get("Function", 3), "Min")
    return f"{fn}({c['Expression']['SourceRef']['Entity']}.{c['Property']})"


# queryRef prefixes per aggregation function (semanticQuery QueryAggregateFunction). Sum and Min are seen in files
# Desktop saved; the others follow the same pattern and are unverified.
AGG_NAMES = {0: "Sum", 1: "Avg", 2: "DistinctCount", 3: "Min", 4: "Max", 5: "CountNonNull", 6: "Median",
             7: "StandardDeviation", 8: "Variance"}      # 6-8: roadmap gap 9, from the schema only
AGG_FUNCS = {"sum": 0, "avg": 1, "average": 1, "distinctcount": 2, "min": 3, "first": 3, "max": 4, "last": 4,
             "count": 5, "median": 6, "stdev": 7, "standarddeviation": 7, "var": 8, "variance": 8}


def native_ref(field):
    """nativeQueryRef as Desktop saves it: the field's own name (the column inside an aggregation), even when the
    projection has a displayName."""
    k = next(iter(field))
    if k in ("Aggregation", "Percentile"):
        return native_ref(field[k]["Expression"])
    return field[k]["Property"]


def font(family):
    """fontFamily literal in Desktop's quoted-list form."""
    return L(f"'''{family}'', helvetica, arial, sans-serif'")


# ---------------------------------------------------------------- object lists
def put(objs, key, props, selector=None):
    """Set props on the entry of objs[key] with exactly this selector (created if missing). Idempotent."""
    lst = objs.setdefault(key, [])
    for e in lst:
        if e.get("selector") == selector:
            e.setdefault("properties", {}).update(props)
            return e
    e = {"properties": dict(props)}
    if selector is not None:
        e["selector"] = selector
    lst.append(e)
    return e


def stable_id(*parts):
    """Stable reference-label id (same id on every run), as 'field-<uuid5>'."""
    return "field-" + str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join(str(p) for p in parts)))


# ---------------------------------------------------------------- container and query
def chrome_off(d, padding=0):
    """No container background, border, shadow, title or header: the panel shape or tile is the card."""
    vco = d["visual"].setdefault("visualContainerObjects", {})
    for k in ("background", "border", "dropShadow", "title", "subTitle", "visualHeader", "divider"):
        vco[k] = [{"properties": {"show": b(False)}}]
    vco["padding"] = [{"properties": {k: n(padding) for k in ("top", "bottom", "left", "right")}}]


def set_query(d, roles, sort=None, direction="Ascending"):
    """roles: {role: [(field, displayName or None)]} -> queryState in Desktop's shape. A displayName renames the field
    in this visual only (a model rename would change every visual)."""
    qs = {}
    for role, items in roles.items():
        projs = []
        for f, disp in items:
            p = {"field": f, "queryRef": qref(f), "nativeQueryRef": native_ref(f)}
            if disp:
                p["displayName"] = disp
            projs.append(p)
        qs[role] = {"projections": projs}
    d["visual"]["query"] = {"queryState": qs}
    if sort:
        d["visual"]["query"]["sortDefinition"] = {"sort": [{"field": sort, "direction": direction}],
                                                  "isDefaultSort": False}


# ---------------------------------------------------------------- shapes, text, images
def shape_objects(fill, outline=None, outline_width=1, transparency=0, radius=0):
    """Shape objects as Desktop saves them. Shapes ignore the theme fill, and fill colour, transparency and line
    colour only apply on selector {id: default} (show stays selector-less), or Desktop draws theme colour 1."""
    o = {"fill": [{"properties": {"show": b(True)}},
                  {"properties": {"fillColor": solid(fill), "transparency": n(transparency)},
                   "selector": {"id": "default"}}],
         "outline": [{"properties": {"show": b(bool(outline))}}],
         "shape": [{"properties": {"tileShape": s("rectangleRoundedByPixel" if radius else "rectangle"),
                                   "rectangleRoundedCurve": i(radius)}}],
         "rotation": [{"properties": {"shapeAngle": i(0)}}]}
    if outline:
        o["outline"].append({"properties": {"lineColor": solid(outline), "weight": n(outline_width),
                                            "transparency": n(0)}, "selector": {"id": "default"}})
    return o


def drop_shadow(color, blur, distance, angle=90, transparency=90):
    """Container drop shadow with preset Custom (without a preset Power BI applies its own angle and distance)."""
    return [{"properties": {"show": b(True), "color": solid(color), "position": s("Outer"), "preset": s("Custom"),
                            "shadowSpread": n(0), "shadowBlur": n(blur), "shadowDistance": n(distance),
                            "angle": n(angle), "transparency": n(transparency)}}]


def text_runs(runs, align=None):
    """runs: [(text, family, size_pt, hex)] -> one textbox paragraph."""
    para = {"textRuns": [{"value": t, "textStyle": {"fontFamily": fam, "fontSize": f"{size}pt", "color": col}}
                         for t, fam, size, col in runs]}
    if align:
        para["horizontalTextAlignment"] = align
    return {"general": [{"properties": {"paragraphs": [para]}}]}


def image_objects(item, scaling="Fit"):
    """Image visual bound to a registered resource (ResourcePackageItem). SVGs can't be registered: render a PNG at
    4x first (svg_to_png.py)."""
    return {"general": [{"properties": {"imageUrl": {"expr": {"ResourcePackageItem": {
                "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": item}}}}}],
            "imageScaling": [{"properties": {"imageScalingType": s(scaling)}}]}


# ---------------------------------------------------------------- new card (cardVisual)
def tile_style(o, fill, transparency, outline, radius, sel=None):
    """New card tile: fill at a transparency, 1px outline, rounded corners. The radius only renders with
    tileShape rectangleRoundedByPixel."""
    sel = sel or {"id": "default"}
    put(o, "fillCustom", {"show": b(True)})
    put(o, "fillCustom", {"fillColor": solid(fill), "transparency": n(transparency)}, sel)
    put(o, "outline", {"show": b(True), "lineColor": solid(outline), "weight": n(1)}, sel)
    put(o, "shapeCustomRectangle", {"tileShape": s("rectangleRoundedByPixel"), "rectangleRoundedCurve": i(radius)},
        sel)


def card_layers_off(o):
    """Every background layer of a new card off (a text measure on a coloured base shows a white box otherwise)."""
    put(o, "fillCustom", {"show": b(False)})
    put(o, "fillCustom", {"transparency": n(100)}, {"id": "default"})
    put(o, "outline", {"show": b(False)}, {"id": "default"})
    put(o, "cardCalloutArea", {"backgroundTransparency": n(100)}, {"id": "default"})
    put(o, "layout", {"backgroundShow": b(False), "backgroundTransparency": n(100)})
    put(o, "divider", {"show": b(False)}, {"id": "default"})
    put(o, "shadowCustom", {"show": b(False)}, {"id": "default"})
    put(o, "glowCustom", {"show": b(False)}, {"id": "default"})
    put(o, "accentBar", {"show": b(False)}, {"id": "default"})


def ref_labels(o, key, tile_ref, labels, fonts=None, colors=None, title_size=None, value_size=None, blanks=None,
               layout="sentence", title_off=False, detail_size="value", backgrounds=None, display_units=1):
    """Several reference labels on one card value, in the JSON shape Desktop saves, with stable ids and order. A label
    without a detail gets detail show:false, or Desktop draws "--". Every setting sits on the label's id'd selector
    (metadata-only entries are ignored once an id'd one exists, CLAUDE.md).
    labels: [(title, value_field, detail_field or None, detail_colour_field or None)]
    fonts: {"regular": family, "semibold": family}; colors: {"title": hex, "value": hex}; a None font, colour or
    size is left to the theme; detail_size "value" (the default) uses value_size. title_off: no title (the title still seeds the stable id). backgrounds: {title: field}
    for the detail background colour from a measure.
    layout: "sentence" (centred, below the value) - "tabular" clips in narrow tiles (Rep 7); None writes no layout."""
    fonts, colors = fonts or {}, colors or {}
    for k in ("referenceLabel", "referenceLabelTitle", "referenceLabelValue", "referenceLabelDetail"):
        o[k] = [e for e in o.get(k, []) if e.get("selector", {}).get("metadata") != tile_ref]
    for order, (title, val, det, col) in enumerate(labels):
        rid = stable_id(key, tile_ref, title)
        base = {"metadata": tile_ref, "id": rid}
        data = {**base, "data": [{"dataViewWildcard": {"matchingOption": 0}}]}
        o["referenceLabel"].append({"properties": {"value": ex(val)}, "selector": {**data, "order": order}})
        if title_off:
            o["referenceLabelTitle"].append({"properties": {"show": b(False)}, "selector": base})
        else:
            o["referenceLabelTitle"].append({"properties": {
                "show": b(True), "titleContentType": s("custom"), "titleText": s(title),
                **({"titleFontFamily": font(fonts["regular"])} if fonts.get("regular") else {}),
                **({"titleFontSize": n(title_size)} if title_size is not None else {}),
                **({"titleFontColor": solid(colors["title"])} if colors.get("title") else {})}, "selector": base})
        o["referenceLabelValue"].append({"properties": {
            "show": b(True),
            **({"valueFontFamily": font(fonts["semibold"])} if fonts.get("semibold") else {}),
            **({"valueFontSize": n(value_size)} if value_size is not None else {}),
            **({"valueFontColor": solid(colors["value"])} if colors.get("value") else {}),
            **({"valueDisplayUnits": n(display_units)} if display_units is not None else {}),
            **({"showBlankAs": s(blanks[title])} if title in (blanks or {}) else {})}, "selector": base})
        if det:
            dsize = value_size if detail_size == "value" else detail_size
            bg = (backgrounds or {}).get(title)
            o["referenceLabelDetail"].append({"properties": {
                "show": b(True), "detailValue": ex(det), **({"detailFontColor": solid_ex(col)} if col else {}),
                **({"detailFontFamily": font(fonts["semibold"])} if fonts.get("semibold") else {}),
                **({"detailFontSize": n(dsize)} if dsize is not None else {}),
                **({"detailBackgroundColor": solid_ex(bg)} if bg else {})}, "selector": data})
        else:
            o["referenceLabelDetail"].append({"properties": {"show": b(False)}, "selector": base})
    if layout == "sentence":
        put(o, "referenceLabelLayout", {"position": s("below"), "style": s("sentence"), "arrangement": s("rows"),
                                        "horizontalAlignment": s("center"), "verticalAlignment": s("top"),
                                        "valueArea": n(0)}, {"id": "default"})


def small_multiples_grid(o, rows, columns, max_sm, gap, cell_fill=None, cell_transparency=None, cell_outline=None,
                         radius=None):
    """New card small multiples as a grid of separate tiles: orientation 0 = Grid (2 = one row, 1 = vertical) and
    style "Cards" (one tile per cell; "Table" shares one grid). Only then do rowCount / columnCount apply.
    Optional glass on each cell (audit_layout.py checks cell-level glass)."""
    put(o, "smallMultiplesLayout", {"orientation": n(0), "style": s("Cards"), "maxSmallMultiples": i(max_sm),
                                    "rowCount": i(rows), "columnCount": i(columns), "autoGrid": b(False),
                                    "fixNumberOfTiles": b(False), "customizePadding": b(True),
                                    "cellPadding": i(gap), "rowPadding": i(gap), "columnPadding": i(gap),
                                    "headerPosition": s("Top")})
    put(o, "smallMultiplesGrid", {"gridlineShow": b(False)})
    if cell_fill:
        put(o, "smallMultiplesCellBackGround", {"backgroundShow": b(True), "backgroundFillColor": solid(cell_fill),
                                                "backgroundTransparency": n(cell_transparency)}, {"id": "default"})
    if cell_outline:
        put(o, "smallMultiplesBorder", {"gridlineShow": b(True), "gridlineColor": solid(cell_outline),
                                        "gridlineWidth": n(1), "gridlineTransparency": n(0),
                                        "gridlineStyle": s("solid")}, {"id": "default"})
    if radius is not None:
        put(o, "smallMultiplesOuterShape", {"rectangleRoundedCurve": i(radius),
                                            "rectangleRoundedCurveCustomStyle": b(False)}, {"id": "default"})
    o["smallMultiplesAccentBar"] = [{"properties": {"show": b(False)}}]


def small_multiples_header_colour(o, colour_measure):
    """Colour each small multiple by a measure on its header (smallMultiplesAccentBar by measure doesn't render)."""
    put(o, "smallMultiplesHeader", {"backgroundShow": b(True)}, {"id": "default"})
    put(o, "smallMultiplesHeader", {"backgroundColor": solid_ex(colour_measure)}, {"data": [{"roles": ["Rows"]}]})


# ---------------------------------------------------------------- charts
def label_above_bars(d, spacer_ref, category_table, category_col, label_family, label_size, label_colour,
                     value_family, value_size, value_colour):
    """Bar chart with each category label above its bar (Rep 6, CLAUDE.md). Bind Y = the category (axis values and
    title off) and X = a zero measure (`_ Blank = 0`) first, then the real measure. This writes the labels: the zero
    series shows only the category as detail (per-data-point entry, the only form that rendered), the real series keeps
    its value at the bar end. spacer_ref = queryRef of the zero measure."""
    y = d["visual"]["query"]["queryState"]["Y"]
    y["projections"].sort(key=lambda pr: 0 if pr.get("queryRef") == spacer_ref else 1)
    for pr in y["projections"]:
        if pr.get("queryRef") == spacer_ref:
            pr["displayName"] = "Category"           # the tooltip reads "Category 0", not "_ Blank 0"
    d["visual"].setdefault("objects", {})["labels"] = [
        {"properties": {"show": b(True), "color": solid(value_colour), "fontSize": n(value_size),
                        "fontFamily": s(value_family), "labelPosition": s("OutsideEnd"),
                        "labelDisplayUnits": n(1), "labelPrecision": n(0), "enableBackground": b(False)}},
        {"properties": {"showSeries": b(True), "labelPosition": s("OutsideEnd"), "labelOverflow": b(True),
                        "horizontalAlignment": s("left"), "enableTitleDataLabel": b(False),
                        "enableValueDataLabel": b(False), "enableDetailDataLabel": b(True),
                        "detailColor": solid(label_colour), "detailFontSize": n(label_size),
                        "detailFontFamily": s(label_family)},
         "selector": {"metadata": spacer_ref}},
        {"properties": {"dynamicLabelDetail": ex(agg(category_table, category_col))},
         "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": spacer_ref,
                      "highlightMatching": 1}},
    ]


def scatter_columns(d, x, y, series=None):
    """Scatter X/Y on unsummarized columns, as Desktop saves them. x, y: (table, column)."""
    roles = {}
    if series:
        roles["Series"] = [(series, None)]
    roles["X"] = [(column(*x), None)]
    roles["Y"] = [(column(*y), None)]
    set_query(d, roles)
    for r, (t, c) in (("X", x), ("Y", y)):
        p = d["visual"]["query"]["queryState"][r]["projections"][0]
        p["queryRef"] = f"Sum({t}.{c})"
        p["nativeQueryRef"] = c


def navigator_states(o, fill, outline, radius, text_family, text_size, colours, transparency):
    """Page / bookmark navigator states: ids are default / hover / selected (not the
    button slicer's selection:selected).
    colours: {"default": hex, "hover": hex, "selected": hex} text; transparency: {state: 0-100} of the fill."""
    put(o, "fill", {"show": b(True)})
    put(o, "outline", {"show": b(True)})
    for sid in ("default", "hover", "selected"):
        put(o, "fill", {"fillColor": solid(fill), "transparency": n(transparency[sid])}, {"id": sid})
        line = outline if sid == "selected" else None
        put(o, "outline", {"lineColor": solid(line or fill), "weight": n(1 if line else 0),
                           "transparency": n(0 if line else 100)}, {"id": sid})
        put(o, "text", {"fontColor": solid(colours[sid])}, {"id": sid})
    put(o, "text", {"fontFamily": font(text_family), "fontSize": n(text_size)}, {"id": "default"})
    put(o, "shape", {"tileShape": s("rectangleRoundedByPixel"), "rectangleRoundedCurve": i(radius)}, {"id": "default"})


def button_slicer_padding(o, top=0, bottom=0, left=12, right=8):
    """Button slicers under ~40px: padding Custom with 0 top/bottom, or the button text disappears."""
    put(o, "padding", {"paddingSelection": s("Custom"), "topMargin": i(top), "bottomMargin": i(bottom),
                       "leftMargin": i(left), "rightMargin": i(right)}, {"id": "default"})



# ---------------------------------------------------------------- files
def load(f):
    return json.loads(pathlib.Path(f).read_text(encoding="utf-8"))


def dumps(d):
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


def save(f, d):
    """Write JSON as Desktop does (2-space indent, UTF-8). Returns True if the file changed."""
    f = pathlib.Path(f)
    text = dumps(d)
    if f.exists() and f.read_text(encoding="utf-8") == text:
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return True
