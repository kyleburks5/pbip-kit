r"""Claude Code PreToolUse hook for the approval window (docs/design/phase1-usability.md, A8).

- A screen-control tool call (computer use) leaves a marker, ~/.pbik/screen-control.json (PBIK_HOME in tests): the
  approval window refuses to open for 10 minutes after the last one (pbikit/gates.py). The call itself isn't blocked.
- While an approval window is open (~/.pbik/gate-window.json), shell commands that drive windows or keys (SendKeys,
  UI Automation, SendInput, AppActivate, pywinauto, pyautogui) are blocked: only a person answers the window.

Copilot has no hooks: it relies on the rule. Exit 2 blocks the tool call and tells the agent why.
"""
import datetime, json, os, pathlib, re, sys

SCREEN = re.compile(r"(computer[-_]use|remote-devices__computer)", re.I)
DRIVERS = re.compile(r"SendKeys|UIAutomation|AutomationElement|SendInput|keybd_event|mouse_event|SetForegroundWindow|"
                     r"AppActivate|pywinauto|pyautogui|InvokePattern|ValuePattern", re.I)
WINDOW_MINUTES = 35


def user_dir():
    return pathlib.Path(os.environ.get("PBIK_HOME") or pathlib.Path.home() / ".pbik")


def window_open():
    f = user_dir() / "gate-window.json"
    try:
        at = datetime.datetime.fromisoformat(json.loads(f.read_text(encoding="utf-8"))["at"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return (datetime.datetime.now() - at).total_seconds() / 60 < WINDOW_MINUTES


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    tool = str(event.get("tool_name", ""))
    if SCREEN.search(tool):
        d = user_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / "screen-control.json").write_text(json.dumps({
            "at": datetime.datetime.now().isoformat(timespec="seconds"), "tool": tool}), encoding="utf-8")
        return 0
    if tool in ("Bash", "PowerShell"):
        cmd = str((event.get("tool_input") or {}).get("command", ""))
        if DRIVERS.search(cmd) and window_open():
            print("An approval window is open: only a person answers it. Don't send keys or clicks to windows; wait "
                  "for the answer (pbik gate wait).", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
