from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from cobol2rust.cli import convert
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, find_tool
from cobol2rust.verification import verify


def program(storage, body, linkage=""):
    return ("identification division.\nprogram-id. pointer-case.\ndata division.\nworking-storage section.\n"
            f"01 p usage pointer.\n01 x pic x(4) value \"ABCD\".\n01 b pic x(4) based.\n{storage}\n"
            f"linkage section.\n01 y pic x(4).\n{linkage}\nprocedure division.\n{body}\nstop run.\n")


class PointerFrontendTests(unittest.TestCase):
    def test_pointer_and_based_descriptions(self):
        parsed = Parser(program("01 g.\n 02 gp pointer.\n 02 gx pic x.\n01 q pointer value null.", "continue.")).parse()
        fields = parsed.fields
        # A void * of libcob: 8 bytes, NULL by default.
        self.assertEqual([(fields[name].kind, fields[name].size) for name in ("P", "G.GP", "Q")], [("pointer", 8)] * 3)
        self.assertEqual(fields["G"].size, 9)
        self.assertTrue(fields["B"].based and parsed.uses_addresses)
        rust = Emitter(parsed).generate()[0]
        self.assertIn("storage_runtime::records(&memory", rust)
        self.assertIn("storage_runtime::unbind(&result.", rust)

    def test_statements(self):
        body = ("set p to address of x. set address of y address of b to p. set p up by 2. set address of y down by 1.\n"
                "allocate 4 characters initialized to all \"z\" returning p. allocate b initialized returning p.\n"
                "if p = null or address of b <> p continue end-if. free p b. free address of b.")
        entry = Parser(program("", body)).parse().entry
        self.assertEqual([s.op for s in entry if s.op not in {"sentence_end", "if"}][:8],
                         ["set_address"] * 4 + ["allocate"] * 2 + ["free"] * 2)
        Emitter(Parser(program("", body)).parse()).generate()

    def test_cobc_errors_and_unmodelled_forms_are_refused(self):
        cases = [
            ("", "set address of x to p."),                       # not BASED or LINKAGE
            ("01 g.\n 02 gy pic x.", "set address of gy to p."),  # not level 1 or 77
            ("", "allocate x."),                                   # not BASED
            ("", "allocate 4 characters."),                       # RETURNING required
            ("01 n pic 9.", "allocate 4 characters returning n."),
            ("", "allocate 4 characters initialized to 5 returning p."),
            ("", "free x."),
            ("01 z pic x(8).", "move p to z."),
            ("01 n pic 9.", "compute n = p + 1."),
            ("01 n pic 9.", "if p = n continue end-if."),
            ("01 r pointer value 5.", "continue."),
            ("01 r pic 9 value null.", "continue."),
            ("01 r program-pointer.", "continue."),
            ("01 r pointer.", "set address of b to address of program \"x\"."),
        ]
        for storage, body in cases:
            with self.subTest(storage=storage, body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(storage, body)).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class PointerNativeTests(unittest.TestCase):
    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "pointers.cob", fmt="free")
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        # Arithmetic inside a record, a group MOVE carrying an address, the
        # ALLOCATE forms of cob_allocate and FREE of cob_free_alloc.
        self.assertIn("z 23\nx 1zz45678\n", stdout)
        self.assertIn("a4 [B1V42F  ]\nb4 null\n", stdout)
        self.assertIn("q held\nws not freed\nzero alloc null\n", stdout)
        # ASSIGN to a BASED item without storage: status 31 (cob_open).
        self.assertIn("open without name 31\n", stdout)
        # A LINKAGE item of no USING keeps its address across CANCEL; the
        # BASED storage is freed.
        self.assertTrue(stdout.endswith("keeper 1 view-of 1z\nkeeper 1 held null\n"))

    def test_pointer_tables_initialize_and_redefined_based_item(self):
        report = verify(ROOT / "tests" / "fixtures" / "pointer_tables.cob", fmt="free")
        self.assertTrue(report["match"], report)
        # INITIALIZE sets a POINTER to NULL; REPLACING names no pointer category.
        self.assertIn("init null 00 [  ]\nrepl kept 05 [zz]\n", report["cobol_stdout"])

    def test_open_without_assign_address_names_the_field_like_libcob(self):
        # cob_field_to_string: "field with NULL address", then status 31.
        source = ("identification division.\nprogram-id. null-assign.\nenvironment division.\n"
                  "input-output section.\nfile-control.\nselect f assign to n.\ndata division.\n"
                  "file section.\nfd f.\n01 r pic x.\nlinkage section.\n01 n pic x(8).\n"
                  "procedure division.\nopen input f.\nstop run.\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "null-assign.cob"
            path.write_text(source, encoding="utf-8")
            report = verify(path, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertIn("('field with NULL address')", report["cobol_stderr"])

    def run_case(self, storage, body):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "case.cob"
            source.write_text(program(storage, body), encoding="utf-8")
            convert(source, root / "rust", fmt="free")
            return subprocess.run([str(build_rust(root / "rust"))], capture_output=True, timeout=30)

    def test_unreproducible_or_undefined_accesses_are_named_stops(self):
        cases = [
            # A native address differs at each run (ASLR).
            ("", "set p to address of x. display p.", b"DISPLAY of a non-NULL address"),
            ("01 g.\n 02 gp pointer.", "set gp to address of x. display g.", b"output of a non-NULL address"),
            # The order of two storage areas is the native layout.
            ("01 x2 pic x.", "if address of x < address of x2 continue end-if.", b"order of addresses of different storage areas"),
            # Beyond an ALLOCATE area, through a NULL address, after FREE.
            ("", "allocate 2 characters returning p. set address of b to p. display b.", b"item extends beyond the storage at its address"),
            ("", "display b.", b"item without storage"),
            ("", "allocate b. set p to address of b. free b. set address of y to p. display y.", b"address of storage released by FREE"),
            # cob_allocate without INITIALIZED TO: malloc leaves the area undetermined.
            ("", "allocate b. display b.", b"read of ALLOCATE storage before it is written"),
            ("", "allocate 4 characters returning p. set address of b to p. move \"ab\" to b(1:2). display b.",
             b"read of ALLOCATE storage before it is written"),
        ]
        for storage, body, message in cases:
            with self.subTest(body=body):
                result = self.run_case(storage, body)
                self.assertEqual(result.returncode, 70, result)
                self.assertIn(message, result.stderr)


if __name__ == "__main__":
    unittest.main()
