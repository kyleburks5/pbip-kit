/*
 *  pbip-kit app-visual template: free-form scene.
 *  Anything can go anywhere: cards, panels, text, pills, buttons, icons and images in the HTML layer, placed by
 *  pixel box. Screens: several views inside one visual, with a back stack, a Back button and a breadcrumb. Every
 *  element is built with DOM calls (never innerHTML: the certification lint rejects it), is keyboard reachable and
 *  takes its look from the Theme.
 */
import { select, Selection } from "d3-selection";
import { ICONS } from "./icons";
import { Theme } from "./theme";

type Div = Selection<HTMLDivElement, unknown, null, undefined>;

export interface Box {
    x: number;
    y: number;
    w: number;
    h: number;
}

export function place(el: Div, b: Box): Div {
    return el.style("left", `${b.x}px`).style("top", `${b.y}px`).style("width", `${b.w}px`).style("height", `${b.h}px`);
}

export function icon(parent: Selection<HTMLElement, unknown, null, undefined> | Div, name: string, size = 16, color = "currentColor"): void {
    const svg = parent.append("svg").attr("viewBox", "0 0 24 24").attr("width", size).attr("height", size)
        .attr("aria-hidden", "true").classed("kit-icon", true);
    svg.append("path").attr("d", ICONS[name] || ICONS.dot).attr("fill", "none").attr("stroke", color)
        .attr("stroke-width", 2).attr("stroke-linecap", "round").attr("stroke-linejoin", "round");
}

export function applyTheme(root: Div, t: Theme, padding: number, gap: number): void {
    root.style("--kit-fg", t.foreground).style("--kit-fg2", t.secondary).style("--kit-bg", t.background)
        .style("--kit-panel", t.panel).style("--kit-accent", t.accent).style("--kit-selected", t.selected)
        .style("--kit-font", t.font).style("--kit-size", `${t.fontPx}px`).style("--kit-head", `${t.headlinePx}px`)
        .style("--kit-radius", `${t.radius}px`).style("--kit-shadow", t.shadow)
        .style("--kit-pad", `${padding}px`).style("--kit-gap", `${gap}px`)
        .classed("kit-hc", t.highContrast);
}

/**
 * The bottom of the visual's header as drawn (the headline, then the Back / breadcrumb / pills row, which may wrap):
 * the drawing area starts below it. Measured, not assumed, so a long headline or a wrapped row still gets its own band.
 */
export function chromeBottom(root: HTMLElement, gap = 8): number {
    const r = root.getBoundingClientRect();
    if (r.width < 40 || r.height < 40) {
        return 0;                                      // not laid out yet (a page not in front): use the formula
    }
    let b = 0;
    root.querySelectorAll<HTMLElement>(".kit-headline, .kit-top > *:not(.kit-clear)").forEach(el => {
        const q = el.getBoundingClientRect();
        if (q.height > 0 && (el.textContent.trim() || el.querySelector("input, button, svg"))) {   // a search box has no text
            b = Math.max(b, q.bottom - r.top);
        }
    });
    return b ? Math.min(Math.ceil(b + gap), Math.round(r.height * 0.45)) : 0;   // never more than the header's share
}

/**
 * A small "Clear" chip in the header row while the visual's own clicks filter the page (n picks); it clears them.
 * Call it after the header row is drawn and whenever the picks change.
 */
export function clearChip(parent: Div, n: number, label: string, onClear: () => void): void {
    parent.selectAll(".kit-clear").remove();
    const root = (parent.node() as HTMLElement)?.closest(".kit-root");
    root?.classList.toggle("has-clear", n > 0);
    if (!n) {
        return;
    }
    parent.append("button").classed("kit-clear kit-ui", true).attr("type", "button")
        .attr("aria-label", `${label}: ${n}`).attr("title", `${label} (${n})`)
        .text(`× ${label}`)
        .on("click", (e: MouseEvent) => { e.stopPropagation(); onClear(); });
}

/**
 * When a click's filter goes out: after the move it starts has landed. Power BI re-draws the rest of the page when a
 * filter arrives, and that work shares the thread the animation runs on (Desktop review 2026-11-17: frames of
 * 300-400 ms mid-move). The visual shows the result at once; the page follows a moment later.
 */
export class Later {
    private timer: number | null = null;
    get pending(): boolean {
        return this.timer != null;
    }
    run(fn: () => void, ms: number): void {
        if (this.timer != null) {
            window.clearTimeout(this.timer);
        }
        this.timer = window.setTimeout(() => { this.timer = null; fn(); }, Math.max(0, ms));
    }
}

export interface PillOption {
    value: string;
    label: string;
    icon?: string;
}

/** A pill group (role tablist): one pill per option, arrow keys move between them. */
export function pills(parent: Div, options: PillOption[], current: string, onPick: (v: string) => void, label = "Views"): Div {
    parent.selectAll(".kit-pills").remove();
    const g = parent.append("div").classed("kit-pills kit-ui", true).attr("role", "tablist").attr("aria-label", label);
    options.forEach((o, i) => {
        const b = g.append("button").classed("kit-pill", true).classed("is-on", o.value === current)
            .attr("role", "tab").attr("aria-selected", String(o.value === current))
            .attr("tabindex", o.value === current ? 0 : -1)
            .on("click", (e: MouseEvent) => { e.stopPropagation(); onPick(o.value); })
            .on("keydown", (e: KeyboardEvent) => {
                const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
                if (d) {
                    e.preventDefault();
                    onPick(options[(i + d + options.length) % options.length].value);
                }
            });
        if (o.icon) {
            icon(b as unknown as Div, o.icon, 14);
        }
        b.append("span").text(o.label);
    });
    return g;
}

export interface CardSpec {
    title: string;
    value?: string;
    note?: string;
    icon?: string;
    onOpen?: () => void;
}

/** A card: title, a big value, a note, an optional icon; clickable (Enter / Space too) when onOpen is given. */
export function card(parent: Div, b: Box, spec: CardSpec): Div {
    const c = place(parent.append("div").classed("kit-card kit-ui", true), b);
    if (spec.onOpen) {
        c.attr("role", "button").attr("tabindex", 0)
            .attr("aria-label", `${spec.title}${spec.value ? ": " + spec.value : ""}. Open details`)
            .on("click", (e: MouseEvent) => { e.stopPropagation(); spec.onOpen(); })
            .on("keydown", (e: KeyboardEvent) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    spec.onOpen();
                }
            });
    }
    const head = c.append("div").classed("kit-card-head", true);
    if (spec.icon) {
        icon(head, spec.icon, 16);
    }
    head.append("span").classed("kit-card-title", true).text(spec.title);
    if (spec.value != null) {
        c.append("div").classed("kit-card-value", true).text(spec.value);
    }
    if (spec.note) {
        c.append("div").classed("kit-card-note", true).text(spec.note);
    }
    return c;
}

export function text(parent: Div, b: Box, value: string, cls = "kit-text"): Div {
    return place(parent.append("div").classed(cls, true), b).text(value);
}

/** Screens inside one visual: a back stack, a Back button and a breadcrumb. */
export class Screens<T = unknown> {
    private stack: Array<{ id: string; title: string; data?: T }> = [];

    constructor(private onShow: (id: string, data: T | undefined) => void) { }

    get current(): { id: string; title: string; data?: T } | undefined {
        return this.stack[this.stack.length - 1];
    }

    get depth(): number {
        return this.stack.length;
    }

    reset(id: string, title: string): void {
        this.stack = [{ id, title }];
        this.onShow(id, undefined);
    }

    push(id: string, title: string, data?: T): void {
        this.stack.push({ id, title, data });
        this.onShow(id, data);
    }

    back(to?: number): void {
        if (this.stack.length <= 1) {
            return;
        }
        this.stack = this.stack.slice(0, to == null ? this.stack.length - 1 : to + 1);
        const s = this.current;
        this.onShow(s.id, s.data);
    }

    /** The Back button and the breadcrumb ("Overview / North / Q3"), each crumb a button. */
    nav(parent: Div): Div {
        parent.selectAll(".kit-nav").remove();
        const n = parent.append("div").classed("kit-nav kit-ui", true).attr("role", "navigation").attr("aria-label", "Breadcrumb");
        if (this.stack.length > 1) {
            const b = n.append("button").classed("kit-back", true).attr("aria-label", "Back")
                .on("click", (e: MouseEvent) => { e.stopPropagation(); this.back(); });
            icon(b as unknown as Div, "back", 14);
            b.append("span").text("Back");
        }
        this.stack.forEach((s, i) => {
            if (i) {
                n.append("span").classed("kit-crumb-sep", true).attr("aria-hidden", "true").text("/");
            }
            const last = i === this.stack.length - 1;
            const c = n.append(last ? "span" : "button").classed("kit-crumb", true).text(s.title);
            if (last) {
                c.attr("aria-current", "page");
            } else {
                c.on("click", (e: MouseEvent) => { e.stopPropagation(); this.back(i); });
            }
        });
        return n;
    }
}

/** "No data" (with what to add), "Too many points" (with what the visual did) and similar states. */
export function stateMessage(parent: Div, title: string, detail: string, iconName = "info"): Div {
    parent.selectAll(".kit-state").remove();
    const s = parent.append("div").classed("kit-state kit-ui", true).attr("role", "status");
    icon(s, iconName, 28);
    s.append("div").classed("kit-state-title", true).text(title);
    s.append("div").classed("kit-state-detail", true).text(detail);
    return s;
}

export function clearState(parent: Div): void {
    parent.selectAll(".kit-state").remove();
}

export { select };
