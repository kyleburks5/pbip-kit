"""Smoke test after any tool or plugin update: one new card, one button slicer and one table on a "_smoke" page.

Built with pbik (the same path as a real build): a small layout written to design/specs/smoke-layout.json, then
`pbik build` with its own ID map, the same patches a rep would use, and `pbik validate`.
Reload in Desktop and check the three visuals against design/checks.md (/smoke does this and records VERSIONS.md).
The button slicer is sized for its items: they come from the open Desktop model (or --items), and the slicer gets a
rowCount x columnCount grid wide enough for the longest label at the token font size, wrapping onto rows if needed.
Usage: python design/scripts/smoke.py --measure "[Measure]" --column "Table[Column]" --table-columns "T[A],T[B]"
       [--items "A,B,C"]   (the slicer's labels, when Desktop isn't open)
       python design/scripts/smoke.py --remove      (deletes the _smoke page folder, its pages.json entry and the
                                                     smoke layout and map files; /smoke asks first)
"""
import argparse, json, math, shutil, sys

from pbik_helpers import (ROOT, Project, b, button_slicer_padding, chrome_off, font, i, load, n, put, s, save,
                          solid, tile_style)
from pbikit import slicerfit  # noqa: E402  (pbik_helpers puts tools/pbik on sys.path)

PAGE = "_smoke"
SPECS = ROOT / "design" / "specs"
ap = argparse.ArgumentParser()
ap.add_argument("--measure", help="[Measure] for the card")
ap.add_argument("--column", help="Table[Column] (text) for the button slicer")
ap.add_argument("--table-columns", help="comma-separated fields for the table: T[A],T[B],[Measure]")
ap.add_argument("--items", help="comma-separated slicer labels (default: from the open Desktop model)")
ap.add_argument("--remove", action="store_true")
a = ap.parse_args()

if a.remove:
    P = Project(layout=SPECS / "layout.json")
    pdir = P.page_dir(PAGE)
    if pdir:
        name = load(pdir / "page.json").get("name", pdir.name)
        shutil.rmtree(pdir)
        print(f"removed {pdir}")
        meta_f = pdir.parent / "pages.json"          # drop it from the page order too, or pages.json points at nothing
        if meta_f.exists():
            meta = load(meta_f)
            meta["pageOrder"] = [x for x in meta.get("pageOrder", []) if x != name]
            if meta.get("activePageName") == name:
                if meta["pageOrder"]:
                    meta["activePageName"] = meta["pageOrder"][0]
                else:
                    meta.pop("activePageName")
            save(meta_f, meta)
            print(f"removed {name} from {meta_f.name}")
    for f in (SPECS / "smoke-layout.json", SPECS / "smoke-visual-map.json"):
        if f.exists():
            f.unlink()
            print(f"removed {f.relative_to(ROOT)}")
    sys.exit(0)
if not (a.measure and a.column and a.table_columns):
    sys.exit("--measure, --column and --table-columns are required")

T = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
SLOT_W, BTN_H, GAP, MARGIN = 600, T.get("control", {}).get("height", 36), 6, 12 + 8   # button_slicer_padding: 12 + 8
if a.items:
    items = [x.strip() for x in a.items.split(",") if x.strip()]
else:
    port = slicerfit.discover_port()
    tbl, col = a.column.split("[", 1)
    try:
        items = slicerfit.dax_values(tbl.strip("'"), col.rstrip("]"), port, slicerfit.find_run_dax(ROOT)) if port else None
    except RuntimeError as e:
        items = None
        print(f"slicer items from Desktop failed: {e}")
    if not items:
        sys.exit("No slicer items: open the report in Desktop, or pass --items \"A,B,C\"")
need = math.ceil(max(slicerfit.text_px(x, T["fontPt"]["body"]) for x in items)) + MARGIN + 8   # 8px slack
cols = max(1, min(len(items), (SLOT_W + GAP) // (need + GAP)))
rows = math.ceil(len(items) / cols)
slicer_h = rows * BTN_H + (rows - 1) * GAP
print(f"slicer: {len(items)} item(s), longest needs ~{need}px: {rows} x {cols} grid, {SLOT_W} x {slicer_h}")

layout = {"_note": "Written by design/scripts/smoke.py.", "pages": {"P0": {"displayName": PAGE, "background": "background"}},
          "visuals": [
              {"id": "P0-V01", "name": "smoke-card", "page": "P0", "type": "cardVisual", "x": 32, "y": 32, "w": 300,
               "h": 160, "bindings": {"Data": [a.measure]}},
              {"id": "P0-V02", "name": "smoke-slicer", "page": "P0", "type": "advancedSlicerVisual",
               "x": 356, "y": 32, "w": SLOT_W, "h": slicer_h, "bindings": {"Values": [a.column]}, "items": items},
              {"id": "P0-V03", "name": "smoke-table", "page": "P0", "type": "tableEx", "x": 32, "y": 216, "w": 924,
               "h": 400, "bindings": {"Values": [c.strip() for c in a.table_columns.split(",")]}}]}
lf = SPECS / "smoke-layout.json"
lf.parent.mkdir(parents=True, exist_ok=True)
lf.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
P = Project(layout=lf)
T = P.tokens
C, F, PT, K = T["colors"], T["font"]["family"], T["fontPt"], T["container"]
P.build(map_path=SPECS / "smoke-visual-map.json")


# 1. New card: rounded tile (radius renders only with rectangleRoundedByPixel), label above, no "--" detail.
def card(d):
    o = d["visual"].setdefault("objects", {})
    tile_style(o, C["card"], 0, C["border"], K["radius"])
    put(o, "layout", {"calloutSize": n(75)})
    put(o, "value", {"fontFamily": font(F), "fontSize": n(PT["kpi"]), "fontColor": solid(C["text"]),
                     "labelDisplayUnits": n(1)}, {"id": "default"})
    put(o, "label", {"show": b(True), "position": s("aboveValue"), "fontSize": n(PT["label"]),
                     "fontColor": solid(C["textMuted"])}, {"id": "default"})
    chrome_off(d)


P.patch("P0-V01", card)


# 2. Button slicer, 36px buttons: padding Custom with 0 top and bottom, or the text disappears. An explicit
#    rowCount x columnCount grid (as Desktop saves it); without one Desktop picks its own tile width and scrolls.
def slicer(d):
    o = d["visual"].setdefault("objects", {})
    button_slicer_padding(o)
    put(o, "layout", {"rowCount": n(rows), "columnCount": n(cols), "columnPadding": n(GAP), "rowPadding": n(GAP)})
    for e in o["layout"]:
        e["properties"].pop("orientation", None)    # written by smoke.py before 2026-10-18; Desktop saves the grid only
    put(o, "value", {"fontFamily": font(F), "fontSize": n(PT["body"]), "fontColor": solid(C["text"])},
        {"id": "default"})
    put(o, "shapeCustomRectangle", {"tileShape": s("rectangleRoundedByPixel"),
                                    "rectangleRoundedCurve": i(T.get("control", {}).get("radius", 8))},
        {"id": "default"})
    chrome_off(d)


P.patch("P0-V02", slicer)


# 3. Table: word wrap off in cells, no totals.
def table(d):
    o = d["visual"].setdefault("objects", {})
    put(o, "values", {"wordWrap": b(False)})
    put(o, "total", {"totals": b(False)})
    put(o, "columnHeaders", {"wordWrap": b(False)})


P.patch("P0-V03", table)
r = P.validate(port="auto")
print("\nNow: close Desktop without saving, reopen, open the _smoke page, and check the card (rounded, label above, "
      "no '--'), the slicer (text visible in every button) and the table (no wrap, no scrollbar, no totals).")
sys.exit(1 if r.returncode else 0)
