"""Polish-loop screenshot check: KPI cards with large empty space inside (docs/lessons/cards.md C-10).

    python design/scripts/card_space.py <Report> --page <display name> --png _snapshots/<page>.png [--limit 0.35]

Reads the page screenshot (`pbik desktop screenshot ... --region 0,0,1920,1080`) and every KPI card's box from the
report, and flags a card whose largest empty band (rows or columns with no content, 8px inside its edge) is more than
`--limit` of its height or width: the label, value and change line should fill the card. Synthetic or sample data
only: it refuses a report on a model that isn't pbik's synthetic one, unless the project's data class is public.
Exit 1 when a card is flagged, 2 when it refuses.
"""
import argparse, pathlib, sys

KIT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools" / "pbik"))

from pbikit import dataclass_ as DC, kpicards as KC  # noqa: E402
from pbikit.report import Report  # noqa: E402


def allowed(rep):
    return DC.is_synthetic(rep.model_folder()) or DC.data_class(rep.path.parent) == "public"


def run(report, page, png, limit=0.35):
    rep = Report(report)
    if not allowed(rep):
        print("card_space: synthetic or sample data only (the report's model isn't pbik's synthetic model and the "
              "project isn't public)", file=sys.stderr)
        return 2, []
    hit = rep.page_by(page)
    if not hit:
        print(f"card_space: no page {page!r}", file=sys.stderr)
        return 2, []
    name, pd, folder = hit
    cards = []
    for d, f in rep.visuals(folder):
        if KC.is_kpi(f.parent.name, d):
            x, y, w, h, _ = KC.box(d)
            cards.append((f.parent.name, x, y, w, h))
    flags = KC.empty_space(png, cards, pd.get("width", 1920), limit=limit)
    for n, frac, where in flags:
        print(f"{n}: {int(frac * 100)}% of its {where} is empty: make the label, value and change line fill the card "
              "(callout area, reference-label insets; C-10)")
    print(f"{len(cards)} KPI card(s), {len(flags)} flagged")
    return (1 if flags else 0), flags


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("report")
    ap.add_argument("--page", required=True)
    ap.add_argument("--png", required=True)
    ap.add_argument("--limit", type=float, default=0.35)
    a = ap.parse_args(argv)
    return run(a.report, a.page, a.png, a.limit)[0]


if __name__ == "__main__":
    sys.exit(main())
