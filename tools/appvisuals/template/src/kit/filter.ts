/*
 *  pbip-kit app-visual template: filter mode.
 *  In filter mode a click doesn't cross-filter (a selection, this page only): it applies a real filter on one column
 *  (`applyJsonFilter`, a BasicFilter "In"), so the visual acts like a slicer: the filter can reach other pages through
 *  sync slicers (`supportsSynchronizingFilterState` in capabilities) and a bookmark keeps it (`options.jsonFilters`).
 *  Chosen per visual in the formatting pane (Interaction > Clicks). BasicFilter is from Microsoft's powerbi-models
 *  package (MIT).
 */
import powerbi from "powerbi-visuals-api";
import { BasicFilter, IBasicFilter, IFilterColumnTarget, ITupleFilter, TupleFilter } from "powerbi-models";

import DataViewMetadataColumn = powerbi.DataViewMetadataColumn;
import IVisualHost = powerbi.extensibility.visual.IVisualHost;
import FilterAction = powerbi.FilterAction;
import ISelectionManager = powerbi.extensibility.ISelectionManager;
import ISelectionId = powerbi.visuals.ISelectionId;
import PrimitiveValue = powerbi.PrimitiveValue;

/** The table and column a field filters ("Deals.Region" -> Deals / Region). */
export function targetOf(col: DataViewMetadataColumn | undefined): IFilterColumnTarget | null {
    const q = col?.queryName || "";
    const i = q.indexOf(".");
    if (i < 1 || col?.isMeasure) {
        return null;
    }
    return { table: q.slice(0, i), column: q.slice(i + 1) };
}

/** Apply (or with no values remove) the visual's filter. */
export function applyFilter(host: IVisualHost, target: IFilterColumnTarget | null, values: Array<string | number | boolean>): void {
    if (!target || !values.length) {
        host.applyJsonFilter(null, "general", "filter", FilterAction.remove);
        return;
    }
    const f = new BasicFilter(target, "In", values);
    host.applyJsonFilter(f.toJSON(), "general", "filter", FilterAction.merge);
}

/**
 * Filter on a combination of columns (a site and its floor: "Floor 2" alone means a floor in every site). Each row of
 * `rows` is one allowed combination, in the order of `targets`. No rows removes the filter.
 */
export function applyTupleFilter(host: IVisualHost, targets: Array<IFilterColumnTarget | null>, rows: Array<Array<string | number | boolean>>): void {
    if (!rows.length || targets.some(t => !t)) {
        host.applyJsonFilter(null, "general", "filter", FilterAction.remove);
        return;
    }
    const f = new TupleFilter(targets as IFilterColumnTarget[], "In", rows.map(r => r.map(value => ({ value }))));
    host.applyJsonFilter(f.toJSON(), "general", "filter", FilterAction.merge);
}

/** The rows of a combination filter coming back (bookmark, reopen): [[site, floor], ...], or null. */
export function tupleValues(jsonFilters: powerbi.IFilter[] | undefined): Array<Array<string | number | boolean>> | null {
    const f = (jsonFilters || [])[0] as unknown as ITupleFilter | undefined;
    return f && Array.isArray(f.values) && Array.isArray(f.target) ? f.values.map(r => r.map(e => e.value as string | number | boolean)) : null;
}

/** The values of the visual's own filter coming back (a bookmark, a sync slicer, a reopen). */
export function filterValues(jsonFilters: powerbi.IFilter[] | undefined): Array<string | number | boolean> | null {
    const f = (jsonFilters || [])[0] as unknown as IBasicFilter | undefined;
    return f && Array.isArray(f.values) && !Array.isArray(f.target) ? f.values as Array<string | number | boolean> : null;
}

// ---------------------------------------------------------------------------------------------------------------
// Clicks out, the same way in every kit visual. A pick is one clicked thing (a state, a person, a site's floor) with
// the column values that name it, by data role ({Location: "Texas"}, {Group: "Site 05", Item: "Floor 2"}).
// Clicks: Filter (the default since the Desktop review of 2026-11-17) applies a real filter, so cards, tables and
// every other visual on the page follow; Cross-highlight sends a selection instead.


export type PickCols = Record<string, PrimitiveValue>;
export interface Pick { id: ISelectionId; cols: PickCols }

/** The column bound to a data role. */
export function columnOf(dv: powerbi.DataView | undefined, role: string): DataViewMetadataColumn | undefined {
    return (dv?.categorical?.categories || []).find(c => c.source.roles && c.source.roles[role])?.source;
}

/** The visual's Clicks setting (Interaction > Clicks). */
export function clickMode(settings: object): "filter" | "crossFilter" {
    const s = settings as { interaction?: { clickMode?: { value?: { value?: unknown } } } };
    return String(s?.interaction?.clickMode?.value?.value) === "crossFilter" ? "crossFilter" : "filter";
}

type Value = string | number | boolean;

/** Send every current pick at once (none: the filter or the selection goes). One kind of pick at a time. */
export function sendPicks(host: IVisualHost, sel: ISelectionManager, dv: powerbi.DataView | undefined, mode: "filter" | "crossFilter", picks: Pick[]): void {
    if (mode === "crossFilter") {
        if (picks.length) {
            sel.select(picks.map(p => p.id), false);
        } else {
            sel.clear();
        }
        return;
    }
    if (!picks.length) {
        applyFilter(host, null, []);
        return;
    }
    const roles = Object.keys(picks[0].cols);
    const same = picks.filter(p => Object.keys(p.cols).join("|") === roles.join("|"));
    const targets = roles.map(r => targetOf(columnOf(dv, r)));
    if (roles.length === 1) {
        applyFilter(host, targets[0], same.map(p => p.cols[roles[0]] as Value));
    } else {
        applyTupleFilter(host, targets, same.map(p => roles.map(r => p.cols[r] as Value)));
    }
}

/** The picks a filter coming back names (a bookmark, a reopen): the keys of `candidates` it matches. */
export function picksFromFilter(jsonFilters: powerbi.IFilter[] | undefined, candidates: Map<string, PickCols>): Set<string> | null {
    const rows = tupleValues(jsonFilters), vals = rows ? null : filterValues(jsonFilters);
    if (!rows && !vals) {
        return jsonFilters ? new Set() : null;
    }
    const out = new Set<string>();
    candidates.forEach((cols, key) => {
        const v = Object.values(cols).map(String);
        if (rows ? rows.some(r => r.length === v.length && r.every((x, i) => String(x) === v[i])) : v.length === 1 && vals.some(x => String(x) === v[0])) {
            out.add(key);
        }
    });
    return out;
}
