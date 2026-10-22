from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import find_tool
from cobol2rust.verification import validate_file_paths, verify
from tests.test_files import file_program


def sequential(body="stop run.", organization="", fd="fd f. 01 rec pic x(5).", storage="01 fs pic xx."):
    return file_program(body, select=f'select f assign to "data.bin" {organization} file status fs.',
                        fd=fd, storage=storage)


class SequentialFrontendTests(unittest.TestCase):
    def test_default_and_explicit_organization_and_record_aliases(self):
        for organization in ("", "organization sequential", "organization is sequential"):
            with self.subTest(organization=organization):
                parsed = Parser(sequential(organization=organization,
                                          fd="fd f. 01 rec pic x(5). 01 other-rec pic x(5).")).parse()
                self.assertEqual(parsed.files["F"].organization, "SEQUENTIAL")
                self.assertEqual(parsed.files["F"].records, ["REC", "OTHER-REC"])
                self.assertEqual(parsed.fields["REC"].offset, parsed.fields["OTHER-REC"].offset)
                self.assertEqual(parsed.memory_size, 7)  # Shared five bytes plus FILE STATUS.
                self.assertIn('"SEQUENTIAL"', Emitter(parsed).generate()[0])

    def test_variable_record_formats_and_unsupported_controls_are_rejected(self):
        cases = [
            sequential(fd="fd f. 01 rec pic x(5). 01 other-rec pic x(3)."),
            sequential(fd="fd f. 01 rec pic x(3). 01 other-rec pic x(5)."),
            sequential(fd="fd f record varying from 3 to 5 characters. 01 rec pic x(5)."),
            sequential("write rec after advancing fs lines."),
            sequential("write rec after advancing -1 lines."),
            sequential("write rec after advancing 1.5 lines."),
            sequential("write rec after advancing 65536 lines."),
            sequential("write rec before advancing 'PAGE'."),
            sequential("write rec after advancing 1 lines.", organization="organization line sequential"),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CobolError):
                Parser(source).parse()

    def test_write_keeps_named_alias_and_advance_control(self):
        parsed = Parser(sequential('write other-rec from "OK" after advancing page.',
                                   fd="fd f. 01 rec pic x(5). 01 other-rec pic x(5).")).parse()
        self.assertEqual(parsed.entry[0].args[:2], ("F", "OTHER-REC"))
        self.assertEqual(parsed.entry[0].args[3], ("AFTER", None))
        self.assertIn("Advance::AfterPage", Emitter(parsed).generate()[0])

    def test_verification_rejects_unmodelled_sequential_concatenation(self):
        for name in ("COB_SEQ_CONCAT_NAME", "COB_SEQ_CONCAT_SEP"):
            with self.subTest(name=name), patch.dict("os.environ", {name: "configured"}):
                with self.assertRaisesRegex(CobolError, name):
                    validate_file_paths({"files": [{"path": {"text": "data.bin"}, "organization": "SEQUENTIAL"}]})


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SequentialNativeTests(unittest.TestCase):
    def check_program(self, contents, expected_files=None, stdout=None, seed=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.cob"
            source.write_text(contents, encoding="utf-8")
            data = None
            if seed is not None:
                data = root / "inputs"
                data.mkdir()
                for name, value in seed.items():
                    (data / name).write_bytes(value)
            report = verify(source, fmt="free", data_dir=data)
        self.assertTrue(report["match"], report)
        if stdout is not None:
            self.assertEqual(report["cobol_stdout"], stdout)
        for name, value in (expected_files or {}).items():
            self.assertEqual(report["cobol_files"][name],
                             {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()})
        return report

    def test_fixed_sequential_has_no_line_delimiters_and_preserves_spaces(self):
        body = 'open output f write rec from "AB" write rec from "CD" close f stop run.'
        for organization in ("", "organization sequential"):
            with self.subTest(organization=organization):
                self.check_program(sequential(body, organization=organization), {"data.bin": b"AB   CD   "})

    def test_equal_length_fd_records_share_bytes_during_move_write_and_read(self):
        body = '''move "AB" to rec
display "[" other-rec "]"
open output f
write other-rec
write rec from "CD"
display "[" other-rec "]"
close f
open input f
read f
display "[" other-rec "]"
close f stop run.'''
        self.check_program(sequential(body, fd="fd f. 01 rec pic x(5). 01 other-rec pic x(5)."),
                           {"data.bin": b"AB   CD   "}, "[AB   ]\n[CD   ]\n[AB   ]\n")

    def test_binary_record_keeps_comp_and_comp3_bytes(self):
        fd = "fd f. 01 rec. 05 n pic s9(5) comp-3. 05 b pic 9(4) comp. 05 tail-a pic x."
        body = '''open output f
move 0 to n b move "Q" to tail-a write rec
move -12345 to n move 258 to b write rec
close f stop run.'''
        self.check_program(sequential(body, fd=fd), {"data.bin": bytes.fromhex("00000c00005112345d010251")})

    def test_partial_read_preserves_record_tail_but_into_uses_actual_bytes(self):
        body = '''open input f move "VVVVV" to rec
read f into destination-a
display fs "[" rec "][" destination-a "]"
read f at end display fs end-read
read f display fs
close f stop run.'''
        self.check_program(sequential(body, storage='01 fs pic xx. 01 destination-a pic x(7) value "ZZZZZZZ".'),
                           stdout="00[ABVVV][AB     ]\n10\n46\n", seed={"data.bin": b"AB"})

    def test_read_treats_nul_high_bytes_and_lf_as_record_data(self):
        contents = '''identification division. program-id. sequential-copy.
environment division. input-output section. file-control.
select source-file assign to "source.bin" organization sequential.
select target-file assign to "target.bin".
data division. file section.
fd source-file. 01 source-record pic x(5).
fd target-file. 01 target-record pic x(5).
procedure division.
open input source-file open output target-file
read source-file write target-record from source-record
close source-file target-file stop run.
'''
        data = b"A\x00\xff\nZ"
        self.check_program(contents, {"source.bin": data, "target.bin": data}, seed={"source.bin": data})

    def test_advancing_controls_and_pending_newline_match_exact_bytes(self):
        cases = [
            ("after advancing 1 lines", "after advancing 1 lines", b"\nAB   \nCD   \n"),
            ("before advancing 1 lines", "before advancing 1 lines", b"AB   \nCD   \n"),
            ("after advancing 0 lines", "after advancing 0 lines", b"\rAB   \rCD   \n"),
            ("before advancing 0 lines", "before advancing 0 lines", b"AB   \rCD   \r"),
            ("after advancing page", "after advancing page", b"\x0cAB   \x0cCD   \n"),
            ("before advancing page", "before advancing page", b"AB   \x0cCD   \x0c"),
            ("after advancing 2 lines", "", b"\n\nAB   CD   \n"),
            ("before advancing 1 lines", "after advancing 1 lines", b"AB   \n\nCD   \n"),
        ]
        for first, second, expected in cases:
            with self.subTest(first=first, second=second):
                body = f'open output f write rec from "AB" {first} write rec from "CD" {second} close f stop run.'
                self.check_program(sequential(body), {"data.bin": expected})

    def test_implicit_close_and_extend_reset_pending_newline(self):
        self.check_program(sequential('open output f write rec from "AB" after advancing 1 line stop run.'),
                           {"data.bin": b"\nAB   \n"})
        body = '''open output f write rec from "AB" after advancing 1 line close f
open extend f write rec from "CD" after advancing 1 line close f stop run.'''
        self.check_program(sequential(body), {"data.bin": b"\nAB   \n\nCD   \n"})
        self.check_program(sequential('open output f close f stop run.'), {"data.bin": b""})

    def test_unexecuted_advancing_does_not_change_plain_writes(self):
        body = '''open output f
if 1 = 2 write rec after advancing page end-if
write rec from "AB" close f stop run.'''
        self.check_program(sequential(body), {"data.bin": b"AB   "})


if __name__ == "__main__":
    unittest.main()
