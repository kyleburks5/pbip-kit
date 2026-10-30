"""Build the Patterns page: a copy of Rep 8 with one page holding the best Desktop-saved example of each visual type.

    python tools/patterns/build_patterns.py                               (%PBIP_REP8% -> %PBIP_PATTERNS%)
    python tools/patterns/build_patterns.py --dest <folder> --spec tools/patterns/patterns.json
    python tools/patterns/build_patterns.py --page-only --dest <copy>      (rebuild only the Patterns page)

Steps (docs/lessons/build.md: templates come from files Desktop saved, never from guesses):
1. copy the Rep 8 project to --dest (not .git or _snapshots) and commit it there as a baseline, so the Desktop save
   that follows shows as a git diff (`pbik roundtrip` reads it);
2. for each pattern in patterns.json, take the visual.json Desktop saved in Rep 4, 5 or 8, give it a P4-V<nn> ID,
   place it on the grid, rebuild its query in layout notation against Rep 8's model where the source is another rep,
   copy Rep 8's container style onto it (`restyle`), drop formatting bound to fields Rep 8's model doesn't have, and
   drop actions (bookmarks and navigation belong to the report, not to a template);
3. write the page, register the image, run pbik validate.

Then: open pbip-patterns in Desktop, review, save; `pbik templates harvest` turns the saved page into
design/templates/ (README "Patterns page").

Paths: --src defaults to %PBIP_REP8%, else the Rep 8 fixture (tools/fixtures/rep8); --dest to %PBIP_PATTERNS%, else
..\pbip-patterns beside the kit. The `sources` in patterns.json are relative to the kit root (the fixtures); point
them at your own Rep folders to build from those.
"""
import argparse, copy, json, os, pathlib, re, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(KIT / "tools" / "pbik"))

from pbikit import build as B, fields as F  # noqa: E402
from pbikit.objects import b, chrome_off, image_objects, load, n, s, save, solid  # noqa: E402
from pbikit.fieldrefs import field_ok, refs_in, clean_visual  # noqa: E402
from pbikit.report import Report, stable_name  # noqa: E402

MARGIN, GUTTER, COLS, WIDTH = 32, 24, 12, 1920
COL = (WIDTH - 2 * MARGIN - (COLS - 1) * GUTTER) / COLS
DROP_TOP = ("parentGroupName", "isHidden", "howCreated")
CONTAINER = ("background", "border", "dropShadow", "padding", "title", "subTitle", "visualHeader", "divider", "spacing")
ICON = ('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
        '<circle cx="24" cy="24" r="23" fill="{fill}"/><circle cx="24" cy="18" r="7" fill="{ink}"/>'
        '<path d="M11 37c2-7 7-10 13-10s11 3 13 10" fill="{ink}"/></svg>')


def grid_box(p):
    if "box" in p:
        return p["box"]
    col, span = p["grid"]
    return [round(MARGIN + col * (COL + GUTTER), 2), p["y"], round(span * COL + (span - 1) * GUTTER, 2), p["h"]]


def find_visual(root, folder):
    hits = list(next(pathlib.Path(root).glob("*.Report")).glob(f"definition/pages/*/visuals/{folder}/visual.json"))
    if len(hits) != 1:
        raise SystemExit(f"{root}: visual folder {folder!r} found {len(hits)} times")
    return load(hits[0])


def recolour(d, src_root, style_root):
    """Literal colours from another rep's palette -> Rep 8's colour of the same token name (text -> text, ...)."""
    if pathlib.Path(src_root) == pathlib.Path(style_root):
        return
    a = load(pathlib.Path(src_root) / "design" / "tokens.json").get("colors", {})
    z = load(pathlib.Path(style_root) / "design" / "tokens.json").get("colors", {})
    m = {a[k].upper(): z[k] for k in a if k in z and k != "_note" and a[k].upper() != z[k].upper()}

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "Value" and isinstance(v, str) and v.startswith("'#") and v[1:-1].upper() in m:
                    node[k] = f"'{m[v[1:-1].upper()]}'"
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(d)


def set_title(vco, text):
    for e in vco.get("title", []):
        if "selector" not in e:
            e.setdefault("properties", {})["text"] = {"expr": {"Literal": {"Value": "'" + text.replace("'", "''") + "'"}}}
            e["properties"]["show"] = b(True)
            return
    vco.setdefault("title", []).append({"properties": {"show": b(True), "text": s(text)}})


# ---------------------------------------------------------------- one pattern
def make_visual(p, spec, rep, ctx, model, ext, style_src, notes, image_item=None):
    vid, name = p["id"], f"{p['id']}_{p['name']}"
    x, y, w, h = grid_box(p) if not p.get("sourceBox") else (None,) * 4
    if "image" in p:
        d = {"$schema": rep.schema_version("visualContainer"), "name": name, "position": {},
             "visual": {"visualType": "image", "objects": image_objects(image_item, "Fit"), "drillFilterOtherVisuals": True}}
        chrome_off(d)
        src_note = "constructed (no image visual in Reps 4, 5 or 8): pbikit.objects.image_objects"
    else:
        rep_key, folder = p["source"]
        d = copy.deepcopy(find_visual(spec["sources"][rep_key], folder))
        src_note = f"{rep_key} {folder}"
        if p.get("sourceBox"):
            pos = d["position"]
            x, y, w, h = pos["x"], pos["y"], pos["width"], pos["height"]
        for k in DROP_TOP:
            d.pop(k, None)
        d["name"] = name
        vis = d["visual"]
        vis.get("visualContainerObjects", {}).pop("visualLink", None)    # actions belong to the report
        if "bindings" in p or "sort" in p:
            vis.pop("query", None)
            B.apply_query(ctx, {"type": vis["visualType"], **{k: p[k] for k in ("bindings", "sort") if k in p}}, d)
        dropped = clean_visual(d, model, ext)
        if p.get("restyle"):
            src = style_src[p["restyle"]].get("visual", {}).get("visualContainerObjects", {})
            vco = vis.setdefault("visualContainerObjects", {})
            for k in CONTAINER:
                if k in src:
                    vco[k] = copy.deepcopy(src[k])
                else:
                    vco.pop(k, None)
        if "query" in vis and any(not field_ok(model, ext, *r) for r in refs_in(vis["query"])):
            raise SystemExit(f"{vid}: the source query binds fields Rep 8's model doesn't have; add `bindings`")
        recolour(d, spec["sources"][rep_key], spec["sources"]["rep8"])
        if p.get("props"):
            B.apply_props(ctx, vid, {"type": vis["visualType"], "props": p["props"]}, d)
        if p.get("title"):
            set_title(vis.setdefault("visualContainerObjects", {}), p["title"])
        if "text" in p:
            paras = vis.get("objects", {}).get("general", [{}])[0].get("properties", {}).get("paragraphs")
            if not paras or not paras[0].get("textRuns"):
                raise SystemExit(f"{vid}: `text` on a visual without text runs")
            first = paras[0]
            first["textRuns"] = [dict(first["textRuns"][0], value=p["text"])]     # keep the first run's style
            vis["objects"]["general"][0]["properties"]["paragraphs"] = [first]
        if dropped:
            src_note += f"; dropped (not in Rep 8's model): {', '.join(dropped)}"
    if d["visual"].get("visualContainerObjects") == {}:
        del d["visual"]["visualContainerObjects"]     # Desktop drops an empty one on save (Patterns save, 2026-10-19)
    x, y, w, h = (round(q) if isinstance(q, float) and q == round(q) else q for q in (x, y, w, h))
    idx = int(vid.rsplit("V", 1)[1])
    d["position"] = {"x": x, "y": y, "z": p.get("z", 1) * 1000 + idx, "height": h, "width": w, "tabOrder": idx * 100}
    notes.append({"id": vid, "type": d["visual"]["visualType"], "label": p["label"], "source": src_note})
    return name, d


def page_doc(rep, spec, pname):
    pg = spec["page"]
    return {"$schema": rep.schema_version("page"), "name": pname, "displayName": pg["displayName"],
            "displayOption": "FitToPage", "height": 1080, "width": 1920,
            "objects": {"background": [{"properties": {"color": solid(pg["background"]), "transparency": n(0)}}]}}


def git(dest, *args):
    return subprocess.run(["git", "-C", str(dest), *args], capture_output=True, text=True)


def copy_rep(src, dest):
    if dest.exists():
        raise SystemExit(f"{dest} exists: pass --page-only to rebuild the Patterns page in it, or remove it first")
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "_snapshots", "__pycache__"))
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    r = git(dest, "commit", "-q", "-m", f"Copy of {src.name} (baseline for the Patterns page)")
    if r.returncode:
        print(r.stdout + r.stderr)


def build_page(dest, spec, force=False):
    rep = Report(next(dest.glob("*.Report")))
    model = rep.model()
    ext = rep.extensions()
    ctx = B.Ctx(rep, {"measureTable": "_Measures"}, load(dest / "design" / "tokens.json"))
    style_src = {}
    for p in spec["patterns"]:
        if p.get("restyle") and p["restyle"] not in style_src:
            style_src[p["restyle"]] = find_visual(dest, p["restyle"])
    pname = stable_name("page", "patterns", spec["page"]["displayName"])
    pdir = rep.defn / "pages" / pname
    stem = next((p["image"] for p in spec["patterns"] if "image" in p), None)
    image_item = f"{stem}.png" if stem else None
    notes, docs = [], {}
    for p in spec["patterns"]:
        name, d = make_visual(p, spec, rep, ctx, model, ext, style_src, notes, image_item)
        docs[name] = d
    if (pdir / "page.json").exists() and not force:
        from pbikit.objects import dumps
        differs = [n_ for n_, d in docs.items() if not (pdir / "visuals" / n_ / "visual.json").exists() or
                   (pdir / "visuals" / n_ / "visual.json").read_text(encoding="utf-8") != dumps(d)]
        if differs:
            raise SystemExit(f"{pdir.name}: the Patterns page exists and {len(differs)} visual(s) differ from the spec "
                             f"(saved in Desktop?). Nothing written; pass --force to replace it.")
    if (pdir / "visuals").is_dir():                      # --page-only: only this page's ID'd visuals are rebuilt
        for f in (pdir / "visuals").iterdir():
            if f.is_dir() and f.name not in docs:
                shutil.rmtree(f)
    if stem:
        add_image(dest, rep, stem, load(dest / "design" / "tokens.json"))
    rep.write(pdir / "page.json", page_doc(rep, spec, pname))
    for name, d in docs.items():
        rep.write(pdir / "visuals" / name / "visual.json", d)
    meta = rep.pages_meta()
    if pname not in meta.setdefault("pageOrder", []):
        meta["pageOrder"].append(pname)
    rep.write(rep.defn / "pages" / "pages.json", meta)
    save(dest / "design" / "specs" / "patterns-sources.json",
         {"_note": "Written by tools/patterns/build_patterns.py: where each Patterns visual came from.", "visuals": notes})
    return rep, notes


def add_image(dest, rep, stem, tokens):
    c = tokens.get("colors", {})
    svg = ICON.format(fill=c.get("tealTint", "#E7F3F5"), ink=c.get("tealDark", "#026E75"))
    out = dest / "design" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.svg").write_text(svg, encoding="utf-8")
    png = out / f"{stem}.png"
    r = subprocess.run([sys.executable, str(KIT / "design" / "scripts" / "svg_to_png.py"), str(out / f"{stem}.svg"),
                        "--out", str(out)], capture_output=True, text=True)
    if not png.exists():
        raise SystemExit(f"svg_to_png failed: {r.stdout}{r.stderr}")
    subprocess.run([sys.executable, str(KIT / "tools" / "pbik" / "pbik.py"), "resource", "add", str(rep.path), str(png),
                    "--name", png.name], check=True, capture_output=True)
    return png.name


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default=os.environ.get("PBIP_REP8", str(KIT / "tools" / "fixtures" / "rep8")))
    ap.add_argument("--dest", default=os.environ.get("PBIP_PATTERNS", str(KIT.parent / "pbip-patterns")))
    ap.add_argument("--spec", default=str(HERE / "patterns.json"))
    ap.add_argument("--page-only", action="store_true", help="rebuild the Patterns page in an existing copy")
    ap.add_argument("--force", action="store_true", help="replace a Patterns page that differs (e.g. saved in Desktop)")
    a = ap.parse_args(argv)
    spec = load(a.spec)
    spec["sources"] = {k: str(KIT / v) for k, v in spec["sources"].items()}   # relative to the kit root
    dest = pathlib.Path(a.dest)
    if not a.page_only:
        copy_rep(pathlib.Path(a.src), dest)
    rep, notes = build_page(dest, spec, a.force)
    for x in notes:
        print(f"{x['id']}  {x['type']:30} {x['label']:40} <- {x['source']}")
    r = subprocess.run([sys.executable, str(KIT / "tools" / "pbik" / "pbik.py"), "validate", str(rep.path)],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr)
    for line in r.stdout.splitlines():
        if line.startswith("error") and "Patterns" in line:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
