from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from cobol2rust.cli import convert
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, compiler_env, find_tool
from tests.test_converter import program
from cobol2rust.audit import audit


class LayoutTests(unittest.TestCase):
    def test_audit_is_static_and_skips_build_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "good.cob").write_text(program("stop run."), encoding="utf-8")
            (root / "bad.cbl").write_text(program("call 'external'."), encoding="utf-8")
            (root / "build").mkdir()
            (root / "build" / "ignored.cob").write_text("unsupported", encoding="utf-8")
            before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
            result = audit(root)
            self.assertEqual((result["sources"], result["accepted"], result["blocked"]), (2, 1, 1))
            self.assertTrue(result["static_only"])
            self.assertTrue(all(not entry["verified"] for entry in result["results"]))
            self.assertEqual(before, sorted(str(p.relative_to(root)) for p in root.rglob("*")))

    def test_offsets_tables_and_overlays(self):
        p = Parser(program("stop run.", '''
01 block-a.
  05 marker pic x.
  05 row-a occurs 3 times.
    10 n pic 99.
    10 tag-a occurs 2 times pic x(3).
01 raw-a redefines block-a pic x(25).
''')).parse()
        self.assertEqual(p.memory_size, 25)
        self.assertEqual(p.fields["BLOCK-A.ROW-A.N"].offset, 1)
        self.assertEqual(p.fields["BLOCK-A.ROW-A.TAG-A"].dimensions, [(8, 3), (3, 2)])
        self.assertEqual(p.fields["RAW-A"].offset, p.fields["BLOCK-A"].offset)

    def test_reject_ambiguous_invalid_and_unmodelled_layouts(self):
        cases = [
            program("display item-a.", "01 a. 05 item-a pic 9. 01 b. 05 item-a pic 9."),
            program("display n.", "01 a. 05 n occurs 3 times pic 9."),
            program("display n(1,2).", "01 a. 05 n occurs 3 times pic 9."),
            program('display n("X").', "01 a. 05 n occurs 3 times pic 9."),
            program("stop run.", "05 orphan pic 9."),
            program("stop run.", "01 a pic 9. 05 n pic 9."),
            program("stop run.", "01 a pic x(2). 01 c pic x. 01 b redefines a pic x(2)."),
            program("stop run.", "01 a. 05 n occurs 2 to 3 depending on other pic 9."),
            program("stop run.", "01 a. 05 n occurs 3 indexed by index-a index-a pic 9."),
            program("stop run.", "01 a. 05 b occurs 10000. 10 n occurs 10000 pic x(256)."),
            program("set active-a to false.", '01 n pic x. 88 active-a value "Y".'),
            program("set active-a to true.", '01 n pic 9. 88 active-a value "Y".'),
            program("stop run.", "01 a. 88 active-a value 1."),
            program('move "x" to n(1:1).', "01 n pic 99 comp-3."),
            program('move "x" to n(1)(1:1).', "01 n pic xx."),
            program('move "x" to n(1:"A").', "01 n pic xx."),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CobolError):
                Emitter(Parser(source).parse()).generate()

    def test_reject_unsafe_variable_layouts_and_index_clauses(self):
        cases = [
            "01 n pic 9. 01 a. 05 cell-a occurs 0 to 3 depending on n pic x. 05 tail-a pic x.",
            "01 n pic 9. 01 a. 05 row-a occurs 2. 10 cell-a occurs 0 to 3 depending on n pic x.",
            "01 a. 05 n pic 9. 05 cell-a occurs 0 to 3 depending on n pic x.",
            "01 n pic 9v9. 01 a. 05 cell-a occurs 0 to 3 depending on n pic x.",
            "01 n pic 9. 01 a. 05 cell-a occurs 0 to 3 depending on n pic x. 01 alias-a redefines a pic x.",
            "01 n pic 9. 01 a. 05 alias-a redefines n pic x.",
            "01 n pic 9. 01 a. 05 cell-a occurs 3 indexed by n pic x.",
            "01 a. 05 cell-a occurs 3 indexed by idx pic x. 05 second-a occurs 2 indexed by idx pic x.",
        ]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(CobolError):
                Emitter(Parser(program("stop run.", data)).parse()).generate()

    def test_error_handlers_validate_calls_and_types(self):
        for body in [
            "compute n = 100 on size error perform absent end-compute.",
            "compute n = 1 not on size error perform absent end-compute.",
            'compute n = "X" on size error continue end-compute.',
            "compute n = 1 on size error end-compute.",
            "set n to 1.",
        ]:
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(body, "01 n pic 99.")).parse()).generate()

    def test_compound_variable_group_initialize_is_explicitly_rejected(self):
        data = "01 n pic 9. 01 g. 05 row-a occurs 0 to 3 depending on n. 10 text-a pic x. 10 number-a pic 99."
        with self.assertRaisesRegex(CobolError, "INITIALIZE de groupe variable"):
            Emitter(Parser(program("initialize g.", data)).parse()).generate()


@unittest.skipUnless(find_tool("cargo"), "Cargo required")
class StructureRuntimeTests(unittest.TestCase):
    def test_native_index_capacity_is_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.cob"
            source.write_text(program("accept idx display idx stop run.",
                                      "01 table-a. 05 cell-a occurs 2 indexed by idx pic x."), encoding="utf-8")
            convert(source, root / "rust")
            binary = build_rust(root / "rust")
            for stdin in (b"2147483648\n", b"-2147483649\n"):
                with self.subTest(stdin=stdin):
                    result = subprocess.run([str(binary)], input=stdin, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 70)
                    # cob_accept moves the line as text: refused for an index.
                    self.assertIn(b"index", result.stderr)

    def test_variable_count_and_active_subscripts_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.cob"
            source.write_text(program("accept n accept i display cell-a(i) stop run.",
                                      "01 n pic 9. 01 i pic 9. 01 table-a. 05 cell-a occurs 0 to 3 depending on n pic x value 'A'."), encoding="utf-8")
            convert(source, root / "rust")
            binary = build_rust(root / "rust")
            for stdin, message in [(b"4\n1\n", "count out of bounds"), (b"1\n2\n", "subscript out of bounds"), (b"0\n1\n", "subscript out of bounds")]:
                with self.subTest(stdin=stdin):
                    result = subprocess.run([str(binary)], input=stdin, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 70)
                    self.assertIn(message, result.stderr.decode())

    def test_invalid_numeric_data_is_not_swallowed_by_size_handler(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.cob"
            source.write_text(program('move "XX" to raw-a compute n = bad-a + 1 on size error display "CAUGHT" end-compute stop run.',
                                      "01 raw-a pic xx. 01 bad-a redefines raw-a pic 99. 01 n pic 99."), encoding="utf-8")
            convert(source, root / "rust")
            binary = build_rust(root / "rust")
            result = subprocess.run([str(binary)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 70)
            self.assertIn(b"invalid DISPLAY numeric data", result.stderr)
            self.assertNotIn(b"CAUGHT", result.stdout)

    def test_bad_reference_modification_is_a_named_abort(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.cob"
            source.write_text(program("accept i display text-a(i:2) stop run.",
                                      '01 i pic 99. 01 text-a pic x(5) value "ABCDE".'), encoding="utf-8")
            convert(source, root / "rust")
            binary = build_rust(root / "rust")
            for index in (b"0\n", b"5\n", b"9\n"):
                with self.subTest(index=index):
                    result = subprocess.run([str(binary)], input=index, capture_output=True, env=compiler_env(find_tool("rustc")), timeout=10)
                    self.assertEqual(result.returncode, 70)
                    self.assertIn("reference modification out of bounds", result.stderr.decode())

    def test_bad_subscripts_are_named_aborts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.cob"
            source.write_text(program("accept i display n(i) stop run.",
                                      "01 i pic 99. 01 table-a. 05 n occurs 3 pic 9 value 7."), encoding="utf-8")
            convert(source, root / "rust")
            binary = build_rust(root / "rust")
            for index in (b"0\n", b"4\n"):
                with self.subTest(index=index):
                    result = subprocess.run([str(binary)], input=index, capture_output=True, env=compiler_env(find_tool("rustc")), timeout=10)
                    self.assertEqual(result.returncode, 70)
                    self.assertIn("subscript out of bounds", result.stderr.decode())
