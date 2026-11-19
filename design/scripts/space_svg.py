"""Pictures of the spatial canvas's built-in spaces, for the native route (docs/patterns/spatial-canvas.md, step 1):
an SVG of the space's lines (and, with --zones, its areas) at the space's own size, to render with svg_to_png.py and
put behind a transparent scatter chart whose axes are fixed to the range this script prints. Also the court's zone
rule, so a model's Zone column can be computed exactly as the kit visual draws it (kit/patterns/spatial.ts court()).

    python design/scripts/space_svg.py court --out design/reference/court.svg [--stroke "#5B6474"] [--px-per-unit 20]

Spaces: court (half court, feet, data in feet from the hoop), pitch (metres), body (generic outline), floor (generic
clinic floor). The shapes are generic: no league, venue or organisation marks. Colours come from tokens.json when
--stroke is not given (textMuted).
"""
import argparse, json, math, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

COURT = dict(W=50, H=47, hoop_y=5.25, three=23.75, corner_x=22, ra=4, lane=16, ft_y=19)


def court_zone(dx, dy):
    """The zone of a shot dx feet across (right +) and dy feet out from the hoop (towards half court +), or None off
    the court. Same rule and names as kit/patterns/spatial.ts court(): keep the two in step."""
    c = COURT
    x, y = c["W"] / 2 + dx, c["hoop_y"] + dy
    if x < 0 or x > c["W"] or y < 0 or y > c["H"]:
        return None
    r = math.hypot(dx, dy)
    a = math.degrees(math.atan2(dy, dx))
    if a < 0:
        a = 0 if dx >= 0 else 180
    side = "right" if a < 60 else "left" if a > 120 else "center"
    meet = c["hoop_y"] + math.sqrt(c["three"] ** 2 - c["corner_x"] ** 2)
    if r <= c["ra"]:
        return "rim"
    if abs(dx) <= c["lane"] / 2 and y <= c["ft_y"]:
        return "paint"
    if abs(dx) >= c["corner_x"] and y <= meet:
        return "corner3-" + ("left" if dx < 0 else "right")
    if r >= c["three"]:
        return "three-top" if side == "center" else "wing3-" + side
    return "mid-" + side


ZONE_NAMES = {"rim": "At the rim", "paint": "Paint", "mid-left": "Mid-range left", "mid-center": "Mid-range centre",
              "mid-right": "Mid-range right", "corner3-left": "Corner three left", "corner3-right": "Corner three right",
              "wing3-left": "Three left wing", "three-top": "Three top", "wing3-right": "Three right wing"}


def arc(cx, cy, r, a0, a1, n=48):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def path(pts, close=False):
    return "M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + ("Z" if close else "")


def circle(cx, cy, r):
    return path(arc(cx, cy, r, 0, 360, 64), True)


def court():
    c = COURT
    W, H, hx, hy = c["W"], c["H"], c["W"] / 2, c["hoop_y"]
    meet = hy + math.sqrt(c["three"] ** 2 - c["corner_x"] ** 2)
    a0 = math.degrees(math.atan2(meet - hy, -c["corner_x"]))
    a1 = math.degrees(math.atan2(meet - hy, c["corner_x"]))
    three = [(hx - c["corner_x"], 0), (hx - c["corner_x"], meet)] + arc(hx, hy, c["three"], a0, a1)[::-1] + [(hx + c["corner_x"], meet), (hx + c["corner_x"], 0)]
    lines = [path([(0, 0), (W, 0), (W, H), (0, H)], True), path([(hx - 8, 0), (hx + 8, 0), (hx + 8, c["ft_y"]), (hx - 8, c["ft_y"])], True),
             circle(hx, c["ft_y"], 6), circle(hx, hy, 0.75), path([(hx - 3, 4), (hx + 3, 4)]), path(arc(hx, hy, c["ra"], 180, 0, 24)),
             path(three), path(arc(hx, H, 6, 180, 360, 24))]
    # data range for a native scatter (feet from the hoop): x across, y out from the hoop
    # a scatter's y axis grows upwards and the image's baseline is at the top: plot -Y (a measure) on [-(H - hy), hy]
    return W, H, lines, {"x": [-hx, W - hx], "y": [-(H - hy), hy], "note": "x = feet across from the hoop; plot -Y (feet out from the hoop, negated), image top = baseline"}


def pitch():
    W, H = 105, 68
    box = lambda x, w, h: path([(x, (H - h) / 2), (x + w, (H - h) / 2), (x + w, (H + h) / 2), (x, (H + h) / 2)], True)
    lines = [path([(0, 0), (W, 0), (W, H), (0, H)], True), path([(W / 2, 0), (W / 2, H)]), circle(W / 2, H / 2, 9.15),
             box(0, 16.5, 40.32), box(W - 16.5, 16.5, 40.32), box(0, 5.5, 18.32), box(W - 5.5, 5.5, 18.32)]
    return W, H, lines, {"x": [0, W], "y": [0, H], "note": "metres from the top-left corner, y down"}


def body():
    return 100, 220, [circle(50, 16, 13), path([(30, 37), (70, 37), (68, 72), (32, 72)], True),
                      path([(32, 72), (68, 72), (68, 100), (32, 100)], True), path([(32, 100), (68, 100), (64, 116), (36, 116)], True),
                      path([(36, 116), (49, 116), (47, 202), (38, 202)], True), path([(51, 116), (64, 116), (62, 202), (53, 202)], True),
                      path([(30, 38), (22, 40), (14, 104), (22, 105), (31, 52)], True), path([(70, 38), (78, 40), (86, 104), (78, 105), (69, 52)], True)], \
        {"x": [0, 100], "y": [0, 220], "note": "outline units, y down; left and right are the person's own (left shows on the right)"}


def floor():
    rooms = [(0, 30, 10, 10), (10, 26, 20, 14), (0, 18, 10, 12), (0, 0, 12, 18), (12, 0, 9, 12), (21, 0, 9, 12), (30, 0, 9, 12),
             (39, 0, 9, 12), (12, 12, 48, 6), (48, 0, 12, 12), (30, 18, 15, 22), (45, 18, 15, 22), (10, 18, 20, 8)]
    return 60, 40, [path([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True) for x, y, w, h in rooms], \
        {"x": [0, 60], "y": [0, 40], "note": "plan units from the top-left corner, y down"}


SPACES = {"court": court, "pitch": pitch, "body": body, "floor": floor}


def svg(space, stroke, px=20, zones=False, fill=None):
    W, H, lines, rng = SPACES[space]()
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * px:.0f}" height="{H * px:.0f}" viewBox="0 0 {W} {H}">']
    if zones and space == "court":            # areas traced from the rule, for a wireframe or a static picture
        step = 0.25
        for z in ZONE_NAMES:
            runs = []
            for j in range(int(H / step)):
                y = j * step + step / 2
                i = 0
                while i < int(W / step):
                    if court_zone(i * step + step / 2 - W / 2, y - COURT["hoop_y"]) == z:
                        k = i
                        while k < int(W / step) and court_zone(k * step + step / 2 - W / 2, y - COURT["hoop_y"]) == z:
                            k += 1
                        runs.append(f"M{i * step:.2f},{j * step:.2f}h{(k - i) * step:.2f}v{step}h{-(k - i) * step:.2f}Z")
                        i = k
                    else:
                        i += 1
            out.append(f'<path d="{"".join(runs)}" fill="{fill or stroke}" fill-opacity="0.12" shape-rendering="crispEdges"><title>{ZONE_NAMES[z]}</title></path>')
    out.append(f'<path d="{"".join(lines)}" fill="none" stroke="{stroke}" stroke-width="{1.5 / px * 2:.3f}" stroke-linejoin="round"/>')
    out.append("</svg>")
    return "\n".join(out), rng


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("space", choices=sorted(SPACES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--stroke", help="line colour (default: tokens textMuted)")
    ap.add_argument("--px-per-unit", type=float, default=20)
    ap.add_argument("--zones", action="store_true", help="also tint the areas (court)")
    a = ap.parse_args()
    stroke = a.stroke
    if not stroke:
        try:
            stroke = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))["colors"]["textMuted"]
        except (OSError, KeyError, ValueError):
            stroke = "#5B6474"
    text, rng = svg(a.space, stroke, a.px_per_unit, a.zones)
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(text, encoding="utf-8")
    print(f"wrote {a.out}; fix the scatter's axes to x {rng['x']}, y {rng['y']} ({rng['note']}); hide the axes, make the "
          "chart transparent and place it exactly over the image (same position and size)")


if __name__ == "__main__":
    main()
