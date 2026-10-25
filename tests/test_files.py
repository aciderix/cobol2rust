from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cobol2rust.cli import convert
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, compiler_env, find_tool
from cobol2rust.verification import snapshot, validate_file_paths, verify


def file_program(body="stop run.", select=None, fd=None, storage="01 fs pic xx."):
    select = select or 'select f assign to "data.txt" organization line sequential file status fs.'
    fd = fd or 'fd f. 01 rec pic x(8).'
    return ("identification division. program-id. file-test.\n"
            "environment division. input-output section. file-control.\n" + select +
            "\ndata division. file section.\n" + fd +
            "\nworking-storage section.\n" + storage + "\nprocedure division.\n" + body)


class FileFrontendTests(unittest.TestCase):
    def test_reject_unmodelled_file_declarations(self):
        select = 'select f assign to "data.txt" organization line sequential file status fs.'
        cases = [
            file_program(select=select.replace("line sequential", "indexed")),
            # ASSIGN TO an undeclared word is a file name since cobc's
            # assign_clause port (tests/test_assign.py); a level 88 is refused.
            file_program(select=select.replace('"data.txt"', "path-ok"), storage="01 fs pic xx. 88 path-ok value 'ok'."),
            file_program(fd="fd f. 01 rec. 05 item-a pic 9(8) comp-3."),
            file_program(fd="fd f. 01 rec pic 9(8)."),
            file_program(fd='fd f. 01 rec pic x(8) value "ABC".'),
            file_program(storage="01 fs pic xxx."),
            file_program(storage="01 fs pic s99."),
            file_program(storage="01 fs pic 99 comp."),
            file_program(storage="01 fs. 02 a pic x."),
            file_program(storage="01 fs. 02 a pic x(3)."),
            file_program(storage="01 g. 02 fs occurs 2. 03 a pic xx."),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CobolError):
                Emitter(Parser(source).parse()).generate()

    def test_two_byte_group_file_status_is_accepted(self):
        for storage in ("01 fs. 02 a pic x. 02 b pic x.", "01 fs. 02 a pic 9. 02 b pic 9.",
                        "01 fs. 02 a pic x occurs 2.", "01 fs. 02 a pic s9(4) comp.",
                        "01 g. 02 fs. 03 a pic x. 03 b pic x."):
            with self.subTest(storage=storage):
                Parser(file_program(storage=storage)).parse()

    def test_reject_unsupported_operations_and_incomplete_input(self):
        cases = ["open f.", "open i-o f.", "open input.", "read.", "write fs.", "close.",
                 "read f into fs.", "read f with lock.", "rewrite rec.",
                 "read f at end perform missing end-read."]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(file_program(body, storage="01 fs pic 99.")).parse()).generate()

    def test_file_metadata_and_read_branches(self):
        p = Parser(file_program("read f at end display 'END' not at end display rec end-read stop run.")).parse()
        self.assertEqual(p.files["F"].record, "REC")
        self.assertEqual(p.files["F"].status, "FS")
        self.assertEqual(p.entry[0].op, "read")
        rust, mapping = Emitter(p).generate()
        self.assertIn("CobolFile::new", rust)
        self.assertEqual(sum(m["operation"] == "display" for m in mapping), 2)

    def test_verification_refuses_paths_outside_work_directories(self):
        for path in ("../data.txt", "C:\\data.txt", "/tmp/data.txt", "..\\data.txt", "C:data.txt"):
            with self.subTest(path=path), self.assertRaises(CobolError):
                validate_file_paths({"files": [{"path": {"text": path}}]})
        validate_file_paths({"files": [{"path": {"text": "inputs/data.txt"}}]})


@unittest.skipUnless(find_tool("cargo"), "Cargo required")
class FileRuntimeTests(unittest.TestCase):
    def test_unmodelled_input_aborts_instead_of_changing_data(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            project = directory / "rust"
            convert(ROOT / "tests" / "fixtures" / "file_read.cob", project)
            binary = build_rust(project)
            for data, diagnostic in ((b"A\x01\n", "printable ASCII"), (b"ABCDE\n", "split/unterminated"), (b"TAIL", "split/unterminated")):
                with self.subTest(data=data):
                    (directory / "records.txt").write_bytes(data)
                    result = subprocess.run([str(binary)], cwd=directory, env=compiler_env(find_tool("rustc")), capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 70)
                    self.assertIn(diagnostic, result.stderr.decode())


@unittest.skipUnless(find_tool("cargo") and find_tool("cobc"), "Cargo and GnuCOBOL required")
class FileVerificationTests(unittest.TestCase):
    def test_one_path_shared_by_two_selects_in_turn(self):
        select = ('select f assign to "data.txt" organization line sequential file status fs. '
                  'select other-file assign to "data.txt" organization line sequential.')
        fd = "fd f. 01 rec pic x(8). fd other-file. 01 other-rec pic x(8)."
        body = ('open output f write rec from "ONE" close f open input other-file read other-file '
                'display "[" other-rec "]" close other-file stop run.')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "shared-path.cob"
            source.write_text(file_program(body, select=select, fd=fd), encoding="utf-8")
            report = verify(source)
            self.assertTrue(report["match"], report)
            self.assertEqual(report["cobol_stdout"], "[ONE     ]\n")
            # Both open at once depends on native locking: the Rust runtime stops.
            source.write_text(file_program('open output f open input other-file stop run.',
                                           select=select, fd=fd), encoding="utf-8")
            convert(source, Path(directory) / "rust")
            binary = build_rust(Path(directory) / "rust")
            result = subprocess.run([str(binary)], cwd=directory, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 70)
        self.assertIn(b"simultaneous OPEN", result.stderr)

    def test_close_with_lock_forbids_reopening(self):
        # A second CLOSE of a locked file takes an abnormal libcob path (it
        # warns and returns 00): the Rust runtime stops there instead.
        body = ('open output f display "[" fs "]" close f with lock display "[" fs "]" '
                'open input f display "[" fs "]" read f display "[" fs "]" stop run.')
        for organization in ("line sequential", "sequential"):
            with self.subTest(organization=organization), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "close-lock.cob"
                select = f'select f assign to "data.txt" organization {organization} file status fs.'
                source.write_text(file_program(body, select=select), encoding="utf-8")
                report = verify(source)
                self.assertTrue(report["match"], report)
                self.assertEqual(report["cobol_stdout"], "[00]\n[00]\n[38]\n[47]\n")

    def test_group_file_status_receives_raw_status_bytes(self):
        body = ('open input f display "[" fs "]" open output f display "[" fs "]" '
                'write rec from "AB" display "[" fs "]" close f display "[" fs "]" stop run.')
        for storage in ("01 fs. 02 a pic x. 02 b pic x.", "01 fs. 02 a pic 9. 02 b pic 9.",
                        "01 fs. 02 a pic s9(4) comp."):
            with self.subTest(storage=storage), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "group-status.cob"
                source.write_text(file_program(body, storage=storage), encoding="utf-8")
                report = verify(source)
                self.assertTrue(report["match"], report)
                self.assertEqual(report["cobol_stdout"], "[35]\n[00]\n[00]\n[00]\n")

    def test_empty_input_directories_are_available_to_both_programs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "inputs"
            (data / "out").mkdir(parents=True)
            source = root / "source.cob"
            source.write_text(file_program('open output f write rec from "OK" close f stop run.',
                                          select='select f assign to "out/data.txt" organization line sequential file status fs.'), encoding="utf-8")
            result = verify(source, data_dir=data)
            self.assertTrue(result["match"], result)
            self.assertIn("out/data.txt", result["cobol_files"])
            self.assertFalse(any((data / "out").iterdir()))

    def test_input_seed_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            original = b"USER INPUT MUST REMAIN UNCHANGED\n"
            (data / "transactions.txt").write_bytes(original)
            result = verify(ROOT / "examples" / "files.cob", data_dir=data)
            self.assertTrue(result["match"], result)
            self.assertTrue(result["files_match"])
            self.assertEqual((data / "transactions.txt").read_bytes(), original)
            self.assertNotEqual(result["input_files"]["transactions.txt"]["sha256"], result["cobol_files"]["transactions.txt"]["sha256"])

    def test_file_difference_is_detected_even_when_stdout_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.cob"
            source.write_text(file_program('open output f write rec from "ORIGINAL" close f stop run.'), encoding="utf-8")

            def corrupt_backend(project):
                main = project / "src" / "main.rs"
                text = main.read_text(encoding="utf-8")
                self.assertIn('Value::text("ORIGINAL")', text)
                main.write_text(text.replace('Value::text("ORIGINAL")', 'Value::text("CHANGED!")'), encoding="utf-8")
                return build_rust(project)

            with patch("cobol2rust.verification.build_rust", side_effect=corrupt_backend):
                result = verify(source)
            self.assertFalse(result["match"])
            self.assertFalse(result["files_match"])
            self.assertEqual(result["cobol_stdout"], result["rust_stdout"])
            self.assertEqual(result["cobol_exit"], 0)
            self.assertEqual(result["rust_exit"], 0)
            self.assertEqual(result["file_differences"], ["data.txt"])
