"""The palette of a reference (design/reference/): an HTML page or an image, for gen_tokens.py --from.

    python design/scripts/ref_palette.py design/reference/mockup.png       prints what it found

HTML (.html, .htm, .svg): the page is drawn in headless Edge (edge_page.py) and every element's computed colours are
weighted: backgrounds by area, text colours by characters, SVG fills and strokes by count; also the font family and
the corner radius of card-sized boxes. Without Edge, the CSS colours are counted from the source text.
Images (.png, .jpg, .jpeg, .webp, .gif, .bmp): drawn into a canvas in headless Edge and the pixels counted in buckets
(no image library needed). An image gives colours only: fonts and corners stay as the base tokens have them.

Returns {"mode", "background", "card", "text", "brand": [hex, ...], "font", "container", "notes"}: background is the
largest surface, card the next one of the same mode, text the most used text colour (images: the most used colour
with 4.5:1 or more on the background), brand the saturated colours by weight, merged when they look alike.
"""
import base64, collections, json, math, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import colour as K  # noqa: E402

IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
          ".gif": "image/gif", ".bmp": "image/bmp"}
FONTS_PBI = {"segoe ui", "segoe ui semibold", "segoe ui light", "arial", "arial black", "calibri", "cambria",
             "candara", "consolas", "constantia", "corbel", "courier new", "din", "georgia", "lucida sans unicode",
             "tahoma", "times new roman", "trebuchet ms", "verdana"}

HTML_JS = r"""<script>window.addEventListener('load', function () {
  var W = document.documentElement.scrollWidth, H = document.documentElement.scrollHeight, out = {bg: {}, text: {}, mark: {}, radius: [], font: {}, shadow: 0};
  function add(m, c, w) { if (!c || c === 'transparent' || /rgba\([^)]*,\s*0\)$/.test(c)) return; m[c] = (m[c] || 0) + w; }
  var root = getComputedStyle(document.body).backgroundColor;
  if (/rgba\([^)]*,\s*0\)$/.test(root) || root === 'transparent') root = getComputedStyle(document.documentElement).backgroundColor;
  add(out.bg, root, W * H * 0.5);
  document.querySelectorAll('body *').forEach(function (el) {
    var s = getComputedStyle(el), r = el.getBoundingClientRect(), a = r.width * r.height;
    if (s.display === 'none' || s.visibility === 'hidden' || a < 1) return;
    var bg = s.backgroundColor, m = bg.match(/rgba?\(([^)]+)\)/);
    if (m) { var p = m[1].split(',').map(Number); if (p.length < 4 || p[3] > 0.5) add(out.bg, bg, a); }
    if (s.backgroundImage && s.backgroundImage.indexOf('gradient') >= 0) (s.backgroundImage.match(/rgba?\([^)]+\)|#[0-9a-f]{3,8}/gi) || []).forEach(function (c) { add(out.mark, c, a / 4); });
    var own = Array.prototype.filter.call(el.childNodes, function (n) { return n.nodeType === 3 && n.textContent.trim(); }).map(function (n) { return n.textContent.trim().length; }).reduce(function (x, y) { return x + y; }, 0);
    if (own) { add(out.text, s.color, own); var f = s.fontFamily.split(',')[0].replace(/["']/g, '').trim(); out.font[f] = (out.font[f] || 0) + own; }
    if (el instanceof SVGElement) { ['fill', 'stroke'].forEach(function (k) { var v = s[k]; if (v && v !== 'none' && v.indexOf('url') < 0) add(out.mark, v, 1); }); }
    var card = (m && (m[1].split(',').length < 4 || +m[1].split(',')[3] > 0.5)) || (s.boxShadow && s.boxShadow !== 'none') || parseFloat(s.borderTopWidth) >= 1;
    if (card && a > W * H * 0.01 && a < W * H * 0.5) { var rad = parseFloat(s.borderTopLeftRadius); if (rad >= 0) out.radius.push(rad); if (s.boxShadow && s.boxShadow !== 'none') out.shadow++; }
  });
  var pre = document.createElement('script'); pre.type = 'application/json'; pre.id = 'pbik-palette'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
});</script>"""

IMAGE_PAGE = r"""<!doctype html><html><body style="margin:0"><canvas id=c></canvas><script>
var img = new Image();
window.pageReady = new Promise(function (ok) { img.onload = function () {
  var k = Math.min(1, 480 / Math.max(img.width, img.height)), w = Math.max(1, Math.round(img.width * k)), h = Math.max(1, Math.round(img.height * k));
  var c = document.getElementById('c'); c.width = w; c.height = h; var g = c.getContext('2d'); g.drawImage(img, 0, 0, w, h);
  var d = g.getImageData(0, 0, w, h).data, b = {};
  for (var i = 0; i < d.length; i += 4) { if (d[i + 3] < 128) continue; var key = (d[i] >> 3) + ',' + (d[i + 1] >> 3) + ',' + (d[i + 2] >> 3); b[key] = (b[key] || 0) + 1; }
  var pre = document.createElement('script'); pre.type = 'application/json'; pre.id = 'pbik-palette'; pre.textContent = JSON.stringify({buckets: b, w: w, h: h}); document.body.appendChild(pre); ok(); };
  img.onerror = function () { ok(); }; });
img.src = '%s';
</script></body></html>"""


def _merge(weights, dist=0.06):
    """[(hex, weight)] merged when two colours are within dist in OKLab; heaviest first."""
    def lab(c):
        L, C, H = K.oklch(c)
        return L, C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    groups = []
    for c, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        p = lab(c)
        for g in groups:
            if math.dist(p, g[2]) < dist:
                g[1] += w
                break
        else:
            groups.append([c, w, p])
    return [(c, w) for c, w, _ in groups]


def _norm_weights(raw):
    out = collections.Counter()
    for c, w in raw.items():
        h = K.norm(c)
        if h:
            out[h] += w
    return out


def _pick(bg_w, text_w, mark_w):
    surfaces = _merge(bg_w, 0.03)
    background = surfaces[0][0] if surfaces else "#FFFFFF"
    mode = "dark" if K.oklch(background)[0] < 0.5 else "light"
    card = next((c for c, _ in surfaces[1:] if K.oklch(c)[1] < 0.05 and (K.oklch(c)[0] < 0.5) == (mode == "dark")
                 and abs(K.oklch(c)[0] - K.oklch(background)[0]) > 0.01), None)
    texts = [c for c, _ in _merge(text_w, 0.04) if K.oklch(c)[1] < 0.06]
    text = next((c for c in texts if K.contrast(c, background) >= 4.5), None)
    pool = collections.Counter()
    for src, k in ((bg_w, 1.0), (mark_w, 4000.0), (text_w, 50.0)):
        for c, w in src.items():
            if K.oklch(c)[1] >= 0.06:
                pool[c] += w * k
    brand = [c for c, _ in _merge(pool, 0.09)][:5]
    # a large dark chromatic surface (a header band or rail) leads in light mode: it becomes primary
    return mode, background, card, text, brand


def _edge_json(page):
    import edge_page
    dom = edge_page.dom(page, delay_ms=300)
    m = re.search(r'<script type="application/json" id="pbik-palette">(.*?)</script>', dom, re.S)
    return json.loads(m.group(1)) if m else None


def extract(path):
    p = pathlib.Path(path)
    if not p.exists():
        raise SystemExit(f"{path}: not found")
    notes = []
    ext = p.suffix.lower()
    font, container = None, {}
    try:
        import edge_page
        edge = edge_page.available()
    except Exception:
        edge = False
    if ext in IMAGES:
        if not edge:
            raise SystemExit("reading an image needs Microsoft Edge (headless); give brand colours instead")
        uri = f"data:{IMAGES[ext]};base64," + base64.b64encode(p.read_bytes()).decode()
        got = _edge_json(IMAGE_PAGE % uri) or {}
        buckets = collections.Counter()
        for key, n in (got.get("buckets") or {}).items():
            r, g, b = (int(x) * 8 + 4 for x in key.split(","))
            buckets[K.to_hex(r / 255, g / 255, b / 255)] += n
        if not buckets:
            raise SystemExit(f"{path}: Edge couldn't read the image")
        total = sum(buckets.values())
        surfaces = collections.Counter({c: n for c, n in buckets.items() if n / total > 0.02 or K.oklch(c)[1] < 0.05})
        text_w = collections.Counter({c: n for c, n in buckets.items() if K.oklch(c)[1] < 0.06})
        mark_w = collections.Counter({c: n / 4000 for c, n in buckets.items() if n / total < 0.25})
        mode, background, card, text, brand = _pick(surfaces, text_w, mark_w)
        notes.append("image reference: colours only; fonts, corners and shadows stay as the base tokens have them")
    elif ext in (".html", ".htm", ".svg", ".css"):
        src = p.read_text(encoding="utf-8", errors="replace")
        got = None
        if edge and ext != ".css":
            page = src if ext != ".svg" else f"<!doctype html><html><body style='margin:0'>{src}</body></html>"
            page = re.sub(r"<script\b(?![^>]*application/json)[^>]*>.*?</script>", "", page, flags=re.S | re.I)
            page = page.replace("</body>", HTML_JS + "</body>", 1) if "</body>" in page else page + HTML_JS
            got = _edge_json(page)
        if got:
            bg_w, text_w, mark_w = (_norm_weights(got[k]) for k in ("bg", "text", "mark"))
            if got.get("font"):
                font = max(got["font"].items(), key=lambda kv: kv[1])[0]
            rad = sorted(got.get("radius") or [])
            if rad:
                container["radius"] = int(round(rad[len(rad) // 2]))
            if got.get("shadow", 0) == 0 and rad:
                container["shadow"] = "0 0 0 rgba(0,0,0,0)"
                container["pbiShadow"] = {"_note": "No shadow in the reference.", "blur": 0, "distance": 0,
                                          "transparency": 100}
        else:                                       # no Edge: count the CSS colours in the source
            found = collections.Counter(K.norm(m) for m in re.findall(
                r"#[0-9A-Fa-f]{3,8}\b|rgba?\([^)]*\)", src) if K.norm(m))
            bodybg = re.search(r"(?:body|html|:root)[^{]*\{[^}]*background(?:-color)?\s*:\s*([^;}]+)", src)
            bg_w = collections.Counter({c: n for c, n in found.items() if K.oklch(c)[1] < 0.05})
            if bodybg and K.norm(bodybg.group(1).strip()):
                bg_w[K.norm(bodybg.group(1).strip())] += 10 ** 6
            text_w, mark_w = bg_w, collections.Counter({c: n / 1000 for c, n in found.items()})
            notes.append("Edge not available: colours counted from the source text, not from the drawn page")
        mode, background, card, text, brand = _pick(bg_w, text_w, mark_w)
    else:
        raise SystemExit(f"{path}: not an image or an HTML file ({', '.join(sorted(IMAGES))}, .html, .htm, .svg)")
    out = {"mode": mode, "background": background, "card": card, "text": text, "brand": brand, "notes": notes}
    if font:
        if font.lower() in FONTS_PBI:
            out["font"] = {"family": font}
        else:
            notes.append(f"font {font!r} isn't one of Power BI's built-in fonts: Segoe UI kept (a custom font needs a "
                         "theme font that every viewer has)")
    if container:
        out["container"] = container
    if not brand:
        notes.append("no saturated colour in the reference: the brand colour is derived from the primary hue")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    print(json.dumps(extract(sys.argv[1]), indent=2))
