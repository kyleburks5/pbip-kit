/*
 *  Spatial canvas (kit proof visual): a picture of a space with data on top (docs/patterns/spatial-canvas.md).
 *  One Space definition (kit/patterns/spatial.ts) draws the background, places every point and decides its zone.
 *  Views: Dots (every row, filled = success, hollow = not), Zones (each zone coloured against its group's own range
 *  or a benchmark, faded or hidden below the small-sample threshold), Ranked (the zones slide out of the space into a
 *  row, best first). Clicking a zone filters the page on the Zone field; details sit in a docked readout beside the
 *  space, never over it; while nothing is picked the readout shows the standout zone.
 */
import powerbi from "powerbi-visuals-api";
import { FormattingSettingsService } from "powerbi-visuals-utils-formattingmodel";
import { select, Selection } from "d3-selection";
import { interpolateRgb } from "d3-interpolate";
import "../style/visual.less";

import { SpatialSettings, VIEWS } from "./settings";
import { readTheme, Theme, ThemeSource } from "./kit/theme";
import { Motion, Mark } from "./kit/motion";
import { Layers, MarkLayer } from "./kit/layers";
import { records, fetchMore, RecordSet, DataRecord } from "./kit/data";
import { applyTheme, pills, stateMessage, clearState, chromeBottom, clearChip, Later, LoadingGate } from "./kit/scene";
import { registerFonts } from "./kit/fonts";
import { FrameMeter } from "./kit/perf";
import { UpdateGate } from "./kit/updates";
import { Quality } from "./kit/quality";
import { StateStore } from "./kit/state";
import { applyFilter, filterValues, targetOf, columnOf } from "./kit/filter";
import { count } from "./kit/words";
import { Space, Zone, spaceByName, track, fitSpace, lineup } from "./kit/patterns/spatial";
import { readSampleRule, sample, countText, bandsFrom, onBand, standout, readableOn, SampleRule } from "./kit/patterns/honest";
import { biggestGap } from "./kit/patterns/headline";

import IVisual = powerbi.extensibility.visual.IVisual;
import IVisualHost = powerbi.extensibility.visual.IVisualHost;
import VisualConstructorOptions = powerbi.extensibility.visual.VisualConstructorOptions;
import VisualUpdateOptions = powerbi.extensibility.visual.VisualUpdateOptions;
import ISandboxExtendedColorPalette = powerbi.extensibility.ISandboxExtendedColorPalette;

type G = Selection<SVGGElement, unknown, null, undefined>;
interface ZoneStat { zone: Zone; n: number; made: number; rate: number; group: string; bench: number | null; modelValue: string | null }
interface Tf { k: number; x: number; y: number }
interface Look { fill: string; alpha: number; note: string; shown: boolean }

export class Visual implements IVisual {
    private host: IVisualHost;
    private fmt = new FormattingSettingsService();
    private s = new SpatialSettings();
    private layers: Layers;
    private markLayer: MarkLayer;
    private motion = new Motion({ animate: true, duration: 650, easing: "cubicInOut", stagger: 0, reduce: false });
    private meter: FrameMeter;
    private quality: Quality;
    private loading = new LoadingGate();
    private gate = new UpdateGate();
    private store: StateStore;
    private later = new Later();
    private theme: Theme;
    private data: RecordSet = { records: [], roles: new Set(), names: {}, formats: {}, hasHighlights: false, more: false };
    private dv: powerbi.DataView;
    private space: Space;
    private spaceKey = "";
    private stats: ZoneStat[] = [];
    private rule: SampleRule;
    private view = "";
    private picked = new Set<string>();             // zone ids
    private hover: string | null = null;
    private ready = false;
    private bg: Selection<SVGSVGElement, unknown, null, undefined>;
    private zonesG: G;
    private linesG: G;
    private outlineG: G;
    private labelsG: G;
    private headlineEl: HTMLDivElement;
    private readoutEl: Selection<HTMLDivElement, unknown, null, undefined>;
    private tfs = new Map<string, Tf>();            // each zone's transform now (on the space or in a ranked slot)
    private mismatch = 0;
    private lastSize = "";

    constructor(options: VisualConstructorOptions) {
        this.host = options.host;
        registerFonts();
        this.layers = new Layers(options.element);
        // the space sits behind every mark layer and takes the clicks; the mark layers let them through
        const svgEl = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        this.layers.root.node().insertBefore(svgEl, this.layers.gl);
        this.bg = select(svgEl).classed("kit-layer kit-space", true).attr("role", "group").attr("aria-label", "Zones");
        this.zonesG = this.bg.append("g").classed("kit-zones", true);
        this.linesG = this.bg.append("g").classed("kit-lines", true).attr("aria-hidden", "true").style("pointer-events", "none");
        this.outlineG = this.bg.append("g").classed("kit-zone-outlines", true).attr("aria-hidden", "true").style("pointer-events", "none");
        this.labelsG = this.layers.svg.append("g").classed("kit-zone-labels", true)   // above the points.attr("aria-hidden", "true").style("pointer-events", "none");
        for (const el of [this.layers.gl, this.layers.canvas, this.layers.svg.node() as unknown as HTMLElement]) {
            el.style.pointerEvents = "none";
        }
        this.markLayer = new MarkLayer(this.layers, 3000, 12000);
        this.meter = new FrameMeter(this.layers.root.node());
        this.quality = new Quality((t, why) => {
            this.layers.maxRatio = t.maxRatio;
            this.layers.resize(this.layers.width, this.layers.height);
            this.markLayer.svgMax = Math.min(3000, t.svgMax * 5);
            this.markLayer.canvasMax = t.canvasMax;
            this.meter.note(why);
        });
        this.quality.expose(this.layers.root.node());
        this.motion.onFrame = g => this.quality.frame(g);
        this.store = new StateStore(this.host);
        this.layers.html.append("div").classed("kit-top", true);
        this.headlineEl = this.layers.html.append("div").classed("kit-headline", true).attr("aria-live", "polite").node();
        this.readoutEl = this.layers.html.append("div").classed("kit-readout kit-ui", true).attr("aria-live", "polite");
        (this.layers.root.node() as unknown as { kitState: () => object }).kitState = () => ({
            view: this.view, picked: [...this.picked], zones: this.stats.map(z => ({ id: z.zone.id, n: z.n, rate: z.rate })),
            mismatch: this.mismatch, space: this.space ? this.space.id : null, standout: this.standoutZone()?.zone.id || null
        });
    }

    public update(options: VisualUpdateOptions): void {
        const t0 = performance.now();
        this.host.eventService.renderingStarted(options);
        try {
            this.updateInner(options);
            this.host.eventService.renderingFinished(options);
        } catch (e) {
            this.host.eventService.renderingFailed(options, String(e));
        } finally {
            this.meter.read(options.dataViews && options.dataViews[0]);
            this.meter.update(performance.now() - t0);
        }
    }

    private updateInner(options: VisualUpdateOptions): void {
        const dv = options.dataViews && options.dataViews[0];
        this.s = this.fmt.populateFormattingSettingsModel(SpatialSettings, dv);
        const s = this.s;
        this.theme = readTheme(this.host.colorPalette as ISandboxExtendedColorPalette, s as unknown as ThemeSource);
        this.motion.options = { animate: s.motion.animate.value, duration: s.motion.speed.value, easing: String(s.motion.easing.value.value), stagger: 0, reduce: s.motion.reduceMotion.value };
        this.layers.resize(options.viewport.width, options.viewport.height);
        this.bg.attr("width", this.layers.width).attr("height", this.layers.height);
        applyTheme(this.layers.root, this.theme, s.layout.padding.value, s.layout.gap.value);
        const kind = this.gate.classify(options, dv);
        this.meter.note(`update: ${kind}`);
        // Desktop is still querying: quiet shapes, not "No data" (a second empty update or 3 s: nothing is bound)
        if (this.loading.wait(this.layers.html, "space", "Loading", !!dv || this.ready, () => this.update({ ...options, dataViews: [] }))) {
            return;
        }
        if (kind === "same" && this.ready && !this.store.isNew(this.store.read(dv))) {
            this.echo(options);
            return;
        }
        this.dv = dv;
        this.data = records(dv, this.host);
        if (fetchMore(dv, this.host, this.data.records.length, 30000)) {
            stateMessage(this.layers.html, `Loading more ${this.noun()}`, this.data.records.length.toLocaleString(), "down");
            return;
        }
        this.rule = readSampleRule(dv?.metadata?.objects);
        if (!this.data.roles.has("X") || !this.data.roles.has("Y")) {
            this.zonesG.selectAll("*").remove();
            this.linesG.selectAll("*").remove();
            this.labelsG.selectAll("*").remove();
            this.markLayer.active.clear();
            this.readoutEl.style("display", "none");
            this.headlineEl.textContent = "";
            stateMessage(this.layers.html, "No data yet", "Add X and Y (where each row sits), an Item (one point per row), and a Zone to filter by.", "dot");
            return;
        }
        clearState(this.layers.html);
        this.buildSpace();
        this.view = this.view || String(s.space.start.value.value);
        const saved = this.store.read(dv);
        if (this.store.isNew(saved)) {
            this.store.remember(saved);
            if (VIEWS.includes(saved.view)) {
                this.view = saved.view;
            }
        }
        if (kind === "data" && this.ready && !this.later.pending) {
            this.picked.clear();                       // the page moved on: this visual's own pick goes
        }
        const back = filterValues(options.jsonFilters);
        if (back && !this.later.pending) {
            this.picked = new Set(this.stats.filter(z => back.some(v => this.sameZone(z, String(v)))).map(z => z.zone.id));
        }
        const size = `${options.viewport.width}x${options.viewport.height}`;
        this.render(size !== this.lastSize || !this.ready);
        this.lastSize = size;
        this.ready = true;
    }

    public getFormattingModel(): powerbi.visuals.FormattingModel {
        return this.fmt.buildFormattingModel(this.s);
    }

    // ------------------------------------------------------------------ data -> space -> zone stats
    private num(r: DataRecord, role: string): number {
        const v = r.fields[role];
        return v == null || v === "" ? NaN : Number(v);
    }

    private buildSpace(): void {
        const s = this.s.space, shape = String(s.shape.value.value);
        if (shape === "track") {
            const pts = this.data.records.map(r => ({ x: this.num(r, "X"), y: this.num(r, "Y"), order: this.data.roles.has("Order") ? this.num(r, "Order") : r.index, stage: this.data.roles.has("Zone") ? r.text.Zone : "Route" }));
            this.space = track(pts);
            this.spaceKey = "";
        } else {
            const key = `${shape}|${s.scale.value}|${s.custom.value}`;
            if (key !== this.spaceKey || !this.space) {
                this.space = spaceByName(shape, { scale: s.scale.value || 1, custom: shape === "custom" ? s.custom.value : "" });
                this.spaceKey = key;
                this.tfs.clear();
            }
        }
        type Acc = { n: number; made: number; groups: Map<string, number>; bench: number[]; model: Map<string, number> };
        const by = new Map<string, Acc>();
        this.mismatch = 0;
        const hasOut = this.data.roles.has("Outcome"), hasZone = this.data.roles.has("Zone");
        for (const r of this.data.records) {
            const z = this.space.zoneOf(this.space.toSpace(this.num(r, "X"), this.num(r, "Y")));
            if (!z) {
                continue;
            }
            let e = by.get(z.id);
            if (!e) {
                e = { n: 0, made: 0, groups: new Map(), bench: [], model: new Map() };
                by.set(z.id, e);
            }
            e.n++;
            e.made += hasOut && this.num(r, "Outcome") > 0 ? 1 : 0;
            const g = this.data.roles.has("Group") ? r.text.Group : "All";
            e.groups.set(g, (e.groups.get(g) || 0) + 1);
            const b = this.num(r, "Benchmark");
            if (Number.isFinite(b)) {
                e.bench.push(b);
            }
            if (hasZone) {
                const mz = String(r.fields.Zone ?? "");
                e.model.set(mz, (e.model.get(mz) || 0) + 1);
                if (this.space.id !== "track" && mz && !this.matches(z, mz)) {
                    this.mismatch++;                     // the model put this row in another zone than the picture does
                }
            }
        }
        const top = (m: Map<string, number>) => [...m].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] ?? null;
        this.stats = this.space.zones.map(zone => {
            const e = by.get(zone.id);
            const n = e ? e.n : 0;
            return {
                zone, n, made: e ? e.made : 0, rate: n ? e.made / n : NaN, group: e ? top(e.groups) : "All",
                bench: e && e.bench.length ? e.bench.reduce((a, b) => a + b, 0) / e.bench.length : null, modelValue: e ? top(e.model) : null
            };
        });
        if (!hasOut) {                                // without an outcome, a zone's value is its share of the rows
            const all = Math.max(1, this.stats.reduce((a, z) => a + z.n, 0));
            this.stats.forEach(z => { z.rate = z.n ? z.n / all : NaN; });
        }
    }

    private matches(z: Zone, v: string): boolean {
        const a = v.trim().toLowerCase();
        return a === z.id.toLowerCase() || a === z.name.toLowerCase();
    }

    private sameZone(z: ZoneStat, v: string): boolean {
        return z.modelValue != null ? z.modelValue === v : this.matches(z.zone, v);
    }

    private fmtRate(v: number): string {
        if (!Number.isFinite(v)) {
            return "-";
        }
        return this.data.roles.has("Outcome") ? `${Math.round(v * 100)}%` : `${Math.round(v * 100)}% of ${this.noun()}`;
    }

    // ------------------------------------------------------------------ words: the model's own nouns (v1.12)
    /** "shots" from the Item field's name (Shot ID), else "rows". */
    private noun(): string {
        const n = (this.data.names.Item || "").replace(/\s*(id|key|number|no\.?|code)$/i, "").trim().toLowerCase();
        return n ? (n.endsWith("s") ? n : `${n}s`) : "rows";
    }
    /** ["made", "missed"] from the Outcome field's name, else ["success", "not"]. */
    private outcomeWords(): [string, string] {
        const n = (this.data.names.Outcome || "").trim().toLowerCase();
        const pairs: Record<string, string> = { made: "missed", won: "lost", win: "loss", scored: "missed", hit: "missed",
            approved: "declined", passed: "failed", success: "failure", converted: "not converted", completed: "not completed",
            "on time": "late", "within sla": "breached", resolved: "unresolved" };
        if (!n) {
            return ["success", "not"];
        }
        const k = Object.keys(pairs).find(p => n === p || n.endsWith(p));
        return k ? [k, pairs[k]] : [n, `not ${n}`];
    }
    /** "the league" from the Benchmark field's name (League FG % by Zone), else "the benchmark". */
    private benchWord(): string {
        const n = (this.data.names.Benchmark || "").toLowerCase();
        const k = ["league", "average", "target", "plan", "budget", "norm", "national", "region"].find(w => n.includes(w));
        return k ? `the ${k}` : "the benchmark";
    }
    private cap(s: string): string {
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    // ------------------------------------------------------------------ colours
    private scale(t: number, confidence: number): string {
        const s = this.s.colors;
        const cold = s.cold.value.value || this.theme.palette[1] || this.theme.secondary;
        const hot = s.hot.value.value || this.theme.accent;
        const mid = interpolateRgb(this.theme.background, this.theme.foreground)(0.38);   // a visible mid grey
        const c = t < 0.5 ? interpolateRgb(cold, mid)(t * 2) : interpolateRgb(mid, hot)((t - 0.5) * 2);
        return interpolateRgb(mid, c)(Math.max(0, Math.min(1, confidence)));     // a thin sample fades to neutral
    }

    private bands(): Map<string, [number, number]> {
        return bandsFrom(this.stats.filter(z => sample(z.n, this.rule).show).map(z => ({ group: z.group, value: z.rate, weight: z.n })), 1.5, 0.05);
    }

    private position(z: ZoneStat, bands: Map<string, [number, number]>): number {
        const span = Math.max(0.001, this.s.space.benchmarkSpan.value || 0.1);
        return z.bench != null ? Math.max(0, Math.min(1, 0.5 + (z.rate - z.bench) / (2 * span))) : onBand(z.rate, bands.get(z.group) || [0, 1]);
    }

    private zoneLook(z: ZoneStat, bands: Map<string, [number, number]>, maxN: number): Look {
        const v = sample(z.n, this.rule);
        if (!v.show) {
            return { fill: this.theme.panel, alpha: z.n ? 0.25 : 0.08, note: v.note, shown: false };
        }
        return { fill: this.scale(this.position(z, bands), v.confidence), alpha: 0.35 + 0.5 * z.n / Math.max(1, maxN), note: v.note, shown: true };
    }

    private fadeMask = "";
    /** The fade mask (space units): full colour inside r0, none beyond r1. */
    private fadeId(): string {
        const f = this.space.fade;
        if (!this.fadeMask) {
            this.fadeMask = `kit-fade-${Math.random().toString(36).slice(2, 8)}`;
        }
        let defs = this.bg.select<SVGDefsElement>("defs");
        if (defs.empty()) {
            defs = this.bg.insert("defs", ":first-child");
        }
        defs.selectAll("*").remove();
        const g = defs.append("radialGradient").attr("id", `${this.fadeMask}-g`).attr("gradientUnits", "userSpaceOnUse")
            .attr("cx", f.x).attr("cy", f.y).attr("r", f.r1);
        g.append("stop").attr("offset", f.r0 / f.r1).attr("stop-color", "#fff");
        g.append("stop").attr("offset", 1).attr("stop-color", "#000");
        defs.append("mask").attr("id", this.fadeMask).attr("maskUnits", "userSpaceOnUse")
            .attr("x", -1e4).attr("y", -1e4).attr("width", 2e4).attr("height", 2e4)
            .append("rect").attr("x", -1e4).attr("y", -1e4).attr("width", 2e4).attr("height", 2e4)
            .attr("fill", `url(#${this.fadeMask}-g)`);
        return this.fadeMask;
    }

    private standoutZone(): ZoneStat | null {
        if (!this.s.space.standout.value || !this.stats.length || !this.rule) {
            return null;
        }
        const maxN = Math.max(1, ...this.stats.map(z => z.n));
        const bands = this.bands();
        const shown = this.stats.filter(z => z.n > 0 && sample(z.n, this.rule).show);
        if (shown.some(z => z.bench != null)) {          // "hot" = above the benchmark: the hottest, as the table ranks it
            const best = shown.filter(z => z.bench != null).sort((a, b) => (b.rate - b.bench) - (a.rate - a.bench))[0];
            return best || null;
        }
        const items = shown.map(z => {
            const edge = this.position(z, bands) - 0.5;
            return { key: z.zone.id, n: z.n, score: (z.n / maxN) * (1 + Math.max(0, edge) * 5), aboveBenchmark: edge > 0, z };
        });
        return standout(items, this.rule.minSample)?.z || null;
    }

    // ------------------------------------------------------------------ drawing
    private safeBox(): { x: number; y: number; w: number; h: number } {
        const s = this.s, pad = s.layout.padding.value;
        const head = s.space.headline.value ? this.theme.headlinePx * 1.5 + 4 : 0;
        const pill = s.space.pills.value ? this.theme.fontPx * 2.4 + 8 : 0;
        const top = Math.max(pad + head + pill, chromeBottom(this.layers.root.node(), 6));
        const ro = s.space.readout.value && this.layers.width > 420 ? Math.min(this.layers.width * 0.4, s.space.readoutWidth.value) : 0;
        this.layers.insets = { top, right: ro, bottom: 0, left: 0 };     // framing keeps clear of the header and readout
        this.readoutEl.style("display", ro ? null : "none").style("top", `${top}px`).style("width", `${ro}px`);
        return { x: pad, y: top, w: Math.max(20, this.layers.width - ro - pad * 2), h: Math.max(20, this.layers.height - top - pad) };
    }

    private render(instant = false): void {
        const s = this.s;
        this.drawChrome();
        const box = this.safeBox();
        const fit = fitSpace(this.space, box);
        const ranked = this.view === "ranked";
        const maxN = Math.max(1, ...this.stats.map(z => z.n));
        const bands = this.bands();
        const looks = new Map(this.stats.map(z => [z.zone.id, this.zoneLook(z, bands, maxN)]));
        const byId = new Map(this.stats.map(z => [z.zone.id, z]));
        const slots = ranked ? lineup(this.stats.filter(z => looks.get(z.zone.id).shown).map(z => z.zone), zn => byId.get(zn.id).rate, box,
            this.theme.fontPx * 3.2, 12, this.theme.fontPx * 12, fit.k * 2.5) : null;
        const lw = 1.2 / fit.k;
        const fg = this.theme.foreground;

        // the picture: the floor and the lines (hidden in the ranked row)
        this.linesG.attr("transform", `translate(${fit.x},${fit.y}) scale(${fit.k})`).style("opacity", ranked ? 0 : 1);
        this.linesG.selectAll<SVGPathElement, string>("path.kit-floor").data(this.space.floor ? [this.space.floor] : []).join("path")
            .classed("kit-floor", true).attr("d", d => d).attr("fill", this.theme.panel).attr("fill-opacity", 0.5);
        this.linesG.selectAll<SVGPathElement, string>("path.kit-line").data([this.space.lines]).join("path")
            .classed("kit-line", true).attr("d", d => d).attr("fill", "none").attr("stroke", fg).attr("stroke-opacity", 0.45)
            .attr("stroke-width", lw).attr("stroke-linejoin", "round");
        this.zonesG.lower();

        // zones: coloured against their own range, clickable, keyboard reachable
        const anyPick = this.picked.size > 0;
        const zoneView = this.view !== "dots";
        const sel = this.zonesG.selectAll<SVGPathElement, ZoneStat>("path.kit-zone").data(this.stats, d => d.zone.id).join("path")
            .classed("kit-zone", true)
            .attr("d", d => d.zone.d)
            .attr("shape-rendering", d => (d.zone.crisp ? "crispEdges" : null))
            .attr("tabindex", 0).attr("role", "button")
            .attr("aria-pressed", d => (this.picked.has(d.zone.id) ? "true" : "false"))
            .attr("aria-label", d => this.zoneLabel(d, looks.get(d.zone.id).note))
            .attr("fill", d => (zoneView ? looks.get(d.zone.id).fill : this.theme.panel))
            .attr("mask", this.space.fade && !ranked ? `url(#${this.fadeId()})` : null)
            .attr("fill-opacity", d => {
                if (ranked && !slots.has(d.zone.id)) {
                    return 0;
                }
                const base = zoneView ? looks.get(d.zone.id).alpha : 0.05;
                return anyPick && !this.picked.has(d.zone.id) ? base * this.theme.dim : base;
            })
            .on("click", (e: MouseEvent, d) => { e.stopPropagation(); this.pick(d, e.ctrlKey || e.metaKey || e.shiftKey); })
            .on("keydown", (e: KeyboardEvent, d) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    this.pick(d, e.ctrlKey || e.shiftKey);
                } else if (e.key === "Escape") {
                    this.clearPicks();
                }
            })
            .on("pointerenter focus", (_e, d) => { this.hover = d.zone.id; this.drawReadout(); this.outline(); })
            .on("pointerleave blur", () => { this.hover = null; this.drawReadout(); this.outline(); });
        this.bg.on("click", () => this.clearPicks());
        this.outline();

        // zone transforms: in place on the space, or sliding into the ranked row
        const target = (id: string): Tf => (slots && slots.has(id) ? slots.get(id) : fit);
        const from = new Map(this.stats.map(z => [z.zone.id, this.tfs.get(z.zone.id) || fit]));
        const apply = (p: number) => {
            sel.attr("transform", d => {
                const a = from.get(d.zone.id), b = target(d.zone.id);
                const t = { k: a.k + (b.k - a.k) * p, x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p };
                this.tfs.set(d.zone.id, t);
                return `translate(${t.x},${t.y}) scale(${t.k})`;
            });
            this.outline();
        };
        if (instant) {
            apply(1);
        } else {
            void this.motion.tween(0, 1, apply);
        }
        this.drawZoneLabels(fit, slots, looks);

        // points: filled = success, hollow = not (shape, not colour alone); hidden in the ranked row
        const hasOut = this.data.roles.has("Outcome");
        const r = Math.max(1.5, s.layout.markSize.value * Math.min(1, Math.sqrt(1500 / Math.max(400, this.data.records.length))));
        const marks: Mark[] = [];
        for (const rec of this.data.records) {
            const p = this.space.toSpace(this.num(rec, "X"), this.num(rec, "Y"));
            if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) {
                continue;
            }
            const z = this.space.zoneOf(p);
            const inPick = !anyPick || (z && this.picked.has(z.id));
            const base = this.view === "dots" ? 0.55 : 0.22;          // dots: see-through, so density shows          // under the zones, the points stay quiet
            marks.push({
                key: rec.key, x: fit.x + p.x * fit.k, y: fit.y + p.y * fit.k, r: ranked ? 0 : this.view === "dots" ? r : r * 0.75,
                color: fg, alpha: ranked ? 0 : inPick ? base : base * this.theme.dim,
                shape: hasOut && !(this.num(rec, "Outcome") > 0) ? "ring" : "disc"
            });
        }
        const renderer = this.markLayer.choose(marks.length);
        void this.motion.to(marks, frame => renderer.draw(frame, { k: 1, x: 0, y: 0 }), instant);
        this.drawReadout();
        this.drawHeadline();
        if (this.mismatch) {
            stateMessage(this.layers.html, "Zones disagree", `${count(this.mismatch, "point")} sit in a different zone than the model's Zone column says.`, "info").classed("kit-banner", true);
        }
    }

    /** The picked and hovered zones' edges (the edge path, not the fill's strips), on top, following each zone. */
    private outline(): void {
        const on = this.stats.filter(z => this.picked.has(z.zone.id) || this.hover === z.zone.id);
        this.outlineG.selectAll<SVGPathElement, ZoneStat>("path").data(on, d => d.zone.id).join("path")
            .attr("d", d => d.zone.outline).attr("fill", "none").attr("stroke-linecap", "square")
            .attr("stroke", d => (this.picked.has(d.zone.id) ? this.theme.selected : this.theme.foreground))
            .attr("transform", d => { const t = this.tfs.get(d.zone.id); return t ? `translate(${t.x},${t.y}) scale(${t.k})` : null; })
            .attr("stroke-width", d => 2 / (this.tfs.get(d.zone.id)?.k || 1));
    }

    private zoneLabel(z: ZoneStat, note: string): string {
        if (!z.n) {
            return `${z.zone.name}: no data`;
        }
        if (!sample(z.n, this.rule).show) {
            return `${z.zone.name}: ${note} ${this.noun()}`;
        }
        return `${z.zone.name}: ${count(z.n, this.noun())}, ${this.fmtRate(z.rate)}${note ? ` (${note})` : ""}`;
    }

    private drawZoneLabels(fit: Tf, slots: Map<string, { slot: { x: number; y: number; w: number; h: number }; rank: number }> | null, looks: Map<string, Look>): void {
        const show = this.s.space.labels.value;
        const data = show ? this.stats.filter(z => (slots ? slots.has(z.zone.id) : z.n > 0 && this.view === "zones" && looks.get(z.zone.id).shown)) : [];
        const px = this.theme.fontPx;
        const at = (d: ZoneStat) => (slots ? { x: slots.get(d.zone.id).slot.x + slots.get(d.zone.id).slot.w / 2, y: slots.get(d.zone.id).slot.y + slots.get(d.zone.id).slot.h + px * 1.3 }
            : { x: fit.x + d.zone.centroid.x * fit.k, y: fit.y + d.zone.centroid.y * fit.k + px * 0.35 });
        const t = this.labelsG.selectAll<SVGTextElement, ZoneStat>("text").data(data, d => d.zone.id).join("text")
            .attr("text-anchor", "middle").attr("font-size", px).attr("font-family", this.theme.font)
            .attr("font-variant-numeric", "tabular-nums")
            .attr("paint-order", "stroke").attr("stroke-width", 4.5).attr("stroke-linejoin", "round")
            .attr("stroke", d => (slots ? "none" : this.theme.background)).attr("stroke-opacity", 0.92)
            .classed("kit-label", true)
            .attr("fill", d => {
                if (slots) {
                    return this.theme.foreground;
                }
                const l = looks.get(d.zone.id);       // the colour as seen: the fill at its opacity over the background
                return readableOn(interpolateRgb(this.theme.background, l.fill)(l.alpha), this.theme.foreground, this.theme.background);
            })
            .attr("x", d => at(d).x).attr("y", d => at(d).y);
        t.selectAll("tspan").remove();
        const fitText = (txt: string, w: number) => {          // shorten to the slot (about 0.55 em a character)
            const max = Math.max(4, Math.floor(w / (px * 0.55)));
            return txt.length > max ? `${txt.slice(0, max - 1).trimEnd()}…` : txt;
        };
        t.append("tspan").text(d => (slots ? fitText(`${slots.get(d.zone.id).rank}. ${d.zone.name}`, slots.get(d.zone.id).slot.w) : this.fmtRate(d.rate)));
        if (slots) {
            t.append("tspan").attr("x", d => at(d).x).attr("dy", px * 1.25).attr("fill-opacity", 0.75)
                .text(d => `${this.fmtRate(d.rate)} · ${countText(d.n, this.rule)}`);
        }
    }

    private drawChrome(): void {
        const s = this.s.space;
        const top = this.layers.html.select<HTMLDivElement>(".kit-top");
        top.selectAll("*").remove();
        if (s.pills.value) {
            pills(top, VIEWS.map(v => ({ value: v, label: v === "dots" ? "Dots" : v === "zones" ? "Zones" : "Ranked", icon: v === "ranked" ? "columns" : v === "dots" ? "scatter" : "grid" })),
                this.view, v => this.setView(v), "Views");
        }
        if (this.view !== "dots") {                          // the zone scale: cold -> usual -> hot (v1.12)
            const benched = this.stats.some(z => z.bench != null);
            const leg = top.append("div").attr("class", "kit-legend").attr("aria-hidden", "true")
                .style("display", "inline-flex").style("align-items", "center").style("gap", "6px")
                .style("font-size", "11px").style("margin-left", "12px").style("opacity", "0.85");
            leg.append("span").text("Colder");
            leg.append("span").style("display", "inline-block").style("width", "72px").style("height", "8px").style("border-radius", "4px")
                .style("background", `linear-gradient(90deg, ${this.scale(0, 1)}, ${this.scale(0.5, 1)}, ${this.scale(1, 1)})`);
            leg.append("span").text(benched ? `Hotter than ${this.benchWord()}` : "Hotter than usual");
        } else {                                             // dots: made filled, missed hollow
            const leg = top.append("div").attr("class", "kit-legend").attr("aria-hidden", "true")
                .style("display", "inline-flex").style("align-items", "center").style("gap", "6px")
                .style("font-size", "11px").style("margin-left", "12px").style("opacity", "0.85");
            const [yes, no] = this.outcomeWords();
            leg.append("span").text(`● ${yes}   ○ ${no}`);
        }
        clearChip(top, this.picked.size, "Clear", () => this.clearPicks());
        this.headlineEl.style.display = s.headline.value ? "" : "none";
        this.layers.root.attr("aria-label", `${this.space.name}, ${count(this.data.records.length, "point")}, ${this.view} view`);
    }

    private drawHeadline(): void {
        if (!this.s.space.headline.value) {
            return;
        }
        const picks = this.stats.filter(z => this.picked.has(z.zone.id));
        if (picks.length === 2 && this.data.roles.has("Outcome")) {
            const [a, b] = picks;
            const all = this.stats.filter(z => sample(z.n, this.rule).show);
            const rates = all.map(z => z.rate), ns = all.map(z => z.n);
            const ok = (z: ZoneStat) => sample(z.n, this.rule).show;
            this.headlineEl.textContent = biggestGap({ a: a.zone.name, b: b.zone.name }, [
                { label: `${this.outcomeWords()[0]} rate`, better: "high", format: v => `${Math.round(v * 100)} points`, a: ok(a) ? a.rate : null, b: ok(b) ? b.rate : null, norm: [Math.min(...rates), Math.max(...rates)] },
                { label: "volume", better: "high", format: v => count(Math.round(v), this.noun()), a: ok(a) ? a.n : null, b: ok(b) ? b.n : null, norm: [Math.min(...ns), Math.max(...ns)] }
            ]) || `${a.zone.name} and ${b.zone.name} are level.`;
            return;
        }
        if (picks.length === 1) {
            this.headlineEl.textContent = `${this.zoneLabel(picks[0], sample(picks[0].n, this.rule).note)}.`;
            return;
        }
        const so = this.standoutZone();
        const total = this.stats.reduce((a, z) => a + z.n, 0);
        const nn = this.noun();
        const hot = so && so.bench != null ? `${so.zone.name} is the hottest against ${this.benchWord()}: ${this.fmtRate(so.rate)}, ` +
            `${Math.round((so.rate - so.bench) * 100) >= 0 ? "+" : ""}${Math.round((so.rate - so.bench) * 100)} points, on ${count(so.n, nn)}.` : null;
        this.headlineEl.textContent = hot || (so ? `${so.zone.name} stands out: ${this.fmtRate(so.rate)} on ${count(so.n, nn)} of ${total.toLocaleString()}.`
            : total ? `${count(total, nn)} across ${count(this.stats.filter(z => z.n).length, "zone")}.` : `No ${nn} in this view.`);
    }

    private drawReadout(): void {
        if (!this.s.space.readout.value) {
            return;
        }
        const id = this.hover || (this.picked.size === 1 ? [...this.picked][0] : null);
        const so = id ? null : this.standoutZone();
        const z = id ? this.stats.find(x => x.zone.id === id) : so;
        const el = this.readoutEl;
        el.selectAll("*").remove();
        if (!z) {
            el.append("div").classed("kit-readout-note", true).text("Point at a zone to read it here.");
            return;
        }
        const v = sample(z.n, this.rule);
        if (so) {
            el.append("div").classed("kit-readout-note", true).text(so.bench != null ? `Hottest against ${this.benchWord()}` : "Standout");
        }
        el.append("div").classed("kit-readout-title", true).text(z.zone.name);
        const row = (k: string, val: string) => { const r = el.append("div").classed("kit-readout-row", true); r.append("span").text(k); r.append("span").text(val); };
        row(this.cap(this.noun()), countText(z.n, this.rule));
        if (v.show) {
            row(this.data.roles.has("Outcome") ? `${this.cap(this.outcomeWords()[0])} rate` : "Share", this.fmtRate(z.rate));
            if (z.bench != null) {
                const d = Math.round((z.rate - z.bench) * 100);
                row(`vs ${this.benchWord().replace(/^the /, "")}`, `${d > 0 ? "+" : ""}${d} points`);
            } else {
                const band = this.bands().get(z.group);
                if (band && this.data.roles.has("Outcome")) {
                    row(`Usual for ${z.group}`, `${Math.round(Math.max(0, band[0]) * 100)}-${Math.round(Math.min(1, band[1]) * 100)}%`);
                }
            }
        }
        if (v.note) {
            el.append("div").classed("kit-readout-note", true).text(v.show ? `Limited sample: fewer than ${this.rule.minSample} ${this.noun()}, shown faded.` : `Not shown: ${v.note} ${this.noun()}.`);
        }
    }

    // ------------------------------------------------------------------ interaction
    private setView(v: string): void {
        if (v === this.view) {
            return;
        }
        this.view = v;
        this.render();
        this.store.save({ view: v, drill: "", camera: null });
    }

    private pick(z: ZoneStat, multi: boolean): void {
        if (!z.n) {
            return;
        }
        const id = z.zone.id;
        if (multi) {
            if (this.picked.has(id)) {
                this.picked.delete(id);
            } else {
                this.picked.add(id);
            }
        } else if (this.picked.size === 1 && this.picked.has(id)) {
            this.picked.clear();
        } else {
            this.picked = new Set([id]);
        }
        this.render();
        this.send();
    }

    private clearPicks(): void {
        if (!this.picked.size) {
            return;
        }
        this.picked.clear();
        this.render();
        this.send();
    }

    /** Filter the page on the Zone field (after the move lands), or cross-highlight the zone's rows. */
    private send(): void {
        const mode = String(this.s.interaction.clickMode.value.value);
        const land = this.motion.options.animate && !this.motion.options.reduce ? Math.min(1400, this.motion.options.duration + 200) : 0;
        if (mode === "crossFilter" || !this.data.roles.has("Zone")) {
            const ids = this.data.records.filter(r => {
                const z = this.space.zoneOf(this.space.toSpace(this.num(r, "X"), this.num(r, "Y")));
                return z && this.picked.has(z.id);
            }).map(r => r.id);
            const sm = this.host.createSelectionManager();
            this.later.run(() => { void (ids.length ? sm.select(ids, false) : sm.clear()); }, land);
            return;
        }
        const values = this.stats.filter(z => this.picked.has(z.zone.id)).map(z => z.modelValue).filter(v => v != null && v !== "") as string[];
        const target = targetOf(columnOf(this.dv, "Zone"));
        this.later.run(() => applyFilter(this.host, target, values), land);
    }

    private echo(options: VisualUpdateOptions): void {
        if (this.later.pending) {
            return;
        }
        const vals = filterValues(options.jsonFilters) || [];
        const next = new Set(this.stats.filter(z => vals.some(v => this.sameZone(z, String(v)))).map(z => z.zone.id));
        if ([...next].sort().join("|") !== [...this.picked].sort().join("|")) {
            this.picked = next;
            this.render();
        }
    }
}
