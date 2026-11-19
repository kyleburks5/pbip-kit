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

export interface GapMetric {
    label: string;                  // "first-visit resolution"
    better: "high" | "low";
    format: (v: number) => string;
    a: number | null;               // side A's value
    b: number | null;               // side B's value
    norm?: [number, number];        // the range both are judged on (all members' low and high); default: the two values
}

export interface GapSides { a: string; b: string }

/**
 * The biggest gap between two members across several measures, in one sentence: "North is 2.3x South on first-visit
 * resolution" (a ratio when both are positive and higher is better), else "North leads South on wait time by 4 days".
 * Measures are compared on a shared 0..1 scale (each measure's own range), so units don't decide the pick. Null when
 * no measure separates them (then say nothing rather than something weak).
 */
export function biggestGap(sides: GapSides, metrics: GapMetric[], t: (key: string, english: string) => string = (_k, e) => e): string | null {
    let best: { m: GapMetric; gap: number; aWins: boolean } | null = null;
    for (const m of metrics) {
        if (m.a == null || m.b == null || !Number.isFinite(m.a) || !Number.isFinite(m.b)) {
            continue;
        }
        const [lo, hi] = m.norm || [Math.min(m.a, m.b), Math.max(m.a, m.b)];
        const span = hi - lo || Math.max(Math.abs(m.a), Math.abs(m.b), 1);
        const na = (m.a - lo) / span, nb = (m.b - lo) / span;
        const gap = Math.abs(na - nb);
        const aWins = m.better === "high" ? m.a >= m.b : m.a <= m.b;
        if (gap > 0.001 && (!best || gap > best.gap)) {
            best = { m, gap, aWins };
        }
    }
    if (!best) {
        return null;
    }
    const { m, aWins } = best;
    const w = aWins ? sides.a : sides.b, l = aWins ? sides.b : sides.a;
    const wv = aWins ? m.a : m.b, lv = aWins ? m.b : m.a;
    if (m.better === "high" && wv > 0 && lv > 0 && wv / lv >= 1.1 && wv / lv < 100) {
        return fill(t("Headline_GapRatio", "{0} is {1}× {2} on {3}."), w, (wv / lv).toFixed(1), l, m.label);
    }
    return fill(t("Headline_GapLead", "{0} leads {1} on {2} by {3}."), w, l, m.label, m.format(Math.abs(wv - lv)));
}
