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
from cobol2rust.toolchain import ROOT, build_rust, compiler_env, find_tool


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
            program("call 'external'."), program("go to finish. finish. stop run."),
            program("open input file-a."), program("display function current-date."),
            program("exec sql select 1 end-exec."), program("next sentence."),
            program("perform missing stop run."), program("if n = 1 or 2 display 'bad' end-if.", "01 n pic 9."),
            program("stop run.", "01 n pic 9(2) occurs 1 to 3 depending on count-a."),
            program("stop run.", "01 group-a."),
            program("stop run.", "01 n pic 9(2) comp-5."),
            program("stop run.", "01 n pic 9(19)."),
            program("stop run.", "01 n pic ZZ9.99."),
            program("stop run.", "01 n pic 9 value 'bad'."),
            program("stop run.", "01 n pic 9. 01 n pic 9."),
            program("stop run.", "01 x pic x(0)."),
            program("accept n from date.", "01 n pic 9(8)."),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CobolError):
                Emitter(Parser(source).parse()).generate()

    def test_semantic_type_errors(self):
        declarations = '01 n pic 99. 01 t pic x(3).'
        for body in ['move t to n.', 'compute n = t + 1.', 'if t = 1 continue end-if.', 'perform t times continue end-perform.']:
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(body, declarations)).parse()).generate()

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
            p = subprocess.run([cargo, "test", "--quiet", "--manifest-path", str(project / "Cargo.toml"), "--target-dir", str(ROOT / "build" / "rust-target")], capture_output=True, env=compiler_env(cargo), timeout=120)
            self.assertEqual(p.returncode, 0, p.stdout.decode(errors="replace") + p.stderr.decode(errors="replace"))

    def test_divide_zero_overflow_and_invalid_input_abort(self):
        rustc = find_tool("rustc")
        cases = [("compute n = 1 / 0 stop run.", b"", "division by zero"),
                 ("compute n = 100 stop run.", b"", "overflow"),
                 ("accept n stop run.", b"bad\n", "invalid numeric input")]
        for body, stdin, diagnostic in cases:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / "main.cob"
                source.write_text(program(body, "01 n pic 99."), encoding="utf-8")
                convert(source, root / "rust")
                binary = build_rust(root / "rust")
                p = subprocess.run([str(binary)], capture_output=True, input=stdin, timeout=10)
                self.assertEqual(p.returncode, 70)
                self.assertIn(diagnostic, p.stderr.decode())


if __name__ == "__main__":
    unittest.main()
