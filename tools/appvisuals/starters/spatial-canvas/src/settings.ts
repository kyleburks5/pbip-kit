/*
 *  Spatial canvas: formatting pane. The shared cards (colours, text, layout, motion, interaction) come from the kit;
 *  this visual adds the Space card and two colours for the cold and hot ends of the zone scale.
 */
import powerbi from "powerbi-visuals-api";
import { formattingSettings } from "powerbi-visuals-utils-formattingmodel";
import { FontsCard, LayoutCard, MotionCard } from "./kit/settings";

import ValidatorType = powerbi.visuals.ValidatorType;
import Card = formattingSettings.SimpleCard;
import Model = formattingSettings.Model;

const items = (values: string[], labels: string[]) => values.map((v, i) => ({ value: v, displayName: labels[i] }));

export const SHAPES = ["court", "pitch", "body", "floor", "areas", "track", "custom"];
export const SHAPE_LABELS = ["Court (half)", "Pitch", "Body map", "Floor plan", "Service areas", "Route / pathway (from the data)", "Custom shapes (paste below)"];
export const VIEWS = ["dots", "zones", "ranked"];

export class SpatialColors extends Card {
    accent = new formattingSettings.ColorPicker({ name: "accent", displayName: "Accent (empty = theme)", value: { value: "" } });
    background = new formattingSettings.ColorPicker({ name: "background", displayName: "Panel background (empty = theme)", value: { value: "" } });
    text = new formattingSettings.ColorPicker({ name: "text", displayName: "Text (empty = theme)", value: { value: "" } });
    cold = new formattingSettings.ColorPicker({ name: "cold", displayName: "Below its range (empty = theme)", value: { value: "" } });
    hot = new formattingSettings.ColorPicker({ name: "hot", displayName: "Above its range (empty = accent)", value: { value: "" } });
    dimOpacity = new formattingSettings.Slider({
        name: "dimOpacity", displayName: "Dimmed opacity %", value: 20,
        options: { minValue: { value: 5, type: ValidatorType.Min }, maxValue: { value: 100, type: ValidatorType.Max } }
    });
    name = "colors";
    displayName = "Colours";
    slices = [this.accent, this.background, this.text, this.cold, this.hot, this.dimOpacity];
}

export class SpaceCard extends Card {
    shape = new formattingSettings.ItemDropdown({ name: "shape", displayName: "Space", items: items(SHAPES, SHAPE_LABELS), value: { value: "court", displayName: SHAPE_LABELS[0] } });
    scale = new formattingSettings.NumUpDown({ name: "scale", displayName: "Data units per space unit", value: 1 });
    custom = new formattingSettings.TextInput({ name: "custom", displayName: "Custom shapes (GeoJSON or {zones})", value: "", placeholder: "{\"zones\": [...]}" });
    start = new formattingSettings.ItemDropdown({ name: "start", displayName: "Start view", items: items(VIEWS, ["Dots", "Zones", "Ranked"]), value: { value: "zones", displayName: "Zones" } });
    pills = new formattingSettings.ToggleSwitch({ name: "pills", displayName: "View pills", value: true });
    headline = new formattingSettings.ToggleSwitch({ name: "headline", displayName: "Headline", value: true });
    readout = new formattingSettings.ToggleSwitch({ name: "readout", displayName: "Docked readout", value: true });
    readoutWidth = new formattingSettings.NumUpDown({ name: "readoutWidth", displayName: "Readout width (px)", value: 220 });
    labels = new formattingSettings.ToggleSwitch({ name: "labels", displayName: "Zone names", value: true });
    standout = new formattingSettings.ToggleSwitch({ name: "standout", displayName: "Show the standout when idle", value: true });
    benchmarkSpan = new formattingSettings.NumUpDown({ name: "benchmarkSpan", displayName: "Benchmark span (rate points to full colour)", value: 0.1 });
    name = "space";
    displayName = "Space";
    slices = [this.shape, this.scale, this.custom, this.start, this.pills, this.headline, this.readout, this.readoutWidth, this.labels, this.standout, this.benchmarkSpan];
}

export class SpatialInteraction extends Card {
    tooltips = new formattingSettings.ToggleSwitch({ name: "tooltips", displayName: "Tooltips", value: true });
    clickMode = new formattingSettings.ItemDropdown({
        name: "clickMode", displayName: "Clicks",
        items: items(["filter", "crossFilter"], ["Filter the page (cards, tables, other pages through sync slicers)", "Cross-highlight this page"]),
        value: { value: "filter", displayName: "Filter the page (cards, tables, other pages through sync slicers)" }
    });
    name = "interaction";
    displayName = "Interaction";
    slices = [this.tooltips, this.clickMode];
}

export class SpatialSettings extends Model {
    colors = new SpatialColors();
    fonts = new FontsCard();
    layout = new LayoutCard();
    motion = new MotionCard();
    space = new SpaceCard();
    interaction = new SpatialInteraction();
    cards = [this.space, this.colors, this.fonts, this.layout, this.motion, this.interaction];
}
