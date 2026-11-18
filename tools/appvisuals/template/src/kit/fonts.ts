/*
 *  pbip-kit app-visual template: bundled fonts. `pbik visual build` writes fonts.generated.ts with the font files as
 *  base64 (Inter, SIL Open Font License 1.1, from @fontsource/inter; licence text in NOTICE.md). They are registered
 *  with the FontFace API from memory: no network, no CSS url(), nothing for the certification check to flag.
 */
import { FONTS } from "./fonts.generated";

let done = false;

export function registerFonts(): void {
    if (done || typeof FontFace === "undefined") {
        return;
    }
    done = true;
    for (const f of FONTS) {
        try {
            const bin = atob(f.data);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) {
                bytes[i] = bin.charCodeAt(i);
            }
            const face = new FontFace(f.family, bytes.buffer, { weight: f.weight, style: "normal" });
            (document.fonts as unknown as { add(f: FontFace): void }).add(face);
            face.load().catch(() => undefined);
        } catch {
            // a font that can't load falls back to the next family in the stack
        }
    }
}
