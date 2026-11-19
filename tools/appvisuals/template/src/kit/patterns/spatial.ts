/*
 *  pbip-kit pattern modules: the spatial canvas (docs/patterns/spatial-canvas.md): a picture of a space with data on
 *  top. A Space is defined once, and the same definition draws the background, places the data and decides which
 *  zone a point is in, so a dot can never sit in one zone and count in another.
 *  Three ways to define zones:
 *  - polygons (a floor plan's rooms, body regions, a pitch grid, a pasted shape file): a point is in the first zone
 *    whose polygon holds it;
 *  - a rule (x, y) -> zone (court areas by distance and angle, service areas by nearest centre): the zone shapes are
 *    traced from the rule on a fine grid, so drawing and counting can't disagree;
 *  - the data's own coordinates (a route or care pathway): ordered points make a track, its stages are the zones.
 *  Built-in shapes are generic (no league, venue or organisation marks). Units are the space's own (feet, metres,
 *  plan units); `toSpace` maps the data's coordinates into them.
 */

export interface Pt { x: number; y: number }
export interface Rect { x: number; y: number; w: number; h: number }

export interface Zone {
    id: string;
    name: string;
    /** SVG path in space units (fill it for the zone). */
    d: string;
    /** The zone's edge only (stroke it to outline the zone); for polygons the same as d. */
    outline: string;
    /** Traced from a rule on a grid: draw with shape-rendering crispEdges (no seams between the grid strips). */
    crisp?: boolean;
    centroid: Pt;
    box: Rect;
    contains(p: Pt): boolean;
}

export interface Space {
    id: string;
    name: string;
    width: number;
    height: number;
    /** The picture: SVG path(s) in space units, stroked in the line colour. */
    lines: string;
    /** Optional filled areas under the zones (a floor, a lane), in the panel tone. */
    floor?: string;
    zones: Zone[];
    zoneOf(p: Pt): Zone | null;
    /** Data coordinates -> space units (default: the same units). */
    toSpace(x: number, y: number): Pt;
}

const f = (v: number) => Math.round(v * 100) / 100;

export function rectPath(r: Rect): string {
    return `M${f(r.x)},${f(r.y)}h${f(r.w)}v${f(r.h)}h${f(-r.w)}Z`;
}

export function polyPath(pts: Pt[]): string {
    return pts.length ? `M${pts.map(p => `${f(p.x)},${f(p.y)}`).join("L")}Z` : "";
}

export function circlePath(c: Pt, r: number): string {
    return `M${f(c.x - r)},${f(c.y)}a${f(r)},${f(r)} 0 1,0 ${f(r * 2)},0a${f(r)},${f(r)} 0 1,0 ${f(-r * 2)},0`;
}

/** Points along an arc (degrees, y down), inclusive. */
export function arcPoints(c: Pt, r: number, deg0: number, deg1: number, n = 24): Pt[] {
    const out: Pt[] = [];
    for (let i = 0; i <= n; i++) {
        const a = (deg0 + (deg1 - deg0) * i / n) * Math.PI / 180;
        out.push({ x: c.x + r * Math.cos(a), y: c.y + r * Math.sin(a) });
    }
    return out;
}

export function ellipsePoints(c: Pt, rx: number, ry: number, n = 36): Pt[] {
    return Array.from({ length: n }, (_, i) => ({ x: c.x + rx * Math.cos(i / n * Math.PI * 2), y: c.y + ry * Math.sin(i / n * Math.PI * 2) }));
}

export function inPolygon(p: Pt, poly: Pt[]): boolean {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const a = poly[i], b = poly[j];
        if ((a.y > p.y) !== (b.y > p.y) && p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x) {
            inside = !inside;
        }
    }
    return inside;
}

function boxOf(pts: Pt[]): Rect {
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    const x = Math.min(...xs), y = Math.min(...ys);
    return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

function centroidOf(pts: Pt[]): Pt {
    let a = 0, cx = 0, cy = 0;
    for (let i = 0; i < pts.length; i++) {
        const p = pts[i], q = pts[(i + 1) % pts.length], c = p.x * q.y - q.x * p.y;
        a += c; cx += (p.x + q.x) * c; cy += (p.y + q.y) * c;
    }
    if (Math.abs(a) < 1e-9) {
        return { x: pts.reduce((s, p) => s + p.x, 0) / pts.length, y: pts.reduce((s, p) => s + p.y, 0) / pts.length };
    }
    return { x: cx / (3 * a), y: cy / (3 * a) };
}

const identity = (x: number, y: number): Pt => ({ x, y });

function space(id: string, name: string, width: number, height: number, lines: string, zones: Zone[], floor?: string,
    toSpace = identity, zoneOf?: (p: Pt) => Zone | null): Space {
    return { id, name, width, height, lines, floor, zones, toSpace, zoneOf: zoneOf || (p => zones.find(z => z.contains(p)) || null) };
}

export interface PolyDef { id: string; name: string; points: Pt[] }

/** Zones from polygons: a point is in the first zone (in the given order) whose polygon holds it. */
export function fromPolygons(id: string, name: string, width: number, height: number, defs: PolyDef[], lines = "", floor?: string): Space {
    const zones = defs.filter(d => d.points.length >= 3).map(d => ({
        id: d.id, name: d.name, d: polyPath(d.points), outline: polyPath(d.points), centroid: centroidOf(d.points), box: boxOf(d.points),
        contains: (p: Pt) => inPolygon(p, d.points)
    }));
    return space(id, name, width, height, lines || zones.map(z => z.d).join(""), zones, floor);
}

/**
 * Zones from a rule: rule(x, y) gives the zone id (or null). Each zone's shape is traced from the rule on a grid of
 * `steps` cells across the longer side (runs per row, merged down the rows), so the fill matches the rule exactly to
 * one cell; draw the space's lines on top to hide the steps. Counting uses the rule itself.
 */
export function fromRule(id: string, name: string, width: number, height: number, names: Array<{ id: string; name: string }>,
    rule: (x: number, y: number) => string | null, lines: string, floor?: string, toSpace = identity, steps = 320): Space {
    const s = Math.max(width, height) / steps;
    const cols = Math.ceil(width / s), rows = Math.ceil(height / s);
    const rects = new Map<string, Rect[]>(names.map(n => [n.id, []]));
    let open = new Map<string, Rect>();                              // run key -> rect still growing downwards
    const index = new Map(names.map((n, i) => [n.id, i + 1]));
    const grid = new Int16Array(cols * rows);                          // zone number per cell (0 = none), for the edges
    for (let r = 0; r < rows; r++) {
        const cy = Math.min(height, r * s + s / 2);
        for (let c = 0; c < cols; c++) {
            grid[r * cols + c] = index.get(rule(Math.min(width, c * s + s / 2), cy)) || 0;
        }
    }
    const at = (r: number, c: number) => (r < 0 || c < 0 || r >= rows || c >= cols ? 0 : grid[r * cols + c]);
    for (let r = 0; r < rows; r++) {
        const y = r * s;
        const next = new Map<string, Rect>();
        let c = 0;
        while (c < cols) {
            const zn = at(r, c), zid = zn ? names[zn - 1].id : null;
            let e = c + 1;
            while (e < cols && at(r, e) === zn) {
                e++;
            }
            if (zid != null && rects.has(zid)) {
                const key = `${zid}|${c}|${e}`;
                const prev = open.get(key);
                const rect = prev ? (prev.h += s, prev) : { x: c * s, y, w: Math.min(width, e * s) - c * s, h: s };
                if (!prev) {
                    rects.get(zid).push(rect);
                }
                next.set(key, rect);
            }
            c = e;
        }
        open = next;
    }
    // each zone's edge: cell sides whose neighbour is another zone, merged into runs along rows and columns
    const edges = (zn: number): string => {
        const out: string[] = [];
        const X = (c: number) => f(Math.min(width, c * s)), Y = (r: number) => f(Math.min(height, r * s));
        for (let r = 0; r <= rows; r++) {
            let c = 0;
            while (c < cols) {
                const edge = (cc: number) => (at(r, cc) === zn) !== (at(r - 1, cc) === zn);
                if (!edge(c)) { c++; continue; }
                let e = c + 1;
                while (e < cols && edge(e)) { e++; }
                out.push(`M${X(c)},${Y(r)}H${X(e)}`);
                c = e;
            }
        }
        for (let c = 0; c <= cols; c++) {
            let r = 0;
            while (r < rows) {
                const edge = (rr: number) => (at(rr, c) === zn) !== (at(rr, c - 1) === zn);
                if (!edge(r)) { r++; continue; }
                let e = r + 1;
                while (e < rows && edge(e)) { e++; }
                out.push(`M${X(c)},${Y(r)}V${Y(e)}`);
                r = e;
            }
        }
        return out.join("");
    };
    const zones: Zone[] = [];
    for (const n of names) {
        const list = rects.get(n.id);
        if (!list.length) {
            continue;
        }
        let a = 0, cx = 0, cy = 0;
        list.forEach(r => { const ar = r.w * r.h; a += ar; cx += (r.x + r.w / 2) * ar; cy += (r.y + r.h / 2) * ar; });
        const x0 = Math.min(...list.map(r => r.x)), y0 = Math.min(...list.map(r => r.y));
        const box = { x: x0, y: y0, w: Math.max(...list.map(r => r.x + r.w)) - x0, h: Math.max(...list.map(r => r.y + r.h)) - y0 };
        zones.push({
            id: n.id, name: n.name, d: list.map(rectPath).join(""), outline: edges(index.get(n.id)), crisp: true, centroid: { x: cx / a, y: cy / a }, box,
            contains: (p: Pt) => rule(p.x, p.y) === n.id
        });
    }
    const byId = new Map(zones.map(z => [z.id, z]));
    return space(id, name, width, height, lines, zones, floor, toSpace, p => byId.get(rule(p.x, p.y)) || null);
}

// ---------------------------------------------------------------------------------------------- built-in shapes

/**
 * A generic basketball half court in feet (50 x 47, baseline at the top, hoop 5.25 ft out), with ten areas by
 * distance and angle from the hoop. Data in feet from the hoop (x across, y towards half court); `scale` turns other
 * units into feet (0.1 for tenths of a foot).
 */
export function court(scale = 1): Space {
    const W = 50, H = 47, hoop = { x: 25, y: 5.25 }, three = 23.75, cornerX = 22, ra = 4, laneW = 16, ftY = 19;
    const meet = hoop.y + Math.sqrt(three * three - cornerX * cornerX);
    const names = [
        { id: "rim", name: "At the rim" }, { id: "paint", name: "Paint" },
        { id: "mid-left", name: "Mid-range left" }, { id: "mid-center", name: "Mid-range centre" }, { id: "mid-right", name: "Mid-range right" },
        { id: "corner3-left", name: "Corner three left" }, { id: "corner3-right", name: "Corner three right" },
        { id: "wing3-left", name: "Three left wing" }, { id: "three-top", name: "Three top" }, { id: "wing3-right", name: "Three right wing" }
    ];
    const rule = (x: number, y: number): string | null => {
        if (x < 0 || x > W || y < 0 || y > H) {
            return null;
        }
        const dx = x - hoop.x, dy = y - hoop.y, r = Math.hypot(dx, dy);
        let a = Math.atan2(dy, dx) * 180 / Math.PI;      // 0 = towards the right sideline, 90 = straight out
        if (a < 0) {
            a = dx >= 0 ? 0 : 180;
        }
        const side = a < 60 ? "right" : a > 120 ? "left" : "center";
        if (r <= ra) {
            return "rim";
        }
        if (Math.abs(dx) <= laneW / 2 && y <= ftY) {
            return "paint";
        }
        if (Math.abs(dx) >= cornerX && y <= meet) {
            return dx < 0 ? "corner3-left" : "corner3-right";
        }
        if (r >= three) {
            return side === "center" ? "three-top" : `wing3-${side}`;
        }
        return `mid-${side}`;
    };
    const a0 = Math.atan2(meet - hoop.y, -cornerX) * 180 / Math.PI, a1 = Math.atan2(meet - hoop.y, cornerX) * 180 / Math.PI;
    const arc = arcPoints(hoop, three, a0, a1, 48).reverse();
    const lines = [
        rectPath({ x: 0, y: 0, w: W, h: H }),
        rectPath({ x: hoop.x - laneW / 2, y: 0, w: laneW, h: ftY }),
        circlePath({ x: hoop.x, y: ftY }, 6),
        circlePath(hoop, 0.75),
        `M${hoop.x - 3},4h6`,
        `M${f(hoop.x - ra)},${hoop.y}` + arcPoints(hoop, ra, 180, 0, 16).map(p => `L${f(p.x)},${f(p.y)}`).join(""),
        `M${W / 2 - cornerX},0V${f(meet)}` + arc.map(p => `L${f(p.x)},${f(p.y)}`).join("") + `V0`,
        `M${W / 2 - 6},${H}` + arcPoints({ x: W / 2, y: H }, 6, 180, 360, 16).map(p => `L${f(p.x)},${f(p.y)}`).join("")
    ].join("");
    return fromRule("court", "Court", W, H, names, rule, lines, rectPath({ x: 0, y: 0, w: W, h: H }),
        (x, y) => ({ x: hoop.x + x * scale, y: hoop.y + y * scale }));
}

/** A generic pitch in metres (105 x 68, landscape), zones by third (own, middle, final) and channel (left, centre, right). */
export function pitch(): Space {
    const W = 105, H = 68, thirds = ["Own third", "Middle third", "Final third"], ch = ["left", "centre", "right"];
    const defs: PolyDef[] = [];
    thirds.forEach((t, i) => ch.forEach((c, j) => {
        const x = i * W / 3, y = j * H / 3;
        defs.push({ id: `${i + 1}-${c}`, name: `${t} ${c}`, points: [{ x, y }, { x: x + W / 3, y }, { x: x + W / 3, y: y + H / 3 }, { x, y: y + H / 3 }] });
    }));
    const box = (x: number, w: number, h: number) => rectPath({ x, y: (H - h) / 2, w, h });
    const lines = [rectPath({ x: 0, y: 0, w: W, h: H }), `M${W / 2},0V${H}`, circlePath({ x: W / 2, y: H / 2 }, 9.15),
        box(0, 16.5, 40.32), box(W - 16.5, 16.5, 40.32), box(0, 5.5, 18.32), box(W - 5.5, 5.5, 18.32)].join("");
    return fromPolygons("pitch", "Pitch", W, H, defs, lines, rectPath({ x: 0, y: 0, w: W, h: H }));
}

/** A generic body outline, front view (100 x 220 units). Left and right are the person's own (left shows on the right). */
export function bodyMap(): Space {
    const r = (x: number, y: number, w: number, h: number): Pt[] => [{ x, y }, { x: x + w, y }, { x: x + w, y: y + h }, { x, y: y + h }];
    const defs: PolyDef[] = [
        { id: "head", name: "Head", points: ellipsePoints({ x: 50, y: 16 }, 12, 14) },
        { id: "neck", name: "Neck", points: r(45, 29, 10, 8) },
        { id: "chest", name: "Chest", points: [{ x: 30, y: 37 }, { x: 70, y: 37 }, { x: 68, y: 72 }, { x: 32, y: 72 }] },
        { id: "abdomen", name: "Abdomen", points: r(32, 72, 36, 28) },
        { id: "pelvis", name: "Pelvis", points: [{ x: 32, y: 100 }, { x: 68, y: 100 }, { x: 64, y: 116 }, { x: 36, y: 116 }] },
        { id: "arm-right", name: "Right arm", points: [{ x: 30, y: 38 }, { x: 22, y: 40 }, { x: 14, y: 104 }, { x: 22, y: 105 }, { x: 31, y: 52 }] },
        { id: "arm-left", name: "Left arm", points: [{ x: 70, y: 38 }, { x: 78, y: 40 }, { x: 86, y: 104 }, { x: 78, y: 105 }, { x: 69, y: 52 }] },
        { id: "hand-right", name: "Right hand", points: ellipsePoints({ x: 17, y: 113 }, 5, 8, 20) },
        { id: "hand-left", name: "Left hand", points: ellipsePoints({ x: 83, y: 113 }, 5, 8, 20) },
        { id: "leg-right", name: "Right leg", points: [{ x: 36, y: 116 }, { x: 49, y: 116 }, { x: 47, y: 202 }, { x: 38, y: 202 }] },
        { id: "leg-left", name: "Left leg", points: [{ x: 51, y: 116 }, { x: 64, y: 116 }, { x: 62, y: 202 }, { x: 53, y: 202 }] },
        { id: "foot-right", name: "Right foot", points: r(33, 202, 14, 10) },
        { id: "foot-left", name: "Left foot", points: r(53, 202, 14, 10) }
    ];
    return fromPolygons("body", "Body map", 100, 220, defs);
}

export interface RoomDef { id: string; name: string; x: number; y: number; w: number; h: number }

/** A floor plan from rooms (rectangles in plan units); the default is a generic clinic floor. */
export function floorPlan(rooms?: RoomDef[]): Space {
    const list = rooms && rooms.length ? rooms : [
        { id: "entrance", name: "Entrance", x: 0, y: 30, w: 10, h: 10 }, { id: "waiting", name: "Waiting", x: 10, y: 26, w: 20, h: 14 },
        { id: "reception", name: "Reception", x: 0, y: 18, w: 10, h: 12 }, { id: "triage", name: "Triage", x: 0, y: 0, w: 12, h: 18 },
        { id: "exam-1", name: "Exam 1", x: 12, y: 0, w: 9, h: 12 }, { id: "exam-2", name: "Exam 2", x: 21, y: 0, w: 9, h: 12 },
        { id: "exam-3", name: "Exam 3", x: 30, y: 0, w: 9, h: 12 }, { id: "exam-4", name: "Exam 4", x: 39, y: 0, w: 9, h: 12 },
        { id: "corridor", name: "Corridor", x: 12, y: 12, w: 48, h: 6 }, { id: "imaging", name: "Imaging", x: 48, y: 0, w: 12, h: 12 },
        { id: "lab", name: "Lab", x: 30, y: 18, w: 15, h: 22 }, { id: "pharmacy", name: "Pharmacy", x: 45, y: 18, w: 15, h: 22 },
        { id: "office", name: "Office", x: 10, y: 18, w: 20, h: 8 }
    ];
    const W = Math.max(...list.map(r => r.x + r.w)), H = Math.max(...list.map(r => r.y + r.h));
    const defs = list.map(r => ({ id: r.id, name: r.name, points: [{ x: r.x, y: r.y }, { x: r.x + r.w, y: r.y }, { x: r.x + r.w, y: r.y + r.h }, { x: r.x, y: r.y + r.h }] }));
    return fromPolygons("floor", "Floor plan", W, H, defs);
}

export interface TrackPoint { x: number; y: number; order: number; stage: string }

/**
 * A route or pathway from the data's own coordinates: points sorted by `order` make the track, consecutive points
 * of one stage make that stage's zone (a band `width` wide). A point belongs to the nearest stage within the band.
 */
export function track(points: TrackPoint[], width = 0): Space {
    const pts = points.filter(p => Number.isFinite(p.x) && Number.isFinite(p.y)).sort((a, b) => a.order - b.order);
    if (pts.length < 2) {
        return fromPolygons("track", "Track", 100, 60, []);
    }
    const x0 = Math.min(...pts.map(p => p.x)), y0 = Math.min(...pts.map(p => p.y));
    const W = Math.max(...pts.map(p => p.x)) - x0 || 1, H = Math.max(...pts.map(p => p.y)) - y0 || 1;
    const pad = Math.max(W, H) * 0.06, band = width || Math.max(W, H) * 0.05;
    const P = pts.map(p => ({ ...p, x: p.x - x0 + pad, y: p.y - y0 + pad }));
    const stages = [...new Set(P.map(p => p.stage))];
    const segs = (s: string) => {
        const out: Array<[Pt, Pt]> = [];
        for (let i = 1; i < P.length; i++) {
            if (P[i].stage === s) {                    // a segment belongs to the stage it arrives in
                out.push([P[i - 1], P[i]]);
            }
        }
        return out;
    };
    const dist = (p: Pt, a: Pt, b: Pt) => {
        const vx = b.x - a.x, vy = b.y - a.y, l = vx * vx + vy * vy || 1;
        const t = Math.max(0, Math.min(1, ((p.x - a.x) * vx + (p.y - a.y) * vy) / l));
        return Math.hypot(p.x - a.x - t * vx, p.y - a.y - t * vy);
    };
    const zones: Zone[] = stages.map(s => {
        const ss = segs(s), own = P.filter(p => p.stage === s);
        const all = ss.flatMap(x => x);
        const d = ss.map(([a, b]) => `M${f(a.x)},${f(a.y)}L${f(b.x)},${f(b.y)}`).join("");
        return {
            id: s, name: s, d, outline: d, centroid: { x: own.reduce((t, p) => t + p.x, 0) / own.length, y: own.reduce((t, p) => t + p.y, 0) / own.length },
            box: boxOf(all.length ? all : own), contains: (p: Pt) => ss.some(([a, b]) => dist(p, a, b) <= band / 2)
        };
    });
    const zoneOf = (p: Pt) => {
        let best: Zone | null = null, bd = band / 2;
        for (const z of zones) {
            for (const [a, b] of segs(z.id)) {
                const d = dist(p, a, b);
                if (d <= bd) {
                    bd = d; best = z;
                }
            }
        }
        return best;
    };
    const lines = `M${P.map(p => `${f(p.x)},${f(p.y)}`).join("L")}`;
    return space("track", "Track", W + pad * 2, H + pad * 2, lines, zones, undefined, (x, y) => ({ x: x - x0 + pad, y: y - y0 + pad }), zoneOf);
}

export interface Centre { id: string; name: string; x: number; y: number }

/** Service areas: each point belongs to its nearest centre (a Voronoi split), traced like a rule. */
export function serviceAreas(centres: Centre[], width: number, height: number): Space {
    const rule = (x: number, y: number) => {
        let best: Centre | null = null, bd = Infinity;
        for (const c of centres) {
            const d = (c.x - x) ** 2 + (c.y - y) ** 2;
            if (d < bd) {
                bd = d; best = c;
            }
        }
        return best ? best.id : null;
    };
    const dots = centres.map(c => circlePath(c, Math.max(width, height) / 120)).join("");
    const s = fromRule("areas", "Service areas", width, height, centres, rule, rectPath({ x: 0, y: 0, w: width, h: height }) + dots, undefined, identity, 160);
    return s;
}

type Ring = number[][];
interface GeoFeature { properties?: Record<string, unknown>; geometry?: { type: string; coordinates: unknown } }

/**
 * A shape file (GeoJSON FeatureCollection of Polygon / MultiPolygon, or the kit's own {width, height, zones: [{id,
 * name, points}]}) fitted into `width` x `height` (plain equirectangular, north up). `nameProp` names each zone.
 */
export function fromShapes(text: string, nameProp = "name", width = 100, height = 70): Space | null {
    let doc: { type?: string; features?: GeoFeature[]; zones?: PolyDef[]; width?: number; height?: number; lines?: string };
    try {
        doc = JSON.parse(text);
    } catch {
        return null;
    }
    if (doc && Array.isArray(doc.zones)) {
        return fromPolygons("custom", "Custom zones", doc.width || width, doc.height || height, doc.zones, doc.lines || "");
    }
    if (!doc || !Array.isArray(doc.features)) {
        return null;
    }
    const rings: Array<{ name: string; ring: Ring }> = [];
    doc.features.forEach((ft, i) => {
        const g = ft.geometry, name = String(ft.properties?.[nameProp] ?? `Zone ${i + 1}`);
        if (g?.type === "Polygon") {
            rings.push({ name, ring: (g.coordinates as Ring[])[0] });
        } else if (g?.type === "MultiPolygon") {
            const polys = g.coordinates as Ring[][];
            const big = polys.map(p => p[0]).sort((a, b) => b.length - a.length)[0];
            rings.push({ name, ring: big });
        }
    });
    if (!rings.length) {
        return null;
    }
    const all = rings.flatMap(r => r.ring);
    const lx = Math.min(...all.map(p => p[0])), hx = Math.max(...all.map(p => p[0]));
    const ly = Math.min(...all.map(p => p[1])), hy = Math.max(...all.map(p => p[1]));
    const k = Math.min(width / (hx - lx || 1), height / (hy - ly || 1));
    const map = (p: number[]): Pt => ({ x: (p[0] - lx) * k, y: (hy - p[1]) * k });
    const defs = rings.map((r, i) => ({ id: `${i}-${r.name}`, name: r.name, points: r.ring.map(map) }));
    const s = fromPolygons("shapes", "Shapes", (hx - lx) * k, (hy - ly) * k, defs);
    s.toSpace = (x, y) => map([x, y]);
    return s;
}

/** A built-in space by name (court, pitch, body, floor, areas) or a pasted shape definition; never null. */
export function spaceByName(name: string, opts: { scale?: number; custom?: string; rooms?: RoomDef[] } = {}): Space {
    if (opts.custom) {
        const s = fromShapes(opts.custom);
        if (s) {
            return s;
        }
    }
    switch (name) {
        case "pitch": return pitch();
        case "body": return bodyMap();
        case "floor": return floorPlan(opts.rooms);
        case "areas": return serviceAreas([{ id: "north", name: "North", x: 30, y: 15 }, { id: "east", name: "East", x: 80, y: 30 },
            { id: "south", name: "South", x: 45, y: 58 }, { id: "west", name: "West", x: 12, y: 45 }], 100, 70);
        default: return court(opts.scale || 1);
    }
}

// ---------------------------------------------------------------------------------------------- views

/** The transform that fits a space into a box (uniform scale, centred). */
export function fitSpace(s: Space, box: Rect): { k: number; x: number; y: number } {
    const k = Math.min(box.w / s.width, box.h / s.height);
    return { k, x: box.x + (box.w - s.width * k) / 2, y: box.y + (box.h - s.height * k) / 2 };
}

/**
 * Any map -> a ranked row: each zone's own shape slides from where it sits into slot i of a row sorted by value
 * (largest first), scaled to fit the slot, with room under it for a label. Returns per zone the move from its place
 * on the map (space units) to its slot (screen pixels): draw the zone with `translate(x,y) scale(k)`.
 */
export function lineup(zones: Zone[], value: (z: Zone) => number, box: Rect, labelPx = 32, gap = 8, minSlot = 120, maxK = Infinity):
    Map<string, { k: number; x: number; y: number; slot: Rect; rank: number }> {
    const order = zones.filter(z => Number.isFinite(value(z))).sort((a, b) => value(b) - value(a) || a.name.localeCompare(b.name));
    const n = Math.max(1, order.length);
    const cols = Math.min(n, Math.max(1, Math.floor((box.w + gap) / (minSlot + gap))));
    const rows = Math.ceil(n / cols);
    const sw = (box.w - gap * (cols - 1)) / cols, sh = (box.h - gap * (rows - 1)) / rows - labelPx;
    const out = new Map<string, { k: number; x: number; y: number; slot: Rect; rank: number }>();
    order.forEach((z, i) => {
        const slot = { x: box.x + (i % cols) * (sw + gap), y: box.y + Math.floor(i / cols) * (sh + labelPx + gap), w: sw, h: Math.max(10, sh) };
        const k = Math.min(maxK, Math.min(slot.w / Math.max(1e-6, z.box.w), slot.h / Math.max(1e-6, z.box.h)) * 0.9);
        out.set(z.id, { k, x: slot.x + (slot.w - z.box.w * k) / 2 - z.box.x * k, y: slot.y + (slot.h - z.box.h * k) / 2 - z.box.y * k, slot, rank: i + 1 });
    });
    return out;
}
