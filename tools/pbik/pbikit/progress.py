"""Plain progress lines during long waits (walkthrough fix 4, v1.7).

Any step that can take longer than 30 seconds (drawing the plan picture, Desktop opening, waiting for the bridge)
runs inside `still("drawing the plan picture")`: every `every` seconds (default 30, PBIK_PROGRESS_EVERY) it prints
one plain line, "Still drawing the plan picture (1 min so far).", straight to the real terminal (also under
`--report json`, whose own output is held to the end), and writes the latest line to .pbik/progress.txt so an agent
that can't see the terminal can read it. When the step ends, the line says how long it took.
"""
import contextlib, os, pathlib, sys, threading, time

EVERY = float(os.environ.get("PBIK_PROGRESS_EVERY", "30"))


def _say(line, root="."):
    stream = sys.__stderr__ or sys.stderr
    try:
        stream.write(line + "\n")
        stream.flush()
    except (OSError, ValueError, AttributeError):
        pass
    try:
        f = pathlib.Path(root) / ".pbik" / "progress.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(line + "\n", encoding="utf-8")
    except OSError:
        pass


def minutes(sec):
    m = int(sec // 60)
    return "under a minute" if m < 1 else ("1 min" if m == 1 else f"{m} min")


@contextlib.contextmanager
def still(what, every=None, root=".", lines=None):
    """Print "Still <what> (n so far)." every `every` seconds while the block runs. `lines` (a list) collects them."""
    every = EVERY if every is None else every
    stop = threading.Event()
    t0 = time.monotonic()

    def tick():
        while not stop.wait(every):
            line = f"Still {what} ({minutes(time.monotonic() - t0)} so far)."
            if lines is not None:
                lines.append(line)
            _say(line, root)

    th = threading.Thread(target=tick, daemon=True)
    th.start()
    try:
        yield
    finally:
        stop.set()
        th.join(timeout=1)
        took = time.monotonic() - t0
        if took >= every:
            _say(f"Done {what} after {minutes(took)}.", root)
