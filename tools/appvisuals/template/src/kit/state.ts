/*
 *  pbip-kit app-visual template: saved state (bookmarks and reopen).
 *  The view, the drilled group and the camera are properties of the `state` object, each marked `"filterState": true`
 *  in capabilities.json, so a bookmark captures them and saving the report keeps them (Microsoft Learn, "Add
 *  bookmark support for Power BI custom visuals": filterState properties). The visual writes them with
 *  persistProperties (debounced) when the person changes them; on update it reads them back. Selection is restored
 *  separately, by the selection manager's callback (interaction.ts).
 */
import powerbi from "powerbi-visuals-api";
import { Camera } from "./layers";

import DataView = powerbi.DataView;
import IVisualHost = powerbi.extensibility.visual.IVisualHost;

export interface ViewState {
    view: string;
    drill: string;
    camera: Camera | null;
}

const EMPTY: ViewState = { view: "", drill: "", camera: null };

export class StateStore {
    private last = "";
    private sent = "";                 // the state Power BI holds now (the last one saved or read)
    private timer: number | null = null;

    // 1.5 s: a save makes Power BI re-draw the page, which freezes any move still running (Desktop review
    // 2026-11-17: 284-412 ms frames during view switches); every kit move lands within about a second
    constructor(private host: IVisualHost, private delay = 1500) { }

    /** The saved state in this update (a bookmark, a reopen or our own save coming back). */
    read(dv: DataView | undefined): ViewState {
        const o = (dv?.metadata?.objects?.state || {}) as Record<string, unknown>;
        let camera: Camera | null = null;
        try {
            camera = o.camera ? JSON.parse(String(o.camera)) as Camera : null;
        } catch {
            camera = null;
        }
        return { view: String(o.view || ""), drill: String(o.drill || ""), camera };
    }

    /**
     * True when the update brings a state we didn't write ourselves (a bookmark was applied). While a save is waiting
     * (the debounce), updates still carry the state saved before it: that is ours too, not a bookmark (an update from
     * a filter or a selection in that window used to re-open the old view, Desktop review 2026-11-17).
     */
    isNew(s: ViewState): boolean {
        const text = JSON.stringify(s);
        if (this.timer != null && text === this.sent) {
            return false;
        }
        return text !== this.last && text !== JSON.stringify(EMPTY);
    }

    remember(s: ViewState): void {
        this.last = JSON.stringify(s);
        this.sent = this.last;
    }

    save(s: ViewState): void {
        const text = JSON.stringify(s);
        if (text === this.last) {
            return;
        }
        this.last = text;
        if (this.timer != null) {
            window.clearTimeout(this.timer);
        }
        this.timer = window.setTimeout(() => {
            this.timer = null;
            this.sent = text;
            this.host.persistProperties({
                merge: [{
                    objectName: "state", selector: null,
                    properties: { view: s.view, drill: s.drill, camera: s.camera ? JSON.stringify(round(s.camera)) : "" }
                }]
            });
        }, this.delay);
    }
}

function round(c: Camera): Camera {
    return { k: Math.round(c.k * 1000) / 1000, x: Math.round(c.x), y: Math.round(c.y) };
}
