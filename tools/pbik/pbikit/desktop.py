"""pbik desktop state | reload | screenshot: a thin wrapper over .claude/scripts/pbi-bridge.ps1 (Desktop Bridge).

If PowerShell, the script or the bridge pipe isn't there, pbik says so and exits with code 3 (no traceback), so a
caller can tell "couldn't check" from "clean". reload refuses while Desktop reports unsaved changes.
Exit codes: 0 ok, 3 bridge not available, 4 unsaved changes (state --fail-if-dirty, reload), 5 Desktop still
opening after the wait (say "still opening", never "not ready").
"""
import json, os, pathlib, shutil, subprocess, sys

UNAVAILABLE, DIRTY = 3, 4
DIRTY_KEYS = ("isdirty", "dirty", "hasunsavedchanges", "unsavedchanges", "unsaved", "ismodified", "modified")


def find_bridge(start=None):
    p = pathlib.Path(start or os.getcwd()).resolve()
    for d in [p, *p.parents]:
        f = d / ".claude" / "scripts" / "pbi-bridge.ps1"
        if f.exists():
            return f
    return None


def unavailable(msg, check_version=False):
    print(f"Desktop bridge not available: {msg}")
    if check_version:                   # roadmap gap 23: say when this Desktop can't reload external changes at all
        from . import versions as V
        issue = V.reload_issue(os.environ.get("PBIK_DESKTOP_VERSION") or V.detect_desktop())
        print(issue or "It needs the August 2026 Desktop or later with the preview option \"Detect and reload "
                       "external PBIP changes\" turned on (Options > Preview features, then restart).")
    sys.exit(UNAVAILABLE)


NOT_READY = 5
READY_WAIT = float(os.environ.get("PBIK_DESKTOP_WAIT", "300"))     # seconds to wait for Desktop to finish opening


def opening_file(root="."):
    return pathlib.Path(root) / ".pbik" / "desktop-opening.txt"


def just_opened(root=".", within=None):
    """True when `pbik desktop open` started Desktop in the last few minutes (its bridge pipe may not exist yet)."""
    import time
    f = opening_file(root)
    try:
        return time.time() - float(f.read_text(encoding="utf-8").strip()) < (within or READY_WAIT)
    except (OSError, ValueError):
        return False


def _call(ps, script, action, args):
    r = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-File", str(script), action, *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout or "", (r.stdout or "") + (r.stderr or "")


def _not_ready(low, opening):
    """Desktop is up but still opening: the bridge says HostNotReady, or (right after `desktop open`) no pipe yet."""
    if "hostnotready" in low or "not ready to accept" in low:
        return True
    no_pipe = "no desktop bridge pipe" in low or "pipe" in low and ("timeout" in low or "not found" in low)
    return bool(opening and no_pipe and desktop_open())


def run(action, *args, bridge=None, wait=None, sleep=None):
    """Run one bridge action. While Desktop is still opening, wait (up to PBIK_DESKTOP_WAIT seconds) with a plain
    "Still waiting for Power BI Desktop to finish opening" line every 30 seconds, instead of failing "not ready"
    (walkthrough fix 4)."""
    import time
    from . import progress as PR
    script = pathlib.Path(bridge) if bridge else find_bridge()
    if not script or not script.exists():
        unavailable("no .claude/scripts/pbi-bridge.ps1 found above the current folder (pass --bridge)")
    ps = shutil.which("powershell") or shutil.which("powershell.exe") or shutil.which("pwsh")
    if not ps:
        unavailable("PowerShell is not on PATH")
    wait = READY_WAIT if wait is None else wait
    sleep = sleep or time.sleep
    end = time.monotonic() + wait
    with PR.still("waiting for Power BI Desktop to finish opening"):
        while True:
            code, stdout, out = _call(ps, script, action, args)
            low = out.lower()
            if code == 0 or not _not_ready(low, just_opened(within=120)) or time.monotonic() >= end:
                break
            sleep(3)
    if code != 0:
        if _not_ready(low, just_opened(within=120)):
            print("Power BI Desktop is still opening the report. I'll try again in a moment.")
            sys.exit(NOT_READY)
        if "no desktop bridge pipe" in low or "pipe" in low and ("timeout" in low or "not found" in low):
            unavailable("Power BI Desktop is not open, or its Desktop Bridge preview is off", check_version=True)
        if "running scripts is disabled" in low or "execution polic" in low:
            unavailable("PowerShell's execution policy blocks the bridge script (tools/doctor.ps1 shows the policy)")
        if "multiple desktop instances" in low:
            unavailable("several Desktop windows are open; close all but one (or pass --process-id)")
        print(out.strip())
        sys.exit(code)
    return stdout


def wait_ready(bridge=None, wait=None):
    """After `desktop open`: wait until Desktop answers (still-opening lines meanwhile). Returns True when ready."""
    try:
        run("state", bridge=bridge, wait=wait)
        return True
    except SystemExit as e:
        if e.code in (NOT_READY, UNAVAILABLE):
            return False
        raise


def dirty_flag(obj):
    """Find an unsaved-changes flag anywhere in the state JSON (None if the bridge doesn't report one)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in DIRTY_KEYS and isinstance(v, bool):
                return v
        for v in obj.values():
            f = dirty_flag(v)
            if f is not None:
                return f
    elif isinstance(obj, list):
        for v in obj:
            f = dirty_flag(v)
            if f is not None:
                return f
    return None


def state(bridge=None, fail_if_dirty=False, quiet=False):
    raw = run("state", bridge=bridge)
    try:
        st = json.loads(raw)
    except json.JSONDecodeError:
        st = None
    flag = dirty_flag(st) if st is not None else None
    if not quiet:
        print(raw.strip())
        print("\nunsaved changes:", {True: "YES", False: "no", None: "unknown (no flag in the bridge state)"}[flag])
    if fail_if_dirty and flag:
        sys.exit(DIRTY)
    return flag


def reload(bridge=None, force=False, report=None, root="."):
    flag = state(bridge=bridge, quiet=True)
    if flag and not force:
        print("Desktop has unsaved changes: not reloading. Close Desktop without saving, reopen, then reload.")
        sys.exit(DIRTY)
    if flag is None and not force:
        print("warning: the bridge reports no unsaved-changes flag; check Desktop's title bar before relying on this")
    print(run("reload", bridge=bridge).strip())
    folder = pathlib.Path(report) if report else next(pathlib.Path(root).glob("*.Report"), None)
    if folder:                                            # the state that proves "only my reload marks" (D1)
        try:
            remember_reload(root, folder, json.loads(run("state", bridge=bridge)))
        except (SystemExit, json.JSONDecodeError):
            pass
    print("Reloaded. The reload marks the report unsaved: close without saving and reopen before the next reload.")
    print("Reloading resets filters and slicer selections to what the files hold (Microsoft Learn, external editing): "
          "a screenshot now shows the report's default state.")


def desktop_open():
    """True when Power BI Desktop is running (PBIK_DESKTOP_OPEN=1/0 overrides, for tests)."""
    env = os.environ.get("PBIK_DESKTOP_OPEN")
    if env in ("0", "1"):
        return env == "1"
    if os.name != "nt":
        return False
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq PBIDesktop.exe", "/NH"], capture_output=True, text=True,
                           errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return "PBIDesktop.exe" in (r.stdout or "")


def screenshot(page, out, report=None, region=None, scale=1, bridge=None):
    from . import dataclass_ as DC
    from .report import Report
    why = DC.guard(Report(report).path.parent if report else pathlib.Path.cwd(), "screenshot")
    if why:
        print(f"pbik: {why}", file=sys.stderr)
        sys.exit(2)
    page_id = page
    if report:
        hit = Report(report).page_by(page)
        if not hit:
            print(f"pbik: no page {page!r} in {report}")
            sys.exit(2)
        page_id = hit[0]
    pathlib.Path(out).resolve().parent.mkdir(parents=True, exist_ok=True)     # e.g. a new project's _snapshots
    args = ["-PageId", page_id, "-Out", str(pathlib.Path(out).resolve()), "-Scale", str(scale)]
    if region:
        args += ["-Region", region]
    print(run("screenshot", *args, bridge=bridge).strip())


# ---------------------------------------------------------------- closing Desktop (v1.7, decision D1)
VOLATILE = ("time", "timestamp", "date", "now", "elapsed", "uptime", "memory", "lastactivity")


def record_file(root="."):
    return pathlib.Path(root) / ".pbik" / "desktop.json"


def normalise(obj):
    """The bridge state without values that change on their own (times, memory)."""
    if isinstance(obj, dict):
        return {k: normalise(v) for k, v in sorted(obj.items()) if not any(w in k.lower() for w in VOLATILE)}
    if isinstance(obj, list):
        return [normalise(v) for v in obj]
    return obj


def desktop_pids():
    """Process ids of running Power BI Desktop windows (PBIK_DESKTOP_PIDS="1,2" overrides, for tests)."""
    env = os.environ.get("PBIK_DESKTOP_PIDS")
    if env is not None:
        return [int(x) for x in env.split(",") if x.strip()]
    if os.name != "nt":
        return []
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq PBIDesktop.exe", "/NH", "/FO", "CSV"],
                           capture_output=True, text=True, errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for ln in (r.stdout or "").splitlines():
        parts = [p.strip('"') for p in ln.split('","')]
        if len(parts) > 1 and parts[0].lower().startswith("pbidesktop") and parts[1].isdigit():
            out.append(int(parts[1]))
    return out


def files_hash(report_folder):
    """A hash of the report's files on disk (to tell whether Desktop saved since the agent's reload)."""
    import hashlib
    h = hashlib.sha1()
    base = pathlib.Path(report_folder)
    for f in sorted(base.rglob("*")) if base.is_dir() else []:
        if f.is_file() and ".pbi" not in f.parts:
            h.update(str(f.relative_to(base)).encode("utf-8"))
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def remember_reload(root, report_folder, state_json, pids=None):
    """After the agent's own reload: the state Desktop is in when its only unsaved changes are its reload marks."""
    import datetime
    from .synth import write_json
    pids = desktop_pids() if pids is None else pids
    write_json(record_file(root), {"pid": pids[0] if len(pids) == 1 else None, "state": normalise(state_json),
                                   "files": files_hash(report_folder), "report": str(pathlib.Path(report_folder)),
                                   "at": datetime.datetime.now().isoformat(timespec="seconds")})


def mark_built(root, report_folder):
    """pbik build changed the report files after the reload: the agent's own change, not Desktop's."""
    from .synth import read_json, write_json
    rec = read_json(record_file(root))
    if rec:
        rec["built"] = files_hash(report_folder)
        write_json(record_file(root), rec)


def why_not_close(root, report_folder, state_json, pids=None):
    """None when it is proven that Desktop's only unsaved changes are its own reload marks; else the plain reason.
    Any doubt is a reason (D1): no reload by the agent on record, another Desktop window, a different process, a
    state that differs from right after the reload, or report files Desktop saved."""
    from .synth import read_json
    rec = read_json(record_file(root))
    pids = desktop_pids() if pids is None else pids
    if not rec:
        return "I haven't reloaded this report in Desktop myself, so I can't tell what changed there"
    if len(pids) != 1:
        return "more than one Power BI Desktop window is open" if pids else "Power BI Desktop isn't open"
    if rec.get("pid") != pids[0]:
        return "this Desktop window isn't the one I reloaded"
    if state_json is None:
        return "Desktop doesn't report its state"
    if normalise(state_json) != rec.get("state"):
        return "something in Desktop changed after my reload (maybe yours)"
    if files_hash(report_folder) not in (rec.get("files"), rec.get("built")):
        return "the report's files changed in a way I didn't make (maybe a save in Desktop)"
    return None


def close(root=".", report=None, bridge=None, kill=None, read_state=None):
    """Close the Desktop window for this report without saving, only when proven safe (D1). Returns the reason it
    didn't, or None after closing."""
    folder = pathlib.Path(report) if report else next(pathlib.Path(root).glob("*.Report"), None)
    if not folder:
        return "there is no report in this project"
    try:
        st = read_state() if read_state else json.loads(run("state", bridge=bridge))
    except SystemExit:
        return "the Desktop bridge isn't available, so I can't check Desktop"
    except (json.JSONDecodeError, ValueError):
        st = None
    why = why_not_close(root, folder, st)
    if why:
        return why
    pid = desktop_pids()[0]
    if kill:
        kill(pid)
    else:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid}"], capture_output=True)
    record_file(root).unlink(missing_ok=True)
    return None
