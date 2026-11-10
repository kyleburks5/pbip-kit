"""pbik desktop state | reload | screenshot: a thin wrapper over .claude/scripts/pbi-bridge.ps1 (Desktop Bridge).

If PowerShell, the script or the bridge pipe isn't there, pbik says so and exits with code 3 (no traceback), so a
caller can tell "couldn't check" from "clean". reload refuses while Desktop reports unsaved changes.
Exit codes: 0 ok, 3 bridge not available, 4 unsaved changes (state --fail-if-dirty, reload).
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


def run(action, *args, bridge=None):
    script = pathlib.Path(bridge) if bridge else find_bridge()
    if not script or not script.exists():
        unavailable("no .claude/scripts/pbi-bridge.ps1 found above the current folder (pass --bridge)")
    ps = shutil.which("powershell") or shutil.which("powershell.exe") or shutil.which("pwsh")
    if not ps:
        unavailable("PowerShell is not on PATH")
    r = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-File", str(script), action, *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        low = out.lower()
        if "no desktop bridge pipe" in low or "pipe" in low and ("timeout" in low or "not found" in low):
            unavailable("Power BI Desktop is not open, or its Desktop Bridge preview is off", check_version=True)
        if "running scripts is disabled" in low or "execution polic" in low:
            unavailable("PowerShell's execution policy blocks the bridge script (tools/doctor.ps1 shows the policy)")
        if "multiple desktop instances" in low:
            unavailable("several Desktop windows are open; close all but one (or pass --process-id)")
        print(out.strip())
        sys.exit(r.returncode)
    return r.stdout


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


def reload(bridge=None, force=False):
    flag = state(bridge=bridge, quiet=True)
    if flag and not force:
        print("Desktop has unsaved changes: not reloading. Close Desktop without saving, reopen, then reload.")
        sys.exit(DIRTY)
    if flag is None and not force:
        print("warning: the bridge reports no unsaved-changes flag; check Desktop's title bar before relying on this")
    print(run("reload", bridge=bridge).strip())
    print("Reloaded. The reload marks the report unsaved: close without saving and reopen before the next reload.")
    print("Reloading resets filters and slicer selections to what the files hold (Microsoft Learn, external editing): "
          "a screenshot now shows the report's default state.")


def screenshot(page, out, report=None, region=None, scale=1, bridge=None):
    page_id = page
    if report:
        from .report import Report
        hit = Report(report).page_by(page)
        if not hit:
            print(f"pbik: no page {page!r} in {report}")
            sys.exit(2)
        page_id = hit[0]
    args = ["-PageId", page_id, "-Out", str(pathlib.Path(out).resolve()), "-Scale", str(scale)]
    if region:
        args += ["-Region", region]
    print(run("screenshot", *args, bridge=bridge).strip())
