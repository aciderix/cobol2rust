from __future__ import annotations

import json
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from cobol2rust.binary import inspect_binary, pe_info, elf_info
from cobol2rust.cli import convert, main
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser, lex, load_source, normalize
from cobol2rust.toolchain import ROOT, build_rust, build_slot, compiler_env, find_tool


def program(body, data=""):
    return ("identification division.\nprogram-id. test-program.\n" +
            ("data division. working-storage section.\n" + data + "\n" if data else "") +
            "procedure division.\n" + body)


class FrontendTests(unittest.TestCase):
    def test_strings_are_never_keywords_or_comments(self):
        p = Parser(program('display "STOP RUN" "a*>b" "a""b" stop run.')).parse()
        self.assertEqual([e.args[0] for e in p.entry[0].args[0]], ["STOP RUN", "a*>b", 'a"b'])

    def test_literal_spaces_is_not_figurative_spaces(self):
        p = Parser(program("stop run.", '01 t pic x(6) value "SPACES".')).parse()
        self.assertEqual(p.fields["T"].initial.text, "SPACES")

    def test_reject_unsupported_instead_of_skipping(self):
        cases = [
            program("call 'external'."), program("alter finish to proceed to other."),
            program("open input file-a."),
            program("exec sql select 1 end-exec."), program("alter p to proceed to q."),
            program("perform missing stop run."),
            program("stop run.", "01 n pic 9(2) occurs 1 to 3 depending on count-a."),
            program("stop run.", "01 group-a."),
            program("stop run.", "01 n usage comp-1."),
            program("stop run.", "01 n pic 9(39)."),
            program("stop run.", "01 n pic 9 value 'bad'."),
            program("display n.", "01 n pic 9. 01 n pic 9."),   # ambiguous reference
            program("stop run.", "01 x pic x(0)."),
            program("accept n from microsecond-time.", "01 n pic 9(8)."),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CobolError):
                Emitter(Parser(source).parse()).generate()

    def test_semantic_type_errors(self):
        declarations = '01 n pic 99. 01 t pic x(3).'
        for body in ['compute n = t + 1.', 'perform t times continue end-perform.']:
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(body, declarations)).parse()).generate()

    def test_times_requires_an_integer_like_cobc(self):
        # cb_check_integer_value, checked against cobc 3.2.
        for body in ("perform f times display 1 end-perform.", "perform 2.5 times display 1 end-perform.",
                     "perform -1 times display 1 end-perform.", "perform n(1:1) times display 1 end-perform."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program(body, "01 f pic 9v9. 01 n pic 9.")).parse()
        Parser(program("perform s times display 1 end-perform.", "01 s pic s9p.")).parse()

    def test_incomplete_input_has_diagnostic_not_traceback(self):
        for body in ["display", "compute", "if", "perform", "move", "compute n ="]:
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program(body, "01 n pic 9.")).parse()

    def test_fixed_comments_columns_and_directive(self):
        self.assertNotIn("IGNORED", normalize("000100*IGNORED\n000200 DISPLAY 'A'.", "fixed"))
        self.assertEqual(normalize(">>source format free\ndisplay 'A'.", "fixed").splitlines()[1], "display 'A'.")
        self.assertEqual(normalize("000100 >>source format free\ndisplay 'A'.", "fixed").splitlines()[1], "display 'A'.")
        with self.assertRaises(CobolError):
            normalize("000100- continuation", "fixed")

    def test_debugging_lines_follow_debugging_mode(self):
        # pplex.l: D lines are source once "WITH DEBUGGING MODE" has been read.
        source = ("000100 IDENTIFICATION DIVISION.\n000200D    DISPLAY 'BEFORE'.\n"
                  "000300 SOURCE-COMPUTER. X WITH DEBUGGING MODE.\n000400D    DISPLAY 'AFTER'.\n")
        text = normalize(source, "fixed")
        self.assertNotIn("BEFORE", text)
        self.assertIn("AFTER", text)
        self.assertNotIn("AFTER", normalize(source.replace("WITH DEBUGGING MODE", ""), "fixed"))

    def test_debugging_targets_outside_the_model_are_rejected(self):
        declaratives = ("declaratives. d section. use for debugging on {}. p. display debug-name. "
                        "end declaratives. m section. a. stop run.")
        data = "01 x pic x. 01 t. 02 e pic x occurs 2."
        for target in ("e (1)", "x x", "p", "d", "missing", "all procedures a"):
            source = ("identification division.\nprogram-id. t.\nenvironment division.\nconfiguration section.\n"
                      "source-computer. c with debugging mode.\ndata division. working-storage section.\n"
                      + data + "\nprocedure division.\n" + declaratives.format(target))
            with self.subTest(target=target), self.assertRaises(CobolError):
                Emitter(Parser(source).parse()).generate()

    def test_indexed_limits_are_refused(self):
        def source(select, procedure="stop run."):
            return ("identification division.\nprogram-id. t.\nenvironment division.\ninput-output section.\n"
                    "file-control.\n    select f assign to \"IXF\" organization indexed access dynamic\n"
                    f"    {select}.\ndata division.\nfile section.\nfd f.\n01 r.\n 02 k pic x(3).\n 02 a pic x(2).\n"
                    "working-storage section.\n01 w pic x(3).\nprocedure division.\n" + procedure)
        Emitter(Parser(source("record key is k alternate record key is a with duplicates")).parse()).generate()
        # READ KEY of an item no key starts at: status 23 (cob_findkey_attr).
        Emitter(Parser(source("record key is k", "read f key is a. stop run.")).parse()).generate()
        for case in (source("record key is w"), source("alternate record key is a"),
                     source("record key is k alternate record key is a suppress when space"),
                     source("record key is k", "start f key is = w. stop run.")):
            with self.subTest(case=case), self.assertRaises(CobolError):
                Emitter(Parser(case).parse()).generate()

    def test_copy_expansion_cycle_and_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "main.cob"
            source.write_text('COPY "values.cpy".', encoding="utf-8")
            copy = root / "values.cpy"
            with self.assertRaisesRegex(CobolError, "introuvable"):
                load_source(source, [])
            copy.write_text('01 n pic 9.', encoding="utf-8")
            expanded, files = load_source(source, [])
            self.assertIn("01 n pic 9", expanded)
            self.assertEqual(files, [str(copy.resolve())])
            copy.write_text('COPY "main.cob".', encoding="utf-8")
            with self.assertRaisesRegex(CobolError, "cyclique"):
                load_source(source, [])

    def test_invalid_conversion_creates_no_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / "bad.cob", root / "output"
            source.write_text(program("call 'external'."), encoding="utf-8")
            with self.assertRaises(CobolError):
                convert(source, output)
            self.assertFalse(output.exists())

    def test_refuse_existing_output_and_emit_map(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / "main.cob", root / "output"
            source.write_text(program('display "ok" stop run.'), encoding="utf-8")
            report = convert(source, output)
            self.assertFalse(report["verified_against_original"])
            self.assertTrue(report["source_map"])
            first = (output / "src" / "main.rs").read_bytes()
            with self.assertRaisesRegex(CobolError, "non vide"):
                convert(source, output)
            self.assertEqual(first, (output / "src" / "main.rs").read_bytes())


class BinaryTests(unittest.TestCase):
    def test_truncated_pe_and_elf(self):
        for data in [b"MZ", b"MZ" + bytes(80)]:
            with self.assertRaises(CobolError):
                pe_info(data)
        with self.assertRaises(CobolError):
            elf_info(b"\x7fELF")

    def test_minimal_elf64(self):
        # A sectionless ELF is legitimate; it must not invent runtime evidence.
        ident = b"\x7fELF\x02\x01\x01" + bytes(9)
        header = struct.pack("<HHIQQQIHHHHHH", 2, 62, 1, 0x401000, 0, 0, 0, 64, 56, 0, 64, 0, 0)
        report = elf_info(ident + header)
        self.assertEqual(report["architecture"], "x86_64")
        self.assertEqual(report["symbols"], [])

    def test_real_pe_imports_without_running_it(self):
        gcc = Path(ROOT / ".tools" / "gc32" / "bin" / "cobc.exe")
        if not gcc.is_file():
            self.skipTest("portable GnuCOBOL not present")
        report = inspect_binary(gcc)
        self.assertEqual(report["format"], "PE")
        self.assertEqual(report["architecture"], "x86")
        self.assertIn("KERNEL32.dll", report["libraries"])
        self.assertTrue(report["rust_conversion"].startswith("unsupported"))
        self.assertEqual(report["aret_commands"][2][-1], "decompile")


@unittest.skipUnless(find_tool("rustc"), "Rust compiler required")
class RuntimeTests(unittest.TestCase):
    def test_verification_command_compiles_and_compares(self):
        if not find_tool("cobc"):
            self.skipTest("GnuCOBOL required")
        from cobol2rust.verification import verify
        result = verify(ROOT / "examples" / "invoice.cob")
        self.assertTrue(result["match"], result)

    def test_runtime_unit_tests(self):
        cargo = find_tool("cargo")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "main.cob"
            source.write_text(program("stop run."), encoding="utf-8")
            project = root / "rust"
            convert(source, project)
            with build_slot() as target:
                p = subprocess.run([cargo, "test", "--quiet", "--manifest-path", str(project / "Cargo.toml"), "--target-dir", str(target)], capture_output=True, env=compiler_env(cargo), timeout=300)
            self.assertEqual(p.returncode, 0, p.stdout.decode(errors="replace") + p.stderr.decode(errors="replace"))

    def test_divide_zero_overflow_and_invalid_input_abort(self):
        rustc = find_tool("rustc")
        # A DISPLAY receiver truncates like cob_decimal_get_display; binary
        # overflow depends on cobc's native add routines and stops.
        # A division by zero is NaN in an arithmetic statement (divide_by_zero
        # fixture); in a condition it is not modelled and stops.
        cases = [("if n / 0 > 1 display 'x' end-if stop run.", b"", "division by zero", "01 n pic 99."),
                 ("compute n = 100 stop run.", b"", "overflow", "01 n pic 99 comp.")]
        for body, stdin, diagnostic, data in cases:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / "main.cob"
                source.write_text(program(body, data), encoding="utf-8")
                convert(source, root / "rust")
                binary = build_rust(root / "rust")
                p = subprocess.run([str(binary)], capture_output=True, input=stdin, timeout=10)
                self.assertEqual(p.returncode, 70)
                self.assertIn(diagnostic, p.stderr.decode())


if __name__ == "__main__":
    unittest.main()
