"""Headless Edge for pages the kit draws: the DOM after the page's scripts ran, and screenshots.

    import edge_page
    html = edge_page.dom(page_text)                     the rendered DOM of a page (scripts included)
    edge_page.screenshot(page_text, out_png, 1920, 1080)

Edge 156 returns from `--dump-dom` before it has printed anything and leaves its headless processes running (the same
change that broke `--screenshot`, VERSIONS.md 2026-10-23). So dom() serves the page from a local server on 127.0.0.1,
the page posts its own DOM back once it is drawn (after `window.pageReady`, a promise the page may set, e.g. while
Vega-Lite renders), and the Edge processes started with this call's own profile are stopped afterwards. Nothing
leaves the machine except what the page itself loads (the wireframe's pinned Vega-Lite scripts, when online).
screenshot() uses Edge's --screenshot and waits for a complete PNG (svg_to_png.wait_for_png).
"""
import http.server, os, pathlib, shutil, subprocess, sys, tempfile, threading

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import svg_to_png  # noqa: E402

EDGE = svg_to_png.EDGE
WAIT = float(os.environ.get("EDGE_WAIT", "30"))
POST_BACK = """<script>(function () {
  function post() { fetch('/dump', {method: 'POST', body: document.documentElement.outerHTML}); }
  window.addEventListener('load', function () { setTimeout(function () {
    Promise.resolve(window.pageReady).catch(function () {}).then(function () { setTimeout(post, 50); }); }, %d); });
})();</script>"""


def available():
    return pathlib.Path(EDGE).exists()


def _serve(page):
    """A local server for one page: GET / returns it, POST /dump stores the body. Returns (server, url, got, box)."""
    got, box = threading.Event(), {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):                    # noqa: N802
            body = page.encode("utf-8")
            self.send_response(200 if self.path in ("/", "/page.html") or self.path.startswith("/page.html") else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):                   # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            box["dom"] = self.rfile.read(n).decode("utf-8", errors="replace")
            self.send_response(204)
            self.end_headers()
            got.set()

        def log_message(self, *a):           # quiet
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/page.html", got, box


def stop_edge(profile):
    """Stop the Edge processes started with this profile folder (Edge 156 leaves them running)."""
    if os.name != "nt":
        return
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like "
          f"'*{str(profile)}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction "
          "SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)


def dom(page, delay_ms=200, timeout=None, hash_=""):
    """The page's DOM after its scripts ran (and window.pageReady settled), as text. Raises RuntimeError if Edge
    doesn't post it back within timeout seconds (default EDGE_WAIT)."""
    text = page.replace("</body>", POST_BACK % delay_ms + "</body>", 1) if "</body>" in page \
        else page + POST_BACK % delay_ms
    srv, url, got, box = _serve(text)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="edge_page-"))
    try:
        subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                          f"--user-data-dir={tmp / 'profile'}", "--window-size=1920,1200", url + hash_],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not got.wait(WAIT if timeout is None else timeout):
            raise RuntimeError("Edge didn't post the page back (set EDGE_WAIT to wait longer)")
        return box["dom"]
    finally:
        srv.shutdown()
        stop_edge(tmp / "profile")
        shutil.rmtree(tmp, ignore_errors=True)


def screenshot(page, out, width=1920, height=1080, hash_="", budget_ms=8000, timeout=None):
    """A PNG of the page at width x height (what a viewer sees at the top of the page). The page is served the same
    way as dom(), so its scripts run alike; Edge waits up to budget_ms of virtual time for loads and timers."""
    srv, url, _, _ = _serve(page)
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="edge_page-"))
    try:
        subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                          f"--user-data-dir={tmp / 'profile'}", f"--window-size={width},{height}",
                          f"--virtual-time-budget={budget_ms}", f"--screenshot={out}", url + hash_],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        svg_to_png.wait_for_png(out, timeout)
        return out
    finally:
        srv.shutdown()
        stop_edge(tmp / "profile")
        shutil.rmtree(tmp, ignore_errors=True)
