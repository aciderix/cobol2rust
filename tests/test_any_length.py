from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.cli import convert
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, find_tool
from cobol2rust.verification import verify


def module(declaration='01 arg pic x any length.', body='goback.', using='using arg', section='linkage'):
    return ('identification division. program-id. SUB.\ndata division.\n'
            f'{section} section.\n{declaration}\nprocedure division {using}.\n{body}\n')


class AnyLengthFrontendTests(unittest.TestCase):
    def test_explicit_and_implicit_picture_have_dynamic_lengths(self):
        for declaration in ('01 arg any length.', '01 arg pic x(1) any length.',
                            '01 arg any length pic x justified synchronized.'):
            with self.subTest(declaration=declaration):
                program = Parser(module(declaration, 'display length of arg function length(arg) '
                                        'function length(arg(2:)) arg(20:30). goback.')).parse()
                self.assertTrue(program.fields['ARG'].any_length)
                rust = Emitter(program).generate()[0]
                self.assertIn('update_any_length', rust)
                self.assertIn('descriptor_size', rust)

    def test_invalid_declarations_are_refused(self):
        declarations = ['77 arg pic x any length.', '01 arg pic xx any length.',
                        '01 arg pic a any length.', '01 arg pic 9 any length.',
                        '01 arg any length occurs 1.', '01 arg any length value space.',
                        '01 arg any length. 05 child-a pic x.',
                        '01 arg any length. 01 other-a redefines arg pic x.',
                        '01 arg any length any length.']
        for declaration in declarations:
            with self.subTest(declaration=declaration), self.assertRaises(CobolError):
                Parser(module(declaration)).parse()
        for source in (module(using=''), module(section='working-storage', using=''),
                       module(body='goback. entry "ALT". goback.', using=''),
                       module(body='goback. entry "ALT" using arg. goback.', using='')):
            with self.subTest(source=source), self.assertRaises(CobolError):
                Parser(source).parse()

    def test_other_dynamic_formats_are_named_refusals(self):
        for declaration, diagnostic in [('01 arg any numeric.', 'ANY NUMERIC'),
                                        ('01 arg pic 9 any numeric.', 'ANY NUMERIC'),
                                        ('01 arg any length usage comp.', 'ANY LENGTH'),
                                        ('01 arg pic n any length.', 'ANY LENGTH')]:
            with self.subTest(declaration=declaration), self.assertRaisesRegex(CobolError, diagnostic):
                Parser(module(declaration)).parse()

    def test_global_dynamic_descriptors_are_a_named_refusal(self):
        with self.assertRaisesRegex(CobolError, 'ANY LENGTH GLOBAL'):
            Parser(module('01 arg pic x any length global.')).parse()

    def test_only_reference_can_forward_a_dynamic_parameter(self):
        Parser(module(body='call "OTHER" using arg(2:). goback.')).parse()
        with self.assertRaisesRegex(CobolError, 'BY REFERENCE'):
            Parser(module(body='call "OTHER" using by content arg. goback.')).parse()

    def test_constant_positions_still_require_positive_values(self):
        for ref in ('arg(0:)', 'arg(1:0)', 'arg(-1:2)'):
            with self.subTest(ref=ref), self.assertRaises(CobolError):
                Parser(module(body=f'display {ref}. goback.')).parse()

    def test_inspect_validation_uses_the_native_nominal_picture(self):
        with self.assertRaisesRegex(CobolError, 'taille|size|longueur'):
            Parser(module(body="inspect arg replacing all arg by 'XX'. goback.")).parse()


@unittest.skipUnless(find_tool('cobc') and find_tool('cargo'), 'GnuCOBOL and Cargo required')
class AnyLengthNativeTests(unittest.TestCase):
    def test_reference_modified_length_does_not_read_an_omitted_argument(self):
        source = ('identification division. program-id. MAIN.\nprocedure division.\n'
                  'call "SUB" using omitted\ngoback.\nend program MAIN.\n' +
                  module(body='display function length(arg(1:1))\n'
                              'display length of arg(1:)\ngoback.') + 'end program SUB.\n')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'omitted.cob'
            path.write_text(source, encoding='utf-8')
            report = verify(path, fmt='free')
        self.assertTrue(report['match'], report)
        self.assertEqual(report['cobol_stdout'], '000000001\n000000001\n')

    def test_storage_operations_and_argument_categories_match_native(self):
        report = verify(ROOT / 'tests' / 'fixtures' / 'any_length.cob', fmt='free')
        self.assertTrue(report['match'], report)
        lines = report['cobol_stdout'].splitlines()
        self.assertIn('read|000000006|000000006|000000005|01234u|1234u|', lines)
        self.assertIn('initialize| QQQQQ|', lines)
        self.assertIn('initialize| QQQQQQQQ|', lines)
        self.assertIn('numeric|1234     |', lines)
        self.assertIn('content|123456789|', lines)
        self.assertIn('right|      END|', lines)

    def test_size_is_received_for_each_call_without_a_nominal_width_limit(self):
        widths = [1, 2, 7, 129, 1024]
        declarations = '\n'.join(f'01 a-{n} pic x({n}) value all "Z".' for n in widths)
        calls = '\n'.join(f'call "SUB" using a-{n}' for n in widths)
        source = ('identification division. program-id. MAIN.\ndata division.\n'
                  f'working-storage section.\n{declarations}\nprocedure division.\n'
                  f'{calls}\ngoback.\nend program MAIN.\n' +
                  module(body='display length of arg. if arg = all "Z" display "equal" end-if. '
                              'move all "A" to arg. display function length(arg). goback.') +
                  'end program SUB.\n')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'widths.cob'
            path.write_text(source, encoding='utf-8')
            report = verify(path, fmt='free')
        self.assertTrue(report['match'], report)
        self.assertEqual(report['cobol_stdout'], ''.join(f'{n:09d}\nequal\n{n:09d}\n' for n in widths))


@unittest.skipUnless(find_tool('cargo'), 'Cargo required')
class AnyLengthRuntimeTests(unittest.TestCase):
    def test_entry_descriptor_can_exceed_argument_until_storage_is_read(self):
        source = ('identification division. program-id. MAIN.\ndata division.\n'
                  'working-storage section.\n01 three pic xxx value "abc".\n'
                  '01 six pic x(6) value "ABCDEF".\nprocedure division.\n'
                  'call "SUB" using three six\ncall "READ-ARG" using three\n'
                  'goback.\nend program MAIN.\n' +
                  module('01 first-arg pic x any length.\n01 arg pic x any length.',
                         'goback.\nentry "READ-ARG" using arg.\n'
                         'display length of arg\ndisplay arg\ngoback.',
                         'using first-arg arg') + 'end program SUB.\n')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'entry-read.cob'
            path.write_text(source, encoding='utf-8')
            convert(path, root / 'rust', fmt='free')
            result = subprocess.run([str(build_rust(root / 'rust'))], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 70)
        self.assertEqual(result.stdout, b'000000006\n')
        self.assertIn(b'item extends beyond the storage at its address', result.stderr)
