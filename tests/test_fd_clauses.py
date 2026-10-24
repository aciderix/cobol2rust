from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from cobol2rust.file_parser import parse_fd_clauses
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import find_tool
from cobol2rust.verification import verify
from tests.test_files import file_program


class FdClauseTests(unittest.TestCase):
    def clauses(self, source):
        parser, spec = Parser(source), SimpleNamespace(fd_clauses={})
        parse_fd_clauses(parser, spec)
        self.assertTrue(parser.at("<EOF>"))
        return spec.fd_clauses

    def test_label_block_and_fixed_record_metadata(self):
        clauses = self.clauses("label records are standard block contains 0 to 120 characters "
                               "record contains 5 characters recording mode is f.")
        self.assertEqual(clauses, {"label_records": "STANDARD",
                                  "block_contains": {"minimum": 0, "maximum": 120, "unit": "CHARACTERS"},
                                  "record_contains": 5, "recording_mode": "F"})
        self.assertEqual(self.clauses("."), {})
        self.assertEqual(self.clauses("block 12."),
                         {"block_contains": {"minimum": 12, "maximum": 12, "unit": "RECORDS"}})
        self.assertEqual(self.clauses("record 5 recording f label record omitted."),
                         {"record_contains": 5, "recording_mode": "F", "label_records": "OMITTED"})

    def test_label_spellings_and_zero_block(self):
        for header in ("label record", "label records"):
            for optional in ("", "is", "are"):
                with self.subTest(header=header, optional=optional):
                    self.assertEqual(self.clauses(f"{header} {optional} omitted."),
                                     {"label_records": "OMITTED"})
        self.assertEqual(self.clauses("block contains 0 records."),
                         {"block_contains": {"minimum": 0, "maximum": 0, "unit": "RECORDS"}})

    def test_documentary_data_records_are_kept_as_metadata(self):
        self.assertEqual(self.clauses("data record is rec."), {"data_records": ["REC"]})
        self.assertEqual(self.clauses("data records are rec-a, rec-b."), {"data_records": ["REC-A", "REC-B"]})
        self.assertEqual(self.clauses("label records standard data records rec-a rec-b block 2."),
                         {"label_records": "STANDARD", "data_records": ["REC-A", "REC-B"],
                          "block_contains": {"minimum": 2, "maximum": 2, "unit": "RECORDS"}})
        # GnuCOBOL 3.2 ne résout pas ces noms : la clause n'a aucun effet.
        parsed = Parser(file_program(fd="fd f data record is unknown-rec. 01 rec pic x(8).")).parse()
        self.assertEqual(parsed.files["F"].fd_clauses["data_records"], ["UNKNOWN-REC"])

    def test_unsupported_and_ambiguous_fd_clauses_are_not_ignored(self):
        cases = [
            "record contains 9 to 7 characters.", "record is varying from 9 to 9 characters.",
            "record contains 0 characters.", "record contains -5 characters.",
            "record contains 5.5 characters.", "record contains 5 character.",
            "block contains 12 to 1 records.", "block contains -1 records.",
            "block contains '1' records.", "block contains 9999999999999999999 records.",
            "label records custom-label.", "label records standard label records omitted.",
            "block contains 1 records block contains 2 records.",
            "record contains 5 characters record contains 5 characters.",
            "recording mode f recording mode f.", "recording mode v.",
            "recording mode s.", "recording mode u.", "linage 66 lines.",
            "code-set is custom-alphabet.",
            "external.", "global.", "data rec.", "data record.", "data records are.",
            "data record is rec data record is rec.", "data record label records standard.",
            "data record is 'rec'.", "data record is rec of f.", "data record rec linage 60.",
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CobolError):
                self.clauses(source)

    def test_record_length_is_checked_after_physical_layout(self):
        select = 'select f assign to "data.bin" organization sequential file status fs.'
        for length in (3, 7):
            with self.subTest(length=length), self.assertRaises(CobolError):
                Parser(file_program(select=select,
                                    fd=f"fd f record contains {length} characters. 01 rec pic x(5).")).parse()
        parsed = Parser(file_program(select=select,
                                     fd="fd f record contains 5 characters. 01 rec pic x(5).")).parse()
        self.assertEqual(parsed.files["F"].fd_clauses["record_contains"], 5)
        # A packed field is three physical bytes, not five PICTURE digits.
        parsed = Parser(file_program(select=select,
                                     fd="fd f record contains 3 characters. 01 rec. 05 n pic s9(5) comp-3.")).parse()
        self.assertEqual(parsed.fields["REC"].size, 3)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class FdClauseNativeTests(unittest.TestCase):
    def test_disk_file_clauses_preserve_native_bytes_and_statuses(self):
        body = 'open output f display fs write rec from "AB" display fs close f display fs stop run.'
        cases = [
            ("organization sequential", "label records omitted block contains 0 records record contains 5 characters", b"AB   "),
            ("organization sequential", "recording mode is f label record is standard block contains 1 to 12 records record contains 5", b"AB   "),
            ("organization line sequential", "label records standard block contains 120 characters record contains 5 characters recording mode f", b"AB\n"),
            ("organization sequential", "label records standard data records are rec, fs", b"AB   "),
            ("organization line sequential", "data record is absent-name record contains 5", b"AB\n"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for number, (organization, clauses, expected) in enumerate(cases):
                with self.subTest(organization=organization, clauses=clauses):
                    source = root / f"case{number}.cob"
                    source.write_text(file_program(body,
                        select=f'select f assign to "data.bin" {organization} file status fs.',
                        fd=f"fd f {clauses}. 01 rec pic x(5)."), encoding="utf-8")
                    result = verify(source)
                    self.assertTrue(result["match"], result)
                    self.assertEqual(result["cobol_stdout"], "00\n00\n00\n")
                    self.assertEqual(result["cobol_files"]["data.bin"],
                                     {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()})


if __name__ == "__main__":
    unittest.main()
