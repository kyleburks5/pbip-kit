"""/theme: build design/tokens.json from brand colours, a reference (image or HTML) or a preset, with every text and
state colour moved until it passes WCAG 2.1 AA.

    python design/scripts/gen_tokens.py --brand "#0E1A2B,#F2B705,#E4572E" --mode dark
    python design/scripts/gen_tokens.py --brand "primary=#1F3864,brand=#2E75B6,bad=#C00000"
    python design/scripts/gen_tokens.py --from design/reference/mockup.png      (or .html / .htm / .css / .svg)
    python design/scripts/gen_tokens.py --preset bento                          (design/themes/presets/<name>.json)
    python design/scripts/gen_tokens.py                                         the default preset (clean)
    ... --base T --out T --report R --dry-run

Sources, first match wins: --brand, then --from, then --preset (default clean). A preset is used only when no brand
colours or reference are given. The output keeps everything in --base (canvas, fonts, polarity, rep keys such as
`series` or `heat`) and replaces `colors`, `chart.series` and `tags`; a preset or reference also sets its font,
container and control values. Rep-specific colour names in the base that the theme doesn't derive are kept and checked
as text on card and background.

Roles. Brand colours are given in order or by role (`primary=`, `brand=`, `bad=`, `good=`, `second=`, and any other
`name=` as an extra series colour). Unnamed colours are assigned: primary (light mode: the darkest colour when it is
dark, else the first; dark mode: the darkest), bad (the first red or orange-red), good (the first green or teal),
brand (the first of the rest), second (the next), extras to the chart series. Missing roles are derived from
the primary hue. Every name the kit's layouts use is written: the roles (primary, brand*, good*, bad*, second*) and the
names the clean palette introduced (teal* = brand, red* = bad marks, slate* = second, accent = bad, warning = second as
text), so an existing layout re-skins without edits.

Mode: light (white cards on a tinted canvas) or dark (cards a step lighter than a dark canvas). --mode auto: the
reference's own background decides; with brand colours, light.

AA (CHECKS below): text 4.5:1 on every surface it sits on, large text is not assumed; selected tiles 3:1 against the
card (the state must show) and their text 4.5:1; chart marks 3:1 against the card. A colour that fails is moved in
OKLCH lightness only (colour.reach: same hue, smallest move). Given colours (brand, preset, reference) that moved are
listed as changes; the report (design/reviews/theme.md) lists every check with its ratio. Exit 1 if a check can't be
met.
"""
import argparse, copy, datetime, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import colour as K  # noqa: E402

PRESETS = ROOT / "design" / "themes" / "presets"
DEFAULT_PRESET = "clean"
ROLES = ("primary", "brand", "bad", "good", "second")

# (foreground, background, ratio, which side moves, what the pair is). Text pairs are 4.5:1; "state" and "mark" pairs
# are WCAG 1.4.11 non-text contrast (3:1). Names missing from a palette are skipped.
CHECKS = [
    ("text", "card", 4.5, "fg", "text on cards"),
    ("text", "background", 4.5, "fg", "text on the canvas"),
    ("textMuted", "card", 4.5, "fg", "muted text on cards"),
    ("textMuted", "background", 4.5, "fg", "muted text on the canvas"),
    ("primaryText", "card", 4.5, "fg", "primary as text on cards (buttons)"),
    ("primaryText", "background", 4.5, "fg", "primary as text on the canvas"),
    ("onDark", "primary", 4.5, "fg", "text on primary bands"),
    ("onDarkMuted", "primary", 4.5, "fg", "muted text on primary bands"),
    ("selected", "card", 3.0, "fg", "selected tile against an unselected one (state)"),
    ("onSelected", "selected", 4.5, "bg", "text on selected tiles (state)"),
    ("brandText", "card", 4.5, "fg", "brand text on cards"),
    ("brandText", "background", 4.5, "fg", "brand text on the canvas"),
    ("brandText", "brandTint", 4.5, "fg", "brand text on brand chips"),
    ("good", "card", 4.5, "fg", "good (improvement) text on cards"),
    ("good", "goodTint", 4.5, "fg", "good text on good chips"),
    ("good", "background", 4.5, "fg", "good text on the canvas"),
    ("bad", "card", 4.5, "fg", "bad (decline) text on cards"),
    ("bad", "badTint", 4.5, "fg", "bad text on bad chips"),
    ("bad", "background", 4.5, "fg", "bad text on the canvas"),
    ("warning", "card", 4.5, "fg", "secondary text on cards"),
    ("warning", "background", 4.5, "fg", "secondary text on the canvas"),
    ("warning", "secondTint", 4.5, "fg", "secondary text on secondary chips (native tag)"),
    ("text", "brandTint", 4.5, "bg", "text on brand chips"),
    ("text", "secondTint", 4.5, "bg", "text on secondary chips"),
    ("text", "badLight", 4.5, "bg", "text on the darkest heat cell (bad light)"),
    ("text", "brandLight", 4.5, "bg", "text on brand light fills"),
    ("html", "htmlTint", 4.5, "fg", "HTML tag text"),
    ("brand", "card", 3.0, "fg", "brand marks (bars, lines) on cards"),
    ("badMark", "card", 3.0, "fg", "bad marks on cards"),
    ("second", "card", 3.0, "fg", "secondary marks on cards"),
]

# names the clean palette (and every layout built from it) uses -> the role they now follow
ALIASES = {"teal": "brand", "tealDark": "brandText", "tealLight": "brandLight", "tealMid": "brandMid",
           "tealTint": "brandTint", "red": "badMark", "redLight": "badLight", "redTint": "badTint",
           "slate": "second", "slateLight": "secondLight", "slateTint": "secondTint", "accent": "bad",
           "neutral": "textMuted"}
FONTS_PBI = {"segoe ui", "segoe ui semibold", "segoe ui light", "arial", "arial black", "calibri", "cambria",
             "candara", "consolas", "constantia", "corbel", "courier new", "din", "georgia", "lucida sans unicode",
             "tahoma", "times new roman", "trebuchet ms", "verdana", "wingdings"}


def load(f):
    return json.loads(pathlib.Path(f).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- roles
def hue_band(c):
    L, C, H = K.oklch(c)
    if C < 0.04:
        return "neutral"
    if H < 50 or H >= 345:
        return "red"
    if H < 115:
        return "yellow"
    if H < 215:
        return "green"
    if H < 290:
        return "blue"
    return "purple"


def parse_brand(text):
    """'#a,#b' or 'primary=#a,brand=#b,x=#c' -> (ordered unnamed, {role: hex})."""
    free, named = [], {}
    for part in re.split(r"[,\s;]+", text.strip()):
        if not part:
            continue
        name, _, val = part.rpartition("=")
        c = K.norm(val)
        if not c:
            raise SystemExit(f"--brand: {part!r} is not a colour (#RRGGBB)")
        (named.__setitem__(name, c) if name else free.append(c))
    return free, named


def assign(free, named, mode):
    """{role: hex} plus the extra series colours."""
    roles = {k: v for k, v in named.items() if k in ROLES}
    extras = [v for k, v in named.items() if k not in ROLES]
    rest = [c for c in free if c not in roles.values()]
    if "primary" not in roles and rest:
        darkest = min(rest, key=lambda c: K.oklch(c)[0])
        roles["primary"] = darkest if (mode == "dark" or K.oklch(darkest)[0] < 0.5) else rest[0]
        rest.remove(roles["primary"])
    for role, band in (("bad", "red"), ("good", "green")):
        if role not in roles:
            hit = next((c for c in rest if hue_band(c) == band), None)
            if hit:
                roles[role] = hit
                rest.remove(hit)
    if "brand" not in roles and rest:
        roles["brand"] = rest.pop(0)
    if "second" not in roles and rest:
        roles["second"] = rest.pop(0)
    return roles, extras + rest


# ---------------------------------------------------------------- derive
def derive(roles, mode, surfaces=None, pinned=None, extras=()):
    """The full palette. surfaces: background / card / text from a reference (given colours); pinned: a preset's full
    palette (given colours). Returns (colors, origin {name: 'given'|'derived'})."""
    surfaces, pinned = surfaces or {}, pinned or {}
    P = roles.get("primary") or roles.get("brand") or "#12343B"
    L0, C0, H0 = K.oklch(P)
    if C0 < 0.02 and roles.get("brand"):          # a grey primary: take the canvas tint from the brand hue
        H0 = K.oklch(roles["brand"])[2]
    cs = min(C0, 0.012)
    c = {}
    if mode == "dark":
        base = surfaces.get("background") or (P if L0 < 0.3 else K.from_oklch(0.2, min(C0, 0.04), H0))
        bl = K.oklch(base)[0]
        c["primary"] = P if L0 < 0.3 else K.with_l(P, max(0.1, bl - 0.03))
        c["background"] = base if surfaces.get("background") else K.with_l(base, bl + 0.035)
        c["card"] = surfaces.get("card") or K.with_l(c["background"], K.oklch(c["background"])[0] + 0.045)
        c["border"] = K.with_l(c["card"], K.oklch(c["card"])[0] + 0.09)
        c["text"] = surfaces.get("text") or K.from_oklch(0.965, 0.008, H0)
        c["textMuted"] = K.from_oklch(0.80, 0.02, H0)
    else:
        c["primary"] = P
        c["background"] = surfaces.get("background") or K.from_oklch(0.968, cs, H0)
        c["card"] = surfaces.get("card") or "#FFFFFF"
        c["border"] = K.mix(c["card"], K.from_oklch(0.86, cs + 0.004, H0), 0.75)
        c["text"] = surfaces.get("text") or K.from_oklch(0.27, min(C0, 0.03), H0)
        c["textMuted"] = K.from_oklch(0.50, min(C0, 0.025), H0)
    card = c["card"]

    def light(x):                               # a faded fill: a pastel already is one
        return x if mode == "light" and K.oklch(x)[0] >= 0.8 else K.mix(x, card, 0.55)

    brand = roles.get("brand") or (P if C0 > 0.06 and 0.35 < L0 < 0.85 else K.from_oklch(0.58, max(C0, 0.11), H0))
    c["brand"] = brand
    c["brandText"] = brand
    c["brandTint"] = K.mix(brand, card, 0.88)
    c["brandLight"] = light(brand)
    c["brandMid"] = K.mix(brand, card, 0.3)
    c["selected"] = brand

    bad = roles.get("bad") or K.from_oklch(0.55, 0.15, 25)
    c["badMark"] = bad
    c["bad"] = bad
    c["badLight"] = light(bad)
    c["badTint"] = K.mix(bad, card, 0.9)
    good = roles.get("good") or (brand if hue_band(brand) == "green" and K.hue_distance(brand, bad) > 60
                                 else K.from_oklch(0.52, 0.10, 175))
    c["good"] = good
    c["goodTint"] = K.mix(good, card, 0.9)

    second = roles.get("second") or K.from_oklch(0.55 if mode == "light" else 0.72, 0.045, (H0 + 20) % 360)
    c["second"] = second
    c["secondLight"] = light(second)
    c["secondTint"] = K.mix(second, card, 0.9)
    c["warning"] = second
    c["neutralTint"] = c["background"]
    c["html"] = K.from_oklch(0.50 if mode == "light" else 0.78, 0.12, 305)
    c["htmlTint"] = K.mix(c["html"], card, 0.88)
    for i, x in enumerate(extras):
        c[f"series{i + 1}"] = x

    origin = {k: "derived" for k in c}
    for r, v in roles.items():                   # the brand colours as given (role names and their copies)
        for k in {"primary": ["primary"], "brand": ["brand", "brandText", "selected"], "bad": ["bad", "badMark"],
                  "good": ["good"], "second": ["second", "warning"]}[r]:
            origin[k] = "given"
    for k in surfaces:
        if k in c:
            origin[k] = "given"
    for k, v in pinned.items():                  # a preset's palette: as given, then checked like the rest
        if k.startswith("_") or not K.norm(v):
            continue
        c[k] = K.norm(v)
        origin[k] = "given"
    for old, role in ALIASES.items():            # a preset may set the clean names: they lead their role
        if old in pinned and K.norm(pinned[old]) and role not in pinned:
            c[role] = K.norm(pinned[old])
            origin[role] = "given"
    # text on primary and on selected tiles follows the final fills (unless the preset sets it)
    if "onDark" not in pinned:
        c["onDark"] = K.best_text(c["primary"], (c["text"], "#FFFFFF", K.from_oklch(0.2, 0.02, H0)))
    if "onDarkMuted" not in pinned:
        c["onDarkMuted"] = K.mix(c["onDark"], c["primary"], 0.22)
    if "primaryText" not in pinned:
        c["primaryText"] = c["primary"]
    if "shadow" not in pinned:
        c["shadow"] = "#000000" if mode == "dark" else (c["primary"] if K.oklch(c["primary"])[0] < 0.45 else c["text"])
    if "onSelected" not in pinned:
        c["onSelected"] = K.best_text(c["selected"], (c["text"], "#FFFFFF", c["primary"]))
    return c, origin


def enforce(c, origin, extra_text=()):
    """Move colours until every CHECKS pair passes. Returns (changes, checks, failures)."""
    rules = list(CHECKS) + [(n, bg, 4.5, "fg", f"{n} (rep colour) as text") for n in extra_text
                            for bg in ("card", "background")]
    first = {k: v for k, v in c.items()}
    failures = []
    for _ in range(4):                          # later rules can move a colour an earlier rule used
        moved = False
        for fg, bg, ratio, side, what in rules:
            if fg not in c or bg not in c:
                continue
            if K.contrast(c[fg], c[bg]) + 1e-9 >= ratio:
                continue
            if side == "fg":
                new = K.reach(c[fg], [c[bg]], ratio)
                key = fg
            else:
                new = K.reach(c[bg], [c[fg]], ratio)
                key = bg
            if new is None:
                continue
            c[key] = new
            moved = True
        if not moved:
            break
    checks = []
    for fg, bg, ratio, side, what in rules:
        if fg in c and bg in c:
            r = K.contrast(c[fg], c[bg])
            checks.append({"fg": fg, "bg": bg, "need": ratio, "ratio": round(r, 2), "what": what,
                           "pass": r + 1e-9 >= ratio})
            if r + 1e-9 < ratio:
                failures.append(f"{fg} {c[fg]} on {bg} {c[bg]}: {r:.2f}:1, needs {ratio:g}:1 ({what})")
    changes = []
    for k, v in c.items():
        if first.get(k) and first[k] != v:
            pair = next((x for x in checks if k in (x["fg"], x["bg"])), None)
            changes.append({"name": k, "from": first[k], "to": v, "origin": origin.get(k, "derived"),
                            "why": pair["what"] if pair else ""})
    return changes, checks, failures


def with_aliases(c):
    out = dict(c)
    for old, role in ALIASES.items():
        if role in c:
            out[old] = c[role]
    return out


# ---------------------------------------------------------------- tokens
def build_tokens(base, colors, mode, source, preset=None, ref=None, changes=(), extras=0):
    t = copy.deepcopy(base)
    t["colors"] = {"_note": (f"From /theme ({source}), mode {mode}: generated by design/scripts/gen_tokens.py; every "
                             "text and state pair is WCAG 2.1 AA (design/reviews/theme.md). Roles: primary (bands, "
                             "with onDark text; primaryText as text), brand (marks; brandText as text), bad / badMark, good, second "
                             "(warning as text), selected + onSelected. teal*/red*/slate*/accent/neutral follow "
                             "their roles so layouts written for the clean palette re-skin unchanged."),
                   **colors}
    series = ["brand", "badMark", "second", "primary" if K.contrast(colors["primary"], colors["card"]) >= 3 else "text",
              "brandLight", "secondLight"] + [f"series{i + 1}" for i in range(extras)]
    t.setdefault("chart", {}).update({"_note": "Series order for the theme's dataColors, as names from colors.",
                                      "series": series[:4] + series[6:] + series[4:6]})
    t["tags"] = {"_note": "Wireframe tags (press T): native / svg / html; text 4.5:1 on its fill.",
                 "native": {"text": "warning", "fill": "secondTint"},
                 "svg": {"text": "brandText", "fill": "brandTint"},
                 "html": {"text": "html", "fill": "htmlTint"}}
    for src in (preset or {}, ref or {}):
        for key in ("font", "container", "control", "fontPt"):
            if isinstance(src.get(key), dict):
                t.setdefault(key, {}).update(src[key])
    if mode == "dark":                          # a dark shadow on a dark canvas: deeper and darker
        sh = t.setdefault("container", {})
        sh.setdefault("shadow", "0 1px 2px rgba(0,0,0,0.30), 0 6px 16px rgba(0,0,0,0.35)")
        if not (preset or {}).get("container", {}).get("shadow") and not (ref or {}).get("container", {}).get("shadow"):
            sh["shadow"] = "0 1px 2px rgba(0,0,0,0.30), 0 6px 16px rgba(0,0,0,0.35)"
            sh["pbiShadow"] = {"_note": sh.get("pbiShadow", {}).get("_note", "Power BI shadow."), "blur": 12,
                               "distance": 3, "transparency": 70}
    t["theme"] = {"_note": "How these tokens were made (gen_tokens.py). recolourTemplates: pbik build maps the "
                           "templates' clean colours to these names (design/templates/palette.json).",
                  "source": source, "mode": mode, "preset": (preset or {}).get("name"),
                  "made": datetime.date.today().isoformat(), "recolourTemplates": True,
                  "changed": [f"{x['name']}: {x['from']} -> {x['to']} ({x['why']})" for x in changes
                              if x["origin"] == "given"]}
    return t


def report_md(t, changes, checks, failures, source, notes=()):
    c = t["colors"]
    lines = [f"# Theme report", "", f"Source: {source}. Mode: {t['theme']['mode']}. Made by design/scripts/gen_tokens.py "
             f"on {t['theme']['made']}.", ""]
    given = [x for x in changes if x["origin"] == "given"]
    lines += ["## What changed", ""]
    if given:
        lines += ["Given colours moved (same hue, smallest lightness change) to pass WCAG 2.1 AA:", "",
                  "| Name | Given | Now | Why |", "| --- | --- | --- | --- |"]
        lines += [f"| {x['name']} | `{x['from']}` | `{x['to']}` | {x['why']} |" for x in given]
    else:
        lines.append("No given colour needed a change.")
    derived = [x for x in changes if x["origin"] != "given"]
    if derived:
        lines += ["", f"{len(derived)} derived colour(s) were tuned after derivation: "
                  + ", ".join(f"{x['name']} {x['to']}" for x in derived) + "."]
    lines += list(notes)
    lines += ["", "## Checks", "", "| Pair | Foreground | Background | Ratio | Needs | |", "| --- | --- | --- | --- | --- | --- |"]
    for x in checks:
        lines.append(f"| {x['what']} | {x['fg']} `{c[x['fg']]}` | {x['bg']} `{c[x['bg']]}` | {x['ratio']:.2f}:1 | "
                     f"{x['need']:g}:1 | {'pass' if x['pass'] else '**FAIL**'} |")
    if failures:
        lines += ["", "## Failed", ""] + [f"- {f}" for f in failures]
    lines += ["", "## Palette", "", "| Name | Colour |", "| --- | --- |"]
    lines += [f"| {k} | `{v}` |" for k, v in c.items() if not k.startswith("_")]
    return "\n".join(lines) + "\n"


def run(brand=None, ref=None, preset=None, mode="auto", base=None, layout=None):
    """Returns (tokens, changes, checks, failures, source, notes)."""
    base = base if base is not None else {}
    notes = []
    pre, refd, surfaces, pinned = None, None, {}, {}
    if brand:
        free, named = parse_brand(brand)
        mode = "light" if mode == "auto" else mode
        roles, extras = assign(free, named, mode)
        source = f"brand colours {', '.join(free + list(named.values()))}"
    elif ref:
        import ref_palette
        refd = ref_palette.extract(ref)
        mode = refd["mode"] if mode == "auto" else mode
        roles, extras = assign(refd["brand"], {}, mode)
        surfaces = {k: refd[k] for k in ("background", "card", "text") if refd.get(k)}
        if refd["mode"] != mode:                 # the reference's surfaces belong to its own mode
            surfaces = {}
        source = f"reference {pathlib.Path(ref).name}"
        notes += [""] + [f"- {n}" for n in refd.get("notes", [])]
    else:
        name = preset or DEFAULT_PRESET
        f = PRESETS / f"{name}.json"
        if not f.exists():
            raise SystemExit(f"no preset {name!r} ({', '.join(p.stem for p in sorted(PRESETS.glob('*.json')))})")
        pre = load(f)
        mode = pre.get("mode", "light") if mode == "auto" else mode
        free, named = parse_brand(",".join(pre.get("brand", [])))
        roles, extras = assign(free, named, mode)
        pinned = pre.get("colors", {}) if mode == pre.get("mode", "light") else {}
        source = f"preset {name}"
    colors, origin = derive(roles, mode, surfaces, pinned, extras)
    known = set(colors) | set(ALIASES)
    extra_text = []
    for k, v in (base.get("colors") or {}).items():   # rep colour names the theme doesn't make: kept, checked as text
        if not k.startswith("_") and k not in known and K.norm(v) and k not in ("onSelected", "selected"):
            if k.startswith("series"):
                continue
            colors[k] = K.norm(v)
            origin[k] = "given"
            extra_text.append(k)
    if extra_text:
        notes.append(f"\nKept from the base tokens (not part of the theme, checked as text): {', '.join(extra_text)}.")
    changes, checks, failures = enforce(colors, origin, extra_text)
    tokens = build_tokens(base, with_aliases(colors), mode, source, pre, refd, changes, len(extras))
    return tokens, changes, checks, failures, source, notes


# ---------------------------------------------------------------- layout roles
SELECTED_SEL = re.compile(r'@\{"id": "(selection:selected|selected|press)"\}$')
TEXT_KEY = re.compile(r"(font|label|title|value|detail|text)color(@|$)|\.color$|^color$", re.I)
TEXT_FOR = {"card": "onDark", "background": "onDark", "primary": "primaryText", "teal": "tealDark",
            "brand": "brandText", "red": "bad", "badMark": "bad", "slate": "warning", "second": "warning"}


def layout_roles(layout, colors):
    """Colour names a layout uses in a role the palette doesn't promise to pass: a fill colour as text (card text on a
    band is onDark, primary as text is primaryText, a mark colour as text is its text role) and selected states that
    don't use selected / onSelected. Returns [(id, where, old, new)]; fix_layout() applies them."""
    out = []

    def text_ok(name):
        return name not in TEXT_FOR or TEXT_FOR[name] not in colors

    for v in layout.get("visuals", []):
        vid = v.get("id")
        for k, val in (v.get("props") or {}).items():
            if not isinstance(val, str) or val not in colors:
                continue
            if SELECTED_SEL.search(k):
                want = "onSelected" if TEXT_KEY.search(k.split("@")[0]) else "selected"
                if val != want and want in colors:
                    out.append((vid, f"props {k}", val, want))
                continue
            if TEXT_KEY.search(k.split("@")[0]) and not text_ok(val):
                out.append((vid, f"props {k}", val, TEXT_FOR[val]))
        for ri, rl in enumerate(v.get("referenceLines") or []):     # the line's colour is also its label's
            if isinstance(rl, dict) and isinstance(rl.get("color"), str) and rl.get("dataLabel", True)                     and not text_ok(rl["color"]):
                out.append((vid, f"referenceLines[{ri}].color", rl["color"], TEXT_FOR[rl["color"]]))
        nav = v.get("navigator") or {}
        for state, val in (nav.get("colors") or {}).items():
            if isinstance(val, str) and not text_ok(val):
                out.append((vid, f"navigator.colors.{state}", val, TEXT_FOR[val]))
        for ri, run in enumerate((v.get("text") or {}).get("runs", []) if isinstance(v.get("text"), dict) else []):
            if isinstance(run, dict) and isinstance(run.get("color"), str) and not text_ok(run["color"]):
                out.append((vid, f"text.runs[{ri}].color", run["color"], TEXT_FOR[run["color"]]))
    return out


def fix_layout(layout, roles):
    for vid, where, old, new in roles:
        v = next(x for x in layout["visuals"] if x.get("id") == vid)
        if where.startswith("props "):
            v["props"][where[6:]] = new
        elif where.startswith("navigator.colors."):
            v["navigator"]["colors"][where.split(".")[-1]] = new
        elif where.startswith("referenceLines["):
            v["referenceLines"][int(re.search(r"\[(\d+)\]", where).group(1))]["color"] = new
        else:
            ri = int(re.search(r"\[(\d+)\]", where).group(1))
            v["text"]["runs"][ri]["color"] = new
    return layout


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--brand", help="brand colours: '#a,#b,#c' or 'primary=#a,brand=#b,bad=#c'")
    g.add_argument("--from", dest="ref", help="a reference image or HTML file (design/reference/)")
    g.add_argument("--preset", help=f"a preset in design/themes/presets/ (default {DEFAULT_PRESET})")
    ap.add_argument("--mode", choices=["auto", "light", "dark"], default="auto")
    ap.add_argument("--base", default=str(ROOT / "design" / "tokens.json"), help="tokens to keep the rest from")
    ap.add_argument("--out", default=str(ROOT / "design" / "tokens.json"))
    ap.add_argument("--report", default=str(ROOT / "design" / "reviews" / "theme.md"))
    ap.add_argument("--layout", help="a layout.json to check for colour names used out of role (text in fill colours, "
                    "selected states without selected / onSelected)")
    ap.add_argument("--fix-layout", action="store_true", help="rename them in --layout (listed in the report)")
    ap.add_argument("--dry-run", action="store_true", help="print the report, write nothing")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(errors="replace")
    base = load(a.base) if pathlib.Path(a.base).exists() else {}
    tokens, changes, checks, failures, source, notes = run(a.brand, a.ref, a.preset, a.mode, base)
    roles = []
    if a.layout:
        lay = load(a.layout)
        roles = layout_roles(lay, tokens["colors"])
        if roles:
            notes.append("\n## Layout roles\n\n" + ("Renamed in " if a.fix_layout else "To rename in ") + a.layout
                         + " (a fill colour used as text, or a selected state off selected / onSelected):\n\n"
                         + "| ID | Where | Was | Now |\n| --- | --- | --- | --- |\n"
                         + "\n".join(f"| {i} | {w} | {o} | {n} |" for i, w, o, n in roles))
        if roles and a.fix_layout and not a.dry_run:
            pathlib.Path(a.layout).write_text(json.dumps(fix_layout(lay, roles), indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
    md = report_md(tokens, changes, checks, failures, source, notes)
    if a.dry_run:
        print(md)
    else:
        for f, text in ((a.out, json.dumps(tokens, indent=2) + "\n"), (a.report, md)):
            pathlib.Path(f).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(f).write_text(text, encoding="utf-8")
    given = [x for x in changes if x["origin"] == "given"]
    print(f"{source}, {tokens['theme']['mode']} mode: {sum(x['pass'] for x in checks)} of {len(checks)} AA checks pass; "
          f"{len(given)} given colour(s) changed" + (":" if given else "."))
    for x in given:
        print(f"  {x['name']}: {x['from']} -> {x['to']} ({x['why']})")
    if roles:
        print(f"layout: {len(roles)} colour name(s) out of role" + (" renamed" if a.fix_layout and not a.dry_run
                                                                  else " (--fix-layout renames them)"))
    if not a.dry_run:
        print(f"wrote {a.out} and {a.report}")
    for f in failures:
        print(f"FAIL {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
