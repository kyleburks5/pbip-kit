"""WCAG 2.1 AA contrast of every text on the drawn wireframe (design/wireframes/wireframe.html), as a viewer sees it.

    python design/scripts/check_contrast.py                              the kit's wireframe
    python design/scripts/check_contrast.py path/to/wireframe.html --json out.json

The page is drawn in headless Edge (edge_page.py) with the ID badges and tags off. On every page, each element with
its own text (HTML text and SVG <text>) is measured against what is really behind it: the first opaque background in
the stack of elements under the text's centre (document.elementsFromPoint), semi-transparent colours blended over it.
4.5:1, or 3:1 for large text (24px and up, or 18.7px and up bold), as WCAG 2.1 AA. Hidden groups (bookmark panels) are
shown one at a time and checked too. Failures are listed by visual ID (data-id). Exit 1 on any failure, 3 when Edge
isn't available (not checked).

This checks the wireframe; `pbik validate` checks the built report's literal colours (pbikit/a11y.py). /theme runs
both.
"""
import argparse, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

JS = r"""<script>window.addEventListener('load', function () { Promise.resolve(window.pageReady0).catch(function () {}).then(function () { setTimeout(function () {
function parse(c) { var m = (c || '').match(/rgba?\(([^)]+)\)/); if (!m) return null; var p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
function lum(c) { return [0, 1, 2].map(function (i) { var x = c[i] / 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }).reduce(function (s, x, i) { return s + x * [0.2126, 0.7152, 0.0722][i]; }, 0); }
function ratio(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
function over(f, b) { var a = f[3]; return [f[0] * a + b[0] * (1 - a), f[1] * a + b[1] * (1 - a), f[2] * a + b[2] * (1 - a), 1]; }
function hex(c) { return '#' + c.slice(0, 3).map(function (x) { return ('0' + Math.round(x).toString(16)).slice(-2); }).join('').toUpperCase(); }
function bgOf(el, page) {
  var r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2, layers = [];
  var stack = document.elementsFromPoint(x, y), past = false;
  for (var i = 0; i < stack.length; i++) {
    var e = stack[i]; if (e === el || el.contains(e)) { past = true; }
    if (!past && !e.contains(el)) continue;
    var s = getComputedStyle(e), c = parse(s.backgroundColor);
    if (e instanceof SVGElement && e !== el && /^(rect|path|circle|polygon)$/.test(e.tagName)) { var fc = parse(s.fill); if (fc && fc[3] * parseFloat(s.fillOpacity || 1) > 0) { fc[3] *= parseFloat(s.fillOpacity || 1) * parseFloat(s.opacity || 1); c = fc; } }
    if (c && c[3] > 0) { layers.push(c); if (c[3] >= 0.999) break; }
    if (e === page) break;
  }
  var base = [255, 255, 255, 1]; for (var j = layers.length - 1; j >= 0; j--) base = over(layers[j], base);
  return base;
}
var out = [], pages = Array.prototype.slice.call(document.querySelectorAll('.page'));
function visible(el) { var s = getComputedStyle(el), r = el.getBoundingClientRect(); return s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05 && r.width > 0 && r.height > 0; }
function own(el) { if (el instanceof SVGElement) return el.tagName === 'text' || el.tagName === 'tspan' ? el.textContent.trim() : '';
  return Array.prototype.filter.call(el.childNodes, function (n) { return n.nodeType === 3; }).map(function (n) { return n.textContent; }).join('').trim(); }
function check(page, scope, pass) {
  scope.querySelectorAll('*').forEach(function (el) {
    if (el.closest('.badge, .tag, .nodata, .hiddenrows, .vlnote')) return;
    var t = own(el); if (!t || !visible(el)) return;
    if (el.tagName === 'tspan' && el.parentElement && own(el.parentElement)) return;
    var s = getComputedStyle(el), fg = parse(el instanceof SVGElement ? s.fill : s.color); if (!fg) return;
    fg[3] *= parseFloat(s.opacity || 1); if (el instanceof SVGElement) fg[3] *= parseFloat(s.fillOpacity || 1);
    var bg = bgOf(el, page), f = over(fg, bg), px = parseFloat(s.fontSize), bold = parseInt(s.fontWeight, 10) >= 600 || s.fontWeight === 'bold';
    var need = (px >= 24 || (bold && px >= 18.66)) ? 3 : 4.5, r = ratio(f, bg);
    var host = el.closest('[data-id]');
    out.push({page: page.dataset.page, id: host ? host.dataset.id : '', text: t.slice(0, 40), fg: hex(f), bg: hex(bg), ratio: Math.round(r * 100) / 100, need: need, px: px, bold: bold, pass: pass});
  });
}
pages.forEach(function (p) {
  pages.forEach(function (q) { q.classList.toggle('on', q === p); }); window.dispatchEvent(new Event('resize'));
  check(p, p, 'default');
  p.querySelectorAll('[data-was-hidden], [data-id][hidden]').forEach(function (g) { g.hidden = false; check(p, g, 'shown: ' + g.dataset.id); g.hidden = true; });
});
var pre = document.createElement('script'); pre.type = 'application/json'; pre.id = 'pbik-contrast'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
window.contrastDone = true; }, 100); }); });</script>"""


def measure(html_text):
    import edge_page
    page = html_text.replace("</body>", JS + "</body>", 1)
    page = page.replace("window.pageReady = Promise.allSettled(READY);",
                        "window.pageReady0 = Promise.allSettled(READY); window.pageReady = window.pageReady0.then("
                        "function () { return new Promise("
                        "function (ok) { (function w() { window.contrastDone ? ok() : setTimeout(w, 50); })(); }); });")
    dom = edge_page.dom(page, delay_ms=400, hash_="#labels=off&shot")
    m = re.search(r'<script type="application/json" id="pbik-contrast">(.*?)</script>', dom, re.S)
    if not m:
        raise RuntimeError("Edge didn't return the contrast results")
    return json.loads(m.group(1))


def summary(rows):
    fails = [r for r in rows if r["ratio"] + 1e-9 < r["need"]]
    lowest = min(rows, key=lambda r: r["ratio"] / r["need"]) if rows else None
    return fails, lowest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("wireframe", nargs="?", default=str(ROOT / "design" / "wireframes" / "wireframe.html"))
    ap.add_argument("--json", help="write every measured text here")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(errors="replace")
    import edge_page
    if not edge_page.available():
        print("not checked: Microsoft Edge isn't available")
        return 3
    rows = measure(pathlib.Path(a.wireframe).read_text(encoding="utf-8"))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    fails, lowest = summary(rows)
    for r in fails:
        print(f"FAIL {r['page']} {r['id'] or '(page)'} \"{r['text']}\": {r['fg']} on {r['bg']} {r['ratio']:.2f}:1, "
              f"needs {r['need']:g}:1 ({r['px']:g}px{' bold' if r['bold'] else ''}, {r['pass']})")
    pages = sorted({r["page"] for r in rows})
    print(f"{len(rows)} text(s) on {len(pages)} page(s): {len(rows) - len(fails)} pass WCAG 2.1 AA, {len(fails)} fail"
          + (f"; lowest {lowest['ratio']:.2f}:1 (needs {lowest['need']:g}) at {lowest['id']} \"{lowest['text']}\""
             if lowest else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
