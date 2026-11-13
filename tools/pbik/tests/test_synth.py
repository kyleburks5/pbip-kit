"""Synthetic-to-live tests (docs/design/synth-to-live.md) on made-up sample data only.

    python tools\\pbik\\tests\\test_synth.py

The sample model (tests/synth_sample/Example Live.SemanticModel) is invented: no real names, IDs, values or colours.
"""
import json, os, pathlib, re, shutil, sys, tempfile, unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
SAMPLE = HERE / "synth_sample"
LIVE = SAMPLE / "Example Live.SemanticModel"
sys.path.insert(0, str(HERE.parent))

from pbikit import dataclass_ as DC, synth as S, synthgen as G, tmdl  # noqa: E402
LAYOUT = SAMPLE / "layout.json"
PLANNED = {"Amount Share": {"table": "_Measures", "formatString": "0.0%",
                            "expression": "DIVIDE ( [Total Amount], CALCULATE ( [Total Amount], ALL ( Area ) ) )"}}


def say(*texts):
    it = iter(texts)
    return lambda prompt: next(it)


def script_from(folder):
    """The sample model as one TMDL createOrReplace script (tables and relationships, one level deeper)."""
    d = pathlib.Path(folder) / "definition"
    parts = [f.read_text(encoding="utf-8") for f in sorted((d / "tables").glob("*.tmdl"))]
    parts += [(d / "relationships.tmdl").read_text(encoding="utf-8")]
    body = "\n".join("\t" + ln if ln.strip() else ln for p in parts for ln in p.splitlines())
    return "createOrReplace\n\n" + body + "\n"


def resolve_all(root):
    for kind, res in (("m-code", "synthesize"), ("connection", "synthesize"), ("entity", "synthesize"),
                      ("rls", "not reproduced"), ("enter-data", "synthesize")):
        S.resolve(root, kind, res, why=f"{kind}: sample rule", every=True)


def approved_project(root, planned=True):
    """A project with an approved contract of the sample model and (optionally) the planned measure."""
    S.contract(LIVE, root)
    resolve_all(root)
    S.approve(root, "Sample Person", ask=say("Example Live"), out=lambda *a: None)
    if planned:
        S.write_json(root / "design/specs/generate.json", {"seed": 7, "dateRange": ["2023-01-01", "2025-12-31"],
                                                          "plannedMeasures": PLANNED, "hints": {}, "deviations": []})


class Tmp(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="pbik_synth_"))
        (self.root / "design" / "specs").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class DataClassTests(Tmp):
    """0a: data classes, the restricted guard and person-only confirmation."""

    def test_default_set_and_lowering_is_person_only(self):
        self.assertEqual(DC.data_class(self.root), "internal")
        DC.set_class(self.root, "restricted")
        self.assertEqual(DC.data_class(self.root), "restricted")
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), self.assertRaises(DC.Refused):
            DC.set_class(self.root, "public")
        with self.assertRaises(DC.Refused):
            DC.set_class(self.root, "public", ask=say("yes"))
        DC.set_class(self.root, "public", ask=say("PUBLIC"))
        self.assertEqual(DC.data_class(self.root), "public")

    def test_restricted_guard(self):
        self.assertIsNone(DC.guard(self.root, "dax"))
        DC.set_class(self.root, "restricted")
        self.assertIn("no synthetic model", DC.guard(self.root, "dax"))
        m = self.root / "X.SemanticModel" / "definition"
        m.mkdir(parents=True)
        (m / "model.tmdl").write_text(f"model Model\n\nannotation {DC.SYNTH_MARK} = 1\n", encoding="utf-8")
        self.assertIsNone(DC.guard(self.root, "screenshot"))
        st = self.root / ".pbik" / "bind"
        st.mkdir(parents=True)
        (st / "state.json").write_text(json.dumps({"mode": "live", "model": "Example"}), encoding="utf-8")
        self.assertIn("bound to the live model", DC.guard(self.root, "screenshot"))

    def test_agent_shell_is_never_a_person(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            self.assertFalse(DC.person_present())
            with self.assertRaises(DC.Refused):
                DC.confirm("ok?", "YES")


class ContractTests(Tmp):
    """0b, 0c: the contract from TMDL (folder, createOrReplace script, TMSL) and its person-only approval."""

    def test_contract_from_folder_flags_and_copies_no_source_values(self):
        c, out = S.contract(LIVE, self.root)
        self.assertEqual(sorted(c["tables"]), sorted(["Orders", "Calendar", "Area", "Member", "Plan Option",
                                                      "Unused Table", "_Measures"]))
        self.assertEqual(c["tables"]["Orders"]["columns"]["Amount"], {"type": "decimal"})
        self.assertEqual(c["tables"]["Calendar"]["columns"]["Month"]["sortBy"], "Month No")
        kinds = {(f["kind"], f["table"]) for f in c["flags"]}
        for k in (("enter-data", "Plan Option"), ("m-code", "Orders"), ("connection", "Orders"), ("rls", "Area"),
                  ("entity", "Member"), ("connection", None)):
            self.assertIn(k, kinds)
        text = out.read_text(encoding="utf-8")
        for secret in ("example-server", "example-db", "North", "Show all", "area.csv"):
            self.assertNotIn(secret, text, "the contract never copies source values")

    def test_contract_from_scripts(self):
        tm = self.root / "model.tmdl"
        tm.write_text(script_from(LIVE), encoding="utf-8")
        a = S.build_contract(tm, self.root)
        b = S.build_contract(LIVE, self.root)
        self.assertEqual(a["tables"]["Orders"], b["tables"]["Orders"])
        self.assertEqual(a["relationships"], b["relationships"])
        tmsl = {"createOrReplace": {"object": {"database": "Sample"}, "database": {"name": "Sample", "model": {
            "tables": [{"name": "T", "columns": [{"name": "K", "dataType": "int64"}],
                        "measures": [{"name": "N", "expression": ["COUNTROWS ( T )"]}],
                        "partitions": [{"source": {"type": "m", "expression": "Sql.Database(\"x\", \"y\")"}}]}],
            "roles": [{"name": "R", "tablePermissions": [{"name": "T", "filterExpression": "TRUE"}]}]}}}}
        js = self.root / "model.json"
        js.write_text(json.dumps(tmsl), encoding="utf-8")
        c = S.build_contract(js, self.root)
        self.assertEqual(c["model"], "Sample")
        self.assertEqual(c["tables"]["T"]["measures"]["N"]["expression"], "COUNTROWS ( T )")
        self.assertEqual(sorted(f["kind"] for f in c["flags"]), ["connection", "m-code", "rls"])

    def test_resolve_records_rules_and_approve_is_person_only(self):
        S.contract(LIVE, self.root)
        with self.assertRaises(S.ContractError):
            S.approve(self.root, "Sample Person", ask=say("Example Live"), out=print)  # flags still open
        with self.assertRaises(S.ContractError):
            S.resolve(self.root, "rls", "synthesize", every=True)            # not a resolution for RLS
        resolve_all(self.root)
        c = S.read_json(self.root / "design/specs/contract.json")
        self.assertTrue(all(f["resolution"] and f["rule"] for f in c["flags"]))
        self.assertEqual(len(c["rules"]), 5)
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), self.assertRaises(DC.Refused):
            S.approve(self.root, "Sample Person")
        with self.assertRaises(DC.Refused):
            S.approve(self.root, "Sample Person", ask=say("wrong name"), out=lambda *a: None)
        c = S.approve(self.root, "Sample Person", ask=say("Example Live"), out=lambda *a: None)
        self.assertTrue(S.approved(c))
        self.assertEqual(c["approval"]["by"], "Sample Person")
        c["tables"]["Orders"]["columns"]["Amount"]["type"] = "double"
        self.assertFalse(S.approved(c), "any change voids the approval")
        # a new contract from the same model keeps the rules and pre-fills every flag from them
        c2, _ = S.contract(LIVE, self.root)
        self.assertTrue(all(f["resolution"] for f in c2["flags"]))


class GenerateTests(Tmp):
    """0d: slice, generate (deterministic inline DATATABLEs) and verify against the contract."""

    def test_slice_keeps_what_the_pages_need(self):
        approved_project(self.root)
        g, missing = S.slice_(self.root, LAYOUT)
        sl = g["slice"]
        self.assertEqual(missing, [])
        self.assertNotIn("Unused Table", sl)
        self.assertNotIn("Member", sl, "no visual or measure uses it")
        self.assertIn("Unused Measure", c_measures(self.root), "still in the contract")
        self.assertEqual(sorted(sl["_Measures"]["measures"]),
                         sorted(["Total Amount", "Amount Share", "Amount LY", "Avg Amount", "Total Units"]))
        self.assertEqual(sorted(sl["Orders"]["columns"]), sorted(["Amount", "Units", "OrderDate", "AreaKey"]))
        self.assertIn("Month No", sl["Calendar"]["columns"], "sort-by column")
        self.assertIn("Date", sl["Calendar"]["columns"], "relationship key and SAMEPERIODLASTYEAR")

    def test_generate_is_deterministic_and_verifies(self):
        approved_project(self.root)
        S.slice_(self.root, LAYOUT)
        f = G.generate(self.root, "Example Synthetic")
        first = {p.name: p.read_bytes() for p in f.rglob("*.tmdl")}
        G.generate(self.root, "Example Synthetic")
        self.assertEqual(first, {p.name: p.read_bytes() for p in f.rglob("*.tmdl")}, "same seed, same files")
        self.assertTrue(DC.is_synthetic(f))
        errs, notes = G.verify(self.root, f)
        self.assertEqual(errs, [])
        m = tmdl.load(f)
        self.assertEqual(m.tables["Orders"].columns["Amount"].data_type, "decimal")
        self.assertIn("DATATABLE", m.tables["Orders"].partitions[0][1])
        self.assertIn("PBIK_Planned", (f / "definition/tables/_Measures.tmdl").read_text(encoding="utf-8"))
        text = "".join(x.decode() for x in first.values())
        for secret in ("example-server", "Show all", "North"):
            self.assertNotIn(secret, text)
        # fact keys come from the dimension
        src = m.tables["Orders"].partitions[0][1]
        self.assertTrue(re.search(r'\{ "\d{4}-\d{2}-\d{2}", [1-8], [\d.]+, \d+ \}', src), src[:300])
        # tampering is caught
        t = f / "definition/tables/Orders.tmdl"
        t.write_text(t.read_text(encoding="utf-8").replace("dataType: decimal", "dataType: double"), encoding="utf-8")
        self.assertTrue(any("Amount" in e for e in G.verify(self.root, f)[0]))

    def test_generate_needs_an_approved_contract_and_a_fresh_slice(self):
        approved_project(self.root)
        S.slice_(self.root, LAYOUT)
        S.resolve(self.root, "F1", "drop")                       # clears the approval
        with self.assertRaises(S.ContractError):
            G.generate(self.root, "X")


class KeepRowsTests(Tmp):
    """Item 7: an option table keeps its exact rows and order when the contract marks it and a person types KEEP n."""

    def setUp(self):
        super().setUp()
        S.contract(LIVE, self.root)
        resolve_all(self.root)
        self.flag = next(f["id"] for f in S.read_json(self.root / "design/specs/contract.json")["flags"]
                         if f["kind"] == "enter-data" and f["table"] == "Plan Option")

    def test_keep_rows_needs_the_mark_and_a_typed_keep(self):
        S.resolve(self.root, self.flag, S.KEEP_ROWS, why="option labels drive the slicer")
        said = []
        with self.assertRaises(DC.Refused):
            S.approve(self.root, "Sample Person", ask=say("Example Live", "KEEP 2"), out=said.append)
        self.assertIn("    Show all | 1", said, "approve prints the rows it keeps")
        self.assertFalse(S.approved(S.read_json(self.root / "design/specs/contract.json")))
        c = S.approve(self.root, "Sample Person", ask=say("Example Live", "KEEP 3"), out=lambda *a: None)
        self.assertEqual(c["tables"]["Plan Option"]["rows"],
                         {"columns": ["Option Label", "Option Order"],
                          "rows": [["Show all", 1], ["Top ten", 2], ["Bottom ten", 3]]})
        S.write_json(self.root / "design/specs/generate.json", {"seed": 3, "hints": {}, "plannedMeasures": PLANNED})
        S.slice_(self.root, LAYOUT)
        f = G.generate(self.root, "Kept")
        src = (f / "definition/tables/Plan Option.tmdl").read_text(encoding="utf-8")
        self.assertLess(src.index('"Show all"'), src.index('"Top ten"'))
        self.assertLess(src.index('"Top ten"'), src.index('"Bottom ten"'))
        # rows edited after the person's KEEP void the approval
        c["tables"]["Plan Option"]["rows"]["rows"][0][0] = "Edited"
        S.write_json(self.root / "design/specs/contract.json", c)
        with self.assertRaises(S.ContractError):
            G.generate(self.root, "Kept")

    def test_never_for_entity_or_other_flags(self):
        cf = self.root / "design/specs/contract.json"
        with self.assertRaises(S.ContractError):
            S.resolve(self.root, "m-code", S.KEEP_ROWS, every=True)
        c = S.read_json(cf)
        c["tables"]["Plan Option"]["entity"] = True
        S.write_json(cf, c)
        with self.assertRaises(S.ContractError):
            S.resolve(self.root, self.flag, S.KEEP_ROWS)
        c["tables"]["Plan Option"]["rows"] = {"columns": ["Option Label"], "rows": [["x"]]}
        with self.assertRaises(S.ContractError):
            G.check_kept_rows(c, {"slice": {"Plan Option": {}}})


class ShapeHintTests(Tmp):
    """Item 8: trend, seasonality and month-end dates."""

    def dates(self, hints):
        approved_project(self.root)
        g = S.read_json(self.root / "design/specs/generate.json")
        g["hints"] = hints
        S.write_json(self.root / "design/specs/generate.json", g)
        S.slice_(self.root, LAYOUT)
        f = G.generate(self.root, "Shaped")
        src = (f / "definition/tables/Orders.tmdl").read_text(encoding="utf-8")
        import datetime as dt
        return [dt.date.fromisoformat(x) for x in re.findall(r'\{ "(\d{4}-\d{2}-\d{2})"', src)]

    def test_trend_and_seasonality(self):
        d = self.dates({"Orders": {"rows": 3000, "trend": 0.4, "seasonality": [1] * 11 + [3]}})
        self.assertEqual(len(d), 3000)
        per_year = [sum(1 for x in d if x.year == y) for y in (2023, 2024, 2025)]
        self.assertLess(per_year[0], per_year[1])
        self.assertLess(per_year[1], per_year[2])
        dec = sum(1 for x in d if x.month == 12)
        self.assertGreater(dec, 2 * (len(d) - dec) / 11, "December is about three times a normal month")

    def test_month_end(self):
        d = self.dates({"Orders": {"rows": 200, "monthEnd": ["OrderDate"]}})
        self.assertTrue(all(G.month_end(x) == x for x in d))
        import random
        plain = G.fact_dates(random.Random(1), {"dateRange": ["2024-01-01", "2024-12-31"]}, {"monthEnd": True}, 50)
        self.assertTrue(all(G.month_end(x) == x for x in plain))
        with self.assertRaises(S.ContractError):
            G.month_weights({}, {"seasonality": [1, 2]})


class PackTests(Tmp):
    """Item 15: register, project new, drift and approve (only the affected tables regenerated)."""

    def setUp(self):
        super().setUp()
        approved_project(self.root)
        S.slice_(self.root, LAYOUT)
        self.model = G.generate(self.root, "Example Synthetic")
        DC.set_class(self.root, "restricted")
        self.packs = pathlib.Path(tempfile.mkdtemp(prefix="pbik_packs_"))
        self.quiet = lambda *a: None

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.packs, ignore_errors=True)

    def test_register_and_new_project(self):
        from pbikit import packs as PK
        with self.assertRaises(PK.PackError):
            PK.register(self.root, self.root / "packs", out=self.quiet)          # inside the project
        with self.assertRaises(PK.PackError):
            PK.register(self.root, KIT / "packs-here", KIT, out=self.quiet)      # inside the kit
        with self.assertRaises(PK.PackError):                                     # in the kit's git repository
            PK._outside(KIT / "tools" / "x", self.root, KIT / "design")
        pack, v = PK.register(self.root, self.packs, out=self.quiet)
        self.assertEqual(v, 1)
        info = S.read_json(pack / "pack.json")
        self.assertEqual((info["dataClass"], info["versions"][0]["approver"]), ("restricted", "Sample Person"))
        self.assertEqual((self.packs / ".gitignore").read_text(encoding="utf-8"), "*\n")
        self.assertTrue((pack / "v1" / "model" / "Example Synthetic.SemanticModel").is_dir())
        c = S.read_json(pack / "v1" / "contract.json")
        self.assertTrue(c["rules"] and all(f["resolution"] for f in c["flags"]), "resolutions and their rules")
        new = pathlib.Path(tempfile.mkdtemp(prefix="pbik_new_"))
        try:
            PK.project_new(new, pack, out=self.quiet)
            self.assertEqual(DC.data_class(new), "restricted")
            self.assertTrue(S.approved(S.read_json(new / "design/specs/contract.json")))
            self.assertTrue(DC.is_synthetic(new / "Example Synthetic.SemanticModel"))
            self.assertEqual(G.verify(new, new / "Example Synthetic.SemanticModel")[0], [])
            with self.assertRaises(PK.PackError):
                PK.project_new(new, pack, out=self.quiet)
        finally:
            shutil.rmtree(new, ignore_errors=True)

    def test_drift_and_approve(self):
        from pbikit import packs as PK
        pack, _ = PK.register(self.root, self.packs, out=self.quiet)
        v1 = pack / "v1" / "model" / "Example Synthetic.SemanticModel" / "definition" / "tables"
        changed = self.packs / "changed.SemanticModel"
        shutil.copytree(LIVE, changed)
        t = changed / "definition" / "tables"
        (t / "Orders.tmdl").write_text((t / "Orders.tmdl").read_text(encoding="utf-8").replace(
            "column Units\n\t\tdataType: int64", "column Units\n\t\tdataType: double"), encoding="utf-8")
        (t / "Area.tmdl").write_text((t / "Area.tmdl").read_text(encoding="utf-8").replace(
            "\tcolumn Region\n", "\tcolumn Zone\n\t\tdataType: string\n\t\tsourceColumn: Zone\n\n\tcolumn Region\n"),
            encoding="utf-8")
        (t / "Extra Choice.tmdl").write_text((t / "Unused Table.tmdl").read_text(encoding="utf-8").replace(
            "'Unused Table'", "'Extra Choice'"), encoding="utf-8")
        said = []
        d = PK.drift(pack, changed, out=said.append)
        whats = sorted((x["change"], x["what"]) for x in d["changes"])
        self.assertEqual(whats, sorted([("changed", "Orders[Units]"), ("added", "Area[Zone]"),
                                        ("added", "Extra Choice"), ("added", "Extra Choice[Note]")]))
        new_flag = next(f for f in d["contract"]["flags"] if f["table"] == "Extra Choice")
        self.assertEqual(new_flag["resolution"], "synthesize", "pre-filled from the saved enter-data rule")
        self.assertIn(new_flag["id"], d["prefilled"])
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), self.assertRaises(DC.Refused):
            PK.approve(pack, "Sample Person", out=self.quiet)
        v, affected = PK.approve(pack, "Sample Person", ask=say("Example Live"), out=self.quiet)
        self.assertEqual(v, 2)
        self.assertEqual(affected, ["Area", "Orders"])
        v2 = pack / "v2" / "model" / "Example Synthetic.SemanticModel" / "definition" / "tables"
        for name in ("Calendar.tmdl", "_Measures.tmdl", "Plan Option.tmdl"):
            self.assertEqual((v1 / name).read_bytes(), (v2 / name).read_bytes(), f"{name} not regenerated")
        self.assertIn("dataType: double", (v2 / "Orders.tmdl").read_text(encoding="utf-8"))
        info = S.read_json(pack / "pack.json")
        self.assertEqual((info["current"], info["versions"][-1]["regenerated"]), (2, ["Area", "Orders"]))
        self.assertFalse((pack / "drift.json").exists())
        self.assertTrue(S.approved(S.read_json(pack / "v2" / "contract.json")))


def c_measures(root):
    return S.read_json(root / "design/specs/contract.json")["tables"]["_Measures"]["measures"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
