// pbip-kit visual harness runner (Node + Playwright, Chromium, everything local).
//   node run.mjs <scenario.json> <out folder>
// `pbik visual test` runs it with the kit's Node and PBIK_TOOLS_DIR set; it never needs Power BI Desktop.
// The scenario: {kind: "custom"|"deneb", bundle: {js, css, guid} | spec, data, objects, theme, viewport,
// highContrast, reducedMotion, record, steps: [...]} (README.md in this folder lists every step).
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const tools = process.env.PBIK_TOOLS_DIR;
if (!tools) throw new Error("PBIK_TOOLS_DIR is not set (run through `pbik visual test`)");
const req = createRequire(path.join(tools, "package.json"));
const { chromium } = req("playwright");

const [scenarioPath, outDir] = process.argv.slice(2);
const sc = JSON.parse(fs.readFileSync(scenarioPath, "utf8"));
const base = path.dirname(path.resolve(scenarioPath));
const abs = p => (path.isAbsolute(p) ? p : path.join(base, p));
fs.mkdirSync(outDir, { recursive: true });

// ---------------------------------------------------------------- made-up data (deterministic)
function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function generate(g) {
  const r = rng(g.seed || 1);
  const rows = [];
  for (let i = 0; i < g.n; i++) {
    const row = {};
    for (const [f, s] of Object.entries(g.fields)) {
      if (s.id) row[f] = `${s.id}${String(i + 1).padStart(4, "0")}`;
      else if (s.pick) {
        const w = s.weights || s.pick.map(() => 1), tot = w.reduce((a, b) => a + b, 0);
        let x = r() * tot, k = 0;
        while (x > w[k]) { x -= w[k]; k++; }
        row[f] = s.pick[Math.min(k, s.pick.length - 1)];
      } else if (s.uniform) row[f] = Math.round((s.uniform[0] + r() * (s.uniform[1] - s.uniform[0])) * 100) / 100;
      else if (s.normal) {
        const z = Math.sqrt(-2 * Math.log(r() || 1e-9)) * Math.cos(2 * Math.PI * r());
        row[f] = Math.round((s.normal[0] + z * s.normal[1]) * 100) / 100;
      } else if (s.from) row[f] = Math.round(row[s.from] * (s.times || 1) * (1 + ((r() - 0.5) * (s.noise || 0))) * 100) / 100;
    }
    rows.push(row);
  }
  return rows;
}
const data = Object.assign({}, sc.data);
if (data.generate) data.rows = generate(data.generate);
if (data.rowsFile) data.rows = JSON.parse(fs.readFileSync(abs(data.rowsFile), "utf8"));
const theme = sc.theme ? (typeof sc.theme === "string" ? JSON.parse(fs.readFileSync(abs(sc.theme), "utf8")) : sc.theme) : {};

// ---------------------------------------------------------------- run
const marks = {};
const report = { scenario: path.basename(scenarioPath), shots: [], frames: [], checks: [], consoleErrors: [], pageErrors: [], network: [] };
const viewport = sc.viewport || { width: 900, height: 560 };
const pad = 16;

async function runOnce(record) {
  // WebGL in headless Chromium: SwiftShader (software). sc.noWebgl turns WebGL off to test a visual's fallback.
  const browser = await chromium.launch({ args: sc.noWebgl ? ["--disable-webgl", "--disable-3d-apis"]
    : ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctxOpts = { viewport: { width: viewport.width + pad * 2, height: viewport.height + pad * 2 }, deviceScaleFactor: sc.scale || 1,
    hasTouch: !!(sc.mobile || sc.touch), isMobile: !!sc.mobile,
    reducedMotion: sc.reducedMotion ? "reduce" : "no-preference", forcedColors: "none" };
  if (record) ctxOpts.recordVideo = { dir: outDir, size: ctxOpts.viewport };
  const ctx = await browser.newContext(ctxOpts);
  const page = await ctx.newPage();
  // no network: anything other than the local files is blocked and listed (a visual must not call out)
  await page.route("**/*", route => {
    const u = route.request().url();
    if (u.startsWith("file:") || u.startsWith("data:") || u.startsWith("blob:") || u === "about:blank") return route.continue();
    report.network.push(u);
    return route.abort();
  });
  page.on("console", m => { if (m.type() === "error") report.consoleErrors.push(m.text()); });
  page.on("pageerror", e => report.pageErrors.push(String(e)));
  const useClock = sc.kind !== "deneb" && !record && !sc.realtime;
  if (useClock) await page.clock.install({ time: new Date("2026-01-01T00:00:00Z") });
  await page.goto("file://" + path.join(here, "page.html").replace(/\\/g, "/"));
  // installed clocks keep flowing in real time: pause it, so only the scenario's waits move time (exact frames)
  if (useClock) await page.clock.pauseAt(new Date("2026-01-01T00:00:01Z"));
  await page.addScriptTag({ path: path.join(here, "host.js") });
  await page.addScriptTag({ path: path.join(here, "page.js") });

  const tick = async ms => { if (useClock) await page.clock.runFor(ms); else await page.waitForTimeout(record || sc.realtime ? ms : Math.min(ms, 50)); };
  const settle = () => tick(sc.settleMs || 6000);
  const visualBox = async () => page.locator("#harness-visual").boundingBox();

  if (sc.kind === "deneb") {
    for (const f of ["vega/build/vega.min.js", "vega-lite/build/vega-lite.min.js", "vega-embed/build/vega-embed.min.js"]) {
      await page.addScriptTag({ path: path.join(tools, "node_modules", f) });
    }
    const spec = typeof sc.spec === "string" ? JSON.parse(fs.readFileSync(abs(sc.spec), "utf8")) : sc.spec;
    await page.evaluate(cfg => window.harness.loadDeneb(cfg), { data, theme, viewport, spec, deneb: sc.deneb || {}, highContrast: sc.highContrast });
  } else {
    await page.evaluate(() => { window.powerbi = { visuals: { plugins: {} }, extensibility: {} }; });
    await page.addStyleTag({ path: abs(sc.bundle.css) });
    await page.addScriptTag({ path: abs(sc.bundle.js) });
    await page.evaluate(cfg => window.harness.loadVisual(cfg), { guid: sc.bundle.guid, data, objects: sc.objects || {}, theme, viewport,
      highContrast: !!sc.highContrast, window: data.window || 0, allowInteractions: sc.allowInteractions, roundTrip: sc.roundTrip, emptyFirst: sc.emptyFirst });
  }
  await settle();

  const markAt = async i => {
    const ms = await page.evaluate(() => window.harness.marks());
    if (!ms.length) throw new Error("no marks drawn");
    const m = ms[(i + ms.length) % ms.length];
    const b = await visualBox();
    return [b.x + m.x, b.y + m.y];
  };
  const mods = s => (s.ctrl ? ["Control"] : []);
  const shot = async (name, golden) => {
    const f = path.join(outDir, `${name}.png`);
    await page.locator("#harness-visual").screenshot({ path: f });
    report.shots.push(path.basename(f));
    if (golden && sc.goldenDir) await compareGolden(name, f, typeof golden === "number" ? golden : 0.003);
  };
  // visual regression: the shot against its golden (test/golden/<scenario>/<name>.png); new goldens with --update-golden
  const compareGolden = async (name, f, tolerance) => {
    const g = path.join(sc.goldenDir, `${name}.png`);
    if (sc.updateGolden || !fs.existsSync(g)) {
      fs.mkdirSync(sc.goldenDir, { recursive: true });
      fs.copyFileSync(f, g);
      report.goldens = (report.goldens || []).concat(`${name} (${sc.updateGolden ? "updated" : "new"})`);
      return;
    }
    const a = "data:image/png;base64," + fs.readFileSync(f).toString("base64");
    const b = "data:image/png;base64," + fs.readFileSync(g).toString("base64");
    // a separate context: a page opened in the test's context would share (and disturb) its frozen clock
    const cmpCtx = await page.context().browser().newContext();
    const p2 = await cmpCtx.newPage();
    const res = await p2.evaluate(async ([a, b]) => {
      const load = src => new Promise(ok => { const i = new Image(); i.onload = () => ok(i); i.src = src; });
      const [ia, ib] = await Promise.all([load(a), load(b)]);
      if (ia.width !== ib.width || ia.height !== ib.height) return { ratio: 1, size: true, diff: null };
      const c = document.createElement("canvas"); c.width = ia.width; c.height = ia.height;
      const x = c.getContext("2d"); x.drawImage(ia, 0, 0); const da = x.getImageData(0, 0, c.width, c.height);
      x.clearRect(0, 0, c.width, c.height); x.drawImage(ib, 0, 0); const db = x.getImageData(0, 0, c.width, c.height);
      const out = x.createImageData(c.width, c.height); let n = 0;
      for (let i = 0; i < da.data.length; i += 4) {
        const d = Math.max(Math.abs(da.data[i] - db.data[i]), Math.abs(da.data[i + 1] - db.data[i + 1]), Math.abs(da.data[i + 2] - db.data[i + 2]));
        const bad = d > 32; if (bad) n++;
        out.data[i] = bad ? 230 : da.data[i] * 0.3 + 178; out.data[i + 1] = bad ? 30 : da.data[i + 1] * 0.3 + 178; out.data[i + 2] = bad ? 60 : da.data[i + 2] * 0.3 + 178; out.data[i + 3] = 255;
      }
      x.putImageData(out, 0, 0);
      return { ratio: n / (da.data.length / 4), diff: c.toDataURL("image/png") };
    }, [a, b]);
    await cmpCtx.close();
    const ok = res.ratio <= tolerance;
    if (!ok && res.diff) fs.writeFileSync(path.join(outDir, `${name}.diff.png`), Buffer.from(res.diff.split(",")[1], "base64"));
    report.checks.push({ step: name, what: `looks like its golden (${(tolerance * 100).toFixed(1)}% pixels may differ)`, ok,
      got: res.size ? "a different size" : `${(res.ratio * 100).toFixed(2)}% of pixels differ` + (ok ? "" : ` (see ${name}.diff.png)`) });
  };

  for (const s of sc.steps || []) {
    try {
      if (s.shot) await shot(s.shot, s.golden);
      else if (s.bookmark) {
        const [what, name] = s.bookmark.split(" ");
        await page.evaluate(([w, n]) => (w === "save" ? window.harness.saveBookmark(n) : window.harness.applyBookmark(n)), [what, name]);
      }
      else if (s.reopen) await page.evaluate(() => window.harness.reopen());
      else if (s.click3d || s.hover3d) {
        const xy = await page.evaluate(n => document.querySelector("#harness-visual .kit-root").kitProject(n), s.click3d || s.hover3d);
        if (!xy) throw new Error(`no 3D object called ${s.click3d || s.hover3d}`);
        const b = await visualBox();
        if (s.click3d) await page.mouse.click(b.x + xy[0], b.y + xy[1], { modifiers: mods(s) });
        else await page.mouse.move(b.x + xy[0], b.y + xy[1]);
      }
      else if (s.profile) {
        // where the time goes while a click plays out: Chrome's sampling profiler, top functions by own time
        // ({"profile": {"clickText": "Tree"}, "ms": 1500}; report.json `profile`, with "(program)" and "(garbage
        // collector)" for the browser's own work)
        const cdp = await page.context().newCDPSession(page);
        await cdp.send("Profiler.enable");
        await cdp.send("Profiler.setSamplingInterval", { interval: 250 });
        await cdp.send("Profiler.start");
        const inner = s.profile, b = await visualBox();
        if (inner.click3d) { const xy = await page.evaluate(n => document.querySelector("#harness-visual .kit-root").kitProject(n), inner.click3d); await page.mouse.click(b.x + xy[0], b.y + xy[1]); }
        else if (inner.clickText) await page.locator("#harness-visual").getByText(inner.clickText, { exact: true }).first().click();
        await page.waitForTimeout(s.ms || 1500);
        const { profile } = await cdp.send("Profiler.stop");
        const dt = profile.timeDeltas.reduce((a, x) => a + x, 0) / Math.max(1, profile.samples.length) / 1000;
        const by = new Map();
        for (const n of profile.nodes) {
          const f = n.callFrame, key = `${f.functionName || "(anonymous)"} ${f.url ? f.url.split("/").pop() : ""}:${f.lineNumber + 1}`;
          by.set(key, (by.get(key) || 0) + n.hitCount * dt);
        }
        report.profile = (report.profile || []).concat({ what: JSON.stringify(inner), top: [...by].sort((x, y) => y[1] - x[1]).slice(0, 14).map(([k, v]) => [k, Math.round(v)]) });
        await cdp.detach();
      }
      else if (s.transition) {
        // a screen change frame by frame (frozen clock): how much the visual paints at each step ("ink": the area of
        // every drawn shape and text, times its effective opacity). A blank frame is ink falling far below both the
        // screen before and the screen after ({"transition": {"clickText": "North"}, "name": "open", "ms": 700, "every": 25})
        const ink = () => page.evaluate(() => {
          const root = document.querySelector("#harness-visual .kit-root");
          if (!root) return 0;
          const R = root.getBoundingClientRect();
          let sum = 0;
          const op = el => { let o = 1; for (let e = el; e && e !== root.parentElement; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.visibility === "hidden" || cs.display === "none") return 0; o *= Number(cs.opacity || 1); } return o; };
          root.querySelectorAll("*").forEach(el => {
            const cs = getComputedStyle(el);
            let paints = false;
            if (el instanceof SVGGraphicsElement && !(el instanceof SVGGElement) && !(el instanceof SVGSVGElement)) paints = cs.fill !== "none" || cs.stroke !== "none";
            else if (!(el instanceof SVGElement)) paints = (cs.backgroundColor && cs.backgroundColor !== "rgba(0, 0, 0, 0)") || [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
            if (!paints) return;
            const r = el.getBoundingClientRect();
            const w = Math.max(0, Math.min(r.right, R.right) - Math.max(r.left, R.left)), h = Math.max(0, Math.min(r.bottom, R.bottom) - Math.max(r.top, R.top));
            sum += w * h * op(el);
          });
          return Math.round(sum);
        });
        const t = s.transition, start = await ink(), b = await visualBox(), samples = [];
        if (t.click3d) { const xy = await page.evaluate(n => document.querySelector("#harness-visual .kit-root").kitProject(n), t.click3d); await page.mouse.click(b.x + xy[0], b.y + xy[1]); }
        else if (t.clickText) await page.locator("#harness-visual").getByText(t.clickText, { exact: true }).first().click();
        else if (t.clickSelector) await page.locator(`#harness-visual ${t.clickSelector}`).nth(t.index || 0).click({ force: true });
        for (let ms = 0; ms < (s.ms || 700); ms += (s.every || 25)) { await tick(s.every || 25); samples.push(await ink()); }
        const end = samples.at(-1) ?? start, low = Math.min(...samples);
        report.transitions = (report.transitions || []).concat({ name: s.name || JSON.stringify(t), start, end, low, ratio: Math.round(low / Math.max(1, Math.min(start, end)) * 100) / 100, samples });
      }
      else if (s.markMoves) {
        marks[s.markMoves] = await page.evaluate(() => { const r = document.querySelector("#harness-visual .kit-root"); return r && r.kitMoves ? r.kitMoves() : 0; });
      }
      else if (s.measure) {
        // any visual: frames drawn and frame gaps while a click plays out in real time ({"measure": {"click3d": "Site 05"}
        // or {"clickText": "Back"}, "ms": 1200}); the same numbers as `perf`, so a before / after needs no debug hook
        await page.evaluate(() => {
          const root = document.querySelector("#harness-visual .kit-root");
          const m = window.__measure = { gaps: [], t0: performance.now(), f0: root && root.kitFrames ? root.kitFrames() : 0, stop: false };
          let last = m.t0;
          const loop = () => { const n = performance.now(); m.gaps.push(n - last); last = n; if (!m.stop) requestAnimationFrame(loop); };
          requestAnimationFrame(loop);
        });
        const inner = s.measure, b = await visualBox();
        if (inner.click3d) { const xy = await page.evaluate(n => document.querySelector("#harness-visual .kit-root").kitProject(n), inner.click3d); await page.mouse.click(b.x + xy[0], b.y + xy[1]); }
        else if (inner.clickText) await page.locator("#harness-visual").getByText(inner.clickText, { exact: true }).first().click();
        else if (inner.clickSelector) await page.locator(`#harness-visual ${inner.clickSelector}`).nth(inner.index || 0).click({ force: true });
        await page.waitForTimeout(s.ms || 1200);
        const got = await page.evaluate(() => {
          const m = window.__measure, root = document.querySelector("#harness-visual .kit-root");
          m.stop = true;
          const secs = (performance.now() - m.t0) / 1000, gaps = m.gaps.slice(1);
          return { fps: Math.round(((root && root.kitFrames ? root.kitFrames() : 0) - m.f0) / secs), slow: Math.round(gaps.filter(g => g > 50).length / Math.max(1, gaps.length) * 100) / 100, worst: Math.round(Math.max(0, ...gaps)) };
        });
        report.perf = (report.perf || []).concat({ ms: s.ms || 1200, mode: JSON.stringify(inner), ...got });
      }
      else if (s.perf) {
        // the visual drives its own motion (`mode`: orbit, fly...) and answers frames a second, or {fps, slow, worst}:
        // slow = the share of frames over 50 ms (what looks frozen), worst = the longest frame in ms
        const got = await page.evaluate(([ms, mode]) => document.querySelector("#harness-visual .kit-root").kitPerf(ms, mode), [s.perf, s.mode || "orbit"]);
        report.perf = (report.perf || []).concat({ ms: s.perf, mode: s.mode || "orbit", ...(typeof got === "number" ? { fps: got } : got) });
      }
      else if (s.tap) { const b = await visualBox(); await page.touchscreen.tap(b.x + s.tap[0], b.y + s.tap[1]); }
      else if (s.tapText) { const bb = await page.locator("#harness-visual").getByText(s.tapText, { exact: true }).first().boundingBox(); await page.touchscreen.tap(bb.x + bb.width / 2, bb.y + bb.height / 2); }
      else if (s.swipe) {
        const b = await visualBox();
        await page.evaluate(([x0, y0, x1, y1]) => {
          const t = document.elementFromPoint(x0, y0) || document.body;
          const ev = (type, x, y) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, pointerType: "touch", isPrimary: true, clientX: x, clientY: y, pointerId: 7 }));
          ev("pointerdown", x0, y0); ev("pointermove", (x0 + x1) / 2, (y0 + y1) / 2); ev("pointerup", x1, y1);
        }, [b.x + s.swipe.from[0], b.y + s.swipe.from[1], b.x + s.swipe.to[0], b.y + s.swipe.to[1]]);
      }
      else if (s.pinch) {
        const b = await visualBox();
        await page.evaluate(([cx, cy, scale]) => {
          const t = document.querySelector("#harness-visual .kit-svg");
          const touches = d => [new Touch({ identifier: 1, target: t, clientX: cx - d, clientY: cy }), new Touch({ identifier: 2, target: t, clientX: cx + d, clientY: cy })];
          const fire = (type, list) => t.dispatchEvent(new TouchEvent(type, { bubbles: true, cancelable: true, touches: type === "touchend" ? [] : list, targetTouches: type === "touchend" ? [] : list, changedTouches: list }));
          fire("touchstart", touches(30));
          for (let i = 1; i <= 6; i++) fire("touchmove", touches(30 + (scale - 1) * 30 * i / 6));
          fire("touchend", touches(30 * scale));
        }, [b.x + s.pinch.at[0], b.y + s.pinch.at[1], s.pinch.scale || 2]);
      }
      else if (s.wait != null) await tick(s.wait);
      else if (s.settle) await settle();
      else if (s.pill) { await page.getByRole("tab", { name: s.pill }).click(); }
      else if (s.clickText) { await page.locator("#harness-visual").getByText(s.clickText, { exact: true }).first().click({ modifiers: mods(s) }); }
      else if (s.clickMark != null) { const [x, y] = await markAt(s.clickMark); await page.mouse.move(x, y); for (const k of mods(s)) await page.keyboard.down(k); await page.mouse.click(x, y); for (const k of mods(s)) await page.keyboard.up(k); }
      else if (s.dblclickMark != null) { const [x, y] = await markAt(s.dblclickMark); await page.mouse.dblclick(x, y); }
      else if (s.contextMark != null) { const [x, y] = await markAt(s.contextMark); await page.mouse.click(x, y, { button: "right" }); }
      else if (s.hoverMark != null) { const [x, y] = await markAt(s.hoverMark); await page.mouse.move(x, y); }
      else if (s.click) { const b = await visualBox(); await page.mouse.click(b.x + s.click[0], b.y + s.click[1], { modifiers: mods(s) }); }
      else if (s.dblclick) { const b = await visualBox(); await page.mouse.dblclick(b.x + s.dblclick[0], b.y + s.dblclick[1]); }
      else if (s.drag) {
        const b = await visualBox();
        await page.mouse.move(b.x + s.drag.from[0], b.y + s.drag.from[1]);
        await page.mouse.down();
        await page.mouse.move(b.x + s.drag.to[0], b.y + s.drag.to[1], { steps: 8 });
        await page.mouse.up();
      }
      else if (s.focus) { await page.locator(`#harness-visual ${s.focus}`).first().focus(); }
      else if (s.key) { for (let i = 0; i < (s.times || 1); i++) await page.keyboard.press(s.key); }
      else if (s.objects !== undefined) await page.evaluate(o => window.harness.setObjects(o), s.objects);
      else if (s.filter !== undefined) await page.evaluate(([c, d]) => (d ? window.harness.filterDeneb(c) : window.harness.filter(c)), [s.filter, sc.kind === "deneb"]);
      else if (s.clickSelector) { await page.locator(`#harness-visual ${s.clickSelector}`).nth(s.index || 0).click({ modifiers: mods(s), force: true }); }
      else if (s.highlight !== undefined) await page.evaluate(c => window.harness.highlight(c), s.highlight);
      else if (s.resize) await page.evaluate(([w, h]) => window.harness.resize(w, h), s.resize);
      else if (s.frames) {
        const names = [];
        for (let i = 0; i < s.frames.count; i++) {
          const n = `${s.frames.name}-${String(i).padStart(2, "0")}`;
          await shot(n);
          names.push(`${n}.png`);
          await tick(s.frames.every);
        }
        report.frames.push({ name: s.frames.name, files: names });
      }
      else if (s.probe) { report.probes = report.probes || []; report.probes.push({ label: s.label || "", expr: s.probe, value: await page.evaluate(s.probe) }); }
      else if (s.expect) {
        const log = await page.evaluate(() => window.harness.log());
        const e = s.expect, res = [];
        if (e.selectCalls != null) res.push([`select calls = ${e.selectCalls}`, log.select.length === e.selectCalls, log.select.length]);
        if (e.minSelectCalls != null) res.push([`select calls >= ${e.minSelectCalls}`, log.select.length >= e.minSelectCalls, log.select.length]);
        if (e.lastMulti != null) res.push([`last select multi = ${e.lastMulti}`, !!(log.select.at(-1) || {}).multi === e.lastMulti, log.select.at(-1)]);
        if (e.lastSelectCount != null) res.push([`last select has ${e.lastSelectCount} item(s)`, ((log.select.at(-1) || {}).keys || []).length === e.lastSelectCount, ((log.select.at(-1) || {}).keys || []).length]);
        if (e.clears != null) res.push([`clear calls >= ${e.clears}`, log.clear >= e.clears, log.clear]);
        if (e.contextMenus != null) res.push([`context menus >= ${e.contextMenus}`, log.contextMenu.length >= e.contextMenus, log.contextMenu.length]);
        if (e.tooltips != null) res.push([`tooltips shown >= ${e.tooltips}`, log.tooltips >= e.tooltips, log.tooltips]);
        if (e.fetchMore != null) res.push([`fetch-more calls >= ${e.fetchMore}`, log.fetchMore >= e.fetchMore, log.fetchMore]);
        if (e.marks != null) { const n = (await page.evaluate(() => window.harness.marks())).length; res.push([`marks = ${e.marks}`, n === e.marks, n]); }
        if (e.text) { const t = await page.locator("#harness-visual").innerText(); res.push([`text contains "${e.text}"`, t.includes(e.text), t.slice(0, 160)]); }
        if (e.noRenderFailures) res.push(["no rendering failures", !log.rendering.failed.length, log.rendering.failed]);
        if (e.renderEvents) res.push(["rendering started and finished events", log.rendering.started > 0 && log.rendering.finished > 0, log.rendering]);
        if (e.persisted) { const st = Object.assign({}, ...(log.persist || []).flatMap(c => (c.merge || []).map(m => m.properties))); res.push([`saved state has ${JSON.stringify(e.persisted)}`, Object.entries(e.persisted).every(([k, v]) => String(st[k]) === String(v)), st]); }
        if (e.filterValues) { const f = (log.filters || []).at(-1) || {}; res.push([`filter values ${JSON.stringify(e.filterValues)}`, JSON.stringify(f.values || []) === JSON.stringify(e.filterValues), f]); }
        if (e.pill) { const on = await page.evaluate(() => (document.querySelector("#harness-visual .kit-pill.is-on") || {}).textContent || ""); res.push([`pill on: ${e.pill}`, on.trim() === e.pill, on]); }
        if (e.lastFilterSize != null) { const f = (log.filters || []).at(-1) || {}; res.push([`last filter has ${e.lastFilterSize} value(s)`, (f.values || []).length === e.lastFilterSize, f]); }
        if (e.selectorText) for (const [css, want] of Object.entries(e.selectorText)) { const got = await page.evaluate(c => Array.from(document.querySelectorAll(`#harness-visual ${c}`)).map(n => n.textContent.trim()), css); res.push([`${css} shows "${want}"`, got.length === 1 && got[0].includes(want), got]); }
        if (e.tooltipFields) { const got = log.lastTooltip || []; res.push([`tooltip fields ${JSON.stringify(e.tooltipFields)}`, JSON.stringify(got) === JSON.stringify(e.tooltipFields), got]); }
        if (e.state) { const st = await page.evaluate(() => { const r = document.querySelector("#harness-visual .kit-root"); return r && r.kitState ? r.kitState() : {}; }); for (const [k, v] of Object.entries(e.state)) res.push([`state ${k} = ${JSON.stringify(v)}`, JSON.stringify(st[k]) === JSON.stringify(v), st[k]]); }
        if (e.noOverlap) {
          // the header (headline text, each item of the Back / pills row), panels and visible labels: no two overlap
          const hits = await page.evaluate(() => {
            const root = document.querySelector("#harness-visual .kit-root");
            const boxes = [];
            const add = (name, r) => { if (r && r.width > 1 && r.height > 1) boxes.push({ name, l: r.left, t: r.top, r: r.right, b: r.bottom }); };
            const head = root.querySelector(".kit-headline");
            if (head && head.textContent.trim()) { const rg = document.createRange(); rg.selectNodeContents(head); add("headline", rg.getBoundingClientRect()); }
            root.querySelectorAll(".kit-top > *").forEach((el, i) => add(`top row ${el.className || el.tagName} ${i}`, el.getBoundingClientRect()));
            root.querySelectorAll(".kit-card, .kit-detail3d").forEach((el, i) => { if (getComputedStyle(el).display !== "none") add(`panel ${i}`, el.getBoundingClientRect()); });
            const cut = Math.max(0, ...boxes.map(b => b.b));
            root.querySelectorAll("svg text, .kit-label3d").forEach(el => {
              const cs = getComputedStyle(el);
              if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0 || !el.textContent.trim()) return;
              const r = el.getBoundingClientRect();
              const layer = el.closest(".kit-layer");
              const clip = layer ? (getComputedStyle(layer).clipPath.match(/inset\((\d+)/) || [])[1] : null;
              if (clip && r.bottom <= layer.getBoundingClientRect().top + Number(clip)) return;     // clipped away under the header
              add(`label "${el.textContent.trim().slice(0, 24)}"`, r);
            });
            const out = [];
            for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
              const a = boxes[i], b = boxes[j];
              const inside = (x, y) => x.l >= y.l && x.r <= y.r && x.t >= y.t && x.b <= y.b;
              if (inside(a, b) || inside(b, a)) continue;          // a label on a panel it belongs to
              if (Math.min(a.r, b.r) - Math.max(a.l, b.l) > 1 && Math.min(a.b, b.b) - Math.max(a.t, b.t) > 1) out.push(`${a.name} / ${b.name}`);
            }
            return out;
          });
          res.push(["no overlapping header, panels or labels", !hits.length, hits.slice(0, 6)]);
        }
        if (e.minTextPx) {
          // every visible text, at the size it is drawn (its font size times the zoom of the SVG group it sits in)
          const small = await page.evaluate(() => {
            const out = [];
            document.querySelectorAll("#harness-visual .kit-root text, #harness-visual .kit-root .kit-html *").forEach(el => {
              if (!el.textContent.trim() || (el.children.length && el.tagName !== "text")) return;
              const cs = getComputedStyle(el);
              if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0 || Number(el.getAttribute("opacity") ?? 1) === 0) return;
              const r = el.getBoundingClientRect();
              if (r.width < 1 || r.height < 1) return;
              const k = el.getScreenCTM ? Math.hypot(el.getScreenCTM().a, el.getScreenCTM().b) : 1;
              out.push([el.textContent.trim().slice(0, 20), Math.round(parseFloat(cs.fontSize) * k * 10) / 10]);
            });
            return out;
          });
          const tooSmall = small.filter(([, px]) => px < e.minTextPx);
          res.push([`all text at least ${e.minTextPx} px`, !tooSmall.length, tooSmall.slice(0, 6).concat([[`${small.length} texts`, Math.min(...small.map(x => x[1]))]])]);
        }
        if (e.smooth) {
          // the last `perf` / `measure` result: no frame over e.smooth.longest ms and under e.smooth.frozen % frozen
          const m = (report.perf || []).at(-1) || {};
          const lim = e.smooth;
          res.push([`smooth: longest <= ${lim.longest} ms, frozen < ${lim.frozen}%`, m.worst <= lim.longest && (m.slow || 0) * 100 < lim.frozen, m]);
        }
        if (e.noBlank) {
          // the named transition never painted less than `minInk` (default 0.6) of the smaller of the screens it joins
          const tr = (report.transitions || []).find(x => x.name === e.noBlank) || {};
          const min = e.minInk ?? 0.6;
          res.push([`no blank frame in ${e.noBlank} (lowest ink at least ${min} of the screens it joins)`, tr.ratio >= min, tr]);
        }
        if (e.movesSince) {
          // no morph or entrance since the mark (a filter round trip must not replay the screen)
          const now = await page.evaluate(() => { const r = document.querySelector("#harness-visual .kit-root"); return r && r.kitMoves ? r.kitMoves() : 0; });
          const was = marks[e.movesSince.mark] ?? 0, max = e.movesSince.max ?? 0;
          res.push([`at most ${max} moves since ${e.movesSince.mark}`, now - was <= max, { was, now }]);
        }
        if (e.filterRemoved) { const f = (log.filters || []).at(-1) || {}; res.push(["filter removed", f.action === 1, f]); }
        if (e.camera) { const cam = await page.evaluate(() => { const r = document.querySelector("#harness-visual .kit-marks"); return r ? r.getAttribute("transform") : ""; }); res.push([`camera ${e.camera}`, e.camera === "zoomed" ? !/scale\(1\)$/.test(cam || "") : /scale\(1\)$/.test(cam || ""), cam]); }
        if (e.ariaLabels) { const n = await page.evaluate(() => document.querySelectorAll("#harness-visual circle.kit-mark[aria-label]").length); res.push([`marks with screen-reader labels >= ${e.ariaLabels}`, n >= e.ariaLabels, n]); }
        for (const [what, ok, got] of res) report.checks.push({ step: s.label || "", what, ok, got });
      }
    } catch (err) {
      report.checks.push({ step: s.label || JSON.stringify(s).slice(0, 60), what: "step ran", ok: false, got: String(err).slice(0, 300) });
    }
  }
  report.log = await page.evaluate(() => window.harness.log());
  if (record) {
    const v = page.video();
    await ctx.close();
    if (v) {                                        // name the video after the scenario
      const to = path.join(outDir, path.basename(scenarioPath).replace(/^_/, "").replace(/\.json$/, "") + ".webm");
      fs.renameSync(await v.path(), to);
      report.video = path.basename(to);
    }
  }
  else await ctx.close();
  // frame strips: each frames step as one image, left to right
  if (!record && report.frames.length) {
    const b2 = await chromium.launch();
    const p2 = await b2.newPage({ viewport: { width: 400, height: 300 } });
    for (const fr of report.frames) {
      const imgs = fr.files.map(f => `<img src="data:image/png;base64,${fs.readFileSync(path.join(outDir, f)).toString("base64")}" style="width:${Math.round(viewport.width / 2)}px;border:1px solid #ddd;margin:2px">`).join("");
      await p2.setContent(`<body style="margin:0;background:#fff"><div id="s" style="display:flex;flex-wrap:wrap;width:${Math.round(viewport.width / 2 + 6) * 3}px">${imgs}</div></body>`);
      await p2.waitForTimeout(150);
      const f = path.join(outDir, `${fr.name}-strip.png`);
      await p2.locator("#s").screenshot({ path: f });
      fr.strip = path.basename(f);
    }
    await b2.close();
  }
  await browser.close();
}

await runOnce(false);
if (sc.record) await runOnce(true);
report.checks.push({ what: "no page errors", ok: !report.pageErrors.length, got: report.pageErrors.slice(0, 5) });
report.checks.push({ what: "no network requests", ok: !report.network.length, got: report.network.slice(0, 5) });
report.ok = report.checks.every(c => c.ok);
fs.writeFileSync(path.join(outDir, "report.json"), JSON.stringify(report, null, 1));
console.log(`${report.ok ? "PASS" : "FAIL"} ${report.checks.filter(c => c.ok).length}/${report.checks.length} checks, ${report.shots.length} screenshot(s)` + (report.video ? `, video ${report.video}` : ""));
for (const c of report.checks.filter(c => !c.ok)) console.log(`  failed: ${c.step ? c.step + ": " : ""}${c.what} (got ${JSON.stringify(c.got)})`);
process.exit(report.ok ? 0 : 1);
