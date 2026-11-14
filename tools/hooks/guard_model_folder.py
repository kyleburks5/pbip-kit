r"""Claude Code PreToolUse hook: the agent never reads the model drop folder itself (docs/design/phase1-usability.md, B3).

Blocks Read, Grep and Glob on the Model folder (the project's top-level `Model` drop folder, v1.7 one-folder setup) and
on design/reference/model (projects made before it), and shell commands naming either unless they run pbik (which
deletes data files before reading). Exit 2 blocks the tool call and tells the agent why.

Works from any working folder (v1.7, A10): .claude/settings.json runs it by the project folder ($CLAUDE_PROJECT_DIR),
relative paths are resolved against the event's `cwd` (so `..\model\x` from design\reference is caught), and it
fails closed: if anything goes wrong while a tool call names a model folder, the call is blocked.
"""
import json, os, re, sys

OLD = r"design[\\/]+reference[\\/]+model(?:[\\/]|$|\"|')"
# the top-level Model folder: a path segment named Model, as a folder (a slash after it) or the last word
NEW = r"(?:^|[\\/\"'\s=])Model(?:[\\/]|[\"']?\s*$)"
FOLDER = re.compile(f"{OLD}|{NEW}", re.I)
PATH_KEYS = ("file_path", "path", "notebook_path")
MESSAGE = ("The Model folder may hold data: don't open it. Run `pbik model intake` (it deletes data files first, "
           "then reads the model).")


def _resolved(value, cwd):
    """The path as given and, for a relative path, resolved against the tool call's working folder."""
    s = str(value or "")
    out = [s]
    if s and cwd and not os.path.isabs(s):
        try:
            out.append(os.path.normpath(os.path.join(cwd, s)))
        except (TypeError, ValueError):
            pass
    return out


def blocked(event):
    tool, inp = event.get("tool_name", ""), event.get("tool_input") or {}
    cwd = event.get("cwd") or ""
    if tool in ("Read", "Grep", "Glob", "Edit", "Write", "NotebookEdit"):
        keys = PATH_KEYS + (("pattern",) if tool == "Glob" else ())
        paths = [p for k in keys for p in _resolved(inp.get(k, ""), cwd if k != "pattern" else "")]
        if tool == "Glob" and inp.get("pattern"):          # a Glob pattern runs under its path (or the cwd)
            base = inp.get("path") or cwd
            paths.append(os.path.join(str(base), str(inp["pattern"])) if base else str(inp["pattern"]))
        if tool in ("Grep", "Glob") and not inp.get("path") and cwd:
            paths.append(str(cwd))                        # searching from inside the model folder itself
        return any(FOLDER.search(p + ("/" if p and not p.endswith(("/", "\\")) else "")) for p in paths)
    if tool in ("Bash", "PowerShell"):
        cmd = str(inp.get("command", ""))
        here = FOLDER.search(cwd + "/") if cwd else None
        return bool(FOLDER.search(cmd) or here) and "pbik" not in cmd
    return False


def main():
    raw = ""
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
        if blocked(event):
            print(MESSAGE, file=sys.stderr)
            return 2
        return 0
    except Exception:                                     # noqa: BLE001  fail closed when the folder is named
        if FOLDER.search(raw.replace("\\\\", "\\")) and "pbik" not in raw:
            print(MESSAGE + " (The guard couldn't read this tool call, so it blocked it.)", file=sys.stderr)
            return 2
        return 0


if __name__ == "__main__":
    sys.exit(main())
