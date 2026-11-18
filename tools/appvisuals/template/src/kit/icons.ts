/*
 *  pbip-kit app-visual template: icons the kit draws itself (24 x 24 grid, stroke paths, no icon pack, no network).
 *  Add an icon by drawing its path on the same grid; keep strokes at 2 and round joins.
 */
export const ICONS: Record<string, string> = {
    back: "M15 5 L8 12 L15 19",
    forward: "M9 5 L16 12 L9 19",
    close: "M6 6 L18 18 M18 6 L6 18",
    grid: "M4 4 H10 V10 H4 Z M14 4 H20 V10 H14 Z M4 14 H10 V20 H4 Z M14 14 H20 V20 H14 Z",
    columns: "M5 20 V9 M12 20 V4 M19 20 V13",
    scatter: "M6 17 h0.01 M10 9 h0.01 M15 13 h0.01 M18 6 h0.01 M4 20 H20 M4 4 V20",
    clusters: "M8 9 m-3 0 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0 M16 8 m-2 0 a2 2 0 1 0 4 0 a2 2 0 1 0 -4 0 M14 16 m-4 0 a4 4 0 1 0 8 0 a4 4 0 1 0 -8 0",
    zoomIn: "M10 10 m-6 0 a6 6 0 1 0 12 0 a6 6 0 1 0 -12 0 M14.5 14.5 L20 20 M10 7 V13 M7 10 H13",
    zoomOut: "M10 10 m-6 0 a6 6 0 1 0 12 0 a6 6 0 1 0 -12 0 M14.5 14.5 L20 20 M7 10 H13",
    reset: "M5 12 a7 7 0 1 0 2 -5 M5 4 V8 H9",
    up: "M6 15 L12 9 L18 15",
    down: "M6 9 L12 15 L18 9",
    dot: "M12 12 m-3 0 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0",
    info: "M12 12 m-9 0 a9 9 0 1 0 18 0 a9 9 0 1 0 -18 0 M12 11 V16 M12 8 h0.01",
    trendUp: "M4 16 L10 10 L14 14 L20 8 M15 8 H20 V13",
    trendDown: "M4 8 L10 14 L14 10 L20 16 M15 16 H20 V11",
    people: "M9 9 m-3 0 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0 M3 20 a6 6 0 0 1 12 0 M16 6 a3 3 0 0 1 0 6 M18 20 a6 6 0 0 0 -3 -5",
    filter: "M4 5 H20 L14 12 V19 L10 17 V12 Z"
};
