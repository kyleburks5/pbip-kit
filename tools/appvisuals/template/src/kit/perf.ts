/*
 *  pbip-kit app-visual template: the frame meter (a debug tool, off by default and not in the formatting pane).
 *  The agent turns it on with the visual's hidden `debug` object (layout.json props `debug.meter`, and
 *  `debug.selfTest` to play the visual's own moves once the page is in front). After each click or move it measures
 *  the display frames for two seconds: how many, the longest gap, the share over 50 ms (frozen), and the updates
 *  Power BI sent meanwhile with the time the visual spent in them. A small panel in the corner lists the last moves,
 *  so a Desktop screenshot carries the numbers; the harness reads them with kitMeter().
 */
import powerbi from "powerbi-visuals-api";

export interface MeterRow {
    label: string;
    frames: number;
    longest: number;
    frozen: number;           // share of frame gaps over 50 ms during the move (its first second), 0-100
    after: number;            // the longest frame after the move (Power BI catching up with a filter or a save), ms
    updates: number;
    updateMs: number;         // the longest update in the window (ms)
}

interface Window_ { label: string; t0: number; last: number; gaps: number[]; updates: number; updateMs: number; until: number }

export class FrameMeter {
    on = false;
    selfTest = false;
    private rows: MeterRow[] = [];
    private cur: Window_ | null = null;
    private panel: HTMLDivElement | null = null;
    private tested = false;
    private notes: string[] = [];
    private created = performance.now();
    private quietSince = 0;
    private done = false;
    private seen = 0;          // animation frames seen since the visual was created: a page in front has them

    constructor(private root: HTMLElement, private windowMs = 2000, private moveMs = 1000) {
        root.addEventListener("pointerdown", () => this.mark("click"), true);
        (root as unknown as { kitMeter: () => MeterRow[] }).kitMeter = () => this.rows.slice();
    }

    /** Counts animation frames and quiet time, for the self-test only (it must know the page is in front and idle). */
    private ticking = false;
    private startTicks(): void {
        if (this.ticking) {
            return;
        }
        this.ticking = true;
        let last = performance.now();
        const tick = () => {
            const now = performance.now();
            this.seen++;
            if (now - last > 40 || !this.quietSince) {
                this.quietSince = now;                 // the page did something heavy: quiet starts again
            }
            last = now;
            if (this.selfTest && !this.done) {
                requestAnimationFrame(tick);
            } else {
                this.ticking = false;
            }
        };
        requestAnimationFrame(tick);
    }

    /** Read the hidden debug object: { meter: true, selfTest: true }. */
    read(dv: powerbi.DataView | undefined): void {
        const o = (dv?.metadata?.objects?.debug || {}) as { meter?: boolean; selfTest?: boolean };
        this.on = !!o.meter || !!o.selfTest;
        this.selfTest = !!o.selfTest;
        if (this.selfTest) {
            this.startTicks();
        }
        if (this.on && !this.panel) {
            this.panel = document.createElement("div");
            this.panel.className = "kit-meter";
            this.panel.setAttribute("aria-hidden", "true");
            this.root.appendChild(this.panel);
            this.draw();
        } else if (!this.on && this.panel) {
            this.panel.remove();
            this.panel = null;
        }
    }

    /** Start measuring a move (a click starts one by itself). */
    mark(label: string): void {
        if (!this.on) {
            return;
        }
        this.finish();
        const t = performance.now();
        const w: Window_ = { label, t0: t, last: t, gaps: [], updates: 0, updateMs: 0, until: t + this.windowMs };
        this.cur = w;
        const loop = () => {
            if (this.cur !== w) {
                return;
            }
            const now = performance.now();
            w.gaps.push(now - w.last);
            w.last = now;
            if (now < w.until) {
                requestAnimationFrame(loop);
            } else {
                this.finish();
            }
        };
        requestAnimationFrame(loop);
    }

    /** The visual spent `ms` in an update (call it at the end of update()). */
    update(ms: number): void {
        if (this.cur) {
            this.cur.updates++;
            this.cur.updateMs = Math.max(this.cur.updateMs, ms);
        }
    }

    /** A line of state for the panel (debug only): what the visual thinks it drew. */
    note(text: string): void {
        if (this.on) {
            this.notes = [...this.notes.filter(n => !n.startsWith(text.split(":")[0] + ":")), text].slice(-4);
            this.draw();
        }
    }

    /** Rename the move being measured (a click becomes "click: Site 05"). */
    label(text: string): void {
        if (this.cur && this.cur.label === "click") {
            this.cur.label = `click: ${text}`;
        }
    }

    /** Play the visual's own moves once, when the page is in front: [label, action] pairs, 2.6 s apart. */
    run(actions: Array<[string, () => void]>): void {
        if (!this.selfTest || this.tested || !actions.length) {
            return;
        }
        this.tested = true;
        const start = () => {
            // in front (animation frames) and quiet: 3 s without a frame over 40 ms, so the page's own loading isn't
            // measured as the visual's moves (at most 40 s of waiting)
            if ((this.seen < 60 || performance.now() - this.quietSince < 3000) && performance.now() - this.created < 40000) {
                window.setTimeout(start, 500);
                return;
            }
            let i = 0;
            const next = () => {
                if (i >= actions.length) {
                    this.done = true;
                    return;
                }
                const [label, act] = actions[i++];
                this.mark(label);
                try {
                    act();
                } catch (e) {
                    const err = e as Error;
                    this.cur.label = `${label} FAILED`;
                    this.notes.push(`${label}: ${err?.message || err} ${(err?.stack || "").split(String.fromCharCode(10))[1] || ""}`.slice(0, 160));
                    this.draw();
                }
                window.setTimeout(next, this.windowMs + 600);
            };
            next();
        };
        window.setTimeout(start, 2500);
    }

    private finish(): void {
        const w = this.cur;
        if (!w) {
            return;
        }
        this.cur = null;
        // split at the end of the move: what you see as stutter, and Power BI catching up after it
        const move: number[] = [], after: number[] = [];
        let t = w.t0;
        for (const g of w.gaps.slice(1)) {
            t += g;
            (t - w.t0 <= this.moveMs ? move : after).push(g);
        }
        this.rows.push({
            label: w.label, frames: move.length + after.length, longest: Math.round(Math.max(0, ...move)),
            frozen: Math.round(move.filter(g => g > 50).length / Math.max(1, move.length) * 100),
            after: Math.round(Math.max(0, ...after)), updates: w.updates, updateMs: Math.round(w.updateMs)
        });
        this.rows = this.rows.slice(-12);
        this.draw();
    }

    private draw(): void {
        if (!this.panel) {
            return;
        }
        this.panel.textContent = "";
        const head = document.createElement("div");
        head.textContent = "move | frozen % | longest ms | after ms | updates (ms)";
        this.panel.appendChild(head);
        for (const r of this.rows) {
            const line = document.createElement("div");
            line.textContent = `${r.label.slice(0, 26)} | ${r.frozen}% | ${r.longest} | ${r.after} | ${r.updates} (${r.updateMs})`;
            if (r.frozen >= 5 || r.longest > 100) {
                line.className = "is-bad";
            }
            this.panel.appendChild(line);
        }
        for (const n of this.notes) {
            const line = document.createElement("div");
            line.textContent = n;
            this.panel.appendChild(line);
        }
    }
}
