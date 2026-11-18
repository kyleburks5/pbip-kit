/*
 *  pbip-kit app-visual template: formatting pane settings.
 *  The card pattern follows Microsoft's Dot Plot visual (dotPlotSettingsModel.ts, MIT, Copyright (c) Microsoft
 *  Corporation; see NOTICE.md). Every look and motion setting lives here: nothing in the visual is hard-coded.
 *  Empty colours mean "take it from the report theme".
 */
import powerbi from "powerbi-visuals-api";
import { formattingSettings } from "powerbi-visuals-utils-formattingmodel";

import ValidatorType = powerbi.visuals.ValidatorType;

import Card = formattingSettings.SimpleCard;
import Model = formattingSettings.Model;

const enumItems = (values: string[], labels: string[]) => values.map((v, i) => ({ value: v, displayName: labels[i] }));

export const EASINGS = ["cubicInOut", "cubicOut", "quadInOut", "expInOut", "backOut", "linear"];
export const VIEWS = ["grid", "columns", "scatter", "clusters"];
export const VIEW_LABELS = ["Grid", "Columns", "Scatter", "Clusters"];

export class ColorsCard extends Card {
    accent = new formattingSettings.ColorPicker({ name: "accent", displayName: "Accent (empty = theme)", value: { value: "" } });
    background = new formattingSettings.ColorPicker({ name: "background", displayName: "Panel background (empty = theme)", value: { value: "" } });
    text = new formattingSettings.ColorPicker({ name: "text", displayName: "Text (empty = theme)", value: { value: "" } });
    byGroup = new formattingSettings.ToggleSwitch({ name: "byGroup", displayName: "Colour by group", value: true });
    dimOpacity = new formattingSettings.Slider({
        name: "dimOpacity", displayName: "Dimmed opacity %", value: 25,
        options: { minValue: { value: 5, type: ValidatorType.Min }, maxValue: { value: 100, type: ValidatorType.Max } }
    });
    name = "colors";
    displayName = "Colours";
    slices = [this.accent, this.background, this.text, this.byGroup, this.dimOpacity];
}

export class FontsCard extends Card {
    family = new formattingSettings.FontPicker({ name: "family", displayName: "Font", value: "Inter, 'Segoe UI', sans-serif" });
    size = new formattingSettings.NumUpDown({
        name: "size", displayName: "Text size (pt)", value: 10,
        options: { minValue: { value: 8, type: ValidatorType.Min }, maxValue: { value: 40, type: ValidatorType.Max } }
    });
    headlineSize = new formattingSettings.NumUpDown({
        name: "headlineSize", displayName: "Headline size (pt)", value: 14,
        options: { minValue: { value: 8, type: ValidatorType.Min }, maxValue: { value: 60, type: ValidatorType.Max } }
    });
    name = "fonts";
    displayName = "Text";
    slices = [this.family, this.size, this.headlineSize];
}

export class LayoutCard extends Card {
    padding = new formattingSettings.NumUpDown({ name: "padding", displayName: "Padding (px)", value: 16 });
    gap = new formattingSettings.NumUpDown({ name: "gap", displayName: "Gap (px)", value: 8 });
    radius = new formattingSettings.NumUpDown({ name: "radius", displayName: "Corner radius (px)", value: 12 });
    shadow = new formattingSettings.ToggleSwitch({ name: "shadow", displayName: "Shadow", value: false });
    markSize = new formattingSettings.Slider({
        name: "markSize", displayName: "Mark size (px)", value: 6,
        options: { minValue: { value: 1, type: ValidatorType.Min }, maxValue: { value: 40, type: ValidatorType.Max } }
    });
    name = "layout";
    displayName = "Layout";
    slices = [this.padding, this.gap, this.radius, this.shadow, this.markSize];
}

export class MotionCard extends Card {
    animate = new formattingSettings.ToggleSwitch({ name: "animate", displayName: "Animate", value: true });
    speed = new formattingSettings.Slider({
        name: "speed", displayName: "Duration (ms)", value: 650,
        options: { minValue: { value: 0, type: ValidatorType.Min }, maxValue: { value: 3000, type: ValidatorType.Max } }
    });
    easing = new formattingSettings.ItemDropdown({
        name: "easing", displayName: "Easing",
        items: enumItems(EASINGS, ["Smooth", "Ease out", "Gentle", "Strong", "Overshoot", "Linear"]),
        value: { value: "cubicInOut", displayName: "Smooth" }
    });
    stagger = new formattingSettings.Slider({
        name: "stagger", displayName: "Stagger per item (ms)", value: 3,
        options: { minValue: { value: 0, type: ValidatorType.Min }, maxValue: { value: 50, type: ValidatorType.Max } }
    });
    reduceMotion = new formattingSettings.ToggleSwitch({ name: "reduceMotion", displayName: "Reduce motion", value: false });
    name = "motion";
    displayName = "Motion";
    slices = [this.animate, this.speed, this.easing, this.stagger, this.reduceMotion];
}

export class ViewCard extends Card {
    initial = new formattingSettings.ItemDropdown({
        name: "initial", displayName: "Start view", items: enumItems(VIEWS, VIEW_LABELS), value: { value: "grid", displayName: "Grid" }
    });
    pills = new formattingSettings.ToggleSwitch({ name: "pills", displayName: "View pills", value: true });
    headline = new formattingSettings.ToggleSwitch({ name: "headline", displayName: "Headline", value: true });
    labels = new formattingSettings.ToggleSwitch({ name: "labels", displayName: "Group labels", value: true });
    order = new formattingSettings.ItemDropdown({
        name: "order", displayName: "Order of groups and stages",
        items: enumItems(["data", "az", "count"], ["As the data sorts them", "A to Z", "Biggest first"]),
        value: { value: "data", displayName: "As the data sorts them" }
    });
    customOrder = new formattingSettings.TextInput({
        name: "customOrder", displayName: "Custom order (comma list, first)", value: "", placeholder: "Lead, Qualified, Won"
    });
    maxItems = new formattingSettings.NumUpDown({ name: "maxItems", displayName: "Most items drawn", value: 30000 });
    name = "view";
    displayName = "Views";
    slices = [this.initial, this.pills, this.headline, this.labels, this.order, this.customOrder, this.maxItems];
}

export class InteractionCard extends Card {
    tooltips = new formattingSettings.ToggleSwitch({ name: "tooltips", displayName: "Tooltips", value: true });
    brush = new formattingSettings.ToggleSwitch({ name: "brush", displayName: "Drag to select a range", value: true });
    zoom = new formattingSettings.ToggleSwitch({ name: "zoom", displayName: "Zoom and pan", value: true });
    clickMode = new formattingSettings.ItemDropdown({
        name: "clickMode", displayName: "Clicks",
        items: enumItems(["filter", "crossFilter"], ["Filter the page (cards, tables, other pages through sync slicers)", "Cross-highlight this page"]),
        value: { value: "filter", displayName: "Filter the page (cards, tables, other pages through sync slicers)" }
    });
    filterField = new formattingSettings.ItemDropdown({
        name: "filterField", displayName: "Filter on",
        items: enumItems(["Item", "Group", "Stage"], ["Item", "Group", "Stage"]), value: { value: "Item", displayName: "Item" }
    });
    name = "interaction";
    displayName = "Interaction";
    slices = [this.tooltips, this.brush, this.zoom, this.clickMode, this.filterField];
}

export class AppSettings extends Model {
    colors = new ColorsCard();
    fonts = new FontsCard();
    layout = new LayoutCard();
    motion = new MotionCard();
    view = new ViewCard();
    interaction = new InteractionCard();
    cards = [this.colors, this.fonts, this.layout, this.motion, this.view, this.interaction];
}

/** The cards every kit visual has (no Views card): for visuals that aren't unit charts (maps, org charts, 3D). */
export class BaseSettings extends Model {
    colors = new ColorsCard();
    fonts = new FontsCard();
    layout = new LayoutCard();
    motion = new MotionCard();
    interaction = new InteractionCard();
    cards = [this.colors, this.fonts, this.layout, this.motion, this.interaction];
}
