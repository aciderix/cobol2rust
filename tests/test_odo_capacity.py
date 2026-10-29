from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from cobol2rust.cli import convert
from cobol2rust.toolchain import ROOT, build_rust, find_tool
from cobol2rust.verification import verify


def source(body):
    return ('identification division. program-id. odo-profile.\n'
            'data division. working-storage section.\n'
            '01 count-a pic s99 value 2.\n01 index-a pic 99 value 2.\n'
            '01 group-a. 05 row-a occurs 0 to 4 depending on count-a pic x value "A".\n'
            'procedure division.\n' + body + '\nstop run.\n')


@unittest.skipUnless(find_tool('cobc') and find_tool('cargo'), 'GnuCOBOL and Cargo required')
class OdoCapacityNativeTests(unittest.TestCase):
    def test_indexed_capacity_and_logical_group_length_match_native(self):
        report = verify(ROOT / 'tests/fixtures/odo_capacity.cob', fmt='free')
        self.assertTrue(report['match'], report)
        self.assertEqual(report['cobol_stdout'],
                         'length|05|PA1A1|\nindexed|B4|\nzero|B4|\nhigh|B4|\nnegative|B4|\nactive|PA1A1|\n')

    def test_active_element_matches_native_with_runtime_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'checked.cob'
            path.write_text(source('move "Z" to row-a(index-a) display row-a(index-a).'), encoding='utf-8')
            report = verify(path, fmt='free', runtime_checks=True)
        self.assertTrue(report['match'], report)
        self.assertEqual(report['cobol_stdout'], 'Z\n')

    def test_sort_uses_the_logical_count_while_indexed_access_uses_capacity(self):
        body = ('move "D" to row-a(1) move "C" to row-a(2) '
                'move "B" to row-a(3) move "A" to row-a(4) '
                'sort row-a ascending key row-a '
                'display row-a(1) row-a(2) row-a(3) row-a(4).')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sort-active.cob'
            path.write_text(source(body), encoding='utf-8')
            report = verify(path, fmt='free')
        self.assertTrue(report['match'], report)
        self.assertEqual(report['cobol_stdout'], 'CDBA\n')


@unittest.skipUnless(find_tool('cargo'), 'Cargo required')
class OdoCapacityRuntimeTests(unittest.TestCase):
    def test_unchecked_subscript_keeps_the_physical_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'capacity.cob'
            path.write_text(source('accept count-a accept index-a '
                                   'move "Z" to row-a(index-a) display row-a(index-a).'), encoding='utf-8')
            convert(path, root / 'rust', fmt='free')
            binary = build_rust(root / 'rust')
            for count in (-1, 0, 2, 9):
                with self.subTest(count=count):
                    result = subprocess.run([str(binary)], input=f'{count}\n4\n'.encode(),
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, b'Z\n')
            for index in (0, 5):
                with self.subTest(index=index):
                    result = subprocess.run([str(binary)], input=f'2\n{index}\n'.encode(),
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 70)
                    self.assertIn(b'COBOL subscript out of bounds', result.stderr)
