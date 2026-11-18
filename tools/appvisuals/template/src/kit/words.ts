/*
 *  pbip-kit app-visual template: a number and its noun, agreeing ("1 site", "24 sites", "1 person", "60 people").
 *  Every count in a headline, a label or an aria-label goes through count() (Desktop review 2026-11-17: "1 items",
 *  "1 regions", "of 1 sites"). English rules; a localised string can give both forms with forms().
 */
const IRREGULAR: Record<string, string> = { person: "people", child: "children", man: "men", woman: "women" };
const SINGULAR: Record<string, string> = Object.fromEntries(Object.entries(IRREGULAR).map(([a, b]) => [b, a]));

/** The singular of an English noun (sites -> site, people -> person, categories -> category). */
export function singular(word: string): string {
    const w = word.trim(), lower = w.toLowerCase();
    if (SINGULAR[lower]) {
        return keepCase(w, SINGULAR[lower]);
    }
    if (/[^aeiou]ies$/i.test(w)) {
        return w.slice(0, -3) + "y";
    }
    if (/(ss|sh|ch|x|z)es$/i.test(w)) {
        return w.slice(0, -2);
    }
    if (/[^s]s$/i.test(w)) {
        return w.slice(0, -1);
    }
    return w;
}

/** The plural of an English noun (site -> sites, person -> people, category -> categories). */
export function plural(word: string): string {
    const w = singular(word), lower = w.toLowerCase();
    if (IRREGULAR[lower]) {
        return keepCase(w, IRREGULAR[lower]);
    }
    if (/[^aeiou]y$/i.test(w)) {
        return w.slice(0, -1) + "ies";
    }
    if (/(s|sh|ch|x|z)$/i.test(w)) {
        return w + "es";
    }
    return w + "s";
}

/** "1 site" / "24 sites": the noun in either form is fine. */
export function count(n: number, noun: string): string {
    return `${n.toLocaleString()} ${n === 1 ? singular(noun) : plural(noun)}`;
}

/** A localised pair: "1 {one}" / "n {many}" when a language's plural isn't an added s. */
export function forms(n: number, one: string, many: string): string {
    return `${n.toLocaleString()} ${n === 1 ? one : many}`;
}

function keepCase(model: string, word: string): string {
    return model[0] === model[0].toUpperCase() ? word[0].toUpperCase() + word.slice(1) : word;
}
