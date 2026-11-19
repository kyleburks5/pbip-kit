/*
 *  pbip-kit app-visual template: automatic quality step-down.
 *  While marks move, the governor watches the frame gaps (Motion.onFrame). When a window of frames runs slow
 *  (an average over 20 ms, under 50 frames a second) it steps down one tier, two when very slow (over 33 ms):
 *  fewer device pixels per canvas pixel, less stagger, and earlier switches from SVG to Canvas to WebGL. It never
 *  steps back up in the same session (no flicker between tiers), waits a second after each change before measuring
 *  again, and only counts moves (an idle page measures nothing). What a tier changes never changes what the visual
 *  shows: positions, colours and text stay the same. The harness reads the tier with kitQuality().
 */

export interface Tier {
    name: string;
    /** Highest device pixels per CSS pixel for the canvases. */
    maxRatio: number;
    /** Share of the motion stagger kept (0 = every mark moves together). */
    stagger: number;
    /** Mark counts at which SVG gives way to Canvas, and Canvas to WebGL. */
    svgMax: number;
    canvasMax: number;
}

export const TIERS: Tier[] = [
    { name: "full", maxRatio: 3, stagger: 1, svgMax: 600, canvasMax: 8000 },
    { name: "sharp", maxRatio: 2, stagger: 1, svgMax: 450, canvasMax: 6000 },
    { name: "balanced", maxRatio: 1.5, stagger: 0.5, svgMax: 300, canvasMax: 4000 },
    { name: "light", maxRatio: 1, stagger: 0, svgMax: 200, canvasMax: 2500 },
    { name: "lightest", maxRatio: 0.75, stagger: 0, svgMax: 120, canvasMax: 1500 }
];

export class Quality {
    tier = 0;
    private gaps: number[] = [];
    private holdUntil = 0;
    readonly log: string[] = [];

    constructor(private onChange: (t: Tier, why: string) => void, private windowFrames = 30, private slowMs = 20, private verySlowMs = 33) { }

    get current(): Tier {
        return TIERS[this.tier];
    }

    /** One frame gap during a move (ms). Gaps over a second are a hidden page or a pause, not a slow frame. */
    frame(gapMs: number): void {
        const now = performance.now();
        if (now < this.holdUntil || gapMs > 1000) {
            return;
        }
        this.gaps.push(gapMs);
        if (this.gaps.length < this.windowFrames) {
            return;
        }
        const avg = this.gaps.reduce((a, b) => a + b, 0) / this.gaps.length;
        this.gaps = [];
        if (avg > this.slowMs && this.tier < TIERS.length - 1) {
            this.tier = Math.min(TIERS.length - 1, this.tier + (avg > this.verySlowMs ? 2 : 1));
            this.holdUntil = now + 1000;
            const why = `frames ${Math.round(avg)} ms on average: quality ${this.current.name}`;
            this.log.push(why);
            this.onChange(this.current, why);
        }
    }

    /** Expose the tier to the harness and the frame meter. */
    expose(root: HTMLElement): void {
        (root as unknown as { kitQuality: () => { tier: number; name: string; log: string[] } }).kitQuality =
            () => ({ tier: this.tier, name: this.current.name, log: this.log.slice() });
    }
}
