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


def program(storage, name="external-case", body="goback."):
    return (f"identification division.\nprogram-id. {name}.\ndata division.\nworking-storage section.\n"
            f"{storage}\nprocedure division.\n{body}\n")


class ExternalAsFrontendTests(unittest.TestCase):
    def test_external_names_follow_cb_to_cname(self):
        fields = Parser(program("01 a-b pic x external.\n01 c pic x external as 'my name-1'.")).parse().fields
        self.assertEqual((fields["A-B"].external_name, fields["C"].external_name), ("A_B", "MY_NAME_1"))

    def test_c_errno_and_invalid_clauses_are_refused(self):
        for storage in ("01 e usage binary-long external as 'errno'.", "01 e pic x external as name.",
                        "01 g. 05 e pic x external as 'x'."):
            with self.subTest(storage=storage), self.assertRaises(CobolError):
                Emitter(Parser(program(storage)).parse()).generate()


@unittest.skipUnless(find_tool("cargo"), "Cargo required")
class ExternalAsRuntimeTests(unittest.TestCase):
    def test_larger_redeclaration_is_the_libcob_error(self):
        source = (program("01 item pic x(2) external.", "external-main", 'call "external-sub"\nstop run.')
                  + "end program external-main.\n"
                  + program("01 item pic x(3) external.", "external-sub") + "end program external-sub.\n")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "larger.cob"
            path.write_text(source, encoding="utf-8")
            convert(path, root / "rust", fmt="free")
            result = subprocess.run([str(build_rust(root / "rust"))], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"libcob: error: EXTERNAL item 'ITEM' previously allocated with size 2, requested size is 3",
                      result.stderr)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ExternalAsNativeTests(unittest.TestCase):
    def test_names_and_smaller_redeclaration_match_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "external_as.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "sub [abcd] [1234]\nmain [WXYZef] [9876]\n")
        self.assertIn("EXTERNAL item 'EXT_NAME' previously allocated with size 6", report["cobol_stderr"])


if __name__ == "__main__":
    unittest.main()
