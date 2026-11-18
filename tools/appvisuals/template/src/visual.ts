/*
 *  pbip-kit app-visual template: the starter visual (a unit chart: one dot per record).
 *  Built on the kit runtime in ./kit and the pattern modules in ./kit/patterns. Started from Microsoft's Dot Plot
 *  visual (MIT, Copyright (c) Microsoft Corporation; see NOTICE.md): its IVisual shape, formatting-model service,
 *  selection behaviour and capabilities layout. Views (grid by group and stage, columns by stage, scatter by X and Y,
 *  clusters with physics) are the same dots moving (morph-layouts); pills switch them (view-pills); a headline says
 *  what the view shows (live-headline); clicks cross-filter the page and dim the rest (focus-dim); a group label
 *  drills in and a double-click flies the camera to a dot (drill-zoom); dragging selects a range (range-select).
 *  `pbik visual new` copies this folder and renames the visual; docs/patterns/app-visuals says how to change it.
 */
import powerbi from "powerbi-visuals-api";
import { FormattingSettingsService } from "powerbi-visuals-utils-formattingmodel";
import { valueFormatter } from "powerbi-visuals-utils-formattingutils";
import "../style/visual.less";

import { AppSettings, VIEWS, VIEW_LABELS } from "./kit/settings";
import { readTheme, Theme, ColorScale } from "./kit/theme";
import { Motion, Mark } from "./kit/motion";
import { Layers, MarkLayer, Camera } from "./kit/layers";
import { records, fetchMore, RecordSet, DataRecord } from "./kit/data";
import { Interaction, Selectable } from "./kit/interaction";
import { applyTheme, pills, stateMessage, clearState, chromeBottom, clearChip, Later } from "./kit/scene";
import { registerFonts } from "./kit/fonts";
import { Unit, Box, Cell, Placed, Order, orderOf, grid, columns, scatter, clusters } from "./kit/patterns/layouts";
import { emphasis } from "./kit/patterns/emphasis";
import { headline } from "./kit/patterns/headline";
import { Drill, flyTo, frameMark } from "./kit/patterns/drill";
import { StateStore, ViewState } from "./kit/state";
import { FrameMeter } from "./kit/perf";
import { UpdateGate } from "./kit/updates";
import { applyFilter, filterValues, targetOf } from "./kit/filter";

import IVisual = powerbi.extensibility.visual.IVisual;
import IVisualHost = powerbi.extensibility.visual.IVisualHost;
import VisualConstructorOptions = powerbi.extensibility.visual.VisualConstructorOptions;
import VisualUpdateOptions = powerbi.extensibility.visual.VisualUpdateOptions;
import ISandboxExtendedColorPalette = powerbi.extensibility.ISandboxExtendedColorPalette;
import VisualUpdateType = powerbi.VisualUpdateType;

const ICON: Record<string, string> = { grid: "grid", columns: "columns", scatter: "scatter", clusters: "clusters" };

export class Visual implements IVisual {
    private meter: FrameMeter;
    private gate = new UpdateGate();
    private ready = false;
    private later = new Later();
    private host: IVisualHost;
    private fmt = new FormattingSettingsService();
    private settings = new AppSettings();
    private layers: Layers;
    private markLayer: MarkLayer;
    private motion = new Motion({ animate: true, duration: 650, easing: "cubicInOut", stagger: 3, reduce: false });
    private ia: Interaction;
    private drill: Drill;
    private theme: Theme;
    private data: RecordSet = { records: [], roles: new Set(), names: {}, formats: {}, hasHighlights: false, more: false };
    private byKey = new Map<string, DataRecord>();
    private view = "";
    private cells: Cell[] = [];
    private headlineEl: HTMLDivElement;
    private colors: ColorScale;
    private loc: powerbi.extensibility.ILocalizationManager;
    private store: StateStore;
    private clusterCache: { key: string; placed: Placed } | null = null;
    private lastSize = "";
    private restoring = false;
    private dv: powerbi.DataView;

    /** A localised string (stringResources/<locale>/resources.resjson), the English text when there is none. */
    private t = (key: string, english: string): string => {
        const v = this.loc ? this.loc.getDisplayName(`Visual_${key}`) : "";
        return v && v !== `Visual_${key}` ? v : english;
    };

    constructor(options: VisualConstructorOptions) {
        this.host = options.host;
        this.loc = this.host.createLocalizationManager();
        registerFonts();
        this.layers = new Layers(options.element);
        this.meter = new FrameMeter(this.layers.root.node());
        this.markLayer = new MarkLayer(this.layers);
        this.layers.svg.append("g").classed("kit-labels", true);          // above the brush: labels are clickable
        this.layers.html.append("div").classed("kit-top", true);
        this.headlineEl = this.layers.html.append("div").classed("kit-headline", true).attr("aria-live", "polite").node();
        this.ia = new Interaction(this.layers, this.host.createSelectionManager(), this.host.tooltipService,
            {
                onSelectionChanged: () => { this.render(); this.chip(); },
                onFilter: keys => this.filterTo(keys),
                onSwipe: d => this.setView(VIEWS[(VIEWS.indexOf(this.view) + d + VIEWS.length) % VIEWS.length])
            }, cam => { this.redraw(cam); this.saveState(); },
            this.host.hostCapabilities?.allowInteractions !== false);
        this.store = new StateStore(this.host);
        this.drill = new Drill(this.t("All", "All"), () => {
            if (this.theme) {
                this.render();
                this.saveState();
            }
        });
        this.layers.svg.on("dblclick", (e: MouseEvent) => {
            e.preventDefault();
            const m = this.ia.hit(e);
            flyTo(this.motion, this.ia, m ? frameMark(this.ia, m) : { k: 1, x: 0, y: 0 });
        });
    }

    public update(options: VisualUpdateOptions): void {
        const t0 = performance.now();
        try {
            this.updateInner(options);
        } finally {
            this.meter.read(options.dataViews && options.dataViews[0]);
            this.meter.update(performance.now() - t0);
            this.meter.run(this.selfTestMoves());
        }
    }

    /** The frame meter's self-test: this visual's own moves, played once when the page is in front (debug only). */
    private selfTestMoves(): Array<[string, () => void]> {
        return [
            ["view: columns", () => this.setView("columns")],
            ["view: clusters", () => this.setView("clusters")],
            ["click: a dot", () => this.ia.select([this.data.records[0].key])],
            ["click: clear", () => this.ia.clear()],
            ["view: grid", () => this.setView("grid")],
        ];
    }

    private stateIsNew(options: VisualUpdateOptions): boolean {
        return this.store.isNew(this.store.read(options.dataViews && options.dataViews[0]));
    }

    /** Our filter coming back: draw it only if it differs from what is picked now (a bookmark, a reopen). */
    private echo(options: VisualUpdateOptions): void {
        if (this.ia.mode !== "filter" || this.later.pending) {
            return;
        }
        const vals = filterValues(options.jsonFilters) || [];
        const role = String(this.settings.interaction.filterField.value.value);
        const keys = this.data.records.filter(r => vals.some(x => String(x) === String(r.fields[role]))).map(r => r.key).sort();
        if (keys.join("|") !== [...this.ia.selected].sort().join("|")) {
            this.ia.restore(keys);
            this.render();
            this.chip();
        }
    }

    private dropPicks(): void {
        if (this.ia.selected.size) {
            this.ia.clear();
        }
    }

    private chip(): void {
        clearChip(this.layers.html.select<HTMLDivElement>(".kit-top"), this.ia.selected.size, this.t("Clear", "Clear"), () => this.ia.clear());
    }
    /** When a click's filter goes out: after its move lands (kit/scene.ts Later). */
    private landing(): number {
        const m = this.motion.options;
        return m.animate && !m.reduce ? Math.min(1400, m.duration + 200) : 0;
    }

    private updateInner(options: VisualUpdateOptions): void {
        this.host.eventService.renderingStarted(options);
        try {
            const dv = options.dataViews && options.dataViews[0];
            this.settings = this.fmt.populateFormattingSettingsModel(AppSettings, dv);
            const s = this.settings;
            this.theme = readTheme(this.host.colorPalette as ISandboxExtendedColorPalette, s);
            this.colors = new ColorScale(this.theme, this.colors);
            this.motion.options = {
                animate: s.motion.animate.value, duration: s.motion.speed.value,
                easing: String(s.motion.easing.value.value), stagger: s.motion.stagger.value, reduce: s.motion.reduceMotion.value
            };
            this.layers.resize(options.viewport.width, options.viewport.height);
            applyTheme(this.layers.root, this.theme, s.layout.padding.value, s.layout.gap.value);
            // what this update brings (kit/updates.ts): our own filter or saved view coming back changes nothing
            const kind = this.gate.classify(options, options.dataViews && options.dataViews[0]);
            this.meter.note(`update: ${kind} (${options.type})`);
            if (kind === "same" && this.ready && !this.stateIsNew(options)) {
                this.echo(options);
                this.host.eventService.renderingFinished(options);
                return;
            }
            const othersChanged = kind === "data" && this.ready;   // a slicer or another visual changed the rows
            this.ia.tooltips = s.interaction.tooltips.value;
            if ((options.type & VisualUpdateType.Data) !== 0 || !this.data.records.length) {
                this.data = records(dv, this.host);
                this.byKey = new Map(this.data.records.map(r => [r.key, r]));
                if (fetchMore(dv, this.host, this.data.records.length, s.view.maxItems.value)) {
                    stateMessage(this.layers.html, this.t("Loading", "Loading more rows"), this.data.records.length.toLocaleString(), "down");
                    this.host.eventService.renderingFinished(options);
                    return;
                }
            }
            if (!this.data.roles.has("Item")) {
                this.markLayer.active.clear();
                this.layers.svg.selectAll(".kit-labels *").remove();
                this.layers.html.selectAll(".kit-pills,.kit-nav").remove();
                this.headlineEl.textContent = "";
                stateMessage(this.layers.html, this.t("NoData", "No data yet"),
                    this.t("NoDataHint", "Add an Item field (one dot per row). Group and Stage arrange the dots; X and Y draw the scatter."), "dot");
                this.host.eventService.renderingFinished(options);
                return;
            }
            clearState(this.layers.html);
            this.view = this.view || String(s.view.initial.value.value);
            this.dv = dv;
            this.ia.mode = String(s.interaction.clickMode.value.value) === "filter" ? "filter" : "crossFilter";
            if (this.ia.mode === "filter") {                 // a filter coming back: a bookmark, a sync slicer, a reopen
                const vals = filterValues(options.jsonFilters);
                const role = String(s.interaction.filterField.value.value);
                this.ia.restore(vals ? this.data.records.filter(r => vals.some(x => String(x) === String(r.fields[role]))).map(r => r.key) : []);
            }
            this.restoreState(this.store.read(dv));
            this.ia.enableBrush(s.interaction.brush.value);
            this.ia.enableZoom(s.interaction.zoom.value);
            // a resize (or the first draw) shows its final state at once: pages that aren't in front get no
            // animation frames, and an export captures what is drawn now
            const size = `${options.viewport.width}x${options.viewport.height}`;
            this.render(size !== this.lastSize);
            this.lastSize = size;
            if (othersChanged) {
                this.dropPicks();                      // the page moved on: this visual's click filter goes
            }
            this.ready = true;
            this.chip();
            if (kind === "first" || kind === "data" || kind === "resize") {
                this.warm();
            }
            this.host.eventService.renderingFinished(options);
        } catch (e) {
            this.host.eventService.renderingFailed(options, String(e));
        }
    }

    public getFormattingModel(): powerbi.visuals.FormattingModel {
        return this.fmt.buildFormattingModel(this.settings);
    }

    // ------------------------------------------------------------------ data -> units -> layout
    private groupOf = (r: DataRecord): string => (this.data.roles.has("Group") ? r.text.Group : this.t("All", "All"));
    private stageOf = (r: DataRecord): string => (this.data.roles.has("Stage") ? r.text.Stage : this.t("All", "All"));

    private unit(r: DataRecord): Unit {
        return { key: r.key, group: this.groupOf(r), stage: this.stageOf(r), x: Number(r.fields.X), y: Number(r.fields.Y) };
    }

    private inView(): DataRecord[] {
        const max = Math.max(1, this.settings.view.maxItems.value);
        const all = this.drill.group == null ? this.data.records : this.data.records.filter(r => this.groupOf(r) === this.drill.group);
        return all.length > max ? all.slice(0, max) : all;
    }

    private plot(): Box {
        const s = this.settings, pad = s.layout.padding.value;
        const head = s.view.headline.value ? this.theme.headlinePx * 1.5 + 4 : 0;
        const pill = s.view.pills.value || this.drill.screens.depth > 1 ? this.theme.fontPx * 2.4 + 8 : 0;
        const labels = s.view.labels.value ? this.theme.fontPx * 1.8 : 0;
        const y = Math.max(pad + head + pill, chromeBottom(this.layers.root.node(), 4));   // below the header as drawn
        this.layers.clipTop(y);
        return { x: pad + labels * 3, y: y + labels, w: Math.max(10, this.layers.width - pad * 2 - labels * 3), h: Math.max(10, this.layers.height - y - pad - labels) };
    }

    /**
     * Settle the clusters layout while nothing moves (1.5 s after new rows), so the first switch to Clusters doesn't
     * spend a 100 ms frame on physics; the result is kept (clusterCache) and reused.
     */
    private warmTimer: number | null = null;
    private warm(): void {
        if (this.warmTimer != null) {
            window.clearTimeout(this.warmTimer);
        }
        this.warmTimer = window.setTimeout(() => {
            this.warmTimer = null;
            if (this.view === "clusters" || !this.data.records.length) {
                return;
            }
            const v = this.view;
            this.view = "clusters";
            try {
                this.place(this.inView().map(r => this.unit(r)));
            } finally {
                this.view = v;
            }
        }, 1500);
    }

    private place(units: Unit[]): Placed {
        const all = this.data.records.map(r => this.unit(r));
        const how = String(this.settings.view.order.value.value) as Order;
        const custom = this.settings.view.customOrder.value;
        const groups = orderOf(all, u => u.group, how, new Set(units.map(u => u.group)), custom);
        const stages = orderOf(all, u => u.stage, how, new Set(units.map(u => u.stage)), custom);
        const P = this.plot(), maxR = this.settings.layout.markSize.value;
        const hasXY = this.data.roles.has("X") && this.data.roles.has("Y");
        if (this.view === "scatter" && hasXY) {
            const fx = valueFormatter.create({ format: this.data.formats.X }), fy = valueFormatter.create({ format: this.data.formats.Y });
            return scatter(units, P, maxR, v => fx.format(v), v => fy.format(v), this.data.names.X, this.data.names.Y, this.theme.fontPx);
        }
        if (this.view === "columns" || this.view === "scatter") {
            return columns(units, P, groups, stages, maxR);
        }
        if (this.view === "clusters") {              // settled once per data, size and drill, then reused
            const key = `${units.length}|${units.map(u => u.key).join(",").length}|${P.w}x${P.h}|${this.drill.group}`;
            if (!this.clusterCache || this.clusterCache.key !== key) {
                const prev = this.clusterCache;      // new rows, same view and size: carry on from where the dots are
                const same = !!prev && prev.key.split("|").slice(2).join("|") === key.split("|").slice(2).join("|");
                this.clusterCache = { key, placed: clusters(units, P, groups, maxR, same ? this.motion.states() : new Map(), same) };
            }
            return this.clusterCache.placed;
        }
        return grid(units, P, groups, stages, maxR);
    }

    // ------------------------------------------------------------------ drawing
    private render(instant = false): void {
        this.colors.seed([...new Set(this.data.records.map(r => this.groupOf(r)))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })));   // a group's colour: its place in the sorted names
        const rs = this.inView();
        const placed = this.place(rs.map(r => this.unit(r)));
        this.cells = placed.cells;
        const sel = this.ia.selected;
        const targets: Mark[] = rs.map(d => {
            const p = placed.pos.get(d.key);
            const base = this.settings.colors.byGroup.value ? this.colors.get(this.groupOf(d)) : this.theme.accent;
            const e = emphasis(this.theme, base, sel.has(d.key), sel.size > 0, this.data.hasHighlights && d.highlighted === false);
            return { key: d.key, x: p.x, y: p.y, r: p.r, color: e.color, alpha: e.alpha, stroke: e.stroke };
        });
        const renderer = this.markLayer.choose(targets.length);
        const items: Selectable[] = rs.map(d => ({ key: d.key, id: d.id, label: this.label(d), tooltip: this.tooltip(d) }));
        this.drawChrome(rs.length);
        this.drawLabels();
        this.ia.setMarks(targets, items);
        this.motion.to(targets, frame => renderer.draw(frame, this.ia.camera), instant).then(() => this.ia.setMarks(targets, items));
        const keys = rs.map(r => r.key);
        this.headlineEl.textContent = headline({
            keys, selected: keys.filter(k => sel.has(k)),
            highlighted: this.data.hasHighlights ? rs.filter(r => r.highlighted).map(r => r.key) : null,
            drilled: this.drill.group, allCount: this.data.records.length,
            groupName: this.data.roles.has("Group") ? this.data.names.Group : null,
            groupOf: k => this.groupOf(this.byKey.get(k)), t: this.t
        });
    }

    private redraw(cam: Camera): void {
        this.markLayer.active.draw([...this.motion.states()].map(([key, s]) => ({ key, ...s })), cam);
        this.drawLabels();
    }

    private label(d: DataRecord): string {
        return ["Item", "Group", "Stage"].filter(r => this.data.roles.has(r)).map(r => d.text[r]).join(", ");
    }

    private tooltip(d: DataRecord): powerbi.extensibility.VisualTooltipDataItem[] {
        return ["Item", "Group", "Stage", "X", "Y", "Size", "Tooltips"].filter(r => this.data.roles.has(r))
            .map(r => ({ displayName: this.data.names[r], value: d.text[r] }));
    }

    private drawChrome(n: number): void {
        const s = this.settings;
        const top = this.layers.html.select<HTMLDivElement>(".kit-top");
        top.selectAll("*").remove();
        if (this.drill.screens.depth > 1) {
            this.drill.screens.nav(top);
        }
        if (s.view.pills.value) {
            pills(top, VIEWS.map((v, i) => ({ value: v, label: this.t(`View_${v}`, VIEW_LABELS[i]), icon: ICON[v] })), this.view,
                v => this.setView(v), this.t("Views", "Views"));
        }
        this.chip();
        const max = s.view.maxItems.value;
        const total = this.drill.group == null ? this.data.records.length : this.data.records.filter(r => this.groupOf(r) === this.drill.group).length;
        if (total > max) {
            stateMessage(this.layers.html, this.t("TooMany", "Too many points"), this.t("TooManyHint", "Showing {0} of {1} items. Filter the page to see the rest.")
                .replace("{0}", max.toLocaleString()).replace("{1}", total.toLocaleString()), "filter").classed("kit-banner", true);
        } else {
            clearState(this.layers.html);
        }
        this.headlineEl.style.display = s.view.headline.value ? "" : "none";
        this.layers.root.attr("aria-label", `Unit chart, ${n} items, ${this.view} view`);
    }

    private drawLabels(): void {
        const cam = this.ia.camera;
        const canDrill = this.view === "grid" && this.drill.group == null;
        const top = this.plot().y;
        this.layers.svg.select<SVGGElement>(".kit-labels").selectAll<SVGTextElement, Cell>("text")
            .data(this.settings.view.labels.value ? this.cells : [], d => d.label + d.x + d.y)
            .join("text")
            .attr("class", d => (d.group && canDrill ? "kit-label is-link" : d.tick ? "kit-label is-tick" : "kit-label"))
            .attr("x", d => (d.w ? d.x + d.w / 2 : d.x) * cam.k + cam.x)
            .attr("y", d => (d.h ? d.y + d.h / 2 : d.y) * cam.k + cam.y)
            .attr("text-anchor", d => (d.title ? "start" : d.w ? "middle" : "end"))
            .attr("dominant-baseline", d => (d.h ? "middle" : d.y > top ? "hanging" : "auto"))
            .attr("tabindex", d => (d.group && canDrill ? 0 : null))
            .attr("role", d => (d.group && canDrill ? "button" : null))
            .text(d => d.label)
            .on("click", (e: MouseEvent, d: Cell) => {
                if (d.group && canDrill) {
                    e.stopPropagation();
                    this.drill.open(d.group);
                }
            })
            .on("keydown", (e: KeyboardEvent, d: Cell) => {
                if ((e.key === "Enter" || e.key === " ") && d.group && canDrill) {
                    e.preventDefault();
                    this.drill.open(d.group);
                }
            });
    }

    private setView(v: string): void {
        if (v === this.view) {
            return;
        }
        this.view = v;
        this.ia.setCamera({ k: 1, x: 0, y: 0 });
        this.render();
        this.ia.announce(`${v} view`);
        this.saveState();
    }

    // ------------------------------------------------------------------ saved state and filter mode
    private current(): ViewState {
        const c = this.ia.camera;
        return { view: this.view, drill: this.drill.group || "", camera: c.k === 1 && c.x === 0 && c.y === 0 ? null : c };
    }

    private saveState(): void {
        if (!this.restoring && this.theme) {
            this.store.save(this.current());
        }
    }

    /** A bookmark (or a reopen) brought a saved view, drill and camera: show them without saving them again. */
    private restoreState(saved: ViewState): void {
        if (!this.store.isNew(saved)) {
            return;
        }
        this.store.remember(saved);
        this.restoring = true;
        try {
            if (saved.view && VIEWS.includes(saved.view)) {
                this.view = saved.view;
            }
            if (saved.drill && saved.drill !== this.drill.group) {
                this.drill.open(saved.drill);
            } else if (!saved.drill && this.drill.group != null) {
                this.drill.screens.reset("all", this.t("All", "All"));
            }
            this.ia.setCamera(saved.camera || { k: 1, x: 0, y: 0 });
        } finally {
            this.restoring = false;
        }
    }

    /** Filter mode: the selected records' values of the chosen field become a BasicFilter (slicer-like). */
    private filterTo(keys: string[]): void {
        const role = String(this.settings.interaction.filterField.value.value);
        const col = this.dv?.metadata?.columns?.find(c => c.roles && c.roles[role]);
        const values = [...new Set(keys.map(k => this.byKey.get(k)?.fields[role]).filter(x => x != null))] as Array<string | number | boolean>;
        this.later.run(() => applyFilter(this.host, targetOf(col), values), this.landing());   // removals too
    }
}
