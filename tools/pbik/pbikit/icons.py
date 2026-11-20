"""The kit's own icons (v1.12, panel style layout): simple line glyphs drawn here on a 24 x 24 grid, no outside icon
pack. Each draws as a stroke in one colour, optionally on a tinted circle.

    svg("phone", fg="#2447A8", bg="#EAF0FD", size=44)

Add a glyph by drawing it here (paths on the 24 grid, round caps, 1.8 stroke) and a keyword in GUESS.
"""
import re

GLYPHS = {
    # service desk
    "phone": ["M7 3.5h3l1.6 4-2.1 1.4a10.5 10.5 0 0 0 5.1 5.1l1.4-2.1 4 1.6v3a2 2 0 0 1-2 2C11 18.5 5.5 13 5 5.5a2 2 0 0 1 2-2z"],
    "chat": ["M4.5 5h15a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8.5l-4.5 3.5V16H4.5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z",
             "M8 10.5h.01M12 10.5h.01M16 10.5h.01"],
    "mail": ["M3.5 6h17v12h-17z", "M3.5 7l8.5 6 8.5-6"],
    "alert": ["M12 3.5l9 16h-18z", "M12 10v4", "M12 17h.01"],
    "headset": ["M4.5 14v-2a7.5 7.5 0 0 1 15 0v2", "M3.5 14h3v5h-3z", "M17.5 14h3v5h-3z", "M19 19c0 1.6-1.8 2.5-5 2.5"],
    # healthcare (lines of business, care settings)
    "cross": ["M9.5 4h5v5.5H20v5h-5.5V20h-5v-5.5H4v-5h5.5z"],
    "bed": ["M3 18V7", "M3 13h18v5", "M21 13v-2a2 2 0 0 0-2-2h-8v4", "M6.5 10.5h.01"],
    "home": ["M4 11l8-6.5 8 6.5", "M6 9.5V19h12V9.5", "M10 19v-5h4v5"],
    "clinic": ["M4 20V8h16v12", "M9 20v-4h6v4", "M12 10v4M10 12h4", "M3 20h18"],
    "heart": ["M12 19.5s-7.5-4.6-7.5-10A4 4 0 0 1 12 7a4 4 0 0 1 7.5 2.5c0 5.4-7.5 10-7.5 10z"],
    "pill": ["M8.5 15.5l7-7a3.5 3.5 0 0 1 5 5l-7 7a3.5 3.5 0 0 1-5-5z", "M12 12l4.5 4.5"],
    "person": ["M12 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z", "M5 20a7 7 0 0 1 14 0"],
    # general
    "clock": ["M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17z", "M12 7.5V12l3 2"],
    "cart": ["M3.5 4.5h2l2 10h10l2-7H7", "M9 19h.01M17 19h.01"],
    "box": ["M4 8l8-4 8 4v8l-8 4-8-4z", "M4 8l8 4 8-4", "M12 12v8"],
    "chart": ["M4 20h16", "M7 17v-5", "M12 17V7", "M17 17v-8"],
    "dot": ["M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"],
}
GUESS = [(r"call|phone|voice", "phone"), (r"chat|message|sms|text", "chat"), (r"e-?mail|mail|letter", "mail"),
         (r"escalat|alert|urgent|incident|critical|risk", "alert"), (r"desk|support|service|help", "headset"),
         (r"emergenc|\bed\b|\ber\b|acute", "cross"), (r"inpatient|bed|ward|admission", "bed"),
         (r"home|community", "home"), (r"outpatient|clinic|ambulatory|office|practice", "clinic"),
         (r"cardio|heart", "heart"), (r"pharm|rx|drug|medic", "pill"), (r"member|patient|person|people|staff", "person"),
         (r"time|wait|duration", "clock"), (r"order|sale|shop|retail", "cart"), (r"stock|inventory|product", "box")]


def guess(name):
    """A glyph for a member by its name (Calls -> phone, Inpatient -> bed), else a dot."""
    for pat, g in GUESS:
        if re.search(pat, str(name or ""), re.I):
            return g
    return "dot"


def svg(name, fg="#1A2233", bg=None, size=44, stroke=1.8):
    """The glyph as an SVG `size` px square: on a `bg` circle when given (the glyph inset), else on its own."""
    paths = GLYPHS.get(name) or GLYPHS["dot"]
    inner = "".join(f'<path d="{d}"/>' for d in paths)
    g = (f'<g fill="none" stroke="{fg}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
         f'{inner}</g>')
    if bg:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 40 40">'
                f'<circle cx="20" cy="20" r="20" fill="{bg}"/><g transform="translate(8 8)">{g}</g></svg>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24">{g}</svg>'
