/*
 * pbip-kit visual harness: a small fake Power BI host (no Power BI, no network).
 * It builds data views from made-up rows, gives a visual the host services it calls (selection, tooltips, colours,
 * events, fetch more data, localisation) and records every call so a test can check cross-filter out
 * (selection calls) and feed cross-filter in (filtered rows or highlights). Written from the visuals API's public
 * type definitions (powerbi-visuals-api, MIT), not from Power BI's code.
 */
(function () {
  "use strict";
  const log = { select: [], clear: 0, contextMenu: [], tooltips: 0, tooltipHide: 0, fetchMore: 0, rendering: { started: 0, finished: 0, failed: [] }, persist: [], launchUrl: [], warnings: [] };
  window.__harness = { log };

  function selId(key) {
    return {
      key,
      equals: o => !!o && o.key === key,
      getKey: () => key,
      getSelector: () => ({ data: [{ key }] }),
      getSelectorsByColumn: () => ({}),
      hasIdentity: () => true,
      includes: o => !!o && String(o.key).indexOf(key) === 0
    };
  }

  function builder() {
    const parts = [];
    const b = {
      withCategory(col, i) { parts.push(`${col.source.queryName}=${col.values[i]}`); return b; },
      withSeries(cols, col) { parts.push(`series=${col && col.name}`); return b; },
      withMeasure(m) { parts.push(`measure=${m}`); return b; },
      withMatrixNode(node, levels) { parts.push(`node=${levels.length}:${node.level}:${node.value}`); return b; },
      withTable(t, i) { parts.push(`row=${i}`); return b; },
      createSelectionId() { return selId(parts.join("|")); }
    };
    return b;
  }

  function palette(theme, highContrast) {
    const data = theme.dataColors || ["#118DFF", "#12239E", "#E66C37", "#6B007B", "#E044A7", "#744EC2", "#D9B300", "#D64550"];
    const map = new Map();
    const c = v => ({ value: v });
    const fg = highContrast ? "#ffffff" : (theme.foreground || "#252423");
    const bg = highContrast ? "#000000" : (theme.background || "#ffffff");
    return {
      isHighContrast: !!highContrast,
      getColor(key) { if (!map.has(key)) map.set(key, data[map.size % data.length]); return c(highContrast ? fg : map.get(key)); },
      reset() { map.clear(); return this; },
      foreground: c(fg), foregroundLight: c(fg), foregroundDark: c(fg), foregroundNeutralLight: c(fg),
      foregroundNeutralDark: c(fg), foregroundNeutralSecondary: c(highContrast ? fg : (theme.foregroundNeutralSecondary || "#605E5C")),
      foregroundNeutralSecondaryAlt: c(fg), foregroundNeutralSecondaryAlt2: c(fg), foregroundNeutralTertiary: c(fg),
      foregroundNeutralTertiaryAlt: c(fg), foregroundSelected: c(highContrast ? "#ffff00" : fg), foregroundButton: c(fg),
      background: c(bg), backgroundLight: c(highContrast ? bg : (theme.backgroundLight || "#F3F2F1")), backgroundNeutral: c(bg),
      backgroundDark: c(bg), hyperlink: c(highContrast ? "#ffff00" : "#0078D4"), visitedHyperlink: c(fg),
      mapPushpin: c(fg), shapeStroke: c(fg), selection: c(fg), separator: c(fg), negative: c("#D64550"),
      neutral: c("#D9B300"), positive: c("#1AAB40")
    };
  }

  /** Data view from rows: categories for grouping roles, values for measure roles (with highlights if asked). */
  function dataView(spec, objects, opts) {
    const rows = spec.rows || [];
    const roles = spec.roles || {};
    const measures = new Set(spec.measures || []);
    const formats = spec.formats || {};
    const cats = [], vals = [];
    const visibleRows = opts.filter ? rows.filter(opts.filter) : rows;
    const win = opts.window;
    const shown = win ? visibleRows.slice(0, win) : visibleRows;
    for (const [role, fieldList] of Object.entries(roles)) {
      for (const field of [].concat(fieldList)) {
        const source = { displayName: field, queryName: `T.${field}`, roles: { [role]: true }, format: formats[field], type: {} };
        const values = shown.map(r => r[field] === undefined ? null : r[field]);
        if (measures.has(role)) {
          source.isMeasure = true;
          source.type = { numeric: true };
          const col = { source, values };
          if (opts.highlight) col.highlights = shown.map((r, i) => (opts.highlight(r) ? values[i] : null));
          vals.push(col);
        } else {
          source.type = { text: true };
          cats.push({ source, values, identity: values.map((v, i) => selId(`${field}=${v}#${i}`)) });
        }
      }
    }
    const columns = cats.map(c => c.source).concat(vals.map(v => v.source));
    const values = Object.assign(vals, { grouped: () => [{ values: vals }], source: undefined });
    const metadata = { columns, objects: objects || {} };
    if (win && visibleRows.length > win) metadata.segment = {};
    return { metadata, categorical: cats.length ? { categories: cats, values } : undefined };
  }

  /** Host and options for one visual instance. state: {theme, highContrast, allowInteractions, locale, strings}. */
  function createHost(state, onFetchMore) {
    const selected = [];
    let callback = null;
    const tip = document.getElementById("harness-tooltip");
    return {
      instanceId: "harness",
      locale: state.locale || "en-US",
      hostCapabilities: { allowInteractions: state.allowInteractions !== false, allowModalDialog: false },
      colorPalette: palette(state.theme || {}, state.highContrast),
      createSelectionIdBuilder: builder,
      createSelectionManager() {
        window.__harness.selection = () => selected.map(i => i.key);
        window.__harness.restoreSelection = keys => { const ids = (keys || []).map(selId); selected.length = 0; selected.push(...ids); if (callback) callback(ids); };
        return {
          select(ids, multi) {
            ids = [].concat(ids);
            log.select.push({ keys: ids.map(i => i.key), multi: !!multi });
            if (!multi) selected.length = 0;
            for (const id of ids) {
              const at = selected.findIndex(s => s.equals(id));
              if (at >= 0 && multi) selected.splice(at, 1); else if (at < 0) selected.push(id);
            }
            return Promise.resolve(selected.slice());
          },
          clear() { log.clear++; selected.length = 0; return Promise.resolve({}); },
          hasSelection() { return selected.length > 0; },
          getSelectionIds() { return selected.slice(); },
          registerOnSelectCallback(cb) { callback = cb; },
          showContextMenu(id, pos) { log.contextMenu.push({ key: id && id.key, x: pos.x, y: pos.y }); return Promise.resolve({}); },
          toggleExpandCollapse(id) { log.select.push({ expand: id && id.key }); return Promise.resolve({}); },
          __restore(ids) { selected.length = 0; selected.push(...ids); if (callback) callback(ids); }
        };
      },
      tooltipService: {
        enabled: () => true,
        show(o) {
          log.tooltips++;
          log.lastTooltip = (o.dataItems || []).map(d => d.displayName);
          tip.style.display = "block";
          tip.style.left = `${o.coordinates[0] + 12}px`;
          tip.style.top = `${o.coordinates[1] + 12}px`;
          tip.textContent = (o.dataItems || []).map(d => `${d.displayName}: ${d.value}`).join("\n");
        },
        move(o) { this.show(o); },
        hide() { log.tooltipHide++; tip.style.display = "none"; }
      },
      eventService: {
        renderingStarted() { log.rendering.started++; },
        renderingFinished() { log.rendering.finished++; },
        renderingFailed(o, reason) { log.rendering.failed.push(String(reason)); }
      },
      fetchMoreData(aggregate) { log.fetchMore++; return onFetchMore(aggregate); },
      createLocalizationManager() { return { getDisplayName: key => (state.strings || {})[key] || key }; },
      persistProperties(changes) { log.persist.push(changes); if (state.onPersist) state.onPersist(changes); },
      applyJsonFilter(filter, objectName, propertyName, action) {
        log.filters = log.filters || [];
        log.filters.push({ values: filter && filter.values, target: filter && filter.target, action });
        if (state.onFilter) state.onFilter(action === 1 ? null : filter);
      },
      launchUrl(url) { log.launchUrl.push(url); },
      displayWarningIcon(hover, detail) { log.warnings.push(`${hover}: ${detail}`); },
      refreshHostData() { },
      switchFocusModeState() { },
      telemetry: { trace() { } },
      authenticationService: undefined,
      downloadService: undefined,
      storageService: undefined,
      drill() { }
    };
  }

  window.HarnessHost = { createHost, dataView, palette, selId };
})();
