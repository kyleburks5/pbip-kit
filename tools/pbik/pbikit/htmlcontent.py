"""HTML Content visuals (visual-method ladder step 4, a custom visual): any `htmlContent<GUID>` visual type.

The visual's settings come from its capabilities.json (dm-p/powerbi-visuals-html-content), not from a Desktop save:
- objects.compatibility[0].properties.legacyRendering: pbik turns it on (true) for every HTML Content visual;
- under MIN_HEIGHT px the visual has no room for its content: pbik build and pbik validate warn.
Not Desktop-tested yet (kit v1.2).
"""
import re

TYPE_RE = re.compile(r"htmlContent[0-9A-Fa-f]{32}")
MIN_HEIGHT = 43
TAG = "HTML Content"


def is_html_content(visual_type):
    return bool(visual_type) and bool(TYPE_RE.fullmatch(str(visual_type)))


def height_issue(h):
    """A warning for a box under MIN_HEIGHT px, or None."""
    if isinstance(h, (int, float)) and h < MIN_HEIGHT:
        return f"HTML Content visual is {h:g}px tall, under {MIN_HEIGHT}px: its content won't show; make it taller"
    return None
