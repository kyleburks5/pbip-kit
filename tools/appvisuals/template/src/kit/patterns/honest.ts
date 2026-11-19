/*
 *  pbip-kit pattern modules: honest data (docs/patterns/honest-data.md).
 *  - Small samples: below `minSample` a value either fades toward the quiet colour with a "limited sample" note
 *    (mode "fade") or is not shown at all (mode "suppress", the privacy mode: small-cell suppression). The threshold
 *    and the mode come from the project (design/specs/project.json `honestData`; suppress by default at work) through
 *    the visual's hidden `honest` object, which pbik build writes.
 *  - Own range: each group is judged against its own normal range or benchmark, not one scale for all (a good rate in
 *    one group can be a poor rate in another).
 *  - Readable text: on any member colour, pick the theme's text or background colour, whichever contrasts more.
 *  - Standout: the member to highlight while nothing is picked (enough sample, best score), or none.
 */

export type SampleMode = "fade" | "suppress";

export interface SampleRule {
    minSample: number;
    mode: SampleMode;
}

export const DEFAULT_SAMPLE: SampleRule = { minSample: 11, mode: "fade" };

export interface SampleVerdict {
    /** Draw the value at all (false: suppressed, show the "fewer than N" text instead). */
    show: boolean;
    /** 0..1: how much of the value's own colour to use (1 at or above the threshold). */
    confidence: number;
    /** A short note for the label or readout ("limited sample", "fewer than 11"), or "". */
    note: string;
}

/** Read the hidden `honest` object ({ minSample, mode }) that pbik build writes from project.json. */
export function readSampleRule(objects: unknown): SampleRule {
    const o = ((objects as { honest?: { minSample?: number; mode?: string } })?.honest) || {};
    const n = Number(o.minSample);
    return {
        minSample: Number.isFinite(n) && n >= 0 ? Math.round(n) : DEFAULT_SAMPLE.minSample,
        mode: o.mode === "suppress" ? "suppress" : o.mode === "fade" ? "fade" : DEFAULT_SAMPLE.mode
    };
}

/** What to do with a value backed by `n` records. A count of 0 is "no data", never "limited". */
export function sample(n: number, rule: SampleRule, words = { limited: "limited sample", fewer: "fewer than {0}" }): SampleVerdict {
    if (!(n > 0)) {
        return { show: false, confidence: 0, note: "" };
    }
    if (n >= rule.minSample || rule.minSample <= 1) {
        return { show: true, confidence: 1, note: "" };
    }
    if (rule.mode === "suppress") {
        return { show: false, confidence: 0, note: words.fewer.replace("{0}", String(rule.minSample)) };
    }
    return { show: true, confidence: Math.max(0.1, n / rule.minSample), note: words.limited };
}

/** A count that may be suppressed, as text ("fewer than 11" instead of 7). */
export function countText(n: number, rule: SampleRule, format: (v: number) => string = v => v.toLocaleString()): string {
    return rule.mode === "suppress" && n > 0 && n < rule.minSample ? `<${rule.minSample}` : format(n);
}

/** A group's own normal range: [low, high] that maps to the cold and hot ends of the colour scale. */
export type Band = [number, number];

/**
 * Bands per group from the data itself when none are given: the group's rates spread around their weighted mean
 * (mean +/- `spread` x the weighted standard deviation, never narrower than `minWidth`). Pass benchmark bands
 * instead when the domain has them (a league average, a target, a national rate).
 */
export function bandsFrom(rows: Array<{ group: string; value: number; weight: number }>, spread = 1.5, minWidth = 0.05): Map<string, Band> {
    const by = new Map<string, Array<{ value: number; weight: number }>>();
    for (const r of rows) {
        if (Number.isFinite(r.value) && r.weight > 0) {
            (by.get(r.group) || by.set(r.group, []).get(r.group)).push(r);
        }
    }
    const out = new Map<string, Band>();
    by.forEach((list, g) => {
        const w = list.reduce((s, r) => s + r.weight, 0);
        const mean = list.reduce((s, r) => s + r.value * r.weight, 0) / w;
        const sd = Math.sqrt(list.reduce((s, r) => s + r.weight * (r.value - mean) ** 2, 0) / w);
        const half = Math.max(minWidth / 2, sd * spread);
        out.set(g, [mean - half, mean + half]);
    });
    return out;
}

/** Position 0..1 of a value on its band (clamped). */
export function onBand(value: number, band: Band): number {
    const [lo, hi] = band;
    return hi > lo ? Math.min(1, Math.max(0, (value - lo) / (hi - lo))) : 0.5;
}

function hex(c: string): [number, number, number] | null {
    const m = /^#?([0-9a-f]{6})$/i.exec((c || "").trim());
    if (m) {
        const n = parseInt(m[1], 16);
        return [n >> 16 & 255, n >> 8 & 255, n & 255];
    }
    const r = /rgba?\(([^)]+)\)/.exec(c || "");
    return r ? (r[1].split(",").slice(0, 3).map(x => parseFloat(x)) as [number, number, number]) : null;
}

/** WCAG relative luminance of a colour (0 black .. 1 white). */
export function luminance(c: string): number {
    const p = hex(c);
    if (!p) {
        return 0.5;
    }
    const lin = (v: number) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * lin(p[0]) + 0.7152 * lin(p[1]) + 0.0722 * lin(p[2]);
}

/** WCAG contrast ratio of two colours (1..21). */
export function contrast(a: string, b: string): number {
    const la = luminance(a), lb = luminance(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** Text on a member colour: whichever of the theme's text and background colours contrasts more with it. */
export function readableOn(fill: string, text: string, background: string): string {
    return contrast(fill, text) >= contrast(fill, background) ? text : background;
}

/**
 * The standout to highlight while nothing is picked: the best `score` among members with at least `minSample`
 * records, preferring members above their benchmark; null when none qualifies (then nothing is highlighted).
 * Ties break by key, so the pick doesn't change between refreshes.
 */
export function standout<T extends { key: string; n: number; score: number; aboveBenchmark?: boolean }>(items: T[], minSample: number): T | null {
    const ok = items.filter(i => i.n >= Math.max(1, minSample) && Number.isFinite(i.score));
    if (!ok.length) {
        return null;
    }
    const pool = ok.some(i => i.aboveBenchmark) ? ok.filter(i => i.aboveBenchmark) : ok;
    return pool.slice().sort((a, b) => b.score - a.score || a.key.localeCompare(b.key))[0];
}
