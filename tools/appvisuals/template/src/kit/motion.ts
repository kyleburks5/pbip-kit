/*
 *  pbip-kit app-visual template: the animation engine.
 *  One tween drives every drawing layer (SVG, Canvas, WebGL): each item moves from its current state to its target
 *  with the formatting pane's duration, easing and per-item stagger; items that enter grow in, items that leave shrink
 *  out. Sequences chain tweens; physics runs d3-force; the camera zooms and pans. Reduce motion (the pane switch or
 *  the operating system's prefers-reduced-motion) makes every move jump to its end state.
 */
import { timer, Timer } from "d3-timer";
import * as ease from "d3-ease";
import { interpolateRgb } from "d3-interpolate";
import { forceSimulation, forceX, forceY, forceCollide, SimulationNodeDatum } from "d3-force";

export interface MarkState {
    x: number;
    y: number;
    r: number;
    color: string;
    alpha: number;
    stroke?: string;
    /** Encode with shape as well as colour: "ring" draws the mark hollow (a miss, an estimate, a not-yet). */
    shape?: "disc" | "ring";
}

export interface Mark extends MarkState {
    key: string;
}

export interface MotionOptions {
    animate: boolean;
    duration: number;
    easing: string;
    stagger: number;
    reduce: boolean;
}

const EASE: Record<string, (t: number) => number> = {
    cubicInOut: ease.easeCubicInOut,
    cubicOut: ease.easeCubicOut,
    quadInOut: ease.easeQuadInOut,
    expInOut: ease.easeExpInOut,
    backOut: ease.easeBackOut,
    linear: ease.easeLinear
};

export function systemPrefersReducedMotion(): boolean {
    try {
        return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch {
        return false;
    }
}

export class Motion {
    private current = new Map<string, MarkState>();
    private running: Timer | null = null;
    private finishing: (() => void) | null = null;
    private lastFrame = 0;
    /** Each animation frame of a move gets the gap since the last one (ms): the quality governor listens (quality.ts). */
    onFrame: ((gapMs: number) => void) | null = null;

    constructor(public options: MotionOptions) { }

    private beat(): void {
        const now = performance.now();
        if (this.lastFrame && this.onFrame) {
            this.onFrame(now - this.lastFrame);
        }
        this.lastFrame = now;
    }

    get reduced(): boolean {
        return !this.options.animate || this.options.reduce || systemPrefersReducedMotion() || this.options.duration <= 0;
    }

    easing(): (t: number) => number {
        return EASE[this.options.easing] || ease.easeCubicInOut;
    }

    /** Total stagger is capped at the duration, so 30,000 items don't take minutes. */
    private staggerFor(n: number): number {
        if (n <= 1) {
            return 0;
        }
        return Math.min(this.options.stagger, this.options.duration / n);
    }

    /** The states currently drawn (for hit tests and the next tween's start). */
    states(): Map<string, MarkState> {
        return this.current;
    }

    stop(): void {
        if (this.running) {
            this.running.stop();
            this.running = null;
        }
        const f = this.finishing;
        this.finishing = null;
        if (f) {
            f();
        }
    }

    /**
     * Move every mark to its target. draw() gets the in-between marks each frame (and once at the end).
     * Resolves when the move has finished (at once with reduced motion).
     */
    to(targets: Mark[], draw: (marks: Mark[]) => void, instant = false): Promise<void> {
        this.stop();
        const from = this.current;
        const keys = new Set(targets.map(t => t.key));
        const leaving: Mark[] = [];
        from.forEach((s, k) => {
            if (!keys.has(k)) {
                leaving.push({ key: k, ...s, r: 0, alpha: 0 });
            }
        });
        const all = targets.concat(leaving);
        const start = all.map(t => {
            const s = from.get(t.key);
            return s ? { key: t.key, ...s } : { key: t.key, ...t, r: 0, alpha: 0 };
        });
        const finalMarks = targets.map(t => ({ ...t }));
        const end = () => {
            this.current = new Map(finalMarks.map(m => [m.key, m]));
            draw(finalMarks);
        };
        // the first frame is the final frame: nothing animates in on the first draw, so a page that isn't in front
        // (no animation frames there) or an export to PDF / PowerPoint never captures a blank starting frame
        if (this.reduced || from.size === 0 || instant) {
            end();
            return Promise.resolve();
        }
        const ez = this.easing();
        const dur = this.options.duration;
        const step = this.staggerFor(all.length);
        const total = dur + step * all.length;
        const colors = all.map((t, i) => (start[i].color === t.color ? null : interpolateRgb(start[i].color, t.color)));
        return new Promise<void>(resolve => {
            this.finishing = () => { end(); resolve(); };
            this.lastFrame = 0;
            this.running = timer(elapsed => {
                this.beat();
                const frame: Mark[] = new Array(all.length);
                for (let i = 0; i < all.length; i++) {
                    const a = start[i], b = all[i];
                    const p = ez(Math.max(0, Math.min(1, (elapsed - i * step) / dur)));
                    frame[i] = {
                        key: b.key,
                        x: a.x + (b.x - a.x) * p,
                        y: a.y + (b.y - a.y) * p,
                        r: Math.max(0, a.r + (b.r - a.r) * p),
                        alpha: a.alpha + (b.alpha - a.alpha) * p,
                        color: colors[i] ? colors[i](p) : b.color,
                        stroke: b.stroke,
                        shape: p < 0.5 ? a.shape : b.shape
                    };
                }
                draw(frame);
                if (elapsed >= total) {
                    this.running.stop();
                    this.running = null;
                    this.finishing = null;
                    end();
                    resolve();
                }
            });
        });
    }

    /** Run moves one after another (a sequence). */
    async sequence(steps: Array<() => Promise<void>>): Promise<void> {
        for (const s of steps) {
            await s();
        }
    }

    /** A single number from a to b (camera moves, counters); onFrame gets each value. */
    tween(a: number, b: number, onFrame: (v: number) => void, duration = this.options.duration): Promise<void> {
        if (this.reduced || duration <= 0) {
            onFrame(b);
            return Promise.resolve();
        }
        const ez = this.easing();
        this.lastFrame = 0;
        return new Promise<void>(resolve => {
            const t = timer(elapsed => {
                this.beat();
                const p = ez(Math.min(1, elapsed / duration));
                onFrame(a + (b - a) * p);
                if (p >= 1) {
                    t.stop();
                    resolve();
                }
            });
        });
    }
}

/**
 * Frame-rate independent smoothing: move `current` towards `target` by the share that `rate` (per second) gives over
 * `dtMs`, so a follow move looks the same at 30 and at 120 frames a second (current + (target - current) * (1 - e^(-rate dt))).
 */
export function damp(current: number, target: number, rate: number, dtMs: number): number {
    return current + (target - current) * (1 - Math.exp(-rate * Math.max(0, dtMs) / 1000));
}

/**
 * A value that follows a moving target smoothly (a camera following a selection, a highlight's strength, a readout
 * sliding beside the pointer). set() a new target; it runs its own timer until it arrives, then stops.
 * Reduce motion: it jumps.
 */
export class Follow {
    value: number[];
    private target: number[];
    private t: Timer | null = null;
    private last = 0;
    constructor(start: number[], private onChange: (v: number[]) => void, private rate = 10, private reduced: () => boolean = () => false) {
        this.value = start.slice();
        this.target = start.slice();
    }
    set(target: number[]): void {
        this.target = target.slice();
        if (this.reduced()) {
            this.stop();
            this.value = target.slice();
            this.onChange(this.value);
            return;
        }
        if (!this.t) {
            this.last = 0;
            this.t = timer(elapsed => {
                const dt = this.last ? elapsed - this.last : 16;
                this.last = elapsed;
                this.value = this.value.map((v, i) => damp(v, this.target[i], this.rate, dt));
                const done = this.value.every((v, i) => Math.abs(v - this.target[i]) < 1e-3 * (1 + Math.abs(this.target[i])));
                if (done) {
                    this.value = this.target.slice();
                }
                this.onChange(this.value);
                if (done) {
                    this.stop();
                }
            });
        }
    }
    stop(): void {
        if (this.t) {
            this.t.stop();
            this.t = null;
        }
    }
}

export interface EnterFrom {
    opacity?: number;
    dx?: number;
    dy?: number;
    scale?: number;
    scaleX?: number;
}

/**
 * Enter effect for HTML or SVG elements (cards, rows, panels): from `from` to their natural state, after `delay` ms,
 * through the same timer, duration and easing as the marks (so the harness clock and reduce motion apply).
 */
export function enter(motion: Motion, el: HTMLElement | SVGElement, from: EnterFrom, delay = 0): void {
    if (motion.reduced) {
        return;
    }
    const ez = motion.easing(), dur = motion.options.duration;
    const set = (p: number) => {
        const q = 1 - p;
        const parts: string[] = [];
        if (from.dx || from.dy) {
            parts.push(`translate(${(from.dx || 0) * q}px, ${(from.dy || 0) * q}px)`);
        }
        if (from.scale != null) {
            parts.push(`scale(${from.scale + (1 - from.scale) * p})`);
        }
        if (from.scaleX != null) {
            parts.push(`scaleX(${from.scaleX + (1 - from.scaleX) * p})`);
        }
        el.style.transform = parts.join(" ");
        if (from.opacity != null) {
            el.style.opacity = String(from.opacity + (1 - from.opacity) * p);
        }
    };
    set(0);
    const t = timer(elapsed => {
        const p = ez(Math.max(0, Math.min(1, (elapsed - delay) / dur)));
        set(p);
        if (p >= 1) {
            t.stop();
            el.style.transform = "";
            el.style.opacity = "";
        }
    });
}

export interface PhysicsNode extends SimulationNodeDatum {
    key: string;
    tx: number;
    ty: number;
    r: number;
}

/**
 * Physics: pull each node to its target point without overlaps (d3-force). Settles synchronously: the result is the
 * layout the Motion tween then moves to, so physics also respects reduce motion and stays deterministic.
 */
const settled = new Map<string, Map<string, { x: number; y: number }>>();   // the last few layouts, by their input

export function settle(nodes: PhysicsNode[], ticks = 160): Map<string, { x: number; y: number }> {
    nodes.forEach(n => {                           // half-pixel starts: the same view always settles the same way
        n.x = Math.round((n.x ?? n.tx) * 2) / 2;      // (tiny float noise from the last animation would otherwise
        n.y = Math.round((n.y ?? n.ty) * 2) / 2;      // grow into a visibly different layout)
    });
    // the same input settles to the same layout: keep the last few, so a redraw never re-runs the physics
    // (Desktop review 2026-11-17: 100-670 ms frames from physics re-run on updates that changed nothing)
    const sig = `${ticks}|` + nodes.map(n => `${n.key}:${n.tx | 0},${n.ty | 0},${Math.round(n.r * 10)},${n.x},${n.y}`).join(";");
    const hit = settled.get(sig);
    if (hit) {
        nodes.forEach(n => { const p = hit.get(n.key); n.x = p.x; n.y = p.y; });
        return new Map(hit);
    }
    const sim = forceSimulation(nodes)
        .force("x", forceX<PhysicsNode>(d => d.tx).strength(0.12))
        .force("y", forceY<PhysicsNode>(d => d.ty).strength(0.12))
        .force("collide", forceCollide<PhysicsNode>(d => d.r + 0.6).iterations(2))
        .stop();
    for (let i = 0; i < ticks; i++) {
        sim.tick();
    }
    const out = new Map(nodes.map(n => [n.key, { x: n.x, y: n.y }]));
    settled.set(sig, out);
    if (settled.size > 8) {
        settled.delete(settled.keys().next().value);
    }
    return new Map(out);
}

/**
 * Physics that carries on from where the nodes are now (set n.x / n.y to the current positions): low energy and few
 * ticks, so new data or a resize nudges the layout instead of restarting it (a restart from scratch made the clusters
 * jiggle on every update, Desktop review 2026-11-17). Nodes without a position start at their target.
 */
export function resume(nodes: PhysicsNode[], ticks = 60, alpha = 0.25): Map<string, { x: number; y: number }> {
    nodes.forEach(n => {
        n.x = n.x ?? n.tx;
        n.y = n.y ?? n.ty;
    });
    const sim = forceSimulation(nodes)
        .force("x", forceX<PhysicsNode>(d => d.tx).strength(0.12))
        .force("y", forceY<PhysicsNode>(d => d.ty).strength(0.12))
        .force("collide", forceCollide<PhysicsNode>(d => d.r + 0.6).iterations(2))
        .alpha(alpha)
        .stop();
    for (let i = 0; i < ticks; i++) {
        sim.tick();
    }
    return new Map(nodes.map(n => [n.key, { x: n.x, y: n.y }]));
}

