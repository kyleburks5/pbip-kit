/*
 *  pbip-kit app-visual template: what an update brings.
 *  Power BI sends an update for many reasons: new data (a slicer, a cross-filter), the visual's own filter or saved
 *  state coming back (a click: the same rows again, after a round trip of a few hundred ms), a format change, a
 *  resize. Only new data and a resize need a new layout; the rest must not touch what is moving (Desktop review
 *  2026-11-17: re-running the layout and physics on the visual's own filter echo froze every click for 100-400 ms and
 *  then snapped). `UpdateGate.classify` tells them apart from cheap fingerprints.
 */
import powerbi from "powerbi-visuals-api";

import DataView = powerbi.DataView;
import VisualUpdateOptions = powerbi.extensibility.visual.VisualUpdateOptions;

export type UpdateKind = "first" | "data" | "resize" | "format" | "same";

/** FNV-1a over a string: a fingerprint, not a secret. */
function fnv(s: string, h = 0x811c9dc5): number {
    for (let i = 0; i < s.length; i++) {
        h ^= s.charCodeAt(i);
        h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h;
}

/** The rows: every category and value column (and highlights), in order. */
export function dataPrint(dv: DataView | undefined): string {
    const c = dv?.categorical;
    if (!c) {
        return "none";
    }
    let h = 0x811c9dc5, n = 0;
    for (const col of [...(c.categories || []), ...(c.values || [])]) {
        h = fnv(`${col.source.queryName}|`, h);
        for (const v of col.values) {
            h = fnv(`${v}|`, h);
        }
        const hl = (col as powerbi.DataViewValueColumn).highlights;
        if (hl) {
            h = fnv(`hl${hl.map(x => (x == null ? "" : "1")).join("")}`, h);
        }
        n = Math.max(n, col.values.length);
    }
    return `${n}:${h.toString(36)}`;
}

/** JSON with sorted keys: Power BI doesn't keep the order of formatting objects from one update to the next. */
function stable(v: unknown): string {
    if (Array.isArray(v)) {
        return `[${v.map(stable).join(",")}]`;
    }
    if (v && typeof v === "object") {
        return `{${Object.keys(v as object).sort().map(k => `${JSON.stringify(k)}:${stable((v as Record<string, unknown>)[k])}`).join(",")}}`;
    }
    return JSON.stringify(v);
}

/** The formatting pane values, without the visual's own saved state (it comes back after every save). */
export function formatPrint(dv: DataView | undefined): string {
    const o = { ...(dv?.metadata?.objects || {}) };
    delete o.state;
    delete o.debug;
    return fnv(stable(o)).toString(36);
}

export class UpdateGate {
    private data = "";
    private format = "";
    private size = "";

    /** What changed since the last update (and remember this one). */
    classify(options: VisualUpdateOptions, dv: DataView | undefined): UpdateKind {
        const d = dataPrint(dv), f = formatPrint(dv), s = `${Math.round(options.viewport.width)}x${Math.round(options.viewport.height)}`;
        const kind: UpdateKind = !this.data ? "first" : d !== this.data ? "data" : s !== this.size ? "resize" : f !== this.format ? "format" : "same";
        this.data = d;
        this.format = f;
        this.size = s;
        return kind;
    }
}
