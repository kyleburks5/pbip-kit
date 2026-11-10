"""Retiring and deprecated visuals and options (roadmap gap 20): `pbik validate` and `pbik build` warnings.

Provenance (roadmap batch 1, item c; Microsoft Learn read 2026-11-10, schemas from pbik's cache):
- Q&A: "Limitations of Power BI Q&A", https://learn.microsoft.com/en-us/power-bi/natural-language/q-and-a-limitations
  (updated 2026-09-10), Important note: Q&A experiences go away in February 2027; use Copilot instead. Covers the Q&A
  visual and a button's Q&A action (visualConfiguration 2.8.0 #VisualLink `qna`).
- Map and Filled map (Bing Maps): "Convert Map and Filled map visuals to an Azure Maps visual",
  https://learn.microsoft.com/en-us/azure/azure-maps/power-bi-visual-conversion (updated 2026-01-21), Important note:
  scheduled for deprecation, no date set. Replacement: Azure Maps.
- "Power BI Report skill", https://learn.microsoft.com/en-us/power-bi/developer/agentic/power-bi-report-skill-overview
  (updated 2026-10-02), Considerations: avoid visuals scheduled for deprecation, including Q&A, Bing Maps and filled maps.
- Page displayOption: page 2.1.0 #PageDisplayOption marks DeprecatedDynamic and ActualSizeTopLeft "Deprecated" (use
  ActualSize). pbik reads the mark from the cached schema; DEPRECATED_DISPLAY is the fallback when it isn't cached.
- visualType ids: `map` and `azureMap` are in Desktop's own base themes (Fluent2-CY26SU09 and CY24SU10 visualStyles,
  in the Rep 4, 5 and 8 fixtures). `filledMap` and `qnaVisual` are not in any file Desktop saved for the kit and Learn
  doesn't print type ids: unconfirmed until a Desktop save shows them (matched case-insensitively).
- The Q&A visual can't be confirmed from a save: Kyle found it in neither Visualizations nor Insert in Desktop
  2.159.883.0 (2026-11-10). Its type id stays unconfirmed, and its warning is validate-only (VALIDATE_ONLY): pbik build
  can't place one from a template anyway, so it only matters on files someone else made.
"""
import re

RETIRING = {
    "qnavisual": ("the Q&A visual", "Q&A goes away in February 2027 (Microsoft Learn, Limitations of Power BI Q&A); "
                                    "use a native visual, or Copilot outside the report"),
    "map": ("the Map visual (Bing Maps)", "Bing Maps visuals are scheduled for deprecation (Microsoft Learn); "
                                          "use Azure Maps (azureMap)"),
    "filledmap": ("the Filled map visual (Bing Maps)", "Bing Maps visuals are scheduled for deprecation "
                                                       "(Microsoft Learn); use Azure Maps (azureMap) or a shape map"),
}
DEPRECATED_DISPLAY = {"DeprecatedDynamic": "FitToPage", "ActualSizeTopLeft": "ActualSize"}
VALIDATE_ONLY = {"qnavisual"}     # type id unconfirmed (no Desktop save possible): warned by pbik validate only
QNA_TYPE = re.compile(r"q\s*&\s*a|qna", re.I)


def visual_issue(visual_type, in_build=False):
    if in_build and (visual_type or "").lower() in VALIDATE_ONLY:
        return None
    hit = RETIRING.get((visual_type or "").lower())
    return f"{hit[0]} is retiring: {hit[1]}" if hit else None


def link_issue(visual_link_entries):
    """A button whose action is Q&A (visualLink type Q&A, or a `qna` property)."""
    for e in visual_link_entries or []:
        p = e.get("properties", {})
        typ = (p.get("type") or {}).get("expr", {}).get("Literal", {}).get("Value", "") if isinstance(p.get("type"), dict) else ""
        if "qna" in p or QNA_TYPE.search(typ or ""):
            return "button action Q&A is retiring: Q&A goes away in February 2027 (Microsoft Learn); use another action"
    return None


def display_issue(value, deprecated=None):
    """deprecated: the values the cached page schema marks Deprecated (None: not cached, use the fallback list)."""
    dep = deprecated if deprecated is not None else set(DEPRECATED_DISPLAY)
    if value in dep:
        return (f"displayOption {value} is deprecated in Microsoft's page schema: use "
                f"{DEPRECATED_DISPLAY.get(value, 'FitToPage, FitToWidth or ActualSize')}")
    return None
