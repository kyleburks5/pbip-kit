"""Render SVG files to transparent PNGs with headless Edge (no image library needed).

Static SVGs (icons, court lines, wallpaper) are rendered to PNG (the route tested in Desktop), registered once
(`pbik resource add`) and bound as a ResourcePackageItem (.claude/rules/svg.md).
The scale defaults to 4x the SVG's width/height attributes, so icons stay sharp when Power BI scales them; full-canvas
images (a 1920x1080 wallpaper) use --scale 1.
Usage: python design/scripts/svg_to_png.py <file.svg> [...] [--scale 4] [--out design/assets/png]
Extracted from Rep 6 gen_icons.py and Rep 7 gen_assets.py.
Edge 156 (2026-10-23) returns from the command before it has written the screenshot, so render() runs Edge with its
own temporary profile and waits until the PNG is complete (the PNG signature at the start, the IEND chunk at the end),
up to EDGE_WAIT seconds (default 30), keeping the page Edge reads in place until then.
"""
import argparse, os, pathlib, re, shutil, subprocess, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
EDGE = os.environ.get("EDGE", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
WAIT = float(os.environ.get("EDGE_WAIT", "30"))
PNG_SIGNATURE = bytes([137, 80, 78, 71, 13, 10, 26, 10])


def png_complete(f):
    """True once f is a whole PNG: the signature at the start and the IEND chunk at the end."""
    try:
        with open(f, "rb") as fh:
            head = fh.read(8)
            fh.seek(0, 2)
            if fh.tell() < 20:
                return False
            fh.seek(-12, 2)
            tail = fh.read(12)
    except OSError:
        return False
    return head == PNG_SIGNATURE and tail[4:8] == b"IEND"


def wait_for_png(f, timeout=None, poll=0.1):
    """Wait until f is a complete PNG; raise SystemExit after timeout seconds (default EDGE_WAIT)."""
    timeout = WAIT if timeout is None else timeout
    end = time.monotonic() + timeout
    while True:
        if png_complete(f):
            return f
        if time.monotonic() >= end:
            raise SystemExit(f"Edge didn't write {f} within {timeout:g}s (set EDGE_WAIT to wait longer, or EDGE to "
                             "another Edge or Chrome executable)")
        time.sleep(poll)


def size_of(svg):
    w = re.search(r'<svg[^>]*\swidth="([\d.]+)', svg)
    h = re.search(r'<svg[^>]*\sheight="([\d.]+)', svg)
    if not (w and h):
        raise SystemExit("the <svg> element needs numeric width and height attributes")
    return float(w.group(1)), float(h.group(1))


def render(svg, out, scale=4, timeout=None):
    """Write a transparent PNG of the SVG text at scale x its size; returns the path once the file is complete."""
    w, h = size_of(svg)
    pw, ph = round(w * scale), round(h * scale)
    big = re.sub(r'(<svg[^>]*\s)width="[\d.]+"', rf'\g<1>width="{pw}"', svg, count=1)
    big = re.sub(r'(<svg[^>]*\s)height="[\d.]+"', rf'\g<1>height="{ph}"', big, count=1)
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()                      # so the wait sees this render, not an earlier file
    d = pathlib.Path(tempfile.mkdtemp(prefix="svg_to_png-"))
    try:
        page = d / "svg.html"
        page.write_text(f'<html><body style="margin:0;background:transparent">{big}</body></html>', encoding="utf-8")
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        f"--user-data-dir={d / 'profile'}", "--default-background-color=00000000",
                        f"--window-size={pw},{ph}", f"--screenshot={out}", page.as_uri()],
                       check=True, capture_output=True)
        wait_for_png(out, timeout)        # Edge 156 returns first and writes later; the page stays until then
    finally:
        shutil.rmtree(d, ignore_errors=True)     # Edge may still hold its profile files for a moment
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--scale", type=float, default=4)
    ap.add_argument("--out", default=str(ROOT / "design" / "assets" / "png"))
    a = ap.parse_args()
    for f in a.files:
        p = pathlib.Path(f)
        print(render(p.read_text(encoding="utf-8"), pathlib.Path(a.out) / (p.stem + ".png"), a.scale))
