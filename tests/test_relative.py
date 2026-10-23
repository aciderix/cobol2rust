from __future__ import annotations

import hashlib
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_files import file_program


def relative(access="dynamic", key="relative key is rk", extra=""):
    return f'select f assign to "rel.dat" organization relative access {access} {key} file status fs {extra}.'


class RelativeFrontendTests(unittest.TestCase):
    def parse(self, body, select=None, storage="01 fs pic xx. 01 rk pic 9(4)."):
        return Parser(file_program(body, select=select or relative(), storage=storage)).parse()

    def test_select_clauses_and_read_modes(self):
        parsed = self.parse("open i-o f read f invalid key display 'I' end-read "
                            "read f next at end display 'E' end-read "
                            "read f at end display 'D' end-read stop run.")
        spec = parsed.files["F"]
        self.assertEqual((spec.organization, spec.access, spec.relative_key), ("RELATIVE", "DYNAMIC", "RK"))
        # cobc: DYNAMIC without NEXT reads by key, except with AT END.
        self.assertEqual([s.args[4] for s in parsed.entry[1:4]], [True, False, False])
        Emitter(parsed).generate()
        for select, body in (
                ('select f assign to "rel.dat" relative access random relative rk status fs reserve 2 areas.',
                 "open input f read f invalid key display 'I' end-read stop run."),
                ('select f assign to "rel.dat" organization is relative access mode is sequential.',
                 "open input f read f at end display 'E' end-read stop run.")):
            with self.subTest(select=select):
                Emitter(self.parse(body, select)).generate()

    def test_key_statements_are_parsed(self):
        parsed = self.parse("open i-o f write rec invalid key display 'W' not invalid key display 'N' end-write "
                            "rewrite rec invalid key display 'R' end-rewrite delete f record invalid key display 'D' "
                            "end-delete start f key is not less than rk invalid key display 'S' end-start "
                            "start f key > rk start f stop run.")
        self.assertEqual([s.op for s in parsed.entry[1:7]], ["write", "rewrite", "delete", "start", "start", "start"])
        self.assertEqual([s.args[2] for s in parsed.entry[4:7]], ["NotLess", "Greater", "Equal"])
        Emitter(parsed).generate()

    def test_unmodelled_relative_forms_are_refused(self):
        cases = [
            (relative(key=""), "stop run."),
            (relative(access="random", key=""), "stop run."),
            (relative(), "start f key < rk stop run."),
            (relative(), "read f previous stop run."),
            (relative(), "read f at end display 'x' invalid key display 'y' stop run."),
            (relative(access="random"), "read f at end display 'x' stop run."),
            (relative(access="random"), "start f stop run."),
            (relative(), "write rec after advancing 1 line stop run."),
            (relative(extra="status vsam"), "stop run."),
            ('select f assign to "a.txt" organization line sequential relative key rk.', "stop run."),
            ('select f assign to "a.txt" organization sequential file status fs.', "delete f stop run."),
            ('select f assign to "a.txt" organization sequential file status fs.',
             "open input f read f invalid key display 'x' stop run."),
        ]
        for select, body in cases:
            with self.subTest(select=select, body=body), self.assertRaises(CobolError):
                Emitter(self.parse(body, select)).generate()
        for storage in ("01 fs pic xx. 01 rk pic s9(4).", "01 fs pic xx. 01 rk pic 9(10).",
                        "01 fs pic xx. 01 rk pic 9(4)v9.", "01 fs pic xx. 01 rk pic x(4)."):
            with self.subTest(storage=storage), self.assertRaises(CobolError):
                self.parse("stop run.", storage=storage)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class RelativeNativeTests(unittest.TestCase):
    def test_fixture_matches_native_statuses_and_slot_bytes(self):
        report = verify(ROOT / "tests" / "fixtures" / "relative.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        for line in ("RW2 22", "RW0 24", "RRW4 00", "RD2B 00", "DN4 46 04 EEEE", "SEW 00 6", "ON2 46", "NO 35"):
            self.assertIn(line, lines)
        # Slots: size_t little endian then 4 data bytes; slot 3 is a hole and
        # slot 4 keeps size 0 after the native rewrite of an empty slot.
        slot = lambda size, data: size.to_bytes(8, "little") + data
        expected = (slot(4, b"AAAA") + slot(4, b"bbbb") + slot(0, b"\0" * 4) + slot(0, b"DDDD")
                    + slot(4, b"EEEE") + slot(4, b"FFFF"))
        self.assertEqual(report["cobol_files"]["rel.dat"],
                         {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()})


if __name__ == "__main__":
    unittest.main()
