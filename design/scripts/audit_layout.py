"""Consistency audit of the built report against design/specs/layout.json and design/tokens.json.

Every visual in layout.json is checked, by its folder "<id>_<name>" on its page (layout.pages[<page>].displayName):
- position and size equal the layout box (text boxes: pbik build's TEXT_FIT, y -6 and h +12, text box headroom);
- panel shapes: fill and transparency from the style tokens (glass), radius = tokens.container.radius, the outline
  as the style says, shadow on with the same signature on every panel (colour, blur, distance, angle, transparency,
  position, preset Custom);
- glass tiles (new cards whose style has a "tile" or glass fill): tile fill transparency, outline on, radius;
- glass cells (small-multiple new cards whose style has a "cell"): each cell's background transparency and border,
  and the inner tile transparent with no outline (the cell is the glass, not the card);
- a header band, if the layout has one: square, no outline, no shadow;
- visuals inside a panel, text boxes and images: no container background, border or shadow, and a z-order above
  their panel shape, so nothing hides behind the card;
- a visual whose build.method is "page-background" (a wallpaper) is checked on page.json instead of a visual folder;
- panels (layout.panels, optional): each panel's visuals sit above its shape in z-order.
Visual IDs themselves (missing, duplicate, retired) are checked by audit_ids.py.
Usage: python design/scripts/audit_layout.py        (read-only; prints a table and the list of mismatches)
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
T = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
K = T["container"]
LAY = json.loads((ROOT / "design" / "specs" / "layout.json").read_text(encoding="utf-8"))
TEXT_FIT = {"textbox": (-6, 12)}      # keep in step with pbik build (tools/pbik/pbikit/build.py)


def find_report():
    """The *.Report folder in the project root; with several, the one the .pbip file points to."""
    reports = sorted(ROOT.glob("*.Report"))
    if len(reports) > 1:
        linked = {(ROOT / a["report"]["path"]).resolve() for pbip in ROOT.glob("*.pbip")
                  for a in json.loads(pbip.read_text(encoding="utf-8-sig")).get("artifacts", []) if "report" in a}
        reports = [r for r in reports if r.resolve() in linked]
    if len(reports) != 1:
        raise SystemExit(f"Expected one *.Report folder (or one linked from a .pbip) in {ROOT}, found {len(reports)}.")
    return reports[0]


PAGES = find_report() / "definition" / "pages"
PAGE_DIRS = {json.loads(f.read_text(encoding="utf-8")).get("displayName"): f.parent for f in PAGES.glob("*/page.json")}
GL = T.get("glass", {})


def page_dir(v):
    """Folder of the visual's page, from layout.pages[<page key>].displayName."""
    return PAGE_DIRS.get(LAY.get("pages", {}).get(v.get("page"), {}).get("displayName"))


def token(path):
    """'glass.panel' / 'container.radius' -> value from tokens.json."""
    cur = T
    for k in str(path).split("."):
        cur = cur[k]
    return cur


def lit(v):
    """Literal value of a PBIR property ({"expr": {"Literal": {"Value": ...}}} or solid colour)."""
    if isinstance(v, dict):
        if "solid" in v:
            return lit(v["solid"]["color"])
        e = v.get("expr", {})
        if "Literal" in e:
            x = e["Literal"]["Value"]
            if not isinstance(x, str):
                return x
            x = x.strip("'")
            # PBIR numbers carry a D/L suffix (54D); colours like #F6EDED must keep their last letter.
            return x[:-1] if x[-1:] in ("D", "L") and x[:-1].replace(".", "", 1).lstrip("-").isdigit() else x
        if "Measure" in e:
            return "fx:" + e["Measure"]["Property"]
    return v


def props(obj, name, sel=None):
    """Merged properties of an object list (entries without a selector, or with the given selector id)."""
    out = {}
    for e in obj.get(name, []) or []:
        s = e.get("selector", {}).get("id")
        if s in (None, sel) or (sel is None and s == "default"):
            out.update({k: lit(v) for k, v in e.get("properties", {}).items()})
    return out


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return x


def on(d):
    return str(d.get("show")).lower() == "true"


rows, issues, shadows = [], [], {}
files = {}
for v in LAY["visuals"]:
    name = f"{v['id']}_{v['name']}"
    pdir = page_dir(v)
    if pdir is None:
        issues.append(f"{name}: page {v.get('page')} not found (layout.pages displayName vs the report)")
        continue
    f = pdir / "visuals" / name / "visual.json"
    f = f if f.exists() else None
    if f is None and (v.get("build") or {}).get("method") == "page-background":
        bg = json.dumps(json.loads((pdir / "page.json").read_text(encoding="utf-8")).get("objects", {}))
        stem = pathlib.Path(v.get("image", v["name"])).stem
        ok = stem in bg
        rows.append((name, "page background", ok, "page background image" if ok else "MISSING"))
        if not ok:
            issues.append(f"{name}: neither a visual nor the page background image ({stem})")
        continue
    if f is None:
        issues.append(f"{name}: missing")
        continue
    d = json.loads(f.read_text(encoding="utf-8"))
    files[v["id"]] = d
    if v["type"] == "group":            # a group's box is its members' (pbik build); its members are checked below
        rows.append((name, "group", True, f"{len(v.get('members', []))} member(s)"))
        continue
    pos, vis = d["position"], d["visual"]
    vco, obj = vis.get("visualContainerObjects", {}), vis.get("objects", {})
    x, y, w, h = v["x"], v["y"], v["w"], v["h"]
    if v["type"] in TEXT_FIT:
        dy, dh = TEXT_FIT[v["type"]]
        y, h = y + dy, h + dh
    ox, oy, parent = 0, 0, d.get("parentGroupName")
    while parent:                       # a member's position is relative to its group: add the groups' offsets
        gf = pdir / "visuals" / parent / "visual.json"
        if not gf.exists():
            issues.append(f"{name}: parentGroupName {parent} has no folder")
            break
        g = json.loads(gf.read_text(encoding="utf-8"))
        ox, oy, parent = ox + g["position"]["x"], oy + g["position"]["y"], g.get("parentGroupName")
    got = tuple(round(pos[k] + o) for k, o in (("x", ox), ("y", oy), ("width", 0), ("height", 0)))
    grid = got == (x, y, w, h)
    if not grid:
        issues.append(f"{name}: position {got} vs layout {(x, y, w, h)}")
    st = v.get("style") or {}
    note = ""
    if v["type"] == "shape":
        radius = props(obj, "shape").get("rectangleRoundedCurve")
        tile = props(obj, "shape").get("tileShape")
        outline, shadow = props(obj, "outline"), props(vco, "dropShadow") or props(obj, "dropShadow")
        r_ = st.get("radius", 0)             # a number, or a tokens.container name ("radius" / "container.radius")
        want_r = K.get(r_.split(".")[-1], 0) if isinstance(r_, str) else r_
        if num(radius or 0) != num(want_r) or (want_r and tile != "rectangleRoundedByPixel"):
            issues.append(f"{name}: radius {radius} / {tile} (token {want_r})")
        if st.get("outline"):
            if not on(outline) or str(outline.get("lineColor", "")).upper() != T["colors"][st["outline"]].upper():
                issues.append(f"{name}: outline {outline.get('show')} {outline.get('lineColor')} "
                              f"(want on, {st['outline']})")
        elif on(outline):
            issues.append(f"{name}: outline on (style says none)")
        fill = props(obj, "fill").get("fillColor", "")
        want_fill = T["colors"].get(st.get("fill"), "")
        if fill.upper() != want_fill.upper():
            issues.append(f"{name}: fill {fill} (token {st.get('fill')} {want_fill})")
        if st.get("transparency") and num(props(obj, "fill").get("transparency")) != num(token(st["transparency"])):
            issues.append(f"{name}: fill transparency {props(obj, 'fill').get('transparency')} "
                          f"(token {st['transparency']} {token(st['transparency'])})")
        cont = v.get("container") if isinstance(v.get("container"), dict) else {}
        if st.get("shadow") or cont.get("shadow"):   # shadow from style or from the container key (pbik)
            sig = tuple(str(num(shadow.get(k))).lower() for k in ("color", "shadowBlur", "shadowDistance", "angle",
                                                                 "transparency", "position", "preset"))
            shadows[name] = sig
            if not on(shadow) or str(shadow.get("preset")).lower() != "custom":
                issues.append(f"{name}: shadow {shadow.get('show')} preset {shadow.get('preset')} (want on, Custom)")
            note = f"radius {radius}, shadow {sig}"
        else:
            if on(shadow):
                issues.append(f"{name}: shadow on (style says none)")
            note = f"radius {radius}, no shadow"
    elif v["type"] == "cardVisual" and st.get("cell"):
        # Small-multiple cards: the glass is on each cell (fix 1), the inner tile is transparent.
        cell = props(obj, "smallMultiplesCellBackGround", "default")
        border = props(obj, "smallMultiplesBorder", "default")
        want_t = token(st["cell"]["transparency"])
        if not on({"show": cell.get("backgroundShow")}) or num(cell.get("backgroundTransparency")) != num(want_t):
            issues.append(f"{name}: cell background {cell.get('backgroundShow')} {cell.get('backgroundTransparency')} "
                          f"(token {st['cell']['transparency']} {want_t})")
        if not on({"show": border.get("gridlineShow")}) or str(border.get("gridlineColor", "")).upper() != T["colors"][st["cell"]["outline"]].upper():
            issues.append(f"{name}: cell border {border.get('gridlineShow')} {border.get('gridlineColor')}")
        if on(props(obj, "outline", "default")) or num(props(obj, "fillCustom", "default").get("transparency")) != 100:
            issues.append(f"{name}: inner tile not transparent (the cell is the glass)")
        note = f"glass cells, transparency {cell.get('backgroundTransparency')}"
    elif v["type"] == "cardVisual" and (st.get("tile") or st.get("fill") == "card"):
        tile_st = st.get("tile") or st
        fill_t = props(obj, "fillCustom", "default").get("transparency")
        line = props(obj, "outline", "default")
        rad = props(obj, "shapeCustomRectangle", "default").get("rectangleRoundedCurve")
        want_t = token(tile_st["transparency"])
        if num(fill_t) != num(want_t):
            issues.append(f"{name}: tile transparency {fill_t} (token {tile_st['transparency']} {want_t})")
        if not on(line) or str(line.get("lineColor", "")).upper() != T["colors"][tile_st["outline"]].upper():
            issues.append(f"{name}: tile outline {line.get('show')} {line.get('lineColor')}")
        if num(rad) != num(K["radius"]):
            issues.append(f"{name}: tile radius {rad} (token {K['radius']})")
        for label, part in (("background", props(vco, "background")), ("border", props(vco, "border")),
                            ("shadow", props(vco, "dropShadow"))):
            if on(part):
                issues.append(f"{name}: container {label} on (the tile is the card)")
        note = f"glass tile, transparency {fill_t}, radius {rad}"
    elif v.get("panel") or v["type"] in ("textbox", "image"):
        bg, border, sh = props(vco, "background"), props(vco, "border"), props(vco, "dropShadow")
        for label, part in (("background", bg), ("border", border), ("shadow", sh)):
            if on(part) and not (v["type"] == "slicer"):
                issues.append(f"{name}: container {label} on (inside a panel/band: off)")
        note = "bare" if not (on(bg) or on(border) or on(sh)) else "container layer on"
    rows.append((name, v["type"], grid, note))

# Panel shapes: one shadow signature.
if len(set(shadows.values())) > 1:
    issues.append(f"panel shadows differ: {shadows}")

# Z-order: each panel's contents above its shape; the band below the panels.
z = {vid: d["position"].get("z", 0) for vid, d in files.items()}
for ch, p in LAY.get("panels", {}).items():
    card = p["visuals"]["card"]
    for k, vid in p["visuals"].items():
        if k != "card" and vid in z and card in z and z[vid] <= z[card]:
            issues.append(f"{vid}: z {z[vid]} not above its panel shape {card} (z {z[card]})")
band = next((v["id"] for v in LAY["visuals"] if v["name"] == "header-band"), None)
for ch, p in LAY.get("panels", {}).items():
    if band and band in z and p["visuals"]["card"] in z and z[p["visuals"]["card"]] <= z[band]:
        issues.append(f"{p['visuals']['card']}: panel below the header band")

print("visual | type | on layout box | style")
for r in rows:
    print(" | ".join(str(x) for x in r))
print(f"\n{len(rows)} of {len(LAY['visuals'])} visuals found.")
print("\nISSUES:" if issues else "No issues.")
for i in issues:
    print(" -", i)
