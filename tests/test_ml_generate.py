from __future__ import annotations

import random
import subprocess
import tempfile
import unittest
from pathlib import Path

from cobol2rust import frontend
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.uri import is_valid
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"

DATA = """01 out pic x(80).
01 num pic 9(3).
01 r.
   03 a pic x(3).
   03 n pic 9v9.
   03 b comp pic 9(4).
   03 g.
      05 g1 pic x.
   03 c redefines g pic x.
66 ren renames a of r.
66 span renames a of r thru n of r.
01 d.
   03 filler pic x.
01 e.
   03 e1 pic x.
   03 f.
      05 e1 pic x.
01 j pic x(9) justified.
"""


def program(statement, data=DATA):
    return ("identification division.\nprogram-id. ml.\ndata division.\nworking-storage section.\n"
            f"{data}procedure division.\n{statement}\nstop run.\n")


# Forms cobc 3.2 refuses, with the diagnostic cobol2rust gives.
REFUSALS = [
    ("xml generate out from r suppress every numeric when zero every element when space",
     "WHEN clause must follow EVERY clause"),
    ("xml generate out from r suppress every element a when space", "WHEN clause must follow EVERY clause"),
    ('xml generate out from r namespace ""', "NAMESPACE must be a valid URI"),
    ('xml generate out from r namespace "urn:x" namespace-prefix "1p"', "NAMESPACE-PREFIX must be a valid XML name"),
    ("xml generate out from r namespace 12", "NAMESPACE must be alphanumeric or national"),
    ('xml generate out from r name of a is "1a"', "NAME OF literal must be a valid XML identifier"),
    ('xml generate out from r name of num is "x"', "NAME OF item must be the input record or a child of it"),
    ('xml generate out from r name of c is "x"', "NAME OF item may not be an ignored item"),
    ("xml generate out from r type of g is attribute", "TYPE OF item must be elementary"),
    ("xml generate out from r type of r is attribute", "TYPE OF item must be elementary"),
    ("xml generate out from num type of num is attribute", "TYPE OF item must be a child of the input record"),
    ("xml generate out from r suppress g when space", "SUPPRESS item with WHEN clause must be elementary"),
    ("xml generate out from r suppress b when space", "SUPPRESS WHEN SPACE item must be USAGE DISPLAY"),
    ("xml generate out from r suppress n when high-value", "SUPPRESS WHEN HIGH-VALUE item must be an integer"),
    ("xml generate num from r", "receiving item must be alphanumeric or national"),
    ("xml generate j from r", "receiving item may not have JUSTIFIED clause"),
    ("xml generate out (2:3) from r", "receiving item may not be reference modified"),
    ("xml generate out from r (1:2)", "input record may not be reference modified"),
    ("xml generate out from span", "input record may not have RENAMES clause"),
    ("xml generate out from d", "all the children of 'D' are ignored"),
    ("xml generate out from e", "subrecords with non-unique names"),
    ("xml generate out from r count in n", "COUNT IN item 'N' must be an integer"),
    ("xml generate out from r with attributes with xml-declaration",
     "XML-DECLARATION clause must come before ATTRIBUTES"),
    ("xml generate out from r with xml-declaration encoding 1208", "ENCODING clause must come before XML-DECLARATION"),
    ("json generate out from r name of a is omitted", "OMITTED only valid for source identifier"),
    ("json generate out from r name of r is '1x'", "NAME OF literal must be a valid JSON identifier"),
]


def in_cobol85(function):
    previous, frontend.STD = frontend.STD, "cobol85"
    try:
        return function()
    finally:
        frontend.STD = previous


class MlGenerateTests(unittest.TestCase):
    def test_refusals(self):
        for statement, message in REFUSALS:
            with self.subTest(statement=statement), self.assertRaisesRegex(CobolError, message):
                Parser(program(statement)).parse()

    def test_contained_program_has_no_register(self):
        # cb_build_register_internal_code: none in a nested program.
        source = (program("call 'inner'")[:-len("stop run.\n")] + "stop run.\n"
                  "identification division.\nprogram-id. inner.\nprocedure division.\n"
                  "xml generate out from r.\nend program inner.\nend program ml.\n")
        with self.assertRaisesRegex(CobolError, "missing register definition"):
            Parser(source).parse()

    def test_cobol85_has_no_statement(self):
        with self.assertRaisesRegex(CobolError, "instruction non prise en charge: XML"):
            in_cobol85(lambda: Parser(program("xml generate out from r")).parse())

    def test_endless_codegen_of_cobc_is_refused(self):
        # get_prev_ml_tree_entry loops on an element whose first attribute
        # leads back to it: cobc never ends.
        with self.assertRaisesRegex(CobolError, "cobc ne termine pas"):
            Parser(program("xml generate out from r2 type of k1 is attribute",
                           DATA + "01 r2.\n   03 k.\n      05 k1 pic x.\n   03 h pic x.\n")).parse()

    def test_suppress_checks_follow_codegen(self):
        # output_ml_suppress_checks: last element first; the attributes of a
        # root with children are never evaluated.
        parsed = Parser(program("xml generate out from r with attributes suppress every attribute when zero "
                                "when space")).parse()
        rust, _ = Emitter(parsed).generate()
        self.assertIn("runtime::ml::xml_generate", rust)
        stmt = next(s for block in parsed.blocks for s in block.body if s.op == "ml_generate")
        tree = stmt.args[0]["tree"]
        self.assertEqual([a.name for a in tree.attrs], [b"a", b"n", b"b"])
        checked = [check[1] for check in stmt.args[0]["checks"]]
        self.assertNotIn(tree.attrs[0], checked)
        self.assertEqual(checked[0].name, b"g1")

    def test_renames_without_thru_is_its_item(self):
        stmt = next(s for block in Parser(program("xml generate out from ren")).parse().blocks
                    for s in block.body if s.op == "ml_generate")
        self.assertEqual(stmt.args[0]["tree"].name, b"ren")

    def test_registers_are_global_binary(self):
        fields = Parser(program("display xml-code json-code")).parse().fields
        for name in ("XML-CODE", "JSON-CODE"):
            self.assertEqual((fields[name].usage, fields[name].digits, fields[name].is_global), ("BINARY", 9, True))

    def test_uri_validator(self):
        for text, valid in [(b"http://www.w3.org/1999/xhtml", True), (b"", True), (b" ", False), (b"a b", False),
                            (b"%zz", False), (b"http://[::1]:80/", True), (b"http://h:99999999999/", False),
                            (b"1abc:def", False), (b"#frag", True), (b"\x00", True)]:
            with self.subTest(text=text):
                self.assertEqual(is_valid(text), valid)


@unittest.skipUnless(find_tool("cobc"), "GnuCOBOL required")
class MlGenerateCobcTests(unittest.TestCase):
    def test_cobc_refuses_the_same_forms(self):
        with tempfile.TemporaryDirectory() as directory:
            for statement, _ in REFUSALS:
                with self.subTest(statement=statement):
                    path = Path(directory) / "ml.cob"
                    path.write_text(program(statement))
                    result = subprocess.run([find_tool("cobc"), "-free", "-fsyntax-only", str(path)],
                                            capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(find_tool("gcc") and find_tool("xml2-config"), "gcc and libxml2 required")
    def test_uri_validator_matches_libxml2(self):
        harness = ("#include <stdio.h>\n#include <string.h>\n#include <libxml/uri.h>\n"
                   "int main(void){char l[4096];while(fgets(l,sizeof l,stdin)){size_t n=strlen(l);"
                   "if(n&&l[n-1]=='\\n')l[--n]=0;xmlURIPtr p=xmlParseURI(l);putchar(p?'1':'0');"
                   "if(p)xmlFreeURI(p);}return 0;}\n")
        flags = subprocess.run(["xml2-config", "--cflags", "--libs"], capture_output=True, text=True).stdout.split()
        rng = random.Random(3)
        alphabet = list("ab:/?#[]@!$&'()*+,;=-._~%09AFz ") + ["%41", "//", "http://", "[::1]", ":80", "\x7f", "\xe9"]
        samples = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12))) for _ in range(5000)]
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory) / "uri.c", Path(directory) / "uri"
            source.write_text(harness)
            subprocess.run(["gcc", "-o", str(binary), str(source), *flags], check=True)
            data = ("\n".join(samples) + "\n").encode("latin-1")
            answers = subprocess.run([str(binary)], input=data, capture_output=True, check=True).stdout.decode()
        self.assertEqual(len(answers), len(samples))
        for text, answer in zip(samples, answers):
            self.assertEqual(is_valid(text.encode("latin-1")), answer == "1", text)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class MlGenerateNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURES / "ml_generate.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertIn("x18 <Sticky><SH>h</SH></Sticky>", lines)
        self.assertIn("x23 <?xml version=\"1.0\"?> |00057|+000000400", lines)
        self.assertIn("x24 04520|xxxxxxxxxxxxxxx</BX>|+000000000", lines)

    def test_decimal_comma_and_float_content(self):
        # dpc-in-data: xml; a floating-point content is cob_fatal_error.
        report = verify(FIXTURES / "ml_generate_comma.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_exit"], 1)
        self.assertIn("non-implemented XML I/O", report["cobol_stderr"])
        self.assertEqual(report["cobol_stdout"].splitlines()[0], "<R><A>-1,50</A><B>01,50</B><C>0,250</C></R>")


if __name__ == "__main__":
    unittest.main()
