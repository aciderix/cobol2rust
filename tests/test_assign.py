"""ASSIGN forms of real programs and libcob's run-time file name mapping."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust import frontend
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def program(select, data="", procedure="stop run."):
    return ("identification division.\nprogram-id. a.\nenvironment division.\ninput-output section.\n"
            f"file-control.\n    {select}\ndata division.\nfile section.\nfd f.\n01 r pic x(4).\n"
            f"working-storage section.\n{data}\nprocedure division.\n{procedure}\n")


class ParseTests(unittest.TestCase):
    def spec(self, select, data=""):
        return Parser(program(select, data)).parse().files["F"]

    def test_undeclared_word_is_the_file_name_as_written(self):
        # implicit-assign-dynamic-var: the word, case kept, is the name.
        self.assertEqual(self.spec("select f assign to outFile.").path.text, "outFile")
        self.assertEqual(self.spec("select f assign f.").path.text, "f")

    def test_declared_item_is_read_at_open(self):
        spec = self.spec("select f assign to n.", "01 g. 02 n pic x(8) value 'x.dat'.")
        self.assertIsNone(spec.path)
        self.assertEqual(spec.assign_field, "G.N")
        rust = "\n".join(Emitter(Parser(program("select f assign to n.", "01 n pic x(8).",
                                                "open input f. close f. stop run.")).parse()).program_lines()[0])
        self.assertIn(".assign(&", rust)

    def test_external_drops_labels_and_devices(self):
        self.assertEqual(self.spec("select f assign to external UT-S-Data1.").path.text, "Data1")
        self.assertEqual(self.spec("select f assign to disk.").path.text, "f")
        self.assertEqual(self.spec("select f assign to disk 'x.dat'.").path.text, "x.dat")
        self.assertEqual(self.spec("select f assign to card-reader 'x'.").organization, "LINE SEQUENTIAL")
        self.assertEqual(self.spec("select f assign to card-reader 'x' organization sequential.").organization,
                         "SEQUENTIAL")

    def test_cobol85_assign_clause_is_external(self):
        frontend.STD = "cobol85"
        try:
            self.assertEqual(self.spec("select f assign to UT-S-NAME.", "01 name pic x(8).").path.text, "NAME")
            with self.assertRaises(CobolError):
                self.spec("select f assign using n.", "01 n pic x(8).")
        finally:
            frontend.STD = "default"

    def test_refusals(self):
        for select, data in [("select f assign to display.", ""), ("select f assign to printer.", ""),
                             ("select f assign to line advancing file 'x'.", ""),
                             ("select f assign using undeclared.", ""),
                             ("select f assign to dynamic undeclared.", ""),
                             ("select f assign to c.", "01 v pic x. 88 c value 'y'."),
                             ("select f assign to t.", "01 g. 02 t pic x occurs 2."),
                             ("select f assign to external 'x'.", "")]:
            with self.subTest(select=select), self.assertRaises(CobolError):
                self.spec(select, data)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NativeTests(unittest.TestCase):
    def test_assign_forms_match_gnucobol(self):
        report = verify(FIXTURES / "assign_names.cob", data_dir=FIXTURES / "assign_names.data")
        self.assertTrue(report["match"], report)
        for name in ("outImplicit", "Extern", "OUT-DEVICE", "Out-Own", "using.dat", "second-name.dat"):
            self.assertIn(name, report["cobol_files"])

    def test_file_name_mapping_matches_libcob(self):
        names = ["plain", "lower", "bare", "name.ext", "$DOLLAR", "$unset", '"quoted"', "1digit", "qv",
                 "$DIR/sub.dat", "a/$DIR/b.dat", "a/$NOPE/c.dat", "$NOPE/d.dat", "first/second.dat", "end"]
        file_env = {"DD_plain": "mapped-dd.dat", "dd_lower": "mapped-lower.dat", "bare": "mapped-bare.dat",
                    "DD_name_ext": "dotted.dat", "DD_DOLLAR": "dollar.dat", "DD_1digit": "never.dat",
                    "DD_qv": '"quoted-value.dat"', "DIR": "dirval", "DD_first": "dirval"}
        with tempfile.TemporaryDirectory() as seed:
            for directory in ("dirval", "a", "a/dirval"):
                (Path(seed) / directory).mkdir(parents=True)
            report = verify(FIXTURES / "assign_mapping.cob", fmt="free", data_dir=Path(seed),
                            stdin=("\n".join(names) + "\n").encode(), file_env=file_env)
        self.assertTrue(report["match"], report)
        for name in ("mapped-dd.dat", "mapped-lower.dat", "mapped-bare.dat", "dotted.dat", "dollar.dat",
                     "$unset", "quoted-value.dat", "dirval/sub.dat", "dirval/second.dat"):
            self.assertIn(name, report["cobol_files"])

    def test_cob_file_path_prefixes_relative_names(self):
        with tempfile.TemporaryDirectory() as seed:
            (Path(seed) / "prefix" / "sub").mkdir(parents=True)
            report = verify(FIXTURES / "assign_mapping.cob", fmt="free", data_dir=Path(seed),
                            stdin=b"x.dat\nsub/y.dat\nend\n", file_env={"COB_FILE_PATH": "prefix"})
        self.assertTrue(report["match"], report)
        self.assertIn("prefix/x.dat", report["cobol_files"])
        self.assertIn("prefix/sub/y.dat", report["cobol_files"])


if __name__ == "__main__":
    unittest.main()
