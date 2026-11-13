"""Synthetic-to-live tests (docs/design/synth-to-live.md) on made-up sample data only.

    python tools\\pbik\\tests\\test_synth.py

The sample model (tests/synth_sample/Example Live.SemanticModel) is invented: no real names, IDs, values or colours.
"""
import json, os, pathlib, shutil, sys, tempfile, unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
SAMPLE = HERE / "synth_sample"
LIVE = SAMPLE / "Example Live.SemanticModel"
sys.path.insert(0, str(HERE.parent))

from pbikit import dataclass_ as DC, synth as S  # noqa: E402


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
