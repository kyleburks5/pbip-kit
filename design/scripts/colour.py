"""Colour maths for the theme tools (gen_tokens.py, check_contrast.py): WCAG 2.1 contrast, OKLCH, and moving a colour
until it reaches a contrast ratio while keeping its hue.

    import colour as K
    K.contrast("#5A6577", "#FFFFFF")                    5.9
    K.reach("#8CCFD3", ["#FFFFFF"], 4.5)                the nearest colour of the same hue that is 4.5:1 on white
    K.mix("#038D96", "#FFFFFF", 0.9)                    90% of the way to white

Lightness, chroma and hue are OKLCH (perceptual): moving L keeps the colour recognisably the same hue, which HSL does
not. Colours out of the sRGB gamut lose chroma until they fit.
"""
import math, re

HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def norm(c):
    """'#abc', '#aabbcc', '#aabbccdd', 'rgb(1,2,3)' or 'rgba(1,2,3,.5)' -> '#AABBCC' (alpha dropped); None otherwise."""
    if not isinstance(c, str):
        return None
    c = c.strip()
    m = re.fullmatch(r"#([0-9A-Fa-f]{3,4})", c)
    if m:
        return "#" + "".join(ch * 2 for ch in m.group(1)[:3]).upper()
    m = re.fullmatch(r"#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?", c)
    if m:
        return "#" + m.group(1).upper()
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+[\d.%]+)?\s*\)", c)
    if m:
        return to_hex(*(min(255, float(x)) / 255 for x in m.groups()))
    return None


def rgb(c):
    c = norm(c)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))


def to_hex(r, g, b):
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(x * 255))) for x in (r, g, b)))


def luminance(c):
    def ch(x):
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(c)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------------------------------------------------------------- OKLab / OKLCH
def _lin(x):
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def _gam(x):
    return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055


def oklch(c):
    r, g, b = (_lin(x) for x in rgb(c))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    A = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    B = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360


def _oklch_rgb(L, C, H):
    A, B = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m_ = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s_ = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def from_oklch(L, C, H):
    """The sRGB hex for an OKLCH colour, chroma reduced until it is in gamut."""
    L = max(0.0, min(1.0, L))
    for _ in range(40):
        lin = _oklch_rgb(L, C, H)
        if all(-1e-6 <= x <= 1 + 1e-6 for x in lin):
            break
        C *= 0.92
    return to_hex(*(_gam(max(0.0, min(1.0, x))) for x in _oklch_rgb(L, C, H)))


def with_l(c, L):
    _, C, H = oklch(c)
    return from_oklch(L, C, H)


def mix(a, b, t):
    """t of the way from a to b, in OKLab (t = 0 gives a, 1 gives b)."""
    la, ca, ha = oklch(a)
    lb, cb, hb = oklch(b)
    xa, ya = ca * math.cos(math.radians(ha)), ca * math.sin(math.radians(ha))
    xb, yb = cb * math.cos(math.radians(hb)), cb * math.sin(math.radians(hb))
    x, y = xa + (xb - xa) * t, ya + (yb - ya) * t
    return from_oklch(la + (lb - la) * t, math.hypot(x, y), math.degrees(math.atan2(y, x)) % 360)


def is_dark(c):
    return oklch(c)[0] < 0.6


def hue_distance(a, b):
    d = abs(oklch(a)[2] - oklch(b)[2]) % 360
    return min(d, 360 - d)


def reach(c, bgs, ratio, direction=None):
    """The colour of c's hue and chroma nearest to c in lightness that has at least `ratio` contrast with every
    background in bgs. direction: 'darker' / 'lighter' / None (whichever needs the smaller move, among those that can
    reach the ratio). Returns c itself when it already passes; None when no lightness of this hue passes (the
    backgrounds sit on both sides)."""
    c = norm(c)
    bgs = [norm(b) for b in bgs if b]
    if all(contrast(c, b) >= ratio for b in bgs):
        return c
    L0, C, H = oklch(c)
    found = []
    for d in ([direction] if direction else ["darker", "lighter"]):
        lo, hi = (0.0, L0) if d == "darker" else (L0, 1.0)
        end = from_oklch(lo if d == "darker" else hi, C, H)
        if not all(contrast(end, b) >= ratio for b in bgs):
            continue
        for _ in range(30):                     # bisect for the smallest move that passes
            mid = (lo + hi) / 2
            ok = all(contrast(from_oklch(mid, C, H), b) >= ratio for b in bgs)
            if d == "darker":
                lo, hi = (lo, mid) if not ok else (mid, hi)
            else:
                lo, hi = (mid, hi) if not ok else (lo, mid)
        L = lo if d == "darker" else hi
        out = from_oklch(L, C, H)
        while not all(contrast(out, b) >= ratio for b in bgs):          # rounding to hex can land just short
            L = L - 0.004 if d == "darker" else L + 0.004
            out = from_oklch(L, C, H)
        found.append((abs(L - L0), out))
    return min(found)[1] if found else None


def best_text(bg, candidates=("#FFFFFF", "#000000")):
    """The candidate with the highest contrast on bg."""
    return max(candidates, key=lambda t: contrast(t, bg))
