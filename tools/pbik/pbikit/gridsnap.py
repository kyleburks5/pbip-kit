"""The layout grid: which visuals are out of line and by how much, and the snap `pbik build` makes before the score
(v1.10). The grid is layout.json `grid` (canvas, margin, columns, gutter; default 1920 x 1080, 32, 12, 24).

Out of line, per visual (shapes, text boxes and images count for the column edges only, as before):
- a left or right edge more than 1 px off a column edge (a full-width band may span 0..1920; a rail, pattern
  rail-panel, may touch one page edge with its inner edge on the grid);
- a data visual's top or bottom off the 8 px baseline;
- a bottom 1-8 px off the bottom of the other visuals that start on the same row (a bigger difference is a choice).
A visual inside a shape that is itself on the grid (a panel, the header band; not a rail, whose contents stay on the
grid) lines up with that shape, not the columns: it is left out, and a
row-mate with the same bottom keeps it (so a row of cards stays one height).

The snap moves an edge to the nearest column edge (rounded to whole pixels, so the gaps stay the gutter), a top and a
bottom to the nearest 8 px line (both rounded the same way, halves down the page, so a gap that was a multiple of 8,
such as the 24 px gutter, stays the same) and a short bottom down to the row's bottom. It never moves:
- a visual placed by hand: one with `desktopPosition` (Desktop's own box) or `snap: false` (layout.json says so
  per visual; `"snap": false` at the top of layout.json turns the snap off). It is listed, with what is off.
- an edge more than SNAP_MAX px from the grid: that is a choice (a card inset in a panel), not a slip. Listed too.
A second run moves nothing.
"""
DECOR = {"shape", "basicShape", "textbox", "image"}
SNAP_MAX = 12                     # px: half a gutter; further off is a choice, so it is listed, not moved
ROW_MAX = 8                       # px: bottoms on one row this close are meant to line up


def grid_of(layout):
    g = (layout or {}).get("grid") or {}
    canvas = g.get("canvas") or [1920, 1080]
    width = canvas[0] if isinstance(canvas, (list, tuple)) else 1920
    margin, cols, gutter = g.get("margin", 32), g.get("columns", 12), g.get("gutter", 24)
    col = (width - 2 * margin - (cols - 1) * gutter) / cols
    lefts = [margin + i * (col + gutter) for i in range(cols)]
    return width, lefts, [x + col for x in lefts]


def _near(value, edges):
    e = min(edges, key=lambda e_: abs(value - e_))
    return e, value - e


def _fmt(x):
    return f"{x:g}" if isinstance(x, (int, float)) else str(x)


def _px(d):
    d = abs(d)
    return f"{round(d, 1):g} px"


def line8(y):
    """The nearest 8 px line; a half goes down the page (ties up), the same for tops and bottoms."""
    return int((y + 4) // 8 * 8)


def _inside(v, shapes):
    x, y, w, h = v["x"], v["y"], v["w"], v["h"]
    return any(s_ is not v and s_.get("page") == v.get("page") and s_["x"] <= x and s_["y"] <= y
               and x + w <= s_["x"] + s_["w"] and y + h <= s_["y"] + s_["h"]
               and (s_["w"], s_["h"]) != (w, h) for s_ in shapes)


def issues(layout):
    """[{id, what, at, want, off, text}] for every visual out of line. `want` is where the snap would put it."""
    width, lefts, rights = grid_of(layout)
    out = []
    vis = [v for v in (layout or {}).get("visuals", []) if v.get("type") != "group"
           and all(isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool) for k in ("x", "y", "w", "h"))]
    shapes = [v for v in vis if v.get("type") in ("shape", "basicShape") and v.get("pattern") != "rail-panel"
              and (v["x"] == 0 or min(abs(v["x"] - e) for e in lefts) <= 1)
              and (v["x"] + v["w"] >= width or min(abs(v["x"] + v["w"] - e) for e in rights) <= 1)]
    fixed = {}                  # bottoms a row-mate that stays put has (on a panel, or placed by hand): keep a row even
    for v in vis:
        if v.get("type") not in DECOR and (_inside(v, shapes) or placed_by_hand(v)):
            fixed.setdefault((v.get("page"), line8(v["y"])), set()).add(v["y"] + v["h"])
    vis = [v for v in vis if not _inside(v, shapes)]
    for v in vis:
        x, y, w, h = v["x"], v["y"], v["w"], v["h"]
        if x != 0:
            e, d = _near(x, lefts)
            if abs(d) > 1:
                out.append({"id": v["id"], "what": "left", "at": x, "want": round(e), "off": d,
                            "text": f"{v['id']} left edge {_fmt(x)} is {_px(d)} {'right' if d > 0 else 'left'} of the "
                                    f"column edge {round(e)}"})
        if x + w < width:
            e, d = _near(x + w, rights)
            if abs(d) > 1:
                out.append({"id": v["id"], "what": "right", "at": x + w, "want": round(e), "off": d,
                            "text": f"{v['id']} right edge {_fmt(x + w)} is {_px(d)} {'right' if d > 0 else 'left'} "
                                    f"of the column edge {round(e)}"})
        if v.get("type") not in DECOR:
            if y % 8:
                want = line8(y)
                out.append({"id": v["id"], "what": "top", "at": y, "want": want, "off": y - want,
                            "text": f"{v['id']} top {_fmt(y)} is {_px(y - want)} off the 8 px line ({want})"})
            if (y + h) % 8 and (y + h) not in fixed.get((v.get("page"), line8(y)), set()):
                want = line8(y + h)
                out.append({"id": v["id"], "what": "bottom8", "at": y + h, "want": want, "off": y + h - want,
                            "text": f"{v['id']} bottom {_fmt(y + h)} is {_px(y + h - want)} off the 8 px line ({want})"})
    rows = {}
    for v in vis:
        if v.get("type") in DECOR:
            continue
        rows.setdefault((v.get("page"), line8(v["y"])), []).append(v)
    for row in rows.values():
        if len(row) < 2:
            continue
        bottoms = [line8(v["y"] + v["h"]) for v in row]
        for v, b in zip(row, bottoms):
            near = [b_ for b_ in bottoms if 0 < b_ - b <= ROW_MAX]
            if near:
                want = max(near)
                out.append({"id": v["id"], "what": "bottom", "at": v["y"] + v["h"], "want": want,
                            "off": v["y"] + v["h"] - want,
                            "text": f"{v['id']} bottom {_fmt(v['y'] + v['h'])} is {_px(v['y'] + v['h'] - want)} above "
                                    f"its row's bottom {_fmt(want)}"})
    row_fix = {i["id"] for i in out if i["what"] == "bottom"}         # the row's bottom is on the line already
    return [i for i in out if not (i["what"] == "bottom8" and i["id"] in row_fix)]


def placed_by_hand(v):
    if v.get("desktopPosition"):
        return "desktopPosition"
    if v.get("snap") is False:
        return "snap: false"
    return None


EDGE = {"left": "left", "right": "right", "top": "top", "bottom8": "bottom", "bottom": "bottom"}


def snap(layout):
    """Snap layout.json's visuals in place. Returns (moved, left): one plain line per visual moved ("P1-V04: left
    344 -> 345, bottom 290 -> 296"), and one per edge still out of line with why it wasn't moved."""
    if (layout or {}).get("snap") is False:
        return [], [f"grid snap off (layout.json \"snap\": false): {i['text']}" for i in issues(layout)]
    by_id = {v.get("id"): v for v in layout.get("visuals", [])}
    start = {vid: {"left": v.get("x"), "right": (v.get("x") or 0) + (v.get("w") or 0), "top": v.get("y"),
                   "bottom": (v.get("y") or 0) + (v.get("h") or 0)} for vid, v in by_id.items()}
    touched, left = [], []
    for _ in range(3):                                  # a moved top can make a new row; settle in a few passes
        changed = False
        for i in issues(layout):
            v = by_id[i["id"]]
            hand = placed_by_hand(v)
            if hand or abs(i["off"]) > SNAP_MAX:
                line = (f"{i['text']}: placed by hand ({hand}), not moved" if hand else
                        f"{i['text']}: too far to snap safely (more than {SNAP_MAX} px), so it stays; move it in "
                        "layout.json")
                if line not in left:
                    left.append(line)
                continue
            if i["what"] == "left":
                right = v["x"] + v["w"]
                v["x"] = i["want"]
                v["w"] = right - v["x"]
            elif i["what"] == "right":
                v["w"] = i["want"] - v["x"]
            elif i["what"] == "top":
                bottom = v["y"] + v["h"]
                v["y"] = i["want"]
                v["h"] = bottom - v["y"]
            elif i["what"] in ("bottom", "bottom8"):
                v["h"] = i["want"] - v["y"]
            for k in ("x", "y", "w", "h"):
                if isinstance(v[k], float) and v[k].is_integer():
                    v[k] = int(v[k])
            if i["id"] not in touched:
                touched.append(i["id"])
            changed = True
        if not changed:
            break
    moved = []
    for vid in touched:
        v, was = by_id[vid], start[vid]
        now = {"left": v["x"], "right": v["x"] + v["w"], "top": v["y"], "bottom": v["y"] + v["h"]}
        parts = [f"{k} {_fmt(round(was[k], 2))} -> {_fmt(now[k])}" for k in ("left", "right", "top", "bottom")
                 if abs(was[k] - now[k]) > 1e-9]
        if parts:
            moved.append(f"{vid}: " + ", ".join(parts))
    return moved, left
