// Type declarations for bundled packages that ship none (pbip-kit app-visual template).
declare module "flubber" {
    interface Options { maxSegmentLength?: number; string?: boolean }
    /** Morph one SVG path into another; returns path strings for t from 0 to 1 (flubber, MIT). */
    export function interpolate(from: string, to: string, options?: Options): (t: number) => string;
    export function toCircle(from: string, x: number, y: number, r: number, options?: Options): (t: number) => string;
    export function fromCircle(x: number, y: number, r: number, to: string, options?: Options): (t: number) => string;
    export function toRect(from: string, x: number, y: number, w: number, h: number, options?: Options): (t: number) => string;
}

declare module "topojson-client" {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    export function feature(topology: any, object: any): any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    export function mesh(topology: any, object?: any, filter?: (a: any, b: any) => boolean): any;
}

declare module "d3-flextree" {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    export function flextree(options?: { nodeSize?: (n: any) => [number, number]; spacing?: number | ((a: any, b: any) => number) }): any;
}

declare module "*.json" {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const value: any;
    export default value;
}
