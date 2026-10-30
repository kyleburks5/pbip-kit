"""Box wireframe (the fallback): draw design/wireframes/wireframe.html from design/specs/layout.json and tokens.json.

The kit default is the high-fidelity wireframe, gen_wireframe_hf.py; this one is for when that can't be drawn.
One box per visual at its layout position and z-order, in its token colours (style.fill / transparency / outline /
radius / shadow), with:
  - an ID badge (data-id="<ID>", the key audit_ids.py checks), toggled with B;
  - the visual type and name;
  - a build-method tag (native / svg-measure / html-measure / ...), toggled with T, coloured from tokens.tags;
  - text boxes show their `text`, other visuals their fields.
Several pages get tabs (keys 1-9 switch). The canvas scales to the window.
Real numbers and per-visual rendering are in gen_wireframe_hf.py and wireframe_data.py.
Usage: python design/scripts/gen_wireframe.py      (writes design/wireframes/wireframe.html)
"""
import html, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
T = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
LAY = json.loads((ROOT / "design" / "specs" / "layout.json").read_text(encoding="utf-8"))
C, K = T["colors"], T.get("container", {})
W, H = T.get("canvas", {}).get("width", 1920), T.get("canvas", {}).get("height", 1080)
FONT = T.get("font", {}).get("family", "Segoe UI")
OUT = ROOT / "design" / "wireframes" / "wireframe.html"


def token(v, default=None):
    """'card' -> colors.card; 'glass.panel' / 'container.radius' -> that value; '#hex' or numbers pass through."""
    if v is None:
        return default
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.startswith("#")):
        return v
    if isinstance(v, dict):             # {color, transparency} (page background); a theme colour has no hex here
        return token(v.get("color"), default)
    if isinstance(v, str) and v.startswith("theme:"):
        return default
    if v in C:
        return C[v]
    cur = T
    for k in str(v).split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def rgba(hex_, transparency):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{1 - float(transparency or 0) / 100:.3f})"


def tag_colours(method):
    tags = T.get("tags", {})
    key = {"svg-measure": "svg", "html-measure": "html"}.get(method, method)
    t = tags.get(key) or tags.get("native") or {}
    return token(t.get("text"), C.get("textMuted", "#555")), token(t.get("fill"), C.get("border", "#ddd"))


def plain_text(t):
    """layout `text`: "...", [(text, style)] or pbik's [{runs: [{text} or "..."], align}] / ["...", ...]."""
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        return plain_text(t.get("runs", t.get("text", "")))
    if isinstance(t, (list, tuple)):
        if len(t) == 2 and isinstance(t[0], str) and not isinstance(t[1], str):    # (text, style)
            return t[0]
        return "".join(plain_text(x) for x in t)
    return ""


def page_box(v):
    """x, y, w, h on the page; a group without its own box spans its members (as pbik build does)."""
    if v["type"] == "group" and not all(k in v for k in ("x", "y", "w", "h")):
        by_id = {x["id"]: x for x in LAY["visuals"]}
        bs = [page_box(by_id[m]) for m in v.get("members", [])]
        x0, y0 = min(b[0] for b in bs), min(b[1] for b in bs)
        return x0, y0, max(b[0] + b[2] for b in bs) - x0, max(b[1] + b[3] for b in bs) - y0
    return v["x"], v["y"], v["w"], v["h"]


def box(v):
    if v["type"] == "group":            # nothing to draw: an empty element so the ID is in the wireframe
        x, y, w, h = page_box(v)
        return (f'<div class="v group" data-id="{v["id"]}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
                f'z-index:0;background:none;outline:none;pointer-events:none" title="group {html.escape(v["name"])}">'
                f'</div>')
    st = v.get("style") or {}
    method = (v.get("build") or {}).get("method", "native")
    fill = token(st.get("fill"))
    css = [f"left:{v['x']}px", f"top:{v['y']}px", f"width:{v['w']}px", f"height:{v['h']}px",
           f"z-index:{int(v.get('z', 1)) * 1000 + int(v['id'].rsplit('V', 1)[1])}"]
    if fill:
        css.append(f"background:{rgba(fill, token(st.get('transparency'), 0))}")
    elif v["type"] not in ("textbox", "image"):
        css.append("background:repeating-linear-gradient(45deg,transparent 0 8px,rgba(127,127,127,.07) 8px 16px)")
    if st.get("outline"):
        css.append(f"border:{st.get('outlineWidth', 1)}px solid {token(st['outline'], C.get('border'))}")
    elif v["type"] not in ("textbox",):
        css.append(f"outline:1px dashed {rgba(C.get('textMuted', '#888'), 60)}")
    r = st.get("radius")
    css.append(f"border-radius:{token(r, 0) if r is not None else (K.get('radius', 0) if fill else 0)}px")
    if st.get("shadow") and K.get("shadow"):
        css.append(f"box-shadow:{K['shadow']}")
    tc, tf = tag_colours(method)
    body = ""
    if v["type"] == "textbox" and v.get("text"):
        text = plain_text(v["text"])
        size = token(str(st.get("font", "font.body")).replace("fontPt.", "font."), T.get("font", {}).get("body", 14))
        body = (f'<div class="text" style="color:{token(st.get("color"), C.get("text"))};font-size:{size}px">'
                f'{html.escape(text)}</div>')
    else:
        f = v.get("fields") or {}
        flat = [x for x in (f.values() if isinstance(f, dict) else f) if isinstance(x, str)]
        body = (f'<div class="type" style="color:{C.get("textMuted")}">{html.escape(v["type"])} · '
                f'{html.escape(v["name"])}</div>'
                + (f'<div class="fields" style="color:{C.get("textMuted")}">{html.escape(", ".join(flat))}</div>'
                   if flat else ""))
    return (f'<div class="v" data-id="{v["id"]}" style="{";".join(css)}" title="{html.escape(v.get("notes", ""))}">'
            f'<span class="badge">{v["id"]}</span>'
            f'<span class="tag" style="color:{tc};background:{tf}">{html.escape(method)}</span>{body}</div>')


pages = LAY.get("pages") or {"P1": {"displayName": "Page 1"}}
canvases, tabs = [], []
for n, (key, pg) in enumerate(pages.items()):
    bg = token(pg.get("background"), C.get("background", "#fff"))
    vis = [v for v in LAY["visuals"] if v.get("page", key) == key]
    canvases.append(f'<section class="page" data-page="{key}" style="background:{bg};{"" if n == 0 else "display:none"}">'
                    + "".join(box(v) for v in vis) + "</section>")
    tabs.append(f'<button data-page="{key}" class="{"on" if n == 0 else ""}">{n + 1} {html.escape(pg.get("displayName", key))}</button>')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Wireframe</title>
<style>
  body {{ margin:0; overflow:hidden; background:#2b2b2b; font-family:'{FONT}', sans-serif; }}
  header {{ display:flex; gap:8px; align-items:center; padding:8px 12px; color:#ddd; font-size:13px; }}
  header button {{ background:#444; color:#ddd; border:0; padding:4px 10px; border-radius:4px; cursor:pointer; }}
  header button.on {{ background:#ddd; color:#222; }}
  header .keys {{ margin-left:auto; opacity:.7; }}
  #wrap {{ overflow:hidden; margin:0 auto; }}
  #stage {{ width:{W}px; height:{H}px; transform-origin:0 0; position:relative; }}
  .page {{ position:absolute; inset:0; overflow:hidden; }}
  .v {{ position:absolute; box-sizing:border-box; overflow:hidden; padding:6px 8px; }}
  .badge {{ position:absolute; top:2px; left:2px; background:#111; color:#fff; font:600 11px/1 monospace;
           padding:3px 5px; border-radius:3px; z-index:2; }}
  .tag {{ position:absolute; top:2px; right:2px; font:600 10px/1 '{FONT}'; padding:3px 6px; border-radius:8px; z-index:2; }}
  .type {{ margin-top:18px; font-size:12px; }}
  .fields {{ font-size:11px; margin-top:2px; opacity:.85; }}
  .text {{ white-space:nowrap; }}
  body.nobadge .badge, body.notag .tag {{ display:none; }}
</style></head>
<body>
<header>{"".join(tabs)}<span class="keys">B badges · T tags · 1-9 pages · generic wireframe from layout.json</span></header>
<div id="wrap"><div id="stage">{"".join(canvases)}</div></div>
<script>
  const stage = document.getElementById('stage');
  const fit = () => {{
    const k = Math.min(innerWidth / {W}, (innerHeight - document.querySelector('header').offsetHeight) / {H});
    stage.style.transform = `scale(${{k}})`;
    const w = document.getElementById('wrap'); w.style.width = {W} * k + 'px'; w.style.height = {H} * k + 'px';
  }};
  addEventListener('resize', fit); fit();
  const show = key => {{
    document.querySelectorAll('.page').forEach(p => p.style.display = p.dataset.page === key ? '' : 'none');
    document.querySelectorAll('header button').forEach(b => b.classList.toggle('on', b.dataset.page === key));
  }};
  document.querySelectorAll('header button').forEach(b => b.onclick = () => show(b.dataset.page));
  addEventListener('keydown', e => {{
    const k = e.key.toLowerCase();
    if (k === 'b') document.body.classList.toggle('nobadge');
    if (k === 't') document.body.classList.toggle('notag');
    const btn = document.querySelectorAll('header button')[parseInt(e.key) - 1];
    if (btn) show(btn.dataset.page);
  }});
</script>
</body></html>
""", encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)}: {len(LAY['visuals'])} visuals on {len(pages)} page(s)")
