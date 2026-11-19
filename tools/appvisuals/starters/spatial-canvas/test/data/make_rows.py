"""Made-up rows for the spatial-canvas harness scenarios (no real people, teams or places).
shots: court points in feet from the hoop, zone by the same rule as kit/patterns/spatial.ts court(), made 0/1.
body:  claim lines placed inside generic body regions (health insurance, made up), approved 0/1.
floor: clinic visits placed in rooms, seen-within-target 0/1, with a benchmark rate."""
import json, math, random, pathlib
HERE = pathlib.Path(__file__).parent

def court_zone(dx, dy):
    hoop_y, three, cx, ra, lane, ft = 5.25, 23.75, 22, 4, 16, 19
    x, y = 25 + dx, hoop_y + dy
    if x < 0 or x > 50 or y < 0 or y > 47: return None
    r = math.hypot(dx, dy); a = math.degrees(math.atan2(dy, dx))
    if a < 0: a = 0 if dx >= 0 else 180
    side = "right" if a < 60 else "left" if a > 120 else "center"
    meet = hoop_y + math.sqrt(three ** 2 - cx ** 2)
    if r <= ra: return "rim"
    if abs(dx) <= lane / 2 and y <= ft: return "paint"
    if abs(dx) >= cx and y <= meet: return "corner3-" + ("left" if dx < 0 else "right")
    if r >= three: return "three-top" if side == "center" else "wing3-" + side
    return "mid-" + side

def shots(n=900, seed=11):
    rnd = random.Random(seed); rows = []
    rate = {"rim": .63, "paint": .44, "mid-left": .41, "mid-center": .43, "mid-right": .38, "corner3-left": .41,
            "corner3-right": .36, "wing3-left": .35, "three-top": .34, "wing3-right": .37}
    while len(rows) < n:
        k = rnd.random()
        if k < .3: r, a = abs(rnd.gauss(0, 3)), rnd.uniform(0, 180)
        elif k < .55: r, a = rnd.uniform(8, 22), rnd.uniform(0, 180)
        elif k < .7: r, a = rnd.uniform(22.2, 23.6), rnd.choice([rnd.uniform(-8, 6), rnd.uniform(174, 188)])
        else: r, a = rnd.uniform(23.9, 27), rnd.uniform(15, 165)
        dx, dy = round(r * math.cos(math.radians(a)), 2), round(r * math.sin(math.radians(a)), 2)
        if abs(dx) > 22 and abs(dx) < 22.3: dx = math.copysign(22.4, dx)
        z = court_zone(dx, dy)
        if not z or dy < -4: continue
        made = 1 if rnd.random() < rate[z] else 0
        kind = "3PT" if z.startswith(("corner3", "wing3", "three")) else "2PT"
        rows.append({"Shot": f"S{len(rows)+1:04d}", "Zone": z, "Kind": kind, "X": round(dx, 2), "Y": round(dy, 2), "Made": made})
    # one thin zone: drop most right-corner threes so the small-sample rule shows
    keep = [r for r in rows if r["Zone"] != "corner3-right"] + [r for r in rows if r["Zone"] == "corner3-right"][:6]
    return keep

def body(seed=5):
    rnd = random.Random(seed)
    regions = {"head": ((50, 16), 7, 8, .58), "chest": ((50, 55), 12, 10, .72), "abdomen": ((50, 86), 12, 8, .66),
               "arm-right": ((22, 70), 2, 14, .81), "arm-left": ((78, 70), 2, 14, .79), "hand-right": ((17, 113), 2, 3, .84),
               "hand-left": ((83, 113), 2, 3, .9), "leg-right": ((43, 160), 2.5, 25, .74), "leg-left": ((57, 160), 2.5, 25, .69),
               "foot-left": ((60, 207), 3, 2, .77), "neck": ((50, 33), 2, 2, .5)}
    counts = {"head": 70, "chest": 120, "abdomen": 95, "arm-right": 60, "arm-left": 55, "hand-right": 40, "hand-left": 35,
              "leg-right": 110, "leg-left": 100, "foot-left": 30, "neck": 7}
    rows = []
    for reg, ((cx, cy), sx, sy, p) in regions.items():
        for _ in range(counts[reg]):
            rows.append({"Claim": f"C{len(rows)+1:04d}", "Region": reg, "Type": rnd.choice(["Outpatient", "Outpatient", "Inpatient"]),
                         "X": round(cx + rnd.uniform(-sx, sx), 2), "Y": round(cy + rnd.uniform(-sy, sy), 2), "Approved": 1 if rnd.random() < p else 0})
    return rows

def floor(seed=3):
    rnd = random.Random(seed)
    rooms = {"triage": (0, 0, 12, 18, .7, 160), "exam-1": (12, 0, 9, 12, .82, 90), "exam-2": (21, 0, 9, 12, .66, 85),
             "exam-3": (30, 0, 9, 12, .78, 80), "exam-4": (39, 0, 9, 12, .9, 9), "imaging": (48, 0, 12, 12, .55, 70),
             "lab": (30, 18, 15, 22, .86, 120), "pharmacy": (45, 18, 15, 22, .74, 110), "waiting": (10, 26, 20, 14, .6, 140)}
    rows = []
    for room, (x, y, w, h, p, n) in rooms.items():
        for _ in range(n):
            rows.append({"Visit": f"V{len(rows)+1:04d}", "Room": room, "X": round(x + rnd.uniform(.8, w - .8), 2),
                         "Y": round(y + rnd.uniform(.8, h - .8), 2), "OnTime": 1 if rnd.random() < p else 0, "Target": .75})
    return rows

for name, rows in (("shots", shots()), ("body", body()), ("floor", floor())):
    (HERE / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")
    print(name, len(rows))
