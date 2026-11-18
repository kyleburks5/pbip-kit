/*
 * pbip-kit visual harness, page side: loads a built visual (the JS and CSS from its .pbiviz) or a Deneb spec, and
 * drives it from run.mjs. Everything is local: the visual bundle, Vega and Vega-Lite come from the kit tools folder.
 */
(function () {
  "use strict";
  const H = window.HarnessHost;
  const state = { visual: null, host: null, spec: null, objects: {}, filter: null, highlight: null, window: 0, rowsShown: 0, theme: {}, viewport: { width: 800, height: 500 } };
  const el = () => document.getElementById("harness-visual");

  function where(cond) {
    if (!cond) return null;
    return r => Object.entries(cond).every(([f, vals]) => [].concat(vals).map(String).includes(String(r[f])));
  }

  function update(type) {
    const dv = H.dataView(state.data, state.objects, { filter: state.filter, highlight: state.highlight, window: state.window });
    state.rowsShown = dv.categorical ? dv.categorical.categories[0].values.length : 0;
    state.visual.update({ dataViews: dv.categorical ? [dv] : [], viewport: state.viewport, type: type == null ? 62 : type, viewMode: 1, editMode: 0,
      operationKind: 0, isInFocus: false, jsonFilters: state.jsonFilter ? [state.jsonFilter] : [] });
  }

  // Power BI writes persisted properties into the visual's objects and sends an update; filters come back as jsonFilters
  function onPersist(changes) {
    for (const m of changes.merge || []) {
      state.objects[m.objectName] = Object.assign({}, state.objects[m.objectName] || {}, m.properties);
    }
    setTimeout(() => update(4), state.roundTrip);
  }
  // Desktop re-queries after a filter or a save and sends the rows again a few hundred ms later (a data update, even
  // when the visual's own filter doesn't change its rows): the harness waits the same (scenario `roundTrip`, ms)
  function onFilter(f) { state.jsonFilter = f; setTimeout(() => update(2), state.roundTrip); }
  const deep = x => JSON.parse(JSON.stringify(x || {}));

  window.harness = {
    /** cfg: {guid, data, objects, theme, highContrast, viewport, window, allowInteractions} */
    loadVisual(cfg) {
      Object.assign(state, { roundTrip: cfg.roundTrip == null ? 400 : cfg.roundTrip, data: cfg.data, objects: cfg.objects || {}, theme: cfg.theme || {}, viewport: cfg.viewport || state.viewport, window: cfg.window || 0 });
      const box = el();
      box.style.width = `${state.viewport.width}px`;
      box.style.height = `${state.viewport.height}px`;
      if (cfg.highContrast) { document.body.style.background = "#000000"; box.style.background = "#000000"; }
      const plugin = window.powerbi.visuals.plugins[cfg.guid];
      if (!plugin) throw new Error(`the bundle didn't register ${cfg.guid}`);
      state.cfg = cfg;
      Object.assign(cfg, { onPersist, onFilter });
      state.host = H.createHost(cfg, () => {
        if (!state.window) return false;
        state.window = 0;                       // the next update brings every row (aggregateSegments)
        setTimeout(() => update(2 | 64), 0);
        return true;
      });
      state.visual = plugin.create({ element: box, host: state.host, module: {} });
      // Desktop sends an empty update while it loads (no data view yet), then the rows; so does the harness, unless
      // the scenario says `emptyFirst: false` (a visual that removed its layers on the empty one drew nothing after)
      if (cfg.emptyFirst !== false) {
        state.visual.update({ dataViews: [], viewport: state.viewport, type: 2, viewMode: 1, editMode: 0, operationKind: 0, isInFocus: false, jsonFilters: [] });
      }
      update();
      return { rows: state.rowsShown };
    },
    setObjects(objects) { state.objects = Object.assign({}, state.objects, objects); update(4); },
    /** A bookmark: what Power BI keeps for a visual (filterState properties, its filter, its selection). */
    saveBookmark(name) {
      state.bookmarks = state.bookmarks || {};
      state.bookmarks[name] = { objects: deep(state.objects), filter: deep(state.jsonFilter), selection: window.__harness.selection() };
      return state.bookmarks[name];
    },
    applyBookmark(name) {
      const b = state.bookmarks[name];
      state.objects = deep(b.objects);
      state.jsonFilter = b.filter && b.filter.values ? deep(b.filter) : null;
      update(4);
      window.__harness.restoreSelection(b.selection);
      return true;
    },
    /** Close and reopen the report: a new visual instance with what the report saved. */
    reopen() {
      const box = el();
      box.textContent = "";
      window.__harness.log.reopened = (window.__harness.log.reopened || 0) + 1;
      state.visual = window.powerbi.visuals.plugins[state.cfg.guid].create({ element: box, host: H.createHost(state.cfg, () => false), module: {} });
      update();
      return true;
    },
    filter(cond) { state.filter = where(cond); update(2); return state.rowsShown; },
    highlight(cond) { state.highlight = where(cond); update(2); return state.rowsShown; },
    resize(w, h) { state.viewport = { width: w, height: h }; const b = el(); b.style.width = `${w}px`; b.style.height = `${h}px`; update(4); },
    marks() {
      const root = el().querySelector(".kit-root");
      const m = root && root.kitMarks ? root.kitMarks() : [];
      return m.map(x => ({ key: x.key, x: x.x, y: x.y, r: x.r }));
    },
    log() { return JSON.parse(JSON.stringify(window.__harness.log)); },
    format() { return state.visual.getFormattingModel ? JSON.parse(JSON.stringify(state.visual.getFormattingModel())) : null; },

    /** Deneb: a Vega-Lite spec over `dataset`, with Deneb's pbiColor / pbiFormat and simple-mode __selected__. */
    async loadDeneb(cfg) {
      Object.assign(state, { data: cfg.data, theme: cfg.theme || {}, viewport: cfg.viewport || state.viewport, spec: cfg.spec, deneb: cfg.deneb || {} });
      state.selected = new Set();
      const colors = cfg.highContrast ? ["#ffffff"] : (state.theme.dataColors || ["#118DFF", "#12239E", "#E66C37", "#6B007B"]);
      const shade = (hex, p) => {
        const n = parseInt(hex.slice(1), 16);
        const ch = [n >> 16 & 255, n >> 8 & 255, n & 255].map(c => Math.round(p >= 0 ? c + (255 - c) * p : c * (1 + p)));
        return "#" + ch.map(c => c.toString(16).padStart(2, "0")).join("");
      };
      vega.expressionFunction("pbiColor", (i, p) => shade(colors[Number(i) % colors.length], Number(p) || 0));
      vega.expressionFunction("pbiFormat", (v, f) => (typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: /0\.0/.test(f || "") ? 1 : 0 }) : String(v)));
      const box = el();
      box.style.width = `${state.viewport.width}px`;
      box.style.height = `${state.viewport.height}px`;
      await this.renderDeneb();
      return { rows: state.data.rows.length };
    },
    async renderDeneb() {
      const rows = (state.filter ? state.data.rows.filter(state.filter) : state.data.rows).map((r, i) => {
        const any = state.selected.size > 0;
        return Object.assign({}, r, { __row__: i, __selected__: !any ? "neutral" : state.selected.has(i) ? "on" : "off" });
      });
      const t = state.theme;
      const config = Object.assign({
        autosize: { type: "fit", contains: "padding" }, background: "transparent",
        font: (t.textClasses && t.textClasses.label && t.textClasses.label.fontFace) || "Segoe UI",
        range: { category: t.dataColors || undefined },
        view: { stroke: "transparent" }, axis: { labelColor: t.foreground || "#605E5C", titleColor: t.foreground || "#252423", grid: false }
      }, (state.deneb.config || {}));
      const spec = Object.assign({}, state.spec, { width: "container", height: "container", data: { name: "dataset", values: rows } });
      const box = el();
      box.textContent = "";
      const res = await vegaEmbed(box, spec, { actions: false, renderer: "svg", config, tooltip: state.deneb.tooltips === false ? false : undefined });
      res.view.addEventListener("click", (e, item) => {
        if (state.deneb.crossFilter === false) return;
        const d = item && item.datum;
        if (!d || d.__row__ == null) { state.selected.clear(); window.__harness.log.clear++; }
        else {
          const multi = e.ctrlKey || e.metaKey || e.shiftKey;
          if (!multi) state.selected = new Set(state.selected.has(d.__row__) && state.selected.size === 1 ? [] : [d.__row__]);
          else if (state.selected.has(d.__row__)) state.selected.delete(d.__row__); else state.selected.add(d.__row__);
          window.__harness.log.select.push({ keys: [...state.selected].map(String), multi });
        }
        this.renderDeneb();
      });
      return true;
    },
    async filterDeneb(cond) { state.filter = where(cond); await this.renderDeneb(); return true; }
  };
})();
