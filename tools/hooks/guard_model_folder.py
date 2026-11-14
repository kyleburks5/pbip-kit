"""Claude Code PreToolUse hook: the agent never reads the model drop folder itself (docs/design/phase1-usability.md, 3).

Blocks Read, Grep and Glob on design/reference/model, and shell commands naming it unless they run pbik (which deletes
data files before reading). Exit 2 blocks the tool call and tells the agent why.
"""
import json, re, sys

FOLDER = re.compile(r"design[\\/]+reference[\\/]+model(?:[\\/]|$|\"|')", re.I)


def blocked(event):
    tool, inp = event.get("tool_name", ""), event.get("tool_input") or {}
    if tool in ("Read", "Grep", "Glob", "Edit", "Write", "NotebookEdit"):
        keys = ("file_path", "path", "notebook_path") + (("pattern",) if tool == "Glob" else ())
        return any(FOLDER.search(str(inp.get(k, ""))) for k in keys)      # paths only, not file contents
    if tool in ("Bash", "PowerShell"):
        cmd = str(inp.get("command", ""))
        return bool(FOLDER.search(cmd)) and "pbik" not in cmd
    return False


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if blocked(event):
        print("The model folder may hold data: don't open it. Run `pbik model intake` (it deletes data files first, "
              "then reads the model).", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
