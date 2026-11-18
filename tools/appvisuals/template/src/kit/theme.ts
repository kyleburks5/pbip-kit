/*
 *  pbip-kit app-visual template: colours and fonts from the report theme and the formatting pane.
 *  High contrast mode: only the host's foreground / background / selected colours, and strokes instead of
 *  transparency (Microsoft Learn, "High-contrast mode support in Power BI visuals").
 */
import powerbi from "powerbi-visuals-api";
import { ColorsCard, FontsCard, LayoutCard } from "./settings";

export interface ThemeSource { colors: ColorsCard; fonts: FontsCard; layout: LayoutCard }

import ISandboxExtendedColorPalette = powerbi.extensibility.ISandboxExtendedColorPalette;

export interface Theme {
    highContrast: boolean;
    palette: string[];
    accent: string;
    foreground: string;
    secondary: string;
    background: string;
    panel: string;
    selected: string;
    font: string;
    fontPx: number;
    headlinePx: number;
    dim: number;
    radius: number;
    shadow: string;
}

const ptToPx = (pt: number) => Math.round(pt * 96 / 72 * 10) / 10;

export function readTheme(palette: ISandboxExtendedColorPalette, s: ThemeSource): Theme {
    const hc = !!palette.isHighContrast;
    const fg = palette.foreground?.value || "#252423";
    const bg = palette.background?.value || "#ffffff";
    const dataColors: string[] = [];
    for (let i = 0; i < 12; i++) {
        dataColors.push(palette.getColor(`kit-${i}`).value);
    }
    palette.reset();
    const pick = (v: string, fallback: string) => (v && !hc ? v : fallback);
    const accent = hc ? fg : pick(s.colors.accent.value.value, dataColors[0]);
    return {
        highContrast: hc,
        palette: hc ? [fg] : dataColors,
        accent,
        foreground: pick(s.colors.text.value.value, fg),
        secondary: hc ? fg : (palette.foregroundNeutralSecondary?.value || fg),
        background: bg,
        panel: pick(s.colors.background.value.value, palette.backgroundLight?.value || bg),
        selected: hc ? (palette.foregroundSelected?.value || fg) : accent,
        font: s.fonts.family.value,
        fontPx: ptToPx(s.fonts.size.value),
        headlinePx: ptToPx(s.fonts.headlineSize.value),
        dim: hc ? 1 : s.colors.dimOpacity.value / 100,
        radius: s.layout.radius.value,
        shadow: s.layout.shadow.value && !hc ? "0 2px 8px rgba(0,0,0,0.12)" : "none"
    };
}

/** A colour per key (group), stable across updates: the theme's data colours in first-seen order. */
export class ColorScale {
    private keys = new Map<string, number>();
    /** `keep`: the scale this one replaces (a new theme): groups keep their colours. */
    constructor(private theme: Theme, keep?: ColorScale) {
        if (keep) {
            keep.keys.forEach((v, k) => this.keys.set(k, v));
        }
    }
    /** Fix the order from all the data (every group, in data order), so a drill or a subset never repaints a group. */
    seed(keys: string[]): void {
        keys.forEach(k => {
            if (!this.keys.has(k)) {
                this.keys.set(k, this.keys.size);
            }
        });
    }
    get(key: string): string {
        if (!this.keys.has(key)) {
            this.keys.set(key, this.keys.size);
        }
        const p = this.theme.palette;
        return p[this.keys.get(key) % p.length];
    }
}
