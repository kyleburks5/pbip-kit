/*
 *  pbip-kit app-visual template: interaction.
 *  Selection (click, Ctrl/Shift/Cmd-click to add, click the background to clear, the context menu, Enter/Space from
 *  the keyboard, the host's callback when a bookmark restores a selection) is adapted from Microsoft's Dot Plot
 *  visual (behavior.ts, MIT, Copyright (c) Microsoft Corporation; see NOTICE.md). The rest is the kit's own: hit tests
 *  that work for every drawing layer, hover tooltips, a brush that selects a range, zoom and pan (the camera), and
 *  arrow-key focus with a live region that reads the focused item.
 */
import powerbi from "powerbi-visuals-api";
import { quadtree, Quadtree } from "d3-quadtree";
import { brush, BrushBehavior, D3BrushEvent } from "d3-brush";
import { zoom, ZoomBehavior, zoomIdentity, ZoomTransform } from "d3-zoom";
import { Selection } from "d3-selection";
import { Layers, Camera } from "./layers";
import { Mark } from "./motion";

import ISelectionId = powerbi.visuals.ISelectionId;
import ISelectionManager = powerbi.extensibility.ISelectionManager;
import ITooltipService = powerbi.extensibility.ITooltipService;
import VisualTooltipDataItem = powerbi.extensibility.VisualTooltipDataItem;

export interface Selectable {
    key: string;
    id: ISelectionId;
    label: string;
    tooltip: VisualTooltipDataItem[];
}

export interface InteractionHandlers {
    onSelectionChanged(selected: Set<string>): void;
    /** Filter mode: the keys now selected become a real filter (the visual applies it); [] removes it. */
    onFilter?(keys: string[]): void;
    /** A swipe on a touch screen: +1 next, -1 previous (the visual switches its view). */
    onSwipe?(direction: number): void;
    onFocus?(key: string | null): void;
    onActivate?(key: string): void;
}

export class Interaction {
    private items = new Map<string, Selectable>();
    private tree: Quadtree<Mark> | null = null;
    private marks: Mark[] = [];
    private focusIndex = -1;
    private live: Selection<HTMLDivElement, unknown, null, undefined>;
    private brushG: Selection<SVGGElement, unknown, null, undefined>;
    private brushB: BrushBehavior<unknown> | null = null;
    private zoomB: ZoomBehavior<SVGSVGElement, unknown> | null = null;
    private syncing = false;
    private allowed = true;
    camera: Camera = { k: 1, x: 0, y: 0 };
    selected = new Set<string>();
    tooltips = true;
    /** "crossFilter" (a selection: this page) or "filter" (a real filter: slicer-like, sync slicers, bookmarks). */
    mode: "crossFilter" | "filter" = "crossFilter";
    private swipeStart: { x: number; y: number } | null = null;

    constructor(private layers: Layers, private selection: ISelectionManager, private tooltip: ITooltipService,
        private handlers: InteractionHandlers, private onCamera: (c: Camera) => void, allowInteractions = true) {
        this.live = layers.root.append("div").classed("kit-live", true).attr("aria-live", "polite");
        // the harness (and any test) reads the marks as drawn; a plain property, no global
        (layers.root.node() as unknown as { kitMarks: () => Mark[] }).kitMarks = () => this.marks;
        this.brushG = layers.overlay.append("g").classed("kit-brush", true);
        this.selection.registerOnSelectCallback((ids: ISelectionId[]) => this.syncFromHost(ids));
        const svg = layers.svg;
        this.allowed = allowInteractions;
        if (!allowInteractions) {
            return;                               // dashboards and other read-only hosts: draw only (hostCapabilities)
        }
        svg.attr("tabindex", 0).attr("role", "listbox").attr("aria-multiselectable", "true");
        svg.on("click", (e: MouseEvent) => this.click(e));
        svg.on("contextmenu", (e: MouseEvent) => this.contextMenu(e));
        svg.on("mousemove", (e: MouseEvent) => this.hover(e));
        svg.on("mouseleave", () => this.tooltip.hide({ immediately: true, isTouchEvent: false }));
        svg.on("keydown", (e: KeyboardEvent) => this.key(e));
        // touch: a horizontal swipe switches the view; taps arrive as clicks; two fingers pinch-zoom (enableZoom)
        layers.root.on("pointerdown.swipe", (e: PointerEvent) => {
            this.swipeStart = e.pointerType === "touch" ? { x: e.clientX, y: e.clientY } : null;
        });
        layers.root.on("pointerup.swipe", (e: PointerEvent) => {
            const s = this.swipeStart;
            this.swipeStart = null;
            if (s && e.pointerType === "touch") {
                const dx = e.clientX - s.x, dy = e.clientY - s.y;
                if (Math.abs(dx) > 60 && Math.abs(dy) < Math.abs(dx) / 2) {
                    this.handlers.onSwipe?.(dx < 0 ? 1 : -1);
                }
            }
        });
    }

    /** The marks as drawn now (positions for hit tests) and the data behind them. */
    setMarks(marks: Mark[], items: Selectable[]): void {
        this.marks = marks;
        this.items = new Map(items.map(i => [i.key, i]));
        this.tree = quadtree<Mark>().x(d => d.x).y(d => d.y).addAll(marks.filter(m => m.r > 0));
        if (this.mode === "crossFilter") {
            this.syncFromHost(this.selection.getSelectionIds() as ISelectionId[], false);
        }
        this.label();
    }

    /** Screen reader names on SVG marks (Canvas and WebGL marks are read through the focus and the live region). */
    label(): void {
        this.layers.marksG.selectAll<SVGCircleElement, Mark>("circle.kit-mark")
            .attr("role", "option")
            .attr("aria-label", d => this.items.get(d.key)?.label || null)
            .attr("aria-selected", d => String(this.selected.has(d.key)));
    }

    /** Keys restored from a filter coming back (filter mode: a bookmark, a sync slicer, a reopen). */
    restore(keys: string[]): void {
        this.selected = new Set(keys);
    }

    private toWorld(e: MouseEvent): [number, number] {
        const r = this.layers.svg.node().getBoundingClientRect();
        return [(e.clientX - r.left - this.camera.x) / this.camera.k, (e.clientY - r.top - this.camera.y) / this.camera.k];
    }

    hit(e: MouseEvent): Mark | null {
        if (!this.tree) {
            return null;
        }
        const [x, y] = this.toWorld(e);
        const maxR = Math.max(4, ...this.marks.slice(0, 50).map(m => m.r));
        const m = this.tree.find(x, y, maxR + 3 / this.camera.k);
        return m && Math.hypot(m.x - x, m.y - y) <= m.r + 3 / this.camera.k ? m : null;
    }

    private click(e: MouseEvent): void {
        const target = e.target as Element;
        if (target.closest && target.closest(".kit-ui")) {
            return;                                   // pills, buttons, panels handle their own clicks
        }
        const m = this.hit(e);
        if (!m) {
            this.clear();
            return;
        }
        this.select([m.key], e.ctrlKey || e.shiftKey || e.metaKey);
    }

    /** Select keys (toggle with multi), and send the selection to the host: cross-filter going out. */
    select(keys: string[], multi = false): void {
        const ids: ISelectionId[] = [];
        if (!multi && keys.length === 1 && this.selected.size === 1 && this.selected.has(keys[0])) {
            this.clear();
            return;
        }
        if (!multi) {
            this.selected.clear();
        }
        for (const k of keys) {
            if (multi && this.selected.has(k)) {
                this.selected.delete(k);
            } else {
                this.selected.add(k);
            }
            const it = this.items.get(k);
            if (it) {
                ids.push(it.id);
            }
        }
        if (this.mode === "filter") {
            this.handlers.onFilter?.([...this.selected]);
        } else if (multi) {
            this.selection.select(ids, true);
        } else if (ids.length) {
            this.selection.select(ids, false);
        } else {
            this.selection.clear();
        }
        this.handlers.onSelectionChanged(new Set(this.selected));
        this.announce(`${this.selected.size} selected`);
    }

    clear(): void {
        if (!this.selected.size) {
            return;
        }
        this.selected.clear();
        if (this.mode === "filter") {
            this.handlers.onFilter?.([]);
        } else {
            this.selection.clear();
        }
        this.handlers.onSelectionChanged(new Set());
        this.announce("Selection cleared");
    }

    private syncFromHost(ids: ISelectionId[], notify = true): void {
        const next = new Set<string>();
        if (ids && ids.length) {
            this.items.forEach((it, k) => {
                if (ids.some(id => id.equals(it.id))) {
                    next.add(k);
                }
            });
        }
        const same = next.size === this.selected.size && [...next].every(k => this.selected.has(k));
        this.selected = next;
        if (!same && notify) {
            this.handlers.onSelectionChanged(new Set(next));
        }
    }

    private contextMenu(e: MouseEvent): void {
        e.preventDefault();
        const m = this.hit(e);
        const id = m ? this.items.get(m.key)?.id : null;
        this.selection.showContextMenu(id || ({} as ISelectionId), { x: e.clientX, y: e.clientY });
    }

    private hover(e: MouseEvent): void {
        if (!this.tooltips) {
            return;
        }
        const m = this.hit(e);
        const it = m ? this.items.get(m.key) : null;
        if (!it) {
            this.tooltip.hide({ immediately: false, isTouchEvent: false });
            return;
        }
        this.tooltip.show({ coordinates: [e.clientX, e.clientY], dataItems: it.tooltip, identities: [it.id], isTouchEvent: false });
    }

    /** Arrow keys move the focus through the marks in reading order; Enter / Space select; Escape clears. */
    private key(e: KeyboardEvent): void {
        const order = [...this.marks].filter(m => m.r > 0).sort((a, b) => (a.y - b.y) || (a.x - b.x));
        if (!order.length) {
            return;
        }
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
        if (step) {
            e.preventDefault();
            this.focusIndex = Math.max(0, Math.min(order.length - 1, this.focusIndex + step));
            const m = order[this.focusIndex];
            this.drawFocus(m);
            this.announce(this.items.get(m.key)?.label || m.key);
            this.handlers.onFocus?.(m.key);
        } else if ((e.key === "Enter" || e.key === " ") && this.focusIndex >= 0) {
            e.preventDefault();
            const m = order[this.focusIndex];
            this.select([m.key], e.ctrlKey || e.shiftKey || e.metaKey);
            this.handlers.onActivate?.(m.key);
        } else if (e.key === "Escape") {
            this.clear();
            this.drawFocus(null);
        }
    }

    drawFocus(m: Mark | null): void {
        const g = this.layers.overlay.selectAll<SVGCircleElement, Mark>("circle.kit-focus").data(m ? [m] : []);
        g.join("circle").classed("kit-focus", true)
            .attr("cx", d => d.x * this.camera.k + this.camera.x)
            .attr("cy", d => d.y * this.camera.k + this.camera.y)
            .attr("r", d => d.r * this.camera.k + 4);
    }

    announce(text: string): void {
        this.live.text(text);
    }

    /** Drag a rectangle (in world units) to select every mark inside it. Off removes the brush. */
    enableBrush(on: boolean): void {
        if (!on || !this.allowed) {
            this.brushG.on(".brush", null).selectAll("*").remove();
            this.brushB = null;
            return;
        }
        this.brushB = brush<unknown>()
            .extent([[0, 0], [this.layers.width, this.layers.height]])
            .filter((e: MouseEvent) => !e.type.startsWith("touch") && e.shiftKey === false && !e.button && !this.hit(e))
            .on("end", (e: D3BrushEvent<unknown>) => {
                if (!e.selection || !e.sourceEvent) {
                    return;
                }
                const [[x0, y0], [x1, y1]] = e.selection as [[number, number], [number, number]];
                const w = (x: number, y: number) => [(x - this.camera.x) / this.camera.k, (y - this.camera.y) / this.camera.k];
                const [a, b] = w(x0, y0), [c, d] = w(x1, y1);
                const keys = this.marks.filter(m => m.r > 0 && m.x >= a && m.x <= c && m.y >= b && m.y <= d).map(m => m.key);
                this.brushG.call(this.brushB.move, null);
                if (keys.length) {
                    this.select(keys, false);
                }
            });
        this.brushG.call(this.brushB);
        // the brush is a mouse gesture: on touch screens taps select, a swipe changes the view and two fingers zoom
        this.brushG.on("touchstart.brush touchmove.brush touchend.brush touchcancel.brush", null);
    }

    /** Wheel / pinch zoom and drag-pan (with Shift so it doesn't fight the brush). */
    enableZoom(on: boolean): void {
        if (!on || !this.allowed) {
            this.layers.svg.on(".zoom", null);
            this.zoomB = null;
            return;
        }
        this.zoomB = zoom<SVGSVGElement, unknown>()
            .scaleExtent([1, 40])
            .filter((e: Event) => e.type === "wheel" || (e as MouseEvent).shiftKey
                || (e.type.startsWith("touch") && ((e as TouchEvent).touches?.length || 0) >= 2))   // pinch
            .on("zoom", (e: { transform: ZoomTransform }) => {
                if (!this.syncing) {
                    this.setCamera({ k: e.transform.k, x: e.transform.x, y: e.transform.y }, true);
                }
            });
        this.layers.svg.call(this.zoomB).on("dblclick.zoom", null);
    }

    setCamera(c: Camera, fromZoom = false): void {
        this.camera = c;
        if (this.zoomB && !fromZoom) {
            this.syncing = true;                  // keep d3-zoom's own state in step with camera moves we animate
            this.layers.svg.call(this.zoomB.transform, zoomIdentity.translate(c.x, c.y).scale(c.k));
            this.syncing = false;
        }
        this.onCamera(c);
    }

    /** The camera that fits a world rectangle into the view (for zoom-to-item). */
    /**
     * The camera that frames a box with `pad` around it, centred in the safe area: the visual minus what its own
     * header, docked panels and legends cover (Layers.insets), so a framed item never sits under one of them.
     */
    fit(x: number, y: number, w: number, h: number, pad = 24): Camera {
        const s = this.layers.insets;
        const W = Math.max(10, this.layers.width - s.left - s.right), H = Math.max(10, this.layers.height - s.top - s.bottom);
        const k = Math.min((W - pad * 2) / Math.max(1, w), (H - pad * 2) / Math.max(1, h));
        return { k, x: s.left + (W - w * k) / 2 - x * k, y: s.top + (H - h * k) / 2 - y * k };
    }
}
