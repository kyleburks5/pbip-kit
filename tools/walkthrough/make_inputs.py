"""The walkthrough's made-up inputs, made to work together (v1.7 walkthrough fix 11).

    python tools/walkthrough/make_inputs.py [--out ..\\pbik-walkthrough-inputs]

Writes, beside the kit by default (docs/PHASE1-WALKTHROUGH.md names each one):
  1 made-up model\\Example Big.SemanticModel   the large made-up model (tools/pbik/tests/big_model.py) with a fake data
                                              cache (.pbi\\cache.abf) on purpose, so the "deleted before reading" warning
                                              is seen
  3 made-up wireframe\\Orders overview.html    one page on that model's names: four KPIs, orders by month, orders by
                                              region, a regions table with its seven columns named
  4 made-up requirements\\Requirements.md      a short brief with no layout (the starter-layout run)
  README.txt                                  where each one goes (the Model and Reference folders of the project)
"2 made-up live pick" (Pick.Report, a stand-in for a report Desktop saved connected to a published model) is kept as
it is when it exists. Everything matches the model: orders link to regions and channels (the walkthrough's example
change, "rank channels, not regions", works); stores don't link to orders, so nothing asks for stores.
"""
import argparse, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(KIT / "tools" / "pbik" / "tests"))

KPIS = [("Orders amount", "4.2M"), ("Orders quantity", "18,204"), ("Average order", "231"), ("Returns amount", "0.3M")]
TABLE = ["Region", "Orders amount", "vs last year", "Orders quantity", "Average order", "Returns amount",
         "Returns share"]
EXAMPLE_CHANGE = ("Make the bar chart rank channels, not regions.", "Dim Channel", "ChannelKey")

STYLE = """body{margin:0;font-family:'Segoe UI',sans-serif;background:#EEF1F6;color:#1D2733}
.page{width:1440px;height:810px;position:relative;box-sizing:border-box;padding:24px}
.card{background:#FFFFFF;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.08);position:absolute;box-sizing:border-box;padding:16px}
.kpi .v{font-size:34px;font-weight:600}.kpi .l{font-size:13px;color:#5A6577}
h1{font-size:26px;margin:0;position:absolute;font-weight:400}
table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:6px 6px;border-bottom:1px solid #e3e6ea;text-align:left}
td.n,th.n{text-align:right}"""


def wireframe():
    kpis = "".join(f'<div class="card kpi" style="left:{24 + 354 * i}px;top:88px;width:330px;height:120px">'
                   f'<div class=l>{lab}</div><div class=v>{val}</div><div class=l>vs LY +2.1%</div></div>'
                   for i, (lab, val) in enumerate(KPIS))
    line = ('<div class="card" style="left:24px;top:232px;width:684px;height:300px"><b>Orders amount by month</b>'
            '<svg width="600" height="200"><polyline fill=none stroke="#038D96" stroke-width=3 '
            'points="0,150 60,120 120,130 180,90 240,100 300,60 360,80 420,40 480,55 540,30"/><polyline fill=none '
            'stroke="#B8C2D6" stroke-width=2 points="0,160 60,150 120,140 180,130 240,120 300,110 360,100 420,90 '
            '480,85 540,70"/></svg></div>')
    bars = "".join(f'<rect x=90 y="{10 + 34 * i}" width="{240 - 30 * i}" height=22 fill="#038D96"/>' for i in range(6))
    bar = ('<div class="card" style="left:732px;top:232px;width:684px;height:300px"><b>Orders amount by region</b>'
           f'<svg width="380" height="220">{bars}</svg></div>')
    head = "".join(f'<th{" class=n" if i else ""}>{c}</th>' for i, c in enumerate(TABLE))
    rows = "".join("<tr>" + "".join(f'<td{" class=n" if j else ""}>{"Region " + str(r + 1) if not j else "—"}</td>'
                                    for j in range(len(TABLE))) + "</tr>" for r in range(6))
    table = ('<div class="card" style="left:24px;top:556px;width:1392px;height:230px"><b>Regions</b>'
             f'<table><tr>{head}</tr>{rows}</table></div>')
    return ("<!doctype html><html><head><meta charset=utf-8><title>Orders overview (made up)</title><style>"
            + STYLE + "</style></head><body><div class=page><h1 style=\"left:24px;top:24px\">Orders overview</h1>"
            '<div class="card" style="left:1180px;top:20px;width:236px;height:40px"><select style="width:100%">'
            "<option>All regions</option></select></div>" + kpis + line + bar + table + "</div></body></html>\n")


REQUIREMENTS = """# Returns check (made up)

Who: the operations lead, every Monday.
Decision: which regions need a call this week because returns are running high.
Numbers: returns amount, orders amount, returns as a share of orders, and the month before for each.
Filters: region and month.
Nothing here is real.
"""

README = """Made-up inputs for the walkthrough (docs/PHASE1-WALKTHROUGH.md in the kit). Nothing here is real.
They go in your project's two folders (the project is your copy of the kit):
1 made-up model: copy the 'Example Big.SemanticModel' folder into the project's Model folder. It holds a fake data
  cache on purpose: the assistant should say it deleted it before reading anything.
2 made-up live pick: stands in for a report Desktop saved connected to a published model; copy 'Pick.Report' where
  the assistant asks when you switch to live.
3 made-up wireframe: 'Orders overview.html', one page on the made-up model's names (four KPIs, orders by month,
  orders by region, a regions table); copy it into the project's Reference folder.
4 made-up requirements: 'Requirements.md', a short brief with no layout (the starter-layout run); copy it into the
  Reference folder of that run's project.
They fit together: orders link to regions and channels in the model, so the example change "Make the bar chart rank
channels, not regions." works.
"""


def make(out):
    import big_model as BM
    out = pathlib.Path(out)
    m = out / "1 made-up model"
    if not (m / "Example Big.SemanticModel" / "definition").is_dir():     # an existing copy is never deleted
        m.mkdir(parents=True, exist_ok=True)
        BM.write(m, "semanticmodel")
    cache = m / "Example Big.SemanticModel" / ".pbi" / "cache.abf"
    if not cache.exists():                                                 # the fake cache the warning is about
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(b"MADE-UP CACHE " * 64)
    w = out / "3 made-up wireframe"
    w.mkdir(parents=True, exist_ok=True)
    (w / "Orders overview.html").write_text(wireframe(), encoding="utf-8")
    r = out / "4 made-up requirements"
    r.mkdir(parents=True, exist_ok=True)
    (r / "Requirements.md").write_text(REQUIREMENTS, encoding="utf-8")
    (out / "README.txt").write_text(README, encoding="utf-8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(KIT.parent / "pbik-walkthrough-inputs"))
    a = ap.parse_args(argv)
    print(f"wrote the made-up inputs in {make(a.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
