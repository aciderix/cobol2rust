from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust import frontend
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_report_writer import program


FIXTURE = ROOT / 'tests/fixtures/report_source_capture.cob'
EXPECTED = (
    b'D 1 AAAA AAAA BCD BC     CDEF   -12.3 -12.3 1200 01\n'
    b'F 1 BBBB AAAA VWX WXY    WXYZ   +45.6 +45.6 3400\n'
    b'D 2 BBBB AAAA VWX WXY    WXYZ   +45.6 +45.6 3400 03\n'
    b'F 1 AAAA AAAA bcd abcd   cdef   +98.7 +98.7 1200\n' + b'\n' * 16
)

POSITION_CASES = [
    ('1 + 1', 2), ('1.0 + 1', 2), ('0.2', 2), ('2.0', 20),
    ('0.2 + 0.2', 4), ('1.5 * 2', 3), ('0.3 / 0.2', 15),
    ('2 / 0.5', 4), ('2 ** 3', 8),
    ('3 / 2', 100), ('(3 / 2) * 2', 100), ('0.0 / 2 + 2', 100),
    ('-(-2)', 100), ('- -2', 100), ('+2.0', 20),
    ('n + 0.2', 100), ('n / 2 * 2', 100), ('n * 0 + 2', 2),
    ('(0.001 + 0.000) * 2', 100),
    ('fraction-a', 100), ('fraction-a * 2', 100), ('fraction-a + 0', 100),
]


def positions_program():
    groups = '01 d type detail.\n' + '\n'.join(
        f'02 line plus 1. 03 column 1 pic x(20) source wide-a(1:{expr}). '
        '03 column 21 pic x value "|".' for expr, _ in POSITION_CASES)
    groups += ('\n02 line plus 1. 03 column 1 pic xxxx source wide-a(0.2:0.2). '
               '03 column 5 pic x value "|".')
    return program('page 30', groups,
                   'move 3 to n open output out-file initiate r generate d terminate r close out-file.',
                   working='01 wide-a pic x(100) value all "ABCDEFGHIJKLMNOPQRSTUVWXYZ". '
                           '01 fraction-a pic 9v9 value 1.5.')


class ReportSourceCaptureFrontendTests(unittest.TestCase):
    def test_native_literal_folding_controls_temporary_widths(self):
        parsed = Parser(positions_program()).parse()
        copies = [parsed.fields[key] for _, key in parsed.reports['R'].move_passes[0]]
        self.assertEqual([f.size for f in copies], [width for _, width in POSITION_CASES] + [2])

    def test_native_literal_bounds_are_checked_after_folding(self):
        for position in ['1:2.0', '1.0:2', '1:0.1 - 0.1', '1:2147483648']:
            with self.subTest(position=position), self.assertRaises(CobolError):
                Parser(program('page 20', f'01 d type detail line plus 1 column 1 pic xxxx source w({position}).',
                               'initiate r generate d terminate r.')).parse()

    def test_nonfolded_integer_power_is_refused(self):
        for expr in ['2.0 ** 1', 'n ** 2', '2 ** -1']:
            with self.subTest(expr=expr), self.assertRaisesRegex(CobolError, 'cob_s32_pow'):
                Parser(program('page 20', f'01 d type detail line plus 1 column 1 pic xxxx source w(1:{expr}).',
                               'initiate r generate d terminate r.')).parse()

    def test_constant_integer_division_by_zero_is_refused(self):
        for expr in ['n / 0', 'n / ZERO', 'n / (1 - 1)']:
            with self.subTest(expr=expr), self.assertRaisesRegex(CobolError, 'division entière par zéro'):
                Parser(program('page 20', f'01 d type detail line plus 1 column 1 pic xxxx source w(1:{expr}).',
                               'initiate r generate d terminate r.')).parse()

    def test_copies_are_distinct_and_keep_native_numeric_descriptions(self):
        groups = ('01 d type detail line plus 1. '
                  '02 column 1 pic +99.9 source amount-a(1). '
                  '02 column 8 pic +99.9 source amount-a(1). '
                  '02 column 15 pic 9(4) source scaled-a(1).')
        parsed = Parser(program('page 20', groups, 'initiate r generate d terminate r.',
                                working='01 t. 02 amount-a occurs 2 pic 99v9 comp-3. '
                                        '02 scaled-a occurs 2 pic 99pp.')).parse()
        moves = parsed.reports['R'].move_passes[0]
        self.assertEqual(len(moves), 3)
        fields = [parsed.fields[key] for _, key in moves]
        self.assertEqual([(f.digits, f.scale, f.signed, f.usage) for f in fields],
                         [(3, 1, True, 'DISPLAY'), (3, 1, True, 'DISPLAY'), (4, 0, True, 'DISPLAY')])
        self.assertEqual(len({f.name for f in fields}), 3)
        self.assertTrue(all(f.explicit_value and not f.linkage and not getattr(f, 'local', False) for f in fields))

    def test_literal_and_variable_refmod_lengths_make_different_temporaries(self):
        groups = ('01 d type detail line plus 1. '
                  '02 column 1 pic xx source w(1:2). '
                  '02 column 4 pic xxxx source w(1:n).')
        parsed = Parser(program('page 20', groups, 'initiate r generate d terminate r.')).parse()
        copies = [parsed.fields[key] for _, key in parsed.reports['R'].move_passes[0]]
        self.assertEqual([f.size for f in copies], [2, 4])

    def test_complex_groups_and_invalid_leading_scaling_are_refused(self):
        for storage, source in [('01 t. 02 row-a occurs 2. 03 item-a pic xx.', 'row-a(1)'),
                                ('01 t. 02 row-a occurs 2 pic pp99.', 'row-a(1)')]:
            with self.subTest(source=source), self.assertRaisesRegex(CobolError, 'SOURCE de rapport complexe'):
                Parser(program('page 20', f'01 d type detail line plus 1 column 1 pic xxxx source {source}.',
                               'initiate r generate d terminate r.', working=storage)).parse()

    def test_simple_group_remains_live(self):
        parsed = Parser(program('page 20', '01 d type detail line plus 1 column 1 pic xx source group-a.',
                                'initiate r generate d terminate r.', working='01 group-a. 02 text-a pic xx.')).parse()
        self.assertEqual(parsed.reports['R'].move_passes, ([], []))
        Emitter(parsed).generate()

    def test_elementary_footing_keeps_native_state_between_passes(self):
        groups = ('01 d type detail line plus 1 column 1 pic xxxx source w(n:). '
                  '01 f type control footing w line plus 1 column 1 pic xxxx source w(n:).')
        parsed = Parser(program('controls w page 20', groups, 'initiate r generate d terminate r.')).parse()
        first, last = parsed.reports['R'].move_passes
        self.assertEqual(len(first), 1)
        self.assertEqual(len(last), 2)
        self.assertEqual(first[0], last[0])

    def test_local_storage_follows_the_compiler_profile(self):
        text = program('page 20', '01 d type detail line plus 1 column 1 pic xxxx source local-a.',
                       'initiate r generate d terminate r.')
        text = text.replace('report section.', 'local-storage section. 01 local-a pic xxxx.\nreport section.')
        previous, frontend.STD = frontend.STD, 'cobol85'
        try:
            with self.assertRaisesRegex(CobolError, 'LOCAL-STORAGE'):
                Parser(text).parse()
        finally:
            frontend.STD = previous

    def test_local_control_is_refused_instead_of_emulating_an_unbuildable_native_report(self):
        text = program('controls local-a page 20',
                       '01 d type detail line plus 1 column 1 pic xxxx source local-a.',
                       'initiate r generate d terminate r.')
        text = text.replace('report section.', 'local-storage section. 01 local-a pic xxxx.\nreport section.')
        with self.assertRaisesRegex(CobolError, 'CONTROL de rapport en LOCAL-STORAGE'):
            Parser(text).parse()


@unittest.skipUnless(find_tool('cobc') and find_tool('cargo'), 'GnuCOBOL and Cargo required')
class ReportSourceCaptureNativeTests(unittest.TestCase):
    def test_reference_positions_follow_native_literal_and_integer_arithmetic(self):
        for checks in [False, True]:
            with self.subTest(checks=checks), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'report-positions.cob'
                path.write_text(positions_program(), encoding='utf-8')
                result = verify(path, fmt='free', runtime_checks=checks)
                self.assertTrue(result['match'], result)
                self.assertTrue(result['stderr_match'], result)
                self.assertEqual(result['cobol_exit'], 0)

    def compare_fixture(self, runtime_checks=False):
        result = verify(FIXTURE, fmt='free', runtime_checks=runtime_checks)
        self.assertTrue(result['match'], result)
        self.assertTrue(result['stderr_match'], result)
        self.assertEqual(result['cobol_stdout'], '')
        self.assertEqual(result['cobol_exit'], 0)
        self.assertEqual(result['cobol_files']['capture.txt'],
                         {'bytes': len(EXPECTED), 'sha256': hashlib.sha256(EXPECTED).hexdigest()})

    def test_generate_captures_sources_before_control_restoration(self):
        # The first footer keeps control 1, while its indexed SOURCE already
        # holds the incoming row 2; TERMINATE refreshes footer sources only.
        self.compare_fixture()

    def test_numeric_temporaries_and_reference_modifications_with_checks(self):
        self.compare_fixture(runtime_checks=True)

    def test_local_source_is_copied_to_working_storage(self):
        groups = ('01 d type detail line plus 1 column 1 pic xxxx source local-a. '
                  '01 f type control footing n line plus 1 column 1 pic xxxx source local-a.')
        text = program('controls n page 20', groups,
                       'open output out-file initiate r generate d '
                       'move "WXYZ" to local-a terminate r close out-file.')
        text = text.replace('report section.', 'local-storage section. 01 local-a pic xxxx value "ABCD".\nreport section.')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'local-report.cob'
            path.write_text(text, encoding='utf-8')
            report = verify(path, fmt='free')
        self.assertTrue(report['match'], report)
        data = b'ABCD\nWXYZ\n' + b'\n' * 18
        self.assertEqual(report['cobol_files']['OUT.TXT'],
                         {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

    def test_elementary_footing_refreshes_its_source_on_terminate(self):
        groups = ('01 d type detail line plus 1 column 1 pic xxxx source w(n:). '
                  '01 f type control footing w line plus 1 column 1 pic xxxx source w(n:).')
        text = program('controls w page 20', groups,
                       'move 1 to n open output out-file initiate r generate d '
                       'move 2 to n terminate r close out-file.')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sticky-report.cob'
            path.write_text(text, encoding='utf-8')
            report = verify(path, fmt='free')
        self.assertTrue(report['match'], report)
        data = b'ABCD\nBCD\n' + b'\n' * 18
        self.assertEqual(report['cobol_files']['OUT.TXT'],
                         {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

    def test_first_procedural_use_controls_copies_and_initial_numeric_zeroes(self):
        template = '''identification division. program-id. report-order.
environment division. input-output section. file-control.
select file-a assign 'A.TXT' organization line sequential.
select file-b assign 'B.TXT' organization line sequential.
data division. file section.
fd file-a report rep-a. fd file-b report rep-b.
working-storage section.
01 control-a pic 9 value 1.
01 text-a pic xxxx value 'ABCD'.
01 number-a pic 9999 value 1234.
report section.
rd rep-a controls control-a page 20.
01 footer-a type control footing control-a line plus 1 column 1 pic xxxx source text-a(1:).
rd rep-b controls control-a page 20.
01 detail-b type detail.
 02 line plus 1 column 1 pic xxx source number-a(1:3).
01 footer-b type control footing control-a.
 02 line plus 1 column 1 pic xxxx source text-a(1:).
procedure division.
open output file-a file-b
initiate {order}
generate detail-b
terminate rep-b rep-a
close file-a file-b
stop run.
'''
        for order, first in [('rep-a rep-b', b'000'), ('rep-b rep-a', b'123')]:
            with self.subTest(order=order), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'report-order.cob'
                path.write_text(template.format(order=order), encoding='utf-8')
                result = verify(path, fmt='free', std='cobol85')
                self.assertTrue(result['match'], result)
                data = first + b'\nABCD\n' + b'\n' * 18
                self.assertEqual(result['cobol_files']['B.TXT'],
                                 {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})


if __name__ == '__main__':
    unittest.main()
