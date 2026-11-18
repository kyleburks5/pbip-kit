/*
 *  pbip-kit app-visual template: screen changes and in-place updates without blank frames.
 *  Elements that are the same thing on two screens carry the same `data-share` key (a stage's mini column on the
 *  overview and its bar on the detail screen; a card and the detail it opens). A change records where every shared
 *  element is, draws the new state, then flies a ghost of each shared element from its old box and colour to its new
 *  one while the rest cross-fades: the outgoing screen stays on screen (a frozen copy) and fades out as the new one
 *  fades in, so no frame is ever empty (Desktop review 2026-11-17: a column click blanked the chart for 0.3 s, then
 *  replayed a 1 s staggered entrance; Back did the same). The same call without `screen` resizes shared elements in
 *  place for a data update or a click inside a screen: no fade, no entrance.
 *  Reduce motion (or Motion off): the new state appears at once.
 */
import { interpolateRgb } from "d3-interpolate";
import { Motion } from "./motion";

interface Shot { key: string; x: number; y: number; w: number; h: number; color: string; opacity: number; radius: string }

export interface MorphOptions {
    /** A screen change: the outgoing screen cross-fades out while the new one fades in (false: in place). */
    screen?: boolean;
    /** Length in ms (default: the motion's duration, capped 300-450 so a screen change never drags). */
    duration?: number;
}

function colourOf(el: Element): { color: string; opacity: number } {
    const cs = getComputedStyle(el);
    if (el instanceof SVGElement) {
        const fill = cs.fill && cs.fill !== "none" ? cs.fill : (el.getAttribute("fill") || "transparent");
        return { color: fill, opacity: Number(cs.fillOpacity || el.getAttribute("fill-opacity") || 1) * Number(cs.opacity || 1) };
    }
    const bg = cs.backgroundColor && cs.backgroundColor !== "rgba(0, 0, 0, 0)" ? cs.backgroundColor : "transparent";
    return { color: bg, opacity: Number(cs.opacity || 1) };
}

/** Where every shared element is now, relative to `origin`. */
export function snapshot(layer: HTMLElement, origin: HTMLElement): Map<string, Shot> {
    const o = origin.getBoundingClientRect();
    const out = new Map<string, Shot>();
    layer.querySelectorAll<HTMLElement | SVGElement>("[data-share]").forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width < 0.5 || r.height < 0.5) {
            return;
        }
        const { color, opacity } = colourOf(el);
        out.set(el.getAttribute("data-share"), {
            key: el.getAttribute("data-share"), x: r.left - o.left, y: r.top - o.top, w: r.width, h: r.height, color, opacity,
            radius: el instanceof SVGElement ? `${Number(el.getAttribute("rx") || 0)}px` : getComputedStyle(el).borderRadius
        });
    });
    return out;
}

/**
 * Change what `layer` shows by running `render` (which draws the new state into `layer`), with shared elements morphing
 * by key and, for a screen change, the old screen cross-fading out. Resolves when the move has finished.
 */
export class Morpher {
    private running: { stop: () => void } | null = null;
    /** How many entrance or morph moves ran: the harness checks a filter round trip adds none. */
    moves = 0;

    constructor(private motion: Motion, private root: HTMLElement) {
        (root as unknown as { kitMoves: () => number }).kitMoves = () => this.moves;
    }

    run(layer: HTMLElement, render: () => void, opts: MorphOptions = {}): Promise<void> {
        this.running?.stop();                          // a new change takes over: the last one lands at once
        const reduce = this.motion.reduced || !this.motion.options.animate;
        const before = reduce ? new Map<string, Shot>() : snapshot(layer, this.root);
        let ghostOld: HTMLElement | null = null;
        if (opts.screen && !reduce) {                  // the outgoing screen, frozen where it is
            ghostOld = layer.cloneNode(true) as HTMLElement;
            ghostOld.removeAttribute("id");
            ghostOld.classList.add("kit-morph-out");
            ghostOld.setAttribute("aria-hidden", "true");
            ghostOld.style.pointerEvents = "none";
            layer.parentElement.insertBefore(ghostOld, layer.nextSibling);
        }
        render();
        if (reduce) {
            ghostOld?.remove();
            return Promise.resolve();
        }
        const after = snapshot(layer, this.root);
        // a screen change flies every element both screens share; in place, only those whose box changed (a colour
        // change alone just shows: hiding the real element for it would only make it flicker)
        const shared = [...after.keys()].filter(k => before.has(k) && (opts.screen || moved(before.get(k), after.get(k))));
        if (!opts.screen && !shared.length) {
            return Promise.resolve();
        }
        // a shared element that holds other content (a card) stays where it is in both screens and cross-fades with
        // them while an outline of it flies; a leaf shape (a column, a bar) is hidden and its ghost flies instead
        const isBox = (el: Element | null) => !!el && !(el instanceof SVGElement) && el.querySelector("*") !== null;
        if (ghostOld) {                                // in the frozen old screen, hide only the leaves that fly
            ghostOld.querySelectorAll<HTMLElement | SVGElement>("[data-share]").forEach(el => {
                if (shared.includes(el.getAttribute("data-share")) && !isBox(el)) {
                    el.style.visibility = "hidden";
                }
            });
        }
        this.moves++;
        if (!opts.screen) {
            return this.inPlace(layer, before, after, shared);
        }
        const fly = document.createElement("div");
        fly.className = "kit-morph-fly";
        fly.setAttribute("aria-hidden", "true");
        this.root.appendChild(fly);
        const reals = new Map<string, HTMLElement | SVGElement>();
        layer.querySelectorAll<HTMLElement | SVGElement>("[data-share]").forEach(el => reals.set(el.getAttribute("data-share"), el));
        const ghosts = shared.map(k => {
            const a = before.get(k), b = after.get(k), g = document.createElement("div");
            g.className = "kit-morph-ghost";
            g.style.borderRadius = b.radius;
            fly.appendChild(g);
            const real = reals.get(k), box = isBox(real);
            if (!box) {
                real.style.visibility = "hidden";
            }
            return { a, b, g, real, box, mix: interpolateRgb(a.color, b.color) };
        });
        if (opts.screen) {
            layer.style.opacity = "0";
        }
        const dur = opts.duration ?? Math.max(300, Math.min(450, this.motion.options.duration * 0.6));
        let stopped = false;
        const finish = () => {
            if (stopped) {
                return;
            }
            stopped = true;
            ghosts.forEach(x => { if (!x.box) { x.real.style.visibility = ""; } });
            fly.remove();
            ghostOld?.remove();
            layer.style.opacity = "";
            this.running = null;
        };
        this.running = { stop: finish };
        const frame = (t: number) => {                // t arrives eased (Motion.tween)
            if (stopped) {
                return;
            }
            const p = Math.max(0, Math.min(1, t));
            for (const x of ghosts) {
                const { a, b, g } = x;
                g.style.left = `${a.x + (b.x - a.x) * p}px`;
                g.style.top = `${a.y + (b.y - a.y) * p}px`;
                g.style.width = `${a.w + (b.w - a.w) * p}px`;
                g.style.height = `${a.h + (b.h - a.h) * p}px`;
                g.style.background = x.mix(p);
                const o = a.opacity + (b.opacity - a.opacity) * p;
                // a box's outline is translucent (its own text shows through) and fades as its screen arrives
                g.style.opacity = String(x.box ? o * 0.35 * Math.max(0, 1 - p * 1.25) : o);
            }
            if (opts.screen) {                         // outgoing out a little faster than incoming in: they overlap
                if (ghostOld) {
                    ghostOld.style.opacity = String(Math.max(0, 1 - t / 0.7));
                }
                layer.style.opacity = String(Math.min(1, Math.max(0, (t - 0.1) / 0.75)));
            }
        };
        frame(0);
        return this.motion.tween(0, 1, frame, dur).then(finish);
    }

    /**
     * In place (new data, a click inside a screen): each moved element slides and resizes from its old box to its new
     * one on itself (a transform that ends at none), so it stays visible and clickable the whole time.
     */
    private inPlace(layer: HTMLElement, before: Map<string, Shot>, after: Map<string, Shot>, keys: string[]): Promise<void> {
        const els = new Map<string, HTMLElement | SVGElement>();
        layer.querySelectorAll<HTMLElement | SVGElement>("[data-share]").forEach(el => els.set(el.getAttribute("data-share"), el));
        const items = keys.map(k => ({ el: els.get(k), a: before.get(k), b: after.get(k) })).filter(x => x.el);
        items.forEach(({ el }) => {
            el.style.transformOrigin = "0 0";
            if (el instanceof SVGElement) {
                el.style.transformBox = "fill-box";
            }
        });
        let stopped = false;
        const set = (p: number) => {
            if (stopped) {
                return;
            }
            for (const { el, a, b } of items) {
                const q = 1 - p;
                const sx = (a.w / Math.max(0.5, b.w)) * q + p, sy = (a.h / Math.max(0.5, b.h)) * q + p;
                el.style.transform = p >= 1 ? "" : `translate(${(a.x - b.x) * q}px, ${(a.y - b.y) * q}px) scale(${sx}, ${sy})`;
            }
        };
        const finish = () => {
            if (!stopped) {
                set(1);
                stopped = true;
                this.running = null;
            }
        };
        this.running = { stop: finish };
        set(0);
        const dur = Math.max(250, Math.min(400, this.motion.options.duration * 0.5));
        return this.motion.tween(0, 1, set, dur).then(finish);
    }
}

function moved(a: Shot, b: Shot): boolean {
    return Math.abs(a.x - b.x) > 0.5 || Math.abs(a.y - b.y) > 0.5 || Math.abs(a.w - b.w) > 0.5 || Math.abs(a.h - b.h) > 0.5;
}
