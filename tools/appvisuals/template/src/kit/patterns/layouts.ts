/*
 *  pbip-kit pattern modules: unit layouts (docs/patterns/app-visuals/morph-layouts.md, unit-chart.md).
 *  Pure functions: the same units get a position in every layout, so Motion can morph between them. Each layout also
 *  returns its labels (cells). No drawing here.
 */
import { scaleLinear, scaleBand } from "d3-scale";
import { extent } from "d3-array";
import { settle, resume, PhysicsNode, MarkState } from "../motion";
import { hash01 } from "../data";

export interface Unit {
    key: string;
    group: string;
    stage: string;
    x?: number;
    y?: number;
}

export interface Box {
    x: number;
    y: number;
    w: number;
    h: number;
}

export interface Cell {
    label: string;
    x: number;
    y: number;
    w: number;
    h: number;
    group?: string;
    tick?: boolean;
    title?: boolean;
}

export interface Placed {
    pos: Map<string, { x: number; y: number; r: number }>;
    cells: Cell[];
}

export type Order = "data" | "az" | "count";

/** Values named in a comma list come first, in that order; the rest keep their order (a funnel: "Lead, Won"). */
export function customFirst(order: string[], list: string): string[] {
    const want = (list || "").split(",").map(x => x.trim()).filter(x => x);
    if (!want.length) {
        return order;
    }
    const named = want.filter(w => order.includes(w));
    return named.concat(order.filter(o => !named.includes(o)));
}

/** One order for every view (so a group keeps its place while units move): data order, A to Z, or biggest first;
 *  `custom` (a comma list) puts the named values first. */
export function orderOf(all: Unit[], f: (u: Unit) => string, how: Order, only?: Set<string>, custom = ""): string[] {
    const counts = new Map<string, number>();
    for (const u of all) {
        counts.set(f(u), (counts.get(f(u)) || 0) + 1);
    }
    let order = [...counts.keys()];
    if (how === "az") {
        order = order.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    } else if (how === "count") {
        order = order.sort((a, b) => counts.get(b) - counts.get(a));
    }
    order = customFirst(order, custom);
    return only ? order.filter(v => only.has(v)) : order;
}

/** Pack n units into a box: columns and spacing that fill it, radius from the spacing (capped at maxR). */
export function pack(n: number, b: { w: number; h: number }, maxR: number): { cols: number; s: number; r: number } {
    const cols = Math.max(1, Math.ceil(Math.sqrt(n * b.w / Math.max(1, b.h))));
    const rows = Math.max(1, Math.ceil(n / cols));
    const s = Math.max(0.5, Math.min(b.w / cols, b.h / rows));
    return { cols, s, r: Math.max(0.6, Math.min(maxR, s * 0.42)) };
}

/** Grid: rows are groups, columns are stages, units packed inside each cell (a unit chart / waffle per cell). */
export function grid(units: Unit[], P: Box, groups: string[], stages: string[], maxR: number): Placed {
    const pos = new Map<string, { x: number; y: number; r: number }>(), cells: Cell[] = [];
    const by = scaleBand().domain(groups).range([P.y, P.y + P.h]).paddingInner(0.14);
    const bx = scaleBand().domain(stages).range([P.x, P.x + P.w]).paddingInner(0.08);
    const byCell = new Map<string, Unit[]>();
    for (const u of units) {
        const k = u.group + "␟" + u.stage;
        if (!byCell.has(k)) {
            byCell.set(k, []);
        }
        byCell.get(k).push(u);
    }
    const k = pack(Math.max(1, ...[...byCell.values()].map(v => v.length)), { w: bx.bandwidth(), h: by.bandwidth() }, maxR);
    byCell.forEach((list, key) => {
        const [g, st] = key.split("␟");
        list.forEach((u, j) => pos.set(u.key, {
            x: bx(st) + (j % k.cols) * k.s + k.s / 2, y: by(g) + Math.floor(j / k.cols) * k.s + k.s / 2, r: k.r
        }));
    });
    groups.forEach(g => cells.push({ label: g, group: g, x: P.x - 6, y: by(g), w: 0, h: by.bandwidth() }));
    stages.forEach(st => cells.push({ label: st, x: bx(st), y: P.y - 4, w: bx.bandwidth(), h: 0 }));
    return { pos, cells };
}

/** Columns: one stacked column of units per stage (a unit bar chart), units sorted by group so colours band. */
export function columns(units: Unit[], P: Box, groups: string[], stages: string[], maxR: number): Placed {
    const pos = new Map<string, { x: number; y: number; r: number }>(), cells: Cell[] = [];
    const bx = scaleBand().domain(stages).range([P.x, P.x + P.w]).paddingInner(0.18);
    const per = stages.map(st => units.filter(u => u.stage === st).sort((a, b) => groups.indexOf(a.group) - groups.indexOf(b.group)));
    const k = pack(Math.max(1, ...per.map(p => p.length)), { w: bx.bandwidth(), h: P.h }, maxR);
    per.forEach((list, i) => {
        const x0 = bx(stages[i]);
        list.forEach((u, j) => pos.set(u.key, {
            x: x0 + (j % k.cols) * k.s + k.s / 2, y: P.y + P.h - Math.floor(j / k.cols) * k.s - k.s / 2, r: k.r
        }));
        cells.push({ label: stages[i], x: x0, y: P.y + P.h + 4, w: bx.bandwidth(), h: 0 });
    });
    return { pos, cells };
}

/** Scatter by two numbers, with tick labels (fmt formats a tick) and axis titles. */
export function scatter(units: Unit[], P: Box, maxR: number, fmtX: (v: number) => string, fmtY: (v: number) => string,
    titleX: string, titleY: string, fontPx: number): Placed {
    const pos = new Map<string, { x: number; y: number; r: number }>(), cells: Cell[] = [];
    const xs = scaleLinear().domain(extent(units, u => u.x) as [number, number]).nice().range([P.x, P.x + P.w]);
    const ys = scaleLinear().domain(extent(units, u => u.y) as [number, number]).nice().range([P.y + P.h, P.y]);
    const r = Math.max(0.8, Math.min(maxR, Math.sqrt((P.w * P.h) / (units.length + 1)) * 0.35));
    units.forEach(u => pos.set(u.key, { x: xs(u.x), y: ys(u.y), r }));
    xs.ticks(6).forEach(t => cells.push({ label: fmtX(t), x: xs(t), y: P.y + P.h + 4, w: 0.001, h: 0, tick: true }));
    ys.ticks(5).forEach(t => cells.push({ label: fmtY(t), x: P.x - 6, y: ys(t), w: 0, h: 0.001, tick: true }));
    cells.push({ label: titleX, x: P.x, y: P.y + P.h + fontPx * 1.6, w: P.w, h: 0 });
    cells.push({ label: titleY, x: P.x, y: P.y - fontPx * 0.6, w: 0, h: 0, title: true });
    return { pos, cells };
}

/** Clusters: units pulled to one centre per group with physics, no overlaps; starts from where units are now. */
export function clusters(units: Unit[], P: Box, groups: string[], maxR: number, now: Map<string, MarkState>, gentle = false): Placed {
    const pos = new Map<string, { x: number; y: number; r: number }>(), cells: Cell[] = [];
    const cols = Math.ceil(Math.sqrt(groups.length)), rows = Math.ceil(groups.length / cols);
    const cw = P.w / cols, ch = P.h / rows;
    const r = Math.max(1, Math.min(maxR, Math.sqrt((P.w * P.h) / (units.length + 1)) * 0.32));
    const nodes: PhysicsNode[] = units.map(u => {
        const gi = groups.indexOf(u.group);
        const cx = P.x + (gi % cols) * cw + cw / 2, cy = P.y + Math.floor(gi / cols) * ch + ch / 2;
        const prev = now.get(u.key);
        return { key: u.key, tx: cx, ty: cy, r, x: prev ? prev.x : cx + (hash01(u.key) - 0.5) * cw * 0.5, y: prev ? prev.y : cy + (hash01(u.key + "y") - 0.5) * ch * 0.5 };
    });
    const at = gentle ? resume(nodes) : settle(nodes, units.length > 3000 ? 60 : 160);   // gentle: new rows, no restart
    nodes.forEach(n => pos.set(n.key, { x: at.get(n.key).x, y: at.get(n.key).y, r }));
    groups.forEach((g, gi) => cells.push({ label: g, group: g, x: P.x + (gi % cols) * cw, y: P.y + Math.floor(gi / cols) * ch, w: cw, h: 0 }));
    return { pos, cells };
}
