"""Table and matrix column widths from the container size (layout `columnWidths: "fit"`).

The columns fill the visual's inner width: the box width less the container padding (left and right) and a reserve for
the vertical scrollbar (tokens `table.scrollbarReserve`, default 16px: Rep 8's hand-set widths left 16 to 21px). Each
column gets at least its header label width (Segoe UI estimate at the header font size, plus cell padding) or the
minimum for its kind (text 120px, number 64px, date 90px, image 100px), the same for every column of a kind; the
space left over is shared with text columns weighted 2 and the others 1. In a matrix the Rows fields share one
stepped column, sized on the first Rows field. Widths are whole pixels and add up exactly to the inner width.

    "columnWidths": "fit"                                     every column
    "columnWidths": {"T[Name]": 240, "[Sales]": "fit", ...}   fixed widths kept, "fit" columns share the rest

A matrix with fields on Columns repeats its value columns once per member, which isn't known on disk: fit refuses it.
"""
from .slicerfit import text_px

MIN = {"text": 120, "number": 64, "date": 90, "image": 100}
WEIGHT = {"text": 2, "number": 1, "date": 1, "image": 1}
CELL_PAD = 16                     # left + right cell padding around a header label
NUMERIC = {"int64", "double", "decimal", "currency"}


class FitError(ValueError):
    pass


def kind_of(model, field, ext=None, text_measure=None):
    """text / number / date / image for a resolved PBIR field (Measure, Column or Aggregation)."""
    if "Aggregation" in field:
        return "number"
    if "Measure" in field:
        m = field["Measure"]
        ent, name = m["Expression"]["SourceRef"]["Entity"], m["Property"]
        if m["Expression"]["SourceRef"].get("Schema") == "extension":
            mm = (ext or {}).get((ent, name), {})
            if mm.get("dataCategory") == "ImageUrl":
                return "image"
            return "text" if mm.get("dataType", "Text") == "Text" else "number"
        mm = model.tables[ent].measures.get(name) if model and ent in model.tables else None
        if mm is not None:
            if (mm.data_category or "").lower() == "imageurl":
                return "image"
            if (text_measure or (lambda x: x.is_text()))(mm):
                return "text"
        return "number"
    c = field["Column"]
    dt = model.column_type(c["Expression"]["SourceRef"]["Entity"], c["Property"]) if model else None
    if dt in NUMERIC:
        return "number"
    if dt in ("dateTime", "date"):
        return "date"
    return "text"


def fit(columns, inner, header_pt=10):
    """columns: [(key, label, kind, fixed px or None)] -> {key: px}, summing to inner. Raises FitError if the fixed
    widths and minimums don't fit."""
    fixed = sum(c[3] for c in columns if c[3] is not None)
    free = [c for c in columns if c[3] is None]
    mins = {c[0]: max(MIN[c[2]], round(text_px(c[1], header_pt) + CELL_PAD)) for c in free}
    for kind in {c[2] for c in free}:          # columns of one kind get one width (as Rep 8's hand-set tables)
        same = [c[0] for c in free if c[2] == kind]
        top = max(mins[k] for k in same)
        for k in same:
            mins[k] = top
    room = inner - fixed - sum(mins.values())
    if room < 0:
        raise FitError(f"needs {inner - room}px, the box has {inner}px inside: widen the visual, drop a column or "
                       "set smaller fixed widths")
    total_w = sum(WEIGHT[c[2]] for c in free) or 1
    out = {c[0]: c[3] for c in columns if c[3] is not None}
    for c in free:
        out[c[0]] = mins[c[0]] + int(room * WEIGHT[c[2]] / total_w)
    if free:                                   # rounding: the last free column takes the remainder
        out[free[-1][0]] += inner - sum(out.values())
    return out


def widths(columns, box_w, pad_left, pad_right, header_pt=10, reserve=16):
    """{key: px} for the columns of a table or matrix box."""
    inner = int(box_w - pad_left - pad_right - reserve)
    return fit(columns, inner, header_pt)
