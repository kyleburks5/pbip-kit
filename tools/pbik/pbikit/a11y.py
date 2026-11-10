"""Accessibility checks for pbik validate (warnings; CLAUDE.md "Accessibility").

- alt text: every data visual (a visual with field bindings, except slicers) and every image has
  visualContainerObjects.general.altText (text or a measure);
- contrast (WCAG 2.1 AA): literal text colours against what is behind the text: the visual's own container background
  when shown and mostly opaque, else the topmost opaque shape or visual background under it (lower z, covering its
  centre), else the page background. 4.5:1, or 3:1 for large text (18pt and up, or 14pt and up in a bold or semibold
  font). Colours from measures or theme indices are not checked;
- font size: no text below the minimum (tokens `a11y.minFontPt`, default 10pt, the kit's caption size);
- tab order: the tab order of the visible, non-decorative visuals on a page follows reading order (top to bottom in
  rows, left to right in a row). Shapes, hidden visuals, visuals in hidden groups and visuals marked `decorative` in
  layout.json are skipped;
- decorative (roadmap gap 21): a shape or image with no alt text that layout.json doesn't mark `decorative: true`
  (Microsoft Learn, "Design Power BI reports for accessibility", updated 2026-09-29: decorative shapes and images are
  hidden from the tab order; the rest need alt text). One warning per page. The PBIR form of "hidden from tab order"
  isn't in Microsoft's schema (visualContainer 2.13.0 #VisualContainerPosition `tabOrder` is a number with no hidden
  value), so pbik doesn't write it yet: validate prints a note listing the decorative visuals to hide in Desktop;
- Learn's checklist (roadmap gap 22): alt text longer than 250 characters (Power BI's limit); a text box whose text
  isn't in its alt text (a screen reader reads the alt text); data visuals with no sort order of their own
  (query.sortDefinition: the accessible Show data table follows the visual's sort), one warning per page.
"""
import re

SLICERS = {"slicer", "advancedSlicerVisual", "listSlicer", "textSlicer"}
DECOR = {"shape", "basicShape"}
STATEFUL = {"actionButton", "pageNavigator", "bookmarkNavigator", "advancedSlicerVisual"}   # text on per-state fills
TEXT_PROPS = re.compile(r"(fontcolor|labelcolor|titlecolor|valuecolor|detailcolor|color)$", re.I)
SIZE_PROPS = re.compile(r"(fontsize|textsize|labelfontsize)$", re.I)
ALT_MAX = 250                    # Learn: alt text is limited to 250 characters
NO_SORT = {"card", "cardVisual", "multiRowCard", "kpi", "gauge", "image", "textbox", "shape", "basicShape",
           "actionButton", "pageNavigator", "bookmarkNavigator"} | SLICERS     # one value, or no data: no order
MIN_OPAQUE = 50                  # transparency below this counts as a solid background


def _lit(v):
    if isinstance(v, dict):
        e = v.get("expr", v)
        if isinstance(e, dict) and "Literal" in e:
            return e["Literal"].get("Value")
    return None


def _hex(v):
    """'#RRGGBB' from a solid colour property or a text run colour; None for measures / theme colours."""
    if isinstance(v, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
        return v.upper()
    if isinstance(v, dict) and "solid" in v:
        x = _lit(v["solid"].get("color", {}))
        if isinstance(x, str) and re.fullmatch(r"'#[0-9A-Fa-f]{6}'", x):
            return x[1:-1].upper()
    return None


def _num(v):
    x = _lit(v)
    if isinstance(x, str):
        m = re.fullmatch(r"(-?[\d.]+)[DLM]?", x)
        return float(m.group(1)) if m else None
    return None


def luminance(hexc):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _entries(vis, where):
    for key, lst in (vis.get(where) or {}).items():
        for e in lst if isinstance(lst, list) else []:
            yield key, e.get("selector"), e.get("properties", {})


def own_background(d):
    """The visual's own opaque fill: container background, or a shape's fill on {id: default}."""
    vis = d.get("visual", {})
    for key, sel, props in _entries(vis, "visualContainerObjects"):
        if key == "background" and sel is None and _lit(props.get("show")) == "true":
            c, t = _hex(props.get("color")), _num(props.get("transparency")) or 0
            if c and t < MIN_OPAQUE:
                return c
    if vis.get("visualType") in DECOR:
        show = next((_lit(p.get("show")) for k, s, p in _entries(vis, "objects") if k == "fill" and "show" in p), "true")
        for key, sel, props in _entries(vis, "objects"):
            if key == "fill" and sel in (None, {"id": "default"}) and "fillColor" in props and show != "false":
                c, t = _hex(props.get("fillColor")), _num(props.get("transparency")) or 0
                if c and t < MIN_OPAQUE:
                    return c
    return None


def state_fills(d):
    """{selector json: hex} of opaque per-state fills (fill / fillCustom) on buttons, navigators and button slicers."""
    import json as _json
    vis = d.get("visual", {})
    if vis.get("visualType") not in STATEFUL:
        return {}
    out = {}
    for key, sel, props in _entries(vis, "objects"):
        if key in ("fill", "fillCustom") and ("fillColor" in props or "color" in props):
            c = _hex(props.get("fillColor", props.get("color")))
            t = _num(props.get("transparency")) or 0
            if c and t < MIN_OPAQUE:
                out[_json.dumps(sel, sort_keys=True)] = c
            elif c:
                out[_json.dumps(sel, sort_keys=True)] = None          # see-through in this state
    return out


def texts(d):
    """(where, colour, size pt or None, bold, selector) for each literal text colour in a visual."""
    vis = d.get("visual", {})
    for where in ("objects", "visualContainerObjects"):
        for key, sel, props in _entries(vis, where):
            if key in ("background", "fill", "outline", "border", "dropShadow", "dataPoint", "shape", "glow",
                       "accentBar", "divider", "fillCustom", "shadowCustom", "glowCustom", "cardCalloutArea"):
                continue
            if _lit(props.get("show")) == "false":
                continue
            size = next((_num(v) for p, v in props.items() if SIZE_PROPS.search(p)), None)
            fam = next((str(_lit(v)) for p, v in props.items() if p.lower() == "fontfamily"), "")
            bold = bool(re.search(r"bold|semibold", fam, re.I)) or _lit(props.get("bold")) == "true"
            for p, v in props.items():
                if TEXT_PROPS.search(p) and not re.search(r"(back|background|line|fill)", p, re.I):
                    c = _hex(v)
                    if c:
                        yield f"{key}.{p}", c, size, bold, sel
    for e in (vis.get("objects", {}).get("general") or []):
        for para in e.get("properties", {}).get("paragraphs", []) or []:
            for run in para.get("textRuns", []):
                st = run.get("textStyle", {})
                c = _hex(st.get("color"))
                size = st.get("fontSize")
                size = float(size[:-2]) if isinstance(size, str) and size.endswith("pt") else None
                bold = bool(re.search(r"bold|semibold", st.get("fontFamily", ""), re.I)) or st.get("fontWeight") == "bold"
                if c:
                    yield "text box run", c, size, bold, None


def sizes(d):
    vis = d.get("visual", {})
    for where in ("objects", "visualContainerObjects"):
        for key, sel, props in _entries(vis, where):
            if _lit(props.get("show")) == "false":
                continue
            for p, v in props.items():
                if SIZE_PROPS.search(p):
                    x = _num(v)
                    if x is not None:
                        yield f"{key}.{p}", x
    for e in (vis.get("objects", {}).get("general") or []):
        for para in e.get("properties", {}).get("paragraphs", []) or []:
            for run in para.get("textRuns", []):
                s = run.get("textStyle", {}).get("fontSize")
                if isinstance(s, str) and s.endswith("pt"):
                    yield "text box run", float(s[:-2])


def boxes(visuals):
    """{name: (x, y, w, h, z, hidden)} on the page, group members made absolute; hidden includes hidden groups."""
    by = {d.get("name"): d for d, _ in visuals}
    out = {}

    def box(name, seen=()):
        if name in out:
            return out[name]
        d = by[name]
        p = d.get("position", {})
        x, y = p.get("x", 0), p.get("y", 0)
        hidden = bool(d.get("isHidden"))
        par = d.get("parentGroupName")
        if par in by and par not in seen:
            gx, gy, _, _, _, gh = box(par, seen + (name,))
            x, y, hidden = x + gx, y + gy, hidden or gh
        out[name] = (x, y, p.get("width", 0), p.get("height", 0), p.get("z", 0), hidden)
        return out[name]
    for n in by:
        box(n)
    return out


def reading_order(items):
    """items: [(name, x, y, w, h)] -> names in reading order: rows top to bottom (a visual joins the row while its
    top is above the middle of the row's shortest visual), left to right in a row."""
    rows = []
    for it in sorted(items, key=lambda t: (t[2], t[1])):
        if rows:
            top = min(r[2] for r in rows[-1])
            low = min(r[4] for r in rows[-1])
            if it[2] < top + low / 2:
                rows[-1].append(it)
                continue
        rows.append([it])
    return [it[0] for row in rows for it in sorted(row, key=lambda t: t[1])]


def check(fd, pages, rep, page_bg_of, min_pt=10, decorative=None):
    """decorative: visual names layout.json marks `decorative: true` (None: no layout given, so every shape or image
    without alt text is listed)."""
    decorative = set(decorative or ())
    to_hide = []
    for _, pd, pfolder in pages:
        page = pd.get("displayName")
        vs = rep.visuals(pfolder)
        bx = boxes(vs)
        bg_page = page_bg_of(pd) or "#FFFFFF"
        tab = []
        undeclared = []
        unsorted = []
        for d, f in vs:
            vis = d.get("visual")
            name = d.get("name", f.parent.name)
            if not vis:
                continue
            vt = vis.get("visualType")
            where = f"{page}/{f.parent.name}"
            x, y, w, h, z, hidden = bx[name]
            # alt text
            bound = bool((vis.get("query") or {}).get("queryState"))
            alt = next((p.get("altText") for k, s, p in _entries(vis, "visualContainerObjects")
                        if k == "general" and p.get("altText")), None)
            no_alt = alt is None or _lit(alt) in ("''", "' '")
            lit_alt = _lit(alt) if alt is not None else None
            if isinstance(lit_alt, str) and len(lit_alt) - 2 > ALT_MAX:
                fd.warn(where, f"a11y: alt text is {len(lit_alt) - 2} characters; Power BI keeps {ALT_MAX} (Microsoft "
                               "Learn): shorten it")
            if vt == "textbox" and name not in decorative:
                words = " ".join(r.get("value", "") for e in (vis.get("objects", {}).get("general") or [])
                                 for para in e.get("properties", {}).get("paragraphs", []) or []
                                 for r in para.get("textRuns", []))
                norm = lambda x: re.sub(r"\s+", " ", x or "").strip().lower()     # noqa: E731
                if norm(words) and norm(words) not in norm(lit_alt.strip("'").replace("''", "'") if
                                                           isinstance(lit_alt, str) else ""):
                    fd.warn(where, "a11y: text box text isn't in its alt text (container.altText): screen readers "
                                   "read the alt text, so repeat the text there (Microsoft Learn checklist, Textbox)")
            if bound and vt not in NO_SORT and not hidden and not (vis.get("query") or {}).get("sortDefinition"):
                unsorted.append(f.parent.name)
            if name in decorative:
                if not hidden:
                    to_hide.append(f"{page}/{f.parent.name}")
            elif (bound and vt not in SLICERS) or vt == "image" and not bound:
                if no_alt:
                    fd.warn(where, "a11y: no alt text (container.altText)" +
                            ("; or mark it `decorative: true` in layout.json if it only decorates" if vt == "image" else ""))
            elif vt in DECOR and no_alt and not hidden:
                undeclared.append(f.parent.name)
            # font size
            for prop, pt in sizes(d):
                if pt < min_pt:
                    fd.warn(where, f"a11y: {prop} is {pt:g}pt, below the {min_pt:g}pt minimum")
            # contrast
            behind = own_background(d)
            if behind is None:
                cx, cy = x + w / 2, y + h / 2
                under = [(bz, n) for n, (bx_, by_, bw, bh, bz, bhid) in bx.items()
                         if n != name and not bhid and bz < z and bx_ <= cx <= bx_ + bw and by_ <= cy <= by_ + bh]
                for _, n in sorted(under, reverse=True):
                    dd = next(dd for dd, _ in vs if dd.get("name") == n)
                    behind = own_background(dd)
                    if behind:
                        break
            behind = behind or bg_page
            fills = state_fills(d)
            default_fill = fills.get('{"id": "default"}')
            import json as _json
            for prop, colour, pt, bold, sel in texts(d):
                sk = _json.dumps(sel, sort_keys=True)
                bg = fills[sk] if sk in fills else default_fill
                bg = bg or behind
                need = 3.0 if pt and (pt >= 18 or (pt >= 14 and bold)) else 4.5
                ratio = contrast(colour, bg)
                if ratio + 1e-9 < need:
                    state = (f" ({sel['id']} state)" if isinstance(sel, dict) and set(sel) == {"id"} and
                             sel["id"] in ("default", "hover", "selected", "disabled", "press", "selection:selected")
                             else "")
                    fd.warn(where, f"a11y: {prop}{state} {colour} on {bg} is {ratio:.2f}:1, below {need:g}:1 (WCAG AA)")
            if not hidden and vt not in DECOR and name not in decorative and "tabOrder" in d.get("position", {}):
                tab.append((name, x, y, w, h, d["position"]["tabOrder"]))
        if undeclared:
            fd.warn(f"{page}", f"a11y: {len(undeclared)} shape(s) with no alt text and not marked `decorative: true` "
                               f"in layout.json ({', '.join(undeclared[:6])}{' ...' if len(undeclared) > 6 else ''}): "
                               "give each alt text, or mark it decorative (Microsoft Learn: decorative shapes and images "
                               "are hidden from the tab order)")
        if unsorted:
            fd.warn(f"{page}", f"a11y: {len(unsorted)} data visual(s) without a sort order of their own "
                               f"({', '.join(unsorted[:6])}{' ...' if len(unsorted) > 6 else ''}): the accessible "
                               "Show data table follows the visual's sort, so set `sort` in layout.json (Microsoft "
                               "Learn checklist, Sort order)")
        want = reading_order([t[:5] for t in tab])
        got = [t[0] for t in sorted(tab, key=lambda t: t[5])]
        if want != got:
            k = next(i for i, (a, b) in enumerate(zip(want, got)) if a != b)
            fd.warn(f"{page}", f"a11y: tab order doesn't follow reading order: tab stop {k + 1} is {got[k]}, "
                               f"reading order expects {want[k]}")
    if to_hide:
        print(f"note    {len(to_hide)} decorative visual(s) still have a tab stop: pbik can't write \"hidden from tab "
              f"order\" yet (its PBIR form isn't in Microsoft's schema; roadmap gap 21). In Desktop: View > Selection, "
              f"Tab order, hide {', '.join(to_hide[:6])}{' ...' if len(to_hide) > 6 else ''}")


SELECTED_STATES = ("selection:selected", "selected", "press")
TEXT_OBJECTS = ("value", "text", "label")


def selected_text(selected, on_selected=None, dark="#12343B"):
    """Text colour for a tile filled with `selected`: tokens colors.onSelected when set, otherwise white or the dark
    primary, whichever has the higher contrast."""
    if on_selected:
        return on_selected.upper()
    return max(("#FFFFFF", dark.upper()), key=lambda c: contrast(c, selected))


TEXT_FOR = {"advancedSlicerVisual": "value", "actionButton": "text", "pageNavigator": "text", "bookmarkNavigator": "text"}


def apply_selected_fill(d, selected, on_selected=None, dark="#12343B"):
    """A template's selected-state tiles (button slicers, buttons, page and bookmark navigators): every selected-state
    fill becomes `selected` (tokens colors.selected), for one selected colour across the report, and an outline in the
    old fill colour follows it. The state's text colour becomes selected_text() (colors.onSelected, or white or the
    dark primary, whichever contrasts more). The contrast check stays: text that still fails WCAG AA is reported.
    Layout props are applied afterwards and win. Returns ([(state, old fill, new fill, text)], [warning text])."""
    import json as _json
    selected = str(selected).upper() if str(selected).startswith("#") else _hex(selected)
    vis = d.get("visual", {})
    objs = vis.get("objects") or {}
    if not selected or vis.get("visualType") not in STATEFUL:
        return [], []

    def entry(key, sel):
        return next((e for e in objs.get(key, []) if e.get("selector") == sel), None)

    def solid_lit(c):
        return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{c}'"}}}}}

    text = selected_text(selected, on_selected, dark)
    changed, warnings = [], []
    for state in SELECTED_STATES:
        sel = {"id": state}
        fills = [e for e in (entry("fillCustom", sel), entry("fill", sel)) if e and "fillColor" in e.get("properties", {})]
        if not fills:
            continue
        for e in fills:
            old = _hex(e["properties"]["fillColor"])
            e["properties"]["fillColor"] = solid_lit(selected)
            o = entry("outline", sel)
            if o and old and _hex(o.get("properties", {}).get("lineColor")) == old:
                o["properties"]["lineColor"] = solid_lit(selected)
            changed.append((state, old, selected, text))
        key = TEXT_FOR[vis["visualType"]]
        te = entry(key, sel)
        if te is None:                               # the state had no text entry: add one with only the colour
            te = {"properties": {}, "selector": dict(sel)}
            objs.setdefault(key, []).append(te)
        te.setdefault("properties", {})["fontColor"] = _json.loads(_json.dumps(solid_lit(text)))
        if contrast(text, selected) < 4.5:
            warnings.append(f"{state} text {text} on colors.selected {selected} is {contrast(text, selected):.2f}:1, "
                            "below 4.5:1 (pick another colors.selected or colors.onSelected)")
    return changed, warnings
