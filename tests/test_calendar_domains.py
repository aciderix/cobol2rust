from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from cobol2rust.toolchain import find_tool
from cobol2rust.verification import verify


BASE = date(1601, 1, 1)
LAST = (date(9999, 12, 31) - BASE).days + 1


def expected(name, value):
    value = int(value)
    try:
        if name == 'INTEGER-OF-DATE':
            result = date(value // 10000, value // 100 % 100, value % 100)
            return (result - BASE).days + 1 if result >= BASE else 0
        if name == 'INTEGER-OF-DAY':
            year, day = divmod(value, 1000)
            if not 1601 <= year <= 9999 or day < 1:
                return 0
            result = date(year, 1, 1) + timedelta(days=day - 1)
            return (result - BASE).days + 1 if result.year == year else 0
        if not 1 <= value <= LAST:
            return 0
        result = BASE + timedelta(days=value - 1)
        if name == 'DATE-OF-INTEGER':
            return result.year * 10000 + result.month * 100 + result.day
        return result.year * 1000 + (result - date(result.year, 1, 1)).days + 1
    except (ValueError, OverflowError):
        return 0


def program(body, storage=''):
    return ('identification division. program-id. calendar-domain.\n'
            'data division. working-storage section.\n' + storage +
            '\nprocedure division.\n' + body + '\nstop run.\n')


@unittest.skipUnless(find_tool('cobc') and find_tool('cargo'), 'GnuCOBOL and Cargo required')
class CalendarDomainNativeTests(unittest.TestCase):
    def compare(self, text, stdout, runtime_checks=False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calendar.cob'
            path.write_text(text, encoding='utf-8')
            report = verify(path, fmt='free', runtime_checks=runtime_checks)
        self.assertTrue(report['match'], report)
        self.assertEqual(report['cobol_stdout'], stdout, report)

    def test_calendar_boundaries_leap_years_and_display_shapes(self):
        cases = {
            'INTEGER-OF-DATE': [-2147483648, -1, 0, 16001231, 16010100, 16010101, 17000229,
                                19000229, 20000229, 20010229, 20240001, 20241301, 20240200,
                                20240229, 20240230, 20240431, 20241231, 99991231, 99991301,
                                100000000, 2147483647, '20240229.75'],
            'INTEGER-OF-DAY': [-1, 0, 1600366, 1601000, 1601001, 1900366, 2000366, 2000367,
                               2024366, 2025366, 9999365, 9999366, 10000001, '2024060.9'],
            'DATE-OF-INTEGER': [-2147483648, -1, 0, 1, 59, 365, 366, LAST, LAST + 1, 2147483647, '1.9'],
            'DAY-OF-INTEGER': [-2147483648, -1, 0, 1, 59, 365, 366, LAST, LAST + 1, 2147483647, '1.9'],
        }
        body, stdout = [], []
        for name, values in cases.items():
            width = 8 if name == 'DATE-OF-INTEGER' else 7 if name == 'DAY-OF-INTEGER' else 9
            for value in values:
                body.append(f'display function {name}({value})')
                stdout.append(f'{expected(name, float(value) if isinstance(value, str) else value):0{width}d}\n')
        self.compare(program('\n'.join(body)), ''.join(stdout))

    def test_invalid_calendar_values_in_fields_continue_with_checks_enabled(self):
        storage = ('01 display-a pic s9(10).\n01 packed-a pic s9(10) comp-3.\n'
                   '01 binary-a pic s9(10) comp-5.\n')
        body, stdout = [], []
        for value in (-1, 0, 20260230, 2025366, 3067672):
            body.append(f'move {value} to display-a packed-a binary-a')
            for field in ('display-a', 'packed-a', 'binary-a'):
                for name, width in (('INTEGER-OF-DATE', 9), ('INTEGER-OF-DAY', 9),
                                    ('DATE-OF-INTEGER', 8), ('DAY-OF-INTEGER', 7)):
                    body.append(f'display function {name}({field})')
                    stdout.append(f'{expected(name, value):0{width}d}\n')
        body.append('display function date-of-integer(function integer-of-date(20260230))')
        stdout.append('00000000\n')
        self.compare(program('\n'.join(body), storage), ''.join(stdout), runtime_checks=True)
