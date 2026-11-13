"""KPI card rule (batch 3 item 10, docs/lessons/cards.md C-10).

The KPI card visual is its own container: background, radius, border and shadow on its own container formatting,
no separate shape behind it (unless the shape matches the card within 1px). Cards in a row have equal width, height
and gaps, span the content width and line up with the row below. `check` is the pbik validate part (warnings);
`empty_space` is the polish-loop screenshot part (scripts call it on a PNG of a synthetic or sample-data page).
"""
import re, struct, zlib

TOL = 1.0
SHAPES = {"shape", "basicShape"}


def is_kpi(folder, d, layout_entry=None):
    if (d.get("visual") or {}).get("visualType") != "cardVisual":
        return False
    if layout_entry and (layout_entry.get("kpi") or "kpi" in str(layout_entry.get("template", "")).lower()):
        return True
    return "kpi" in folder.lower()


def box(d):
    p = d.get("position", {})
    return [float(p.get(k, 0) or 0) for k in ("x", "y", "width", "height")] + [float(p.get("z", 0) or 0)]


def _lit(objs, key, prop):
    for e in objs.get(key, []):
        v = (e.get("properties", {}).get(prop) or {}).get("expr", {}).get("Literal", {}).get("Value")
        if v is not None:
            return v
    return None


def own_container(d):
    """True when the card draws its own background (its container background isn't turned off)."""
    vco = (d.get("visual") or {}).get("visualContainerObjects", {})
    return _lit(vco, "background", "show") != "false"


def near(a, b):
    return abs(a - b) <= TOL


def rows_of(cards):
    rows = []
    for c in sorted(cards, key=lambda c: (c["box"][1], c["box"][0])):
        for r in rows:
            if near(r[0]["box"][1], c["box"][1]):
                r.append(c)
                break
        else:
            rows.append([c])
    return [sorted(r, key=lambda c: c["box"][0]) for r in rows]


def check_page(page, visuals, page_w, margin=32, layout=None):
    """Warnings for one page. visuals: [(folder, visual.json dict)]."""
    out = []
    lay = {v.get("id"): v for v in (layout or {}).get("visuals", [])}
    items = []
    for folder, d in visuals:
        vid = folder.split("_", 1)[0]
        items.append({"folder": folder, "d": d, "box": box(d), "type": (d.get("visual") or {}).get("visualType"),
                      "kpi": is_kpi(folder, d, lay.get(vid))})
    cards = [x for x in items if x["kpi"]]
    for c in cards:
        x, y, w, h, z = c["box"]
        for s in items:
            if s["type"] not in SHAPES:
                continue
            sx, sy, sw, sh, sz = s["box"]
            behind = sz <= z and sx <= x + TOL and sy <= y + TOL and sx + sw >= x + w - TOL and sy + sh >= y + h - TOL
            if behind and not all(near(a, b) for a, b in zip((sx, sy, sw, sh), (x, y, w, h))):
                out.append(f"{page}/{c['folder']}: shape {s['folder']} sits behind the KPI card; the card is the "
                           "container (its own background, radius, border, shadow): remove the shape, or match the "
                           "card within 1px (C-10)")
        if not own_container(c["d"]):
            out.append(f"{page}/{c['folder']}: KPI card has its container background off; put background, radius, "
                       "border and shadow on the card itself (C-10)")
    content_l, content_r = margin, page_w - margin
    for row in rows_of(cards):
        if len(row) < 2:
            continue
        name = f"{page}: KPI row at y {row[0]['box'][1]:g}"
        ws = [c["box"][2] for c in row]
        hs = [c["box"][3] for c in row]
        gaps = [row[k + 1]["box"][0] - (row[k]["box"][0] + row[k]["box"][2]) for k in range(len(row) - 1)]
        if max(ws) - min(ws) > TOL or max(hs) - min(hs) > TOL:
            out.append(f"{name}: cards differ in size ({', '.join(f'{w:g}x{h:g}' for w, h in zip(ws, hs))}); "
                       "make them equal (C-10)")
        if gaps and max(gaps) - min(gaps) > TOL:
            out.append(f"{name}: gaps differ ({', '.join(f'{g:g}' for g in gaps)}); make them equal (C-10)")
        left, right = row[0]["box"][0], row[-1]["box"][0] + row[-1]["box"][2]
        if not (near(left, content_l) and near(right, content_r)):
            out.append(f"{name}: spans {left:g}-{right:g}, the content width is {content_l:g}-{content_r:g} (C-10)")
        bottom = max(c["box"][1] + c["box"][3] for c in row)
        below = [s for s in items if s["box"][1] >= bottom - TOL and s not in row and s["type"] not in SHAPES]
        if below:
            top = min(s["box"][1] for s in below)
            nxt = [s for s in below if near(s["box"][1], top)]
            bl, br = min(s["box"][0] for s in nxt), max(s["box"][0] + s["box"][2] for s in nxt)
            if not (near(bl, left) and near(br, right)):
                out.append(f"{name}: doesn't line up with the row below ({bl:g}-{br:g} against {left:g}-{right:g}) "
                           "(C-10)")
    return out


def layer_order(page, visuals):
    """Lesson C-11: a shape behind other visuals keeps its layer order (container.keepLayerOrder)."""
    out = []
    items = [(f, d, box(d)) for f, d in visuals]
    for f, d, (x, y, w, h, z) in items:
        if (d.get("visual") or {}).get("visualType") not in SHAPES:
            continue
        backs = [g for g, e, (gx, gy, gw, gh, gz) in items if g != f and gz > z and gx >= x - TOL and gy >= y - TOL
                 and gx + gw <= x + w + TOL and gy + gh <= y + h + TOL]
        vco = (d.get("visual") or {}).get("visualContainerObjects", {})
        if backs and _lit(vco, "general", "keepLayerOrder") != "true":
            out.append(f"{page}/{f}: background shape behind {', '.join(backs[:3])} without keepLayerOrder: set "
                       "container.keepLayerOrder true, or a click brings it to the front (C-11)")
    return out


def check(fd, rep, pages, layout=None, margin=None):
    """pbik validate: KPI card layout warnings, and background shapes' layer order, on every page."""
    if margin is None:
        margin = ((layout or {}).get("grid") or {}).get("margin", 32)
    for name, pd, folder in pages:
        vis = [(f.parent.name, d) for d, f in rep.visuals(folder)]
        for w in check_page(pd.get("displayName", name), vis, pd.get("width", 1920), margin, layout):
            fd.warn("kpi cards", w)
        for w in layer_order(pd.get("displayName", name), vis):
            fd.warn("layers", w)


# ---------------------------------------------------------------- the screenshot check
def read_png(path):
    """(width, height, rows of (r, g, b) tuples) from an 8-bit RGB or RGBA, non-interlaced PNG (standard library)."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    k, idat, w = 8, b"", None
    while k < len(data):
        n, typ = struct.unpack(">I4s", data[k:k + 8])
        body = data[k + 8:k + 8 + n]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or inter:
                raise ValueError(f"{path}: only 8-bit RGB/RGBA, non-interlaced PNGs")
            bpp = 3 if ctype == 2 else 4
        elif typ == b"IDAT":
            idat += body
        k += 12 + n
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([tuple(line[i:i + 3]) for i in range(0, stride, bpp)])
        prev = line
    return w, h, rows


def empty_space(png, cards, page_w, inset=8, limit=0.35):
    """[(name, fraction, where)] for cards whose largest empty band (rows or columns with no content, inside an
    inset) is more than `limit` of the card's height or width. cards: [(name, x, y, w, h)] in page units."""
    W, H, px = read_png(png)
    s = W / page_w
    out = []
    for name, x, y, w, h in cards:
        x0, y0 = int((x + inset) * s), int((y + inset) * s)
        x1, y1 = int((x + w - inset) * s), int((y + h - inset) * s)
        crop = [r[x0:x1] for r in px[y0:y1]]
        if not crop or not crop[0]:
            continue
        counts = {}
        for r in crop:
            for p in r:
                counts[p] = counts.get(p, 0) + 1
        bg = max(counts, key=counts.get)
        ink = lambda p: sum(abs(a - b) for a, b in zip(p, bg)) > 60          # noqa: E731
        rows_ink = [any(ink(p) for p in r) for r in crop]
        cols_ink = [any(ink(r[i]) for r in crop) for i in range(len(crop[0]))]
        for flags, size, where in ((rows_ink, len(crop), "rows"), (cols_ink, len(crop[0]), "columns")):
            run = best = 0
            for f in flags:
                run = 0 if f else run + 1
                best = max(best, run)
            frac = best / size if size else 0
            if frac > limit:
                out.append((name, round(frac, 2), "height" if where == "rows" else "width"))
    return out
