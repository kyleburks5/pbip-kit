/*
 *  pbip-kit app-visual template: data.
 *  - records(): one record per row of a categorical data view, fields by role name, a selection id per row, and the
 *    host's highlight (cross-highlight from other visuals: cross-filter coming in).
 *  - fetchMore(): asks for the next segment of rows (the `window` data reduction in capabilities) until the kit's
 *    limit or the end of the data (Microsoft Learn, "Fetch more data from Power BI").
 *  - hierarchy(): a tree from a matrix data view (drill and expand), with a selection id per node.
 */
import powerbi from "powerbi-visuals-api";
import { valueFormatter } from "powerbi-visuals-utils-formattingutils";

import DataView = powerbi.DataView;
import DataViewMatrixNode = powerbi.DataViewMatrixNode;
import DataViewHierarchyLevel = powerbi.DataViewHierarchyLevel;
import ISelectionId = powerbi.visuals.ISelectionId;
import IVisualHost = powerbi.extensibility.visual.IVisualHost;
import PrimitiveValue = powerbi.PrimitiveValue;

export interface DataRecord {
    key: string;
    index: number;
    id: ISelectionId;
    fields: Record<string, PrimitiveValue>;
    text: Record<string, string>;
    highlighted: boolean | null;
}

export interface RecordSet {
    records: DataRecord[];
    roles: Set<string>;
    names: Record<string, string>;
    formats: Record<string, string>;
    hasHighlights: boolean;
    more: boolean;
}

/** Records from a categorical data view: every category role and every measure role becomes a field. */
export function records(dv: DataView, host: IVisualHost): RecordSet {
    const out: RecordSet = { records: [], roles: new Set(), names: {}, formats: {}, hasHighlights: false, more: false };
    const cat = dv?.categorical;
    if (!cat?.categories?.length) {
        return out;
    }
    out.more = !!dv.metadata?.segment;
    const n = cat.categories[0].values.length;
    const cols: Array<{ role: string; values: PrimitiveValue[]; highlights?: PrimitiveValue[]; format: valueFormatter.IValueFormatter }> = [];
    for (const c of cat.categories) {
        for (const role of Object.keys(c.source.roles || {})) {
            cols.push({ role, values: c.values, format: valueFormatter.create({ format: c.source.format }) });
            out.roles.add(role);
            out.names[role] = c.source.displayName;
            out.formats[role] = c.source.format;
        }
    }
    for (const v of cat.values || []) {
        for (const role of Object.keys(v.source.roles || {})) {
            cols.push({ role, values: v.values, highlights: v.highlights, format: valueFormatter.create({ format: v.source.format }) });
            out.roles.add(role);
            out.names[role] = v.source.displayName;
            out.formats[role] = v.source.format;
            out.hasHighlights = out.hasHighlights || !!v.highlights;
        }
    }
    for (let i = 0; i < n; i++) {
        let b = host.createSelectionIdBuilder();
        for (const c of cat.categories) {
            b = b.withCategory(c, i);
        }
        const fields: Record<string, PrimitiveValue> = {};
        const text: Record<string, string> = {};
        let hl: boolean | null = null;
        for (const c of cols) {
            fields[c.role] = c.values[i];
            text[c.role] = c.values[i] == null ? "(blank)" : c.format.format(c.values[i]);
            if (c.highlights) {
                hl = (hl || false) || c.highlights[i] != null;
            }
        }
        const key = cat.categories.map(c => String(c.values[i])).join("␟");
        out.records.push({ key, index: i, id: b.createSelectionId(), fields, text, highlighted: hl });
    }
    return out;
}

/**
 * A selection id for only some roles of row i (a Group, or a Group and a Stage), so a card or a bar selects the whole
 * group in other visuals (Region = North) rather than every row one by one.
 */
export function idFor(dv: DataView, host: IVisualHost, roles: string[], i: number): ISelectionId {
    let b = host.createSelectionIdBuilder();
    for (const c of dv?.categorical?.categories || []) {
        if (Object.keys(c.source.roles || {}).some(r => roles.includes(r))) {
            b = b.withCategory(c, i);
        }
    }
    return b.createSelectionId();
}

/** Ask for the next segment of rows while under the limit. True when a request went out (an update follows). */
export function fetchMore(dv: DataView, host: IVisualHost, have: number, limit: number): boolean {
    if (!dv?.metadata?.segment || have >= limit) {
        return false;
    }
    return host.fetchMoreData(true);
}

export interface TreeNode {
    name: string;
    level: number;
    value: number | null;
    id: ISelectionId;
    children: TreeNode[];
    expanded: boolean;
}

/** A tree from a matrix data view's rows (drilldown / expand-collapse), values from the first measure. */
export function hierarchy(dv: DataView, host: IVisualHost): TreeNode | null {
    const m = dv?.matrix;
    if (!m?.rows?.root) {
        return null;
    }
    const levels: DataViewHierarchyLevel[] = m.rows.levels;
    const walk = (node: DataViewMatrixNode, level: number): TreeNode => {
        const v = node.values ? node.values[0] : undefined;
        return {
            name: node.value == null ? "(all)" : String(node.value),
            level,
            value: v && typeof v.value === "number" ? v.value : null,
            id: level < 0 ? null : host.createSelectionIdBuilder().withMatrixNode(node, levels).createSelectionId(),
            children: (node.children || []).map(c => walk(c, level + 1)),
            expanded: !!node.isCollapsed === false && !!node.children
        };
    };
    return walk(m.rows.root, -1);
}

/** Stable small hash (layout jitter without Math.random, which the certification lint rejects). */
export function hash01(s: string): number {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
        h ^= s.charCodeAt(i);
        h = Math.imul(h, 16777619);
    }
    return ((h >>> 0) % 10000) / 10000;
}
