/*
 *  pbip-kit pattern modules: a headline that says what the view shows (docs/patterns/app-visuals/live-headline.md).
 *  Pure: keys in, one sentence out. Selection first, then a highlight from another visual, then a drill-in, then the
 *  whole view. Every sentence is a localisable template ({0}, {1}, ...).
 */
import { count } from "../words";

export interface HeadlineInput {
    keys: string[];                 // the units in the view
    selected: string[];             // selected here
    highlighted: string[] | null;   // highlighted from another visual (null: no highlight coming in)
    drilled: string | null;         // the group drilled into
    allCount: number;               // every unit, before the drill
    groupName: string | null;       // the Group field's name (null: no Group field)
    groupOf: (key: string) => string;
    t: (key: string, english: string) => string;
}

const fill = (s: string, ...v: Array<string | number>) => v.reduce<string>((acc, x, i) => acc.split(`{${i}}`).join(String(x)), s);
const n = (x: number) => x.toLocaleString();

/** The biggest group among keys and its share of them, in whole percent. */
export function topShare(keys: string[], groupOf: (k: string) => string): { group: string; pct: number } {
    const c = new Map<string, number>();
    keys.forEach(k => c.set(groupOf(k), (c.get(groupOf(k)) || 0) + 1));
    let group = "", best = 0;
    c.forEach((v, g) => {
        if (v > best) {
            best = v;
            group = g;
        }
    });
    return { group, pct: keys.length ? Math.round(best / keys.length * 100) : 0 };
}

export function headline(h: HeadlineInput): string {
    const total = h.keys.length;
    if (h.selected.length) {
        const top = topShare(h.selected, h.groupOf);
        return fill(h.t("Headline_Selected", "{0} of {1} selected. {2} holds {3}% of the selection."), n(h.selected.length), count(total, h.t("Item", "item")), top.group, top.pct);
    }
    if (h.highlighted) {
        const top = topShare(h.highlighted, h.groupOf);
        return fill(h.t("Headline_Highlighted", "{0} of {1} highlighted from another visual{2}."), n(h.highlighted.length), count(total, h.t("Item", "item")),
            top.group ? `; ${top.group} ${top.pct}%` : "");
    }
    if (h.drilled != null) {
        return fill(h.t("Headline_Drilled", "{0}: {1}, {2}% of all {3}."), h.drilled, count(total, h.t("Item", "item")),
            Math.round(total / Math.max(1, h.allCount) * 100), n(h.allCount));
    }
    if (h.groupName) {
        const top = topShare(h.keys, h.groupOf);
        return fill(h.t("Headline_ByGroup", "{0} by {1}. {2} holds {3}% of them."), count(total, h.t("Item", "item")), h.groupName, top.group, top.pct);
    }
    return fill(h.t("Headline_Items", "{0}."), count(total, h.t("Item", "item")));
}
