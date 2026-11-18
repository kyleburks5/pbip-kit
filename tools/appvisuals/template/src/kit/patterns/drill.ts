/*
 *  pbip-kit pattern modules: drill zoom and camera zoom (docs/patterns/app-visuals/drill-zoom.md).
 *  - Drill: click a group (label, card, bar) to open it as its own screen; its units re-pack to fill the view; Back or
 *    the breadcrumb returns. Built on Screens (scene.ts), so the back stack and keyboard come with it.
 *  - Camera: fly the camera to a box (an item) and back, through the Motion engine (reduce motion jumps).
 */
import { Screens } from "../scene";
import { Motion } from "../motion";
import { Camera } from "../layers";
import { Interaction } from "../interaction";

export class Drill {
    readonly screens: Screens<string>;
    group: string | null = null;

    constructor(rootTitle: string, private onChange: (group: string | null) => void) {
        this.screens = new Screens<string>((id, g) => {
            this.group = id === "group" ? g : null;
            this.onChange(this.group);
        });
        this.screens.reset("all", rootTitle);
    }

    open(group: string): void {
        if (this.group !== group) {
            this.screens.push("group", group, group);
        }
    }

    back(): void {
        this.screens.back();
    }
}

/** Fly the camera from where it is to `to` (identity camera: { k: 1, x: 0, y: 0 } zooms back out). */
export function flyTo(motion: Motion, ia: Interaction, to: Camera): Promise<void> {
    const from = { ...ia.camera };
    return motion.tween(0, 1, p => ia.setCamera({ k: from.k + (to.k - from.k) * p, x: from.x + (to.x - from.x) * p, y: from.y + (to.y - from.y) * p }));
}

/** The camera that frames one mark with room around it (zoom into an item). */
export function frameMark(ia: Interaction, m: { x: number; y: number; r: number }, room = 8): Camera {
    return ia.fit(m.x - m.r * room, m.y - m.r * room, m.r * room * 2, m.r * room * 2);
}
