/*
 *  pbip-kit app-visual template: drawing layers.
 *  One visual stacks a WebGL canvas, a 2D canvas, an SVG layer and an HTML layer, back to front. Marks pick their
 *  renderer by count (SVG for a few hundred: crisp and inspectable; Canvas for thousands; WebGL for tens of
 *  thousands); text, focus rings and anything a screen reader needs stay in SVG or HTML. A shared camera (zoom and
 *  pan) applies to every mark layer.
 */
import { select, Selection } from "d3-selection";
import { Mark } from "./motion";

export interface Camera {
    k: number;
    x: number;
    y: number;
}

export type RendererKind = "svg" | "canvas" | "webgl";

export interface MarkRenderer {
    kind: RendererKind;
    draw(marks: Mark[], camera: Camera): void;
    clear(): void;
}

export class Layers {
    readonly root: Selection<HTMLDivElement, unknown, null, undefined>;
    readonly gl: HTMLCanvasElement;
    readonly canvas: HTMLCanvasElement;
    readonly svg: Selection<SVGSVGElement, unknown, null, undefined>;
    readonly marksG: Selection<SVGGElement, unknown, null, undefined>;
    readonly overlay: Selection<SVGGElement, unknown, null, undefined>;
    readonly html: Selection<HTMLDivElement, unknown, null, undefined>;
    width = 0;
    height = 0;
    ratio = 1;
    /** The quality tier's cap on device pixels per CSS pixel (quality.ts); 3 = full. */
    maxRatio = 3;
    /**
     * The safe area: what the visual's own header, docked panels and legends cover (px from each edge). Camera
     * framing (Interaction.fit) centres in what is left, so a framed item never sits under a panel.
     */
    insets = { top: 0, right: 0, bottom: 0, left: 0 };

    constructor(host: HTMLElement) {
        this.root = select(host).append("div").classed("kit-root", true);
        this.gl = this.root.append("canvas").classed("kit-layer kit-gl", true).attr("aria-hidden", "true").node();
        this.canvas = this.root.append("canvas").classed("kit-layer kit-canvas", true).attr("aria-hidden", "true").node();
        this.svg = this.root.append("svg").classed("kit-layer kit-svg", true);
        this.marksG = this.svg.append("g").classed("kit-marks", true);
        this.overlay = this.svg.append("g").classed("kit-overlay", true);
        this.html = this.root.append("div").classed("kit-layer kit-html", true);
    }

    /**
     * Draw only below `top` (the visual's own header: headline, Back, pills): every drawing layer is clipped, so a
     * zoomed map or a flown camera never slides under the header text, and clicks up there reach the header.
     */
    clipTop(top: number): void {
        const clip = top > 0 ? `inset(${Math.round(top)}px 0 0 0)` : "";
        for (const el of [this.svg.node() as unknown as HTMLElement, this.canvas, this.gl] as HTMLElement[]) {
            if (el) {
                el.style.clipPath = clip;
            }
        }
    }

    resize(width: number, height: number): void {
        this.width = Math.max(0, Math.floor(width));
        this.height = Math.max(0, Math.floor(height));
        this.ratio = Math.min(this.maxRatio, window.devicePixelRatio || 1);
        for (const c of [this.gl, this.canvas]) {
            const w = Math.floor(this.width * this.ratio), h = Math.floor(this.height * this.ratio);
            if (c.width !== w || c.height !== h) {     // setting a canvas size wipes it (and a WebGL one reallocates):
                c.width = w;                          // only on a real resize, never on every update (Desktop review
                c.height = h;                         // 2026-11-17: the 3D canvas was wiped mid-flight by each update)
            }
            c.style.width = `${this.width}px`;
            c.style.height = `${this.height}px`;
        }
        this.root.style("width", `${this.width}px`).style("height", `${this.height}px`);
        this.svg.attr("width", this.width).attr("height", this.height);
    }
}

export class SvgMarks implements MarkRenderer {
    kind: RendererKind = "svg";
    constructor(private layers: Layers) { }
    draw(marks: Mark[], cam: Camera): void {
        this.layers.marksG.attr("transform", `translate(${cam.x},${cam.y}) scale(${cam.k})`);
        this.layers.marksG.selectAll<SVGCircleElement, Mark>("circle.kit-mark")
            .data(marks, d => d.key)
            .join("circle")
            .classed("kit-mark", true)
            .attr("cx", d => d.x)
            .attr("cy", d => d.y)
            .attr("r", d => (d.shape === "ring" ? Math.max(0, d.r - 1 / cam.k) : d.r))
            .attr("fill", d => (d.shape === "ring" ? "none" : d.color))
            .attr("fill-opacity", d => d.alpha)
            .attr("stroke", d => (d.shape === "ring" ? d.color : d.stroke || null))
            .attr("stroke-opacity", d => (d.shape === "ring" ? d.alpha : null))
            .attr("stroke-width", d => (d.shape === "ring" ? 2 / cam.k : d.stroke ? 1.5 / cam.k : null));
    }
    clear(): void {
        this.layers.marksG.selectAll("circle.kit-mark").remove();
    }
}

export class CanvasMarks implements MarkRenderer {
    kind: RendererKind = "canvas";
    constructor(private layers: Layers) { }
    draw(marks: Mark[], cam: Camera): void {
        const ctx = this.layers.canvas.getContext("2d");
        const r = this.layers.ratio;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, this.layers.canvas.width, this.layers.canvas.height);
        ctx.setTransform(r * cam.k, 0, 0, r * cam.k, r * cam.x, r * cam.y);
        for (const m of marks) {
            if (m.r <= 0 || m.alpha <= 0) {
                continue;
            }
            ctx.globalAlpha = m.alpha;
            ctx.beginPath();
            if (m.shape === "ring") {                           // hollow: shape carries the meaning, not colour alone
                ctx.arc(m.x, m.y, Math.max(0, m.r - 1 / cam.k), 0, Math.PI * 2);
                ctx.lineWidth = 2 / cam.k;
                ctx.strokeStyle = m.color;
                ctx.stroke();
                continue;
            }
            ctx.fillStyle = m.color;
            ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2);
            ctx.fill();
            if (m.stroke) {
                ctx.globalAlpha = 1;
                ctx.lineWidth = 1.5 / cam.k;
                ctx.strokeStyle = m.stroke;
                ctx.stroke();
            }
        }
        ctx.globalAlpha = 1;
    }
    clear(): void {
        const ctx = this.layers.canvas.getContext("2d");
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, this.layers.canvas.width, this.layers.canvas.height);
    }
}

const VS = `attribute vec2 p; attribute float s; attribute vec4 c; attribute float h; uniform vec2 v; uniform vec3 cam; uniform float ratio;
varying vec4 vc; varying float vh; varying float vpx; void main(){ vec2 q = (p * cam.x + cam.yz) / v * 2.0 - 1.0; gl_Position = vec4(q.x, -q.y, 0.0, 1.0);
gl_PointSize = s * 2.0 * cam.x * ratio; vc = c; vh = h; vpx = gl_PointSize; }`;
const FS = `precision mediump float; varying vec4 vc; varying float vh; varying float vpx; void main(){ vec2 d = gl_PointCoord - 0.5;
float r2 = dot(d, d); if (r2 > 0.25) discard; if (vh > 0.5) { float inner = 0.5 - 2.0 / max(vpx, 4.0); if (r2 < inner * inner) discard; }
gl_FragColor = vec4(vc.rgb * vc.a, vc.a); }`;

function rgba(color: string, alpha: number): [number, number, number, number] {
    const m = /^#?([0-9a-f]{6})$/i.exec(color.trim());
    if (m) {
        const n = parseInt(m[1], 16);
        return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255, alpha];
    }
    const r = /rgba?\(([^)]+)\)/.exec(color);
    if (r) {
        const p = r[1].split(",").map(x => parseFloat(x));
        return [p[0] / 255, p[1] / 255, p[2] / 255, alpha * (p.length > 3 ? p[3] : 1)];
    }
    return [0.5, 0.5, 0.5, alpha];
}

/** Points with WebGL 1 (no extensions): tens of thousands of animated marks. Falls back to Canvas if unavailable. */
export class GlMarks implements MarkRenderer {
    kind: RendererKind = "webgl";
    private ctx: WebGLRenderingContext | null;
    private prog: WebGLProgram | null = null;
    private buf: WebGLBuffer | null = null;

    constructor(private layers: Layers) {
        this.ctx = layers.gl.getContext("webgl", { premultipliedAlpha: true, antialias: true }) as WebGLRenderingContext | null;
        if (this.ctx) {
            this.prog = this.program(this.ctx);
            this.buf = this.ctx.createBuffer();
        }
    }

    get available(): boolean {
        return !!(this.ctx && this.prog);
    }

    private program(gl: WebGLRenderingContext): WebGLProgram | null {
        const sh = (type: number, src: string) => {
            const s = gl.createShader(type);
            gl.shaderSource(s, src);
            gl.compileShader(s);
            return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
        };
        const v = sh(gl.VERTEX_SHADER, VS), f = sh(gl.FRAGMENT_SHADER, FS);
        if (!v || !f) {
            return null;
        }
        const p = gl.createProgram();
        gl.attachShader(p, v);
        gl.attachShader(p, f);
        gl.linkProgram(p);
        return gl.getProgramParameter(p, gl.LINK_STATUS) ? p : null;
    }

    draw(marks: Mark[], cam: Camera): void {
        const gl = this.ctx;
        if (!gl || !this.prog) {
            return;
        }
        gl.viewport(0, 0, this.layers.gl.width, this.layers.gl.height);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        const data = new Float32Array(marks.length * 8);
        marks.forEach((m, i) => {
            const c = rgba(m.color, m.alpha);
            data.set([m.x, m.y, m.r, c[0], c[1], c[2], c[3], m.shape === "ring" ? 1 : 0], i * 8);
        });
        gl.useProgram(this.prog);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
        gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW);
        const at = (name: string, size: number, offset: number) => {
            const loc = gl.getAttribLocation(this.prog, name);
            gl.enableVertexAttribArray(loc);
            gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 32, offset);
        };
        at("p", 2, 0);
        at("s", 1, 8);
        at("c", 4, 12);
        at("h", 1, 28);
        gl.uniform2f(gl.getUniformLocation(this.prog, "v"), this.layers.width, this.layers.height);
        gl.uniform3f(gl.getUniformLocation(this.prog, "cam"), cam.k, cam.x, cam.y);
        gl.uniform1f(gl.getUniformLocation(this.prog, "ratio"), this.layers.ratio);
        gl.drawArrays(gl.POINTS, 0, marks.length);
    }

    clear(): void {
        const gl = this.ctx;
        if (gl) {
            gl.clearColor(0, 0, 0, 0);
            gl.clear(gl.COLOR_BUFFER_BIT);
        }
    }
}

/** Pick the renderer for a mark count: SVG up to svgMax, Canvas up to canvasMax, WebGL above (Canvas if no WebGL). */
export class MarkLayer {
    private svg: SvgMarks;
    private canvas: CanvasMarks;
    private glr: GlMarks | null = null;
    active: MarkRenderer;

    constructor(private layers: Layers, public svgMax = 600, public canvasMax = 8000) {
        this.svg = new SvgMarks(layers);
        this.canvas = new CanvasMarks(layers);
        this.active = this.svg;
    }

    choose(count: number, force?: RendererKind): MarkRenderer {
        let want: RendererKind = force || (count <= this.svgMax ? "svg" : count <= this.canvasMax ? "canvas" : "webgl");
        if (want === "webgl") {
            this.glr = this.glr || new GlMarks(this.layers);
            if (!this.glr.available) {
                want = "canvas";
            }
        }
        const next = want === "svg" ? this.svg : want === "canvas" ? this.canvas : this.glr;
        if (next !== this.active) {
            this.active.clear();
            this.active = next;
        }
        return this.active;
    }
}
