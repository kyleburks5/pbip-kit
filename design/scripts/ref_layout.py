"""/plan from a reference of any layout style: a draft layout.json with visual IDs, and what Power BI can't reproduce.

    python design/scripts/ref_layout.py design/reference/mockup.html                 one page per HTML file
    python design/scripts/ref_layout.py design/reference/a.html design/reference/b.html
    python design/scripts/ref_layout.py design/reference/boxes.json                   boxes read from an image
    ... --out design/specs/layout.reference.json --report design/specs/reference-map.md

HTML references are drawn in headless Edge (edge_page.py) and read from the page itself: cards (an own background,
border or shadow), tables, charts (SVG or canvas: bar, column, line, area, donut, scatter from their marks), KPI
numbers, titles, slicers (select and inputs), buttons, button groups, tab bars and navigation rails.
An image can't be read that way: the agent looks at it and writes a boxes file in the reference's own pixels,
    {"width": 1440, "height": 810, "pages": [{"name": "Overview", "boxes": [
        {"kind": "kpi", "x": 24, "y": 88, "w": 330, "h": 120, "label": "Revenue"},
        {"kind": "chart", "chart": "line", "x": 24, "y": 232, "w": 684, "h": 300, "label": "Revenue by month"},
        {"kind": "table", "x": 24, "y": 556, "w": 1392, "h": 230, "rows": 6, "features": ["sparkline in a cell"]}]}]}
with kinds title, text, kpi, chart (chart: bar | column | line | area | donut | scatter | map | other), table (rows,
rowHeight), matrix, slicer, buttons (a button group), button, tabs, rail, image, panel (a card that holds several
visuals), band (a full-width or full-height colour block), and `features` for anything special.

Both go through the same mapping: the reference is scaled to 1920 wide, each box snapped to the 12-column grid
(32px margin, 24px gutters) and to 8px vertically (boxes touching an edge keep it), the visual type chosen
(tabs and rails become a page navigator, a button group a button slicer, a panel a shape behind its visuals, a card
with one visual becomes that visual's own container), IDs given in reading order per page (P<page>-V<nn>, rails and
bands first), and the layout style named: grid, bento (mixed spans and heights), rail, tabs, dense table.
Everything Power BI can't draw natively is listed by ID with the native option used instead (the ladder: CLAUDE.md
"Native first"). The draft has no bindings: /plan fills them, the alt text and the build reasons.
"""
import argparse, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

CANVAS_W, CANVAS_H, MARGIN, GUTTER, COLUMNS = 1920, 1080, 32, 24, 12


def canvas_height(tokens=None):
    """tokens.json canvas.height (batch 3 item 14); 1080 stays the default."""
    try:
        t = tokens if tokens is not None else json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
        return int((t.get("canvas") or {}).get("height") or 1080)
    except (OSError, ValueError, AttributeError):
        return 1080
COL = (CANVAS_W - 2 * MARGIN - (COLUMNS - 1) * GUTTER) / COLUMNS
FONTS_PBI = {"segoe ui", "segoe ui semibold", "segoe ui light", "arial", "arial black", "calibri", "cambria",
             "candara", "consolas", "constantia", "corbel", "courier new", "din", "georgia", "lucida sans unicode",
             "tahoma", "times new roman", "trebuchet ms", "verdana", "sans-serif", "system-ui"}

TYPES = {"title": "textbox", "text": "textbox", "kpi": "cardVisual", "table": "tableEx", "matrix": "pivotTable",
         "slicer": "slicer", "buttons": "advancedSlicerVisual", "button": "actionButton", "tabs": "pageNavigator",
         "rail": "pageNavigator", "image": "image", "panel": "shape", "band": "shape"}
CHARTS = {"bar": "clusteredBarChart", "column": "clusteredColumnChart", "line": "lineChart", "area": "areaChart",
          "donut": "donutChart", "pie": "pieChart", "scatter": "scatterChart", "map": "filledMap",
          "other": "lineChart"}

# what Power BI can't draw natively -> (the native option, the ladder step if a fallback is needed)
GAPS = {
    "gradient fill": ("a solid fill from the tokens; a gradient only as a page or shape background image", 1),
    "background blur (glass)": ("a semi-transparent shape fill (no blur behind visuals)", 1),
    "rotated or skewed element": ("an unrotated visual; rotated text only in a shape's text", 1),
    "scrolling region inside a card": ("one visual with its own scroll (table, matrix) or a taller page", 1),
    "sticky or fixed element": ("visuals stay where they are; pages don't scroll at 1080 high", 1),
    "different corner radii": ("one radius for all four corners (container.radius)", 1),
    "dashed or dotted border": ("a solid 1px border", 1),
    "animation": ("no motion; bookmarks for state changes", 1),
    "text shadow": ("plain text", 1),
    "tabs inside a card": ("buttons with bookmarks that show one visual at a time, or a bookmark navigator", 1),
    "expanding section": ("a bookmark that shows or hides a group", 1),
    "hover-only content": ("a tooltip page or the default tooltip", 1),
    "sparkline in a cell": ("a table column with an SVG measure image (DaxLib.SVG, ladder step 2)", 2),
    "chart in a cell": ("a table column with an SVG measure image (DaxLib.SVG, ladder step 2)", 2),
    "chart type unclear": ("a line chart until the design names the type", 1),
    "responsive breakpoints": ("one fixed 1920x1080 page; the reference is read at its drawn width", 1),
    "custom font": ("Segoe UI (Power BI's built-in fonts only)", 1),
    "taller than one page": ("a page taller than 1080 (scrolls in the Service) or a second page", 1),
}

PAGE_JS = r"""<script>window.addEventListener('load', function () {
var BIG = /^[\s$€£¥+\-−]?[\d][\d.,]*\s?(%|[KMBkmb]|bn|d|days|pts)?$/;
function vis(el) { var s = getComputedStyle(el), r = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; }
function alpha(c) { var m = c.match(/rgba?\(([^)]+)\)/); if (!m) return 0; var p = m[1].split(',').map(Number); return p.length < 4 ? 1 : p[3]; }
function own(el) { return Array.prototype.filter.call(el.childNodes, function (n) { return n.nodeType === 3; }).map(function (n) { return n.textContent; }).join('').trim(); }
function box(el) { var r = el.getBoundingClientRect(); return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height}; }
var all = Array.prototype.slice.call(document.querySelectorAll('body *')).filter(vis);
var W = 0, H = 0, X0 = 1e9, Y0 = 1e9;
all.forEach(function (el) { var b = box(el); W = Math.max(W, b.x + b.w); H = Math.max(H, b.y + b.h); });
var pg = document.body.firstElementChild; if (pg && vis(pg)) { var pb = box(pg); if (pb.w > W * 0.9) { W = pb.x + pb.w; H = Math.max(H, pb.y + pb.h); } }
var area = W * H, items = [], seen = new Set(), feats = {};
function features(el, f) {
  var s = getComputedStyle(el);
  if (s.backgroundImage.indexOf('gradient') >= 0) f.push('gradient fill');
  if ((s.backdropFilter && s.backdropFilter !== 'none') || (s.webkitBackdropFilter && s.webkitBackdropFilter !== 'none')) f.push('background blur (glass)');
  if (s.transform !== 'none' && !/^matrix\(1, 0, 0, 1,/.test(s.transform)) f.push('rotated or skewed element');
  if (s.position === 'sticky' || s.position === 'fixed') f.push('sticky or fixed element');
  var rs = [s.borderTopLeftRadius, s.borderTopRightRadius, s.borderBottomLeftRadius, s.borderBottomRightRadius];
  if (new Set(rs).size > 1) f.push('different corner radii');
  if (/dashed|dotted/.test(s.borderTopStyle + s.borderLeftStyle)) f.push('dashed or dotted border');
  if ((s.animationName && s.animationName !== 'none') || parseFloat(s.transitionDuration) > 0) f.push('animation');
  if (s.textShadow && s.textShadow !== 'none') f.push('text shadow');
  return f;
}
function deepFeatures(el, f) {
  features(el, f);
  el.querySelectorAll('*').forEach(function (c) { if (!vis(c)) return; var s = getComputedStyle(c);
    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && c.scrollHeight > c.clientHeight + 4 && c.tagName !== 'TABLE') f.push('scrolling region inside a card');
    features(c, f); });
  if (el.querySelector('details, summary')) f.push('expanding section');
  return Array.from(new Set(f));
}
function isCard(el) {
  if (/^(TABLE|THEAD|TBODY|TR|TD|TH|BUTTON|SELECT|INPUT|A|SVG|svg|PATH|RECT|CIRCLE|LI|UL|OL|SPAN|B|STRONG|LABEL|OPTION)$/.test(el.tagName)) return false;
  var s = getComputedStyle(el), b = box(el); if (b.w * b.h < area * 0.004) return false;
  var bg = alpha(s.backgroundColor) > 0.5, pbg = el.parentElement ? getComputedStyle(el.parentElement).backgroundColor : '';
  var border = parseFloat(s.borderTopWidth) >= 1 && parseFloat(s.borderLeftWidth) >= 1;
  return (bg && s.backgroundColor !== pbg) || border || (s.boxShadow && s.boxShadow !== 'none');
}
function chartKind(svg) {
  var rects = svg.querySelectorAll('rect').length, arcs = Array.prototype.some.call(svg.querySelectorAll('path'), function (p) { return /[Aa]/.test(p.getAttribute('d') || ''); });
  var lines = svg.querySelectorAll('polyline, line').length + Array.prototype.filter.call(svg.querySelectorAll('path'), function (p) { return !/[Aa]/.test(p.getAttribute('d') || ''); }).length;
  var circles = svg.querySelectorAll('circle').length, polys = svg.querySelectorAll('polygon').length;
  var cls = ((svg.getAttribute('class') || '') + ' ' + (svg.getAttribute('aria-label') || '')).toLowerCase();
  var named = ['donut', 'pie', 'scatter', 'area', 'line', 'column', 'bar', 'map'].find(function (k) { return cls.indexOf(k) >= 0; });
  if (named) return named;
  if (arcs || (circles >= 1 && circles <= 3 && svg.querySelector('circle[stroke-width]'))) return 'donut';
  if (rects >= 2) { var w = 0, h = 0; svg.querySelectorAll('rect').forEach(function (r) { var b = r.getBBox(); w += b.width; h += b.height; }); return w > h ? 'bar' : 'column'; }
  if (polys) return 'area';
  if (lines) return 'line';
  if (circles >= 8) return 'scatter';
  return 'other';
}
function add(el, kind, extra) { if (seen.has(el)) return; seen.add(el); var it = Object.assign({el: el, kind: kind}, box(el), extra || {}); items.push(it); return it; }
all.forEach(function (el) {
  var t = el.tagName.toUpperCase(), role = el.getAttribute('role'), b = box(el);
  if (el.closest('svg') && t !== 'SVG') return;
  if (t === 'TABLE' || role === 'grid' || role === 'table') {
    if (el.parentElement.closest('table')) return;
    var rows = el.querySelectorAll('tr').length, rh = rows ? b.h / rows : 0, f = [];
    if (el.querySelector('td svg, td canvas')) f.push(el.querySelector('td svg polyline, td svg path') ? 'sparkline in a cell' : 'chart in a cell');
    var cols = el.querySelector('tr') ? el.querySelector('tr').children.length : 0;
    add(el, el.querySelector('th[rowspan], th[colspan]') ? 'matrix' : 'table', {rows: rows, rowHeight: rh, columns: cols, features: f});
  } else if ((t === 'SVG' && b.w >= 80 && b.h >= 50 && !el.closest('td')) || (t === 'CANVAS' && b.w >= 80)) {
    add(el, 'chart', {chart: t === 'SVG' ? chartKind(el) : 'other'});
  } else if (t === 'IMG' && b.w >= 24) { add(el, 'image');
  } else if (t === 'SELECT' || (t === 'INPUT' && /range|date|search|text|number/.test(el.type))) { add(el, 'slicer');
  } else if (t === 'NAV' || role === 'tablist') {
    if (el.parentElement.closest('nav, [role=tablist]')) return;
    var n = el.querySelectorAll('a, button, [role=tab]').length;
    var card = el.parentElement.closest('div'); var inCard = false;
    for (var p = el.parentElement; p && p !== document.body; p = p.parentElement) if (isCard(p) && box(p).w * box(p).h < area * 0.6) { inCard = true; break; }
    var kind = b.h > b.w * 1.5 ? 'rail' : 'tabs';
    var it = add(el, inCard ? 'tabs-in-card' : kind, {items: n});
    el.querySelectorAll('*').forEach(function (c) { seen.add(c); });
  } else if (t === 'BUTTON' && !el.closest('nav, [role=tablist]')) {
    var sib = Array.prototype.filter.call(el.parentElement.children, function (c) { return c.tagName === 'BUTTON'; });
    if (sib.length >= 2) { if (!seen.has(el.parentElement)) { add(el.parentElement, 'buttons', {items: sib.length}); } }
    else add(el, 'button');
  } else if (/^H[1-3]$/.test(t) || (own(el) && parseFloat(getComputedStyle(el).fontSize) >= 20 && !BIG.test(own(el)))) {
    var host = null; for (var p2 = el.parentElement; p2 && p2 !== document.body; p2 = p2.parentElement) if (isCard(p2)) { host = p2; break; }
    if (!host || box(host).w * box(host).h > area * 0.6) add(el, 'title', {text: own(el) || el.textContent.trim().slice(0, 60)});
  } else if (own(el) && BIG.test(own(el)) && parseFloat(getComputedStyle(el).fontSize) >= 24) {
    add(el, 'kpi-value', {text: own(el)});
  }
});
// cards: the card-like boxes; a card holding visuals is a panel (or that visual's own container)
var cards = all.filter(isCard).filter(function (el) { return box(el).w * box(el).h < area * 0.8; });
var out = cards.map(function (el, i) {
  var b = box(el), f = deepFeatures(el, []), title = el.querySelector('b, strong, h2, h3, h4, .title');
  return {i: i, el: el, kind: 'card', x: b.x, y: b.y, w: b.w, h: b.h, features: f, text: title ? title.textContent.trim().slice(0, 60) : '', band: (b.w >= W * 0.97 || b.h >= H * 0.95)};
});
items.forEach(function (it) {
  it.card = -1; var best = null;
  out.forEach(function (c) { if (c.el !== it.el && c.el.contains(it.el)) { if (!best || best.el.contains(c.el)) best = c; } });
  if (best) it.card = best.i;
  if (it.features) it.features = Array.from(new Set(it.features.concat(features(it.el, []))));
  else it.features = features(it.el, []);
  if (it.kind === 'tabs-in-card' && best) { best.features.push('tabs inside a card'); }
});
var css = Array.prototype.map.call(document.querySelectorAll('style'), function (s) { return s.textContent; }).join('\n');
var fam = getComputedStyle(document.body).fontFamily.split(',')[0].replace(/["']/g, '').trim();
var res = {width: W, height: H, title: document.title, font: fam, hover: /:hover/.test(css), media: /@media/.test(css),
  items: items.map(function (it) { var o = Object.assign({}, it); delete o.el; return o; }),
  cards: out.map(function (c) { var o = Object.assign({}, c); delete o.el; return o; })};
var pre = document.createElement('script'); pre.type = 'application/json'; pre.id = 'pbik-ref'; pre.textContent = JSON.stringify(res); document.body.appendChild(pre);
});</script>"""


# ---------------------------------------------------------------- read
def read_html(path):
    import edge_page
    if not edge_page.available():
        raise SystemExit("reading an HTML reference needs Microsoft Edge (headless); write a boxes file instead")
    src = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    src = re.sub(r"<script\b(?![^>]*application/json)[^>]*>.*?</script>", "", src, flags=re.S | re.I)
    page = src.replace("</body>", PAGE_JS + "</body>", 1) if "</body>" in src else src + PAGE_JS
    dom = edge_page.dom(page, delay_ms=300)
    m = re.search(r'<script type="application/json" id="pbik-ref">(.*?)</script>', dom, re.S)
    if not m:
        raise SystemExit(f"{path}: Edge didn't return the page's boxes")
    return boxes_from_dom(json.loads(m.group(1)), pathlib.Path(path).stem)


def boxes_from_dom(r, name):
    """The DOM reading -> one page of boxes in the boxes-file format."""
    out, cards = [], r["cards"]
    items = [i for i in r["items"] if i["kind"] != "tabs-in-card"]
    # KPI values: the box is the card that holds them when it holds one value, else the value's own box
    per_card = {}
    for it in items:
        if it["card"] >= 0:
            per_card.setdefault(it["card"], []).append(it)
    for it in items:
        if it["kind"] == "kpi-value":
            it["kind"] = "kpi"
    used_cards = set()
    for ci, members in per_card.items():
        c = cards[ci]
        kinds = [m["kind"] for m in members]
        if len(members) == 1 and kinds[0] in ("chart", "table", "matrix", "kpi", "slicer", "buttons", "image"):
            m = members[0]                       # the card is this visual's container
            m.update({k: c[k] for k in ("x", "y", "w", "h")})
            m["label"] = c.get("text") or m.get("text") or ""
            m["features"] = sorted(set(m.get("features", []) + c.get("features", [])))
            used_cards.add(ci)
        elif len(members) > 1 and all(k == "kpi" for k in kinds) and len(members) <= 6:
            # one card holding a row of KPI numbers: a panel with a card per number, or a multi-value card
            used_cards.discard(ci)
    for ci, c in enumerate(cards):
        if ci in used_cards:
            continue
        members = per_card.get(ci, [])
        if not members and not c.get("band"):
            continue                             # an empty decorative box inside another card
        out.append({"kind": "band" if c.get("band") else "panel", "x": c["x"], "y": c["y"], "w": c["w"],
                    "h": c["h"], "label": c.get("text", ""), "features": c.get("features", [])})
    for it in items:
        b = {k: it[k] for k in ("kind", "x", "y", "w", "h")}
        for k in ("chart", "rows", "rowHeight", "columns", "items"):
            if k in it:
                b[k] = it[k]
        b["label"] = it.get("label") or it.get("text") or ""
        b["features"] = it.get("features", [])
        out.append(b)
    page_feats = []
    if r.get("hover"):
        page_feats.append("hover-only content")
    if r.get("media"):
        page_feats.append("responsive breakpoints")
    if r.get("font") and r["font"].lower() not in FONTS_PBI:
        page_feats.append("custom font")
    return {"width": r["width"], "height": r["height"],
            "pages": [{"name": (r.get("title") or name).strip() or name, "boxes": out, "features": page_feats,
                       "font": r.get("font")}]}


# ---------------------------------------------------------------- map
def col_x(i):                                    # 0-based column -> left edge
    return MARGIN + i * (COL + GUTTER)


def snap_cols(x, w):
    """(first, last) 1-based columns whose span is nearest to x..x+w."""
    first = min(range(COLUMNS), key=lambda i: abs(col_x(i) - x))
    last = min(range(first, COLUMNS), key=lambda i: abs(col_x(i) + COL - (x + w)))
    return first + 1, last + 1


def grid_box(first, last):
    x = col_x(first - 1)
    return round(x), round(col_x(last - 1) + COL - x)


def snap8(v):
    return int(round(v / 8.0) * 8)


def name_of(b, kind):
    words = re.sub(r"[^a-z0-9]+", "-", (b.get("label") or "").lower()).strip("-")
    return (words[:40].strip("-") or kind)


def layout_style(page_boxes, scale):
    """grid / bento / rail / tabs / dense table, and why."""
    kinds = [b["kind"] for b in page_boxes]
    styles = []
    if "rail" in kinds:
        styles.append("rail")
    if "tabs" in kinds:
        styles.append("tabs")
    tables = [b for b in page_boxes if b["kind"] in ("table", "matrix")]
    area = sum(b["w"] * b["h"] for b in page_boxes if b["kind"] not in ("band", "panel")) or 1
    if any((b.get("rowHeight") or 99) * scale <= 30 or (b.get("rows") or 0) >= 15 for b in tables) and \
            sum(b["w"] * b["h"] for b in tables) / area > 0.3:
        styles.append("dense table")
    tiles = [b for b in page_boxes if b["kind"] in ("chart", "table", "matrix", "kpi", "panel", "image")]
    spans = {snap_cols(b["x"] * scale, b["w"] * scale)[1] - snap_cols(b["x"] * scale, b["w"] * scale)[0] for b in tiles}
    heights = {snap8(b["h"] * scale) for b in tiles if b["kind"] != "kpi"}
    rows = {snap8(b["y"] * scale) for b in tiles}
    if len(spans) >= 3 and len(heights) >= 3 and len(rows) >= 3:
        styles.append("bento")
    return styles or ["grid"]


def map_reference(ref, page_offset=0):
    """boxes-file dict -> (layout, findings, styles). findings: [(id, feature, native option, step)]."""
    W = ref.get("width") or CANVAS_W
    scale = CANVAS_W / W
    layout = {"_note": "Draft from ref_layout.py: boxes, types and IDs from the reference. /plan adds bindings, alt "
                       "text, styles and build reasons, then saves it as design/specs/layout.json.",
              "grid": {"canvas": [CANVAS_W, CANVAS_H], "margin": MARGIN, "columns": COLUMNS, "gutter": GUTTER,
                       "column": round(COL, 2)},
              "pages": {}, "retired": [], "visuals": []}
    findings, styles = [], {}
    for pi, page in enumerate(ref["pages"], start=1 + page_offset):
        pk = f"P{pi}"
        boxes = [dict(b) for b in page["boxes"]]
        ph = snap8((ref.get("height") or CANVAS_H / scale) * scale)
        layout["pages"][pk] = {"displayName": page.get("name") or f"Page {pi}", "background": "background",
                               **({"height": ph} if ph > CANVAS_H + 8 else {}), **({"active": True} if pi == 1 else {})}
        styles[pk] = layout_style(boxes, scale)
        placed = []
        for b in boxes:
            x, y, w, h = (b[k] * scale for k in ("x", "y", "w", "h"))
            edge_l, edge_t = x <= 4, y <= 4
            edge_r, edge_b = x + w >= CANVAS_W - 4, y + h >= ph - 4
            v = {"kind": b["kind"], "src": b}
            if edge_l or edge_r or b["kind"] in ("band", "rail"):
                v["cols"] = None
                if edge_l and edge_r:
                    v["x"], v["w"] = 0, CANVAS_W
                elif edge_l:
                    right = min((col_x(i) + COL for i in range(COLUMNS)), key=lambda e: abs(e - (x + w)))
                    v["x"], v["w"] = 0, round(right)
                else:
                    first, last = snap_cols(x, w)
                    v["x"] = round(col_x(first - 1))
                    v["w"] = CANVAS_W - v["x"] if edge_r else grid_box(first, last)[1]
            else:
                first, last = snap_cols(x, w)
                v["cols"] = [first, last]
                v["x"], v["w"] = grid_box(first, last)
            top = 0 if edge_t else snap8(y)
            bottom = ph if edge_b else snap8(y + h)
            v["y"], v["h"] = top, max(8, bottom - top)
            placed.append(v)
        # a run of three or more look-alike boxes in a row (same kind, widths within 10%) shares its span equally, as
        # the reference does, even where the span doesn't divide into whole columns (gutters stay 24px)
        for v in placed:
            v.setdefault("split", None)
        by_row = {}
        for v in placed:
            if v.get("cols") and v["kind"] in ("kpi", "chart", "slicer", "image", "panel", "table"):
                by_row.setdefault((v["y"], v["h"], v["kind"]), []).append(v)
        for run in by_row.values():
            ws = [r["src"]["w"] for r in run]
            if len(run) >= 3 and max(ws) <= min(ws) * 1.1:
                run.sort(key=lambda r: r["x"])
                first, last = run[0]["cols"][0], run[-1]["cols"][1]
                x0, total = grid_box(first, last)
                w = (total - GUTTER * (len(run) - 1)) / len(run)
                for i, r in enumerate(run):
                    r["x"], r["w"] = round(x0 + i * (w + GUTTER)), round(w)
                    r["split"] = f"equal split of columns {first}-{last} ({len(run)} boxes)"
                    r["cols"] = None
        # titles and text widen to the next box in their row (at least 4 columns): a reference's text box is as wide
        # as its words, a Power BI text box needs room for longer titles
        for v in placed:
            if v["kind"] in ("title", "text") and v.get("cols"):
                first = v["cols"][0]
                right = [o["cols"][0] for o in placed if o is not v and o.get("cols") and o["cols"][0] > v["cols"][1]
                         and o["y"] < v["y"] + v["h"] and o["y"] + o["h"] > v["y"]]
                last = max(v["cols"][1], min(min(right) - 1 if right else COLUMNS, first + 5))
                v["cols"] = [first, last]
                v["x"], v["w"] = grid_box(first, last)
        # reading order: bands and rails first, then rows top to bottom (a box joins a row while its top is above
        # the middle of the row's shortest box), left to right in a row, a panel before what it holds
        lead = [v for v in placed if v["kind"] in ("band", "rail")]
        rest = sorted((v for v in placed if v not in lead), key=lambda v: (v["y"], v["x"]))
        rows = []
        for v in rest:
            if rows and v["y"] < min(o["y"] for o in rows[-1]) + min(o["h"] for o in rows[-1]) / 2                     and v["kind"] != "panel":
                rows[-1].append(v)
            else:
                rows.append([v])
        out = sorted(lead, key=lambda v: (v["kind"] != "band", v["x"])) +             [v for row in rows for v in sorted(row, key=lambda v: (v["x"], v["kind"] != "panel"))]
        n = 0
        for v in out:
            n += 1
            vid = f"{pk}-V{n:02d}"
            b = v["src"]
            kind = b["kind"]
            vt = CHARTS.get(b.get("chart") or "other") if kind == "chart" else TYPES.get(kind, "shape")
            entry = {"id": vid, "name": name_of(b, kind), "page": pk, "type": vt}
            if v["cols"]:
                entry["cols"] = v["cols"]
            entry.update({"x": v["x"], "y": v["y"], "w": v["w"], "h": v["h"],
                          "z": 0 if kind in ("band", "panel", "rail") and vt == "shape" else 1000})
            notes = [v["split"]] if v.get("split") else []
            reason = {"textbox": "Text box", "shape": "Shape behind the visuals it holds",
                                 "pageNavigator": "Page navigator", "advancedSlicerVisual": "Button slicer",
                                 "slicer": "Slicer", "actionButton": "Button", "image": "Image",
                                 "cardVisual": "Card (new)", "tableEx": "Table", "pivotTable": "Matrix"}.get(vt, vt)
            if kind == "rail":
                entry["navigator"] = {"orientation": "vertical"}
                entry["z"] = 1000
                notes.append(f"navigation rail ({b.get('items', '?')} items): a vertical page navigator on a band shape")
                if not any(o["kind"] == "band" and o["x"] <= v["x"] + 8 and o["w"] >= v["w"] - 8 for o in placed):
                    layout["visuals"].append({"id": None, "_railBand": True, "page": pk, "x": 0, "y": 0,
                                              "w": v["w"], "h": v["h"]})
            if kind == "tabs":
                notes.append(f"tab bar ({b.get('items', '?')} tabs): one page per tab and a page navigator")
            if kind == "buttons":
                notes.append(f"button group ({b.get('items', '?')} buttons): a button slicer")
            if kind in ("table", "matrix") and b.get("rows"):
                dense = (b.get("rowHeight") or 99) * scale <= 30
                notes.append(f"{b['rows']} rows{', dense (row padding 2-3, caption font)' if dense else ''}")
                if dense:
                    entry["props"] = {"grid.rowPadding": 2}
            if kind == "chart" and (b.get("chart") in (None, "other")):
                b.setdefault("features", []).append("chart type unclear")
            entry["build"] = {"method": "native", "step": 1, "reason": reason}
            for f in sorted(set(b.get("features") or [])):
                native, step = GAPS.get(f, ("check by hand", 1))
                findings.append((vid, f, native, step))
                notes.append(f"reference has {f}: {native}")
            if notes:
                entry["notes"] = "; ".join(notes)
            entry["reference"] = {**{k: round(b[k]) for k in ("x", "y", "w", "h")},
                                  **({"label": b["label"]} if b.get("label") else {})}
            layout["visuals"].append(entry)
        for f in page.get("features") or []:
            native, step = GAPS.get(f, ("check by hand", 1))
            if f == "custom font":
                native = f"Segoe UI instead of {page.get('font')!r} (Power BI's built-in fonts only)"
            findings.append((pk, f, native, step))
        if ph > CANVAS_H + 8:
            findings.append((pk, "taller than one page", GAPS["taller than one page"][0], 1))
    # rail bands: a shape under each rail, with its own ID after the rail's page visuals
    bands = [v for v in layout["visuals"] if v.get("_railBand")]
    layout["visuals"] = [v for v in layout["visuals"] if not v.get("_railBand")]
    for rb in bands:
        n = sum(1 for v in layout["visuals"] if v["page"] == rb["page"]) + 1
        layout["visuals"].append({"id": f"{rb['page']}-V{n:02d}", "name": "rail-band", "page": rb["page"],
                                  "type": "shape", "x": rb["x"], "y": rb["y"], "w": rb["w"], "h": rb["h"], "z": 0,
                                  "style": {"fill": "primary"},
                                  "build": {"method": "native", "step": 1, "reason": "Shape behind the rail"}})
    return layout, findings, styles


def report_md(layout, findings, styles, sources):
    lines = ["# Reference map", "", f"From {', '.join(sources)} (ref_layout.py). The draft layout has "
             f"{len(layout['visuals'])} visuals on {len(layout['pages'])} page(s).", ""]
    for pk, p in layout["pages"].items():
        lines += [f"## {pk} {p['displayName']}: {', '.join(styles[pk])}", "",
                  "| ID | Type | Columns | Box | Notes |", "| --- | --- | --- | --- | --- |"]
        for v in layout["visuals"]:
            if v["page"] == pk:
                cols = f"{v['cols'][0]}-{v['cols'][1]}" if v.get("cols") else "edge"
                lines.append(f"| {v['id']} | {v['type']} | {cols} | {v['x']},{v['y']} {v['w']}x{v['h']} | "
                             f"{v.get('notes', '')} |")
        lines.append("")
    lines += ["## Can't be reproduced in Power BI", ""]
    if findings:
        lines += ["| Where | In the reference | Native option instead | Ladder step if kept |", "| --- | --- | --- | --- |"]
        lines += [f"| {w} | {f} | {n} | {s} |" for w, f, n, s in findings]
    else:
        lines.append("Nothing: every element has a native visual.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("refs", nargs="+", help="HTML reference(s) (one page each) or a boxes .json file")
    ap.add_argument("--out", default=str(ROOT / "design" / "specs" / "layout.reference.json"))
    ap.add_argument("--report", default=str(ROOT / "design" / "specs" / "reference-map.md"))
    ap.add_argument("--canvas-height", type=int, help="page height (default: tokens.json canvas.height, else 1080)")
    a = ap.parse_args(argv)
    global CANVAS_H
    CANVAS_H = a.canvas_height or canvas_height()
    sys.stdout.reconfigure(errors="replace")
    pages, width, height = [], None, None
    for r in a.refs:
        p = pathlib.Path(r)
        ref = json.loads(p.read_text(encoding="utf-8")) if p.suffix.lower() == ".json" else read_html(p)
        for pg in ref["pages"]:                 # each page keeps its own scale
            pages.append((ref.get("width"), ref.get("height"), pg))
    layout, findings, styles = None, [], {}
    for i, (w, h, pg) in enumerate(pages):
        lay, f, s = map_reference({"width": w, "height": h, "pages": [pg]}, page_offset=i)
        if layout is None:
            layout = lay
        else:
            layout["pages"].update(lay["pages"])
            layout["visuals"] += lay["visuals"]
        findings += f
        styles.update(s)
    for f, text in ((a.out, json.dumps(layout, indent=2) + "\n"), (a.report, report_md(layout, findings, styles, a.refs))):
        pathlib.Path(f).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(f).write_text(text, encoding="utf-8")
    for pk, p in layout["pages"].items():
        n = sum(1 for v in layout["visuals"] if v["page"] == pk)
        print(f"{pk} {p['displayName']}: {n} visuals, {', '.join(styles[pk])}")
    print(f"{len(findings)} thing(s) Power BI can't reproduce natively (listed in {a.report}); wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
