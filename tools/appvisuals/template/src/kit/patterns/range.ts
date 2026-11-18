/*
 *  pbip-kit pattern modules: range select along one axis (docs/patterns/app-visuals/range-select.md).
 *  Drag a span on a time or number axis: the units inside it are selected (cross-filter out); a click clears.
 *  The 2D version (drag a box) is Interaction.enableBrush; this one keeps the other axis whole, for timelines.
 */
import { brushX, brushY, BrushBehavior, D3BrushEvent } from "d3-brush";
import { Selection } from "d3-selection";

export interface RangeOptions {
    axis: "x" | "y";
    box: { x: number; y: number; w: number; h: number };
    /** world value -> keys inside [a, b] (pixels along the axis) */
    keysIn: (a: number, b: number) => string[];
    onRange: (keys: string[], span: [number, number] | null) => void;
}

export function rangeSelect(g: Selection<SVGGElement, unknown, null, undefined>, o: RangeOptions): BrushBehavior<unknown> {
    const ext: [[number, number], [number, number]] = [[o.box.x, o.box.y], [o.box.x + o.box.w, o.box.y + o.box.h]];
    const b = (o.axis === "x" ? brushX<unknown>() : brushY<unknown>()).extent(ext)
        .on("end", (e: D3BrushEvent<unknown>) => {
            if (!e.sourceEvent) {
                return;
            }
            if (!e.selection) {
                o.onRange([], null);
                return;
            }
            const [a, c] = e.selection as [number, number];
            o.onRange(o.keysIn(a, c), [a, c]);
        });
    g.classed("kit-range", true).call(b);
    return b;
}
