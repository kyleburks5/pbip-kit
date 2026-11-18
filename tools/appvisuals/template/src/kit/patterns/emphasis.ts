/*
 *  pbip-kit pattern modules: selection highlight and dimming (docs/patterns/app-visuals/focus-dim.md).
 *  One rule for every visual: what is selected here, or highlighted from another visual, stays strong; everything
 *  else dims to the pane's "Dimmed opacity". High contrast: no transparency, hollow marks with a foreground stroke,
 *  the host's selected colour on the selection.
 */
import { Theme } from "../theme";

export interface Emphasis {
    color: string;
    alpha: number;
    stroke?: string;
    on: boolean;
}

/**
 * base: the mark's own colour. selected: is it in this visual's selection; anySelected: is anything selected here;
 * highlightedOff: another visual highlighted something else (cross-filter coming in as a highlight).
 */
export function emphasis(t: Theme, base: string, selected: boolean, anySelected: boolean, highlightedOff: boolean): Emphasis {
    const on = anySelected ? selected : !highlightedOff;
    if (t.highContrast) {
        return { on, color: on ? t.foreground : t.background, alpha: 1, stroke: selected ? t.selected : t.foreground };
    }
    return { on, color: base, alpha: on ? 1 : t.dim, stroke: selected ? t.foreground : undefined };
}
