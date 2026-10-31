from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from cobol2rust.cli import convert
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, compiler_env, find_tool
from cobol2rust.verification import verify


FIXTURE = ROOT / 'tests/fixtures/system_byte_calls.cob'
FIXTURE_DIGEST = 'd420b7baf1c856087bc5d76514c10da561903bd4b3b036b231ec8406aa275515'


def program(storage, body):
    return ('identification division. program-id. system-call-case.\n'
            'data division. working-storage section.\n' + storage +
            '\nprocedure division.\n' + body + '\nstop run.\n')


SCALAR_CASES = [
    ('literal-decimal', '2.0'),
    ('fractional-display', 'decimal-a'),
    ('negative-display', 'negative-a'),
    ('explicit-sign', 'explicit-sign-a'),
    ('fractional-packed', 'packed-number-a'),
    ('negative-packed', 'negative-packed'),
    ('fractional-native', 'native-decimal'),
    ('display-trailing-P', 'scaled-display'),
    ('binary-trailing-P', 'scaled-binary'),
    ('packed-trailing-P', 'scaled-packed'),
    ('packed6-odd-P', 'scaled-packed6'),
    ('binary-leading-P', 'leading-binary'),
    ('large-display', 'large-display'),
    ('large-native', 'large-native'),
    ('large-packed', 'large-packed'),
    ('size1-wrap', 'size 1 small-wrap-a'),
    ('size1-negative', 'size 1 -1'),
    ('size1-signed-cast', 'unsigned size 1 255'),
    ('size2-wrap', 'size 2 medium-wrap-a'),
    ('size-default-wrap', 'size default large-display'),
    ('size8-wrap', 'size 8 4294967298'),
    ('size-auto-negative', 'size auto -4294967296'),
    ('unsigned64', 'unsigned size 8 18446744073709551615'),
    ('intrinsic-integer', 'function integer-part(2.5)'),
    ('declared-length', 'length of buffer-a'),
    ('invalid-display', 'bad-length'),
    ('invalid-packed-table', 'size 1 invalid-packed'),
    ('inherited-trailing', 'inherited-sign-a'),
    ('inherited-leading-separate', 'inherited-leading-a'),
]


def scalar_program():
    storage = '''01 buffer-a pic x(256).
01 decimal-a pic 9v9 value 2.5.
01 negative-a pic s9v9 value -2.5.
01 explicit-sign-a pic s9v9 sign trailing value -2.5.
01 packed-number-a pic 9v9 comp-3 value 2.5.
01 negative-packed pic s9v9 comp-3 value -2.5.
01 native-decimal pic 9v9 comp-5 value 2.5.
01 scaled-display pic 99pp value 100.
01 scaled-binary pic 99pp comp-5 value 100.
01 scaled-packed pic 99pp comp-3 value 100.
01 scaled-packed6 pic 99p comp-6 value 120.
01 leading-binary pic pp99 comp-5 value 0.0012.
01 large-display pic 9(10) value 4294967298.
01 large-native pic 9(10) comp-5 value 4294967298.
01 large-packed pic 9(10) comp-3 value 4294967298.
01 small-wrap-a pic 9(3) value 258.
01 medium-wrap-a pic 9(5) value 65539.
01 bad-raw pic x value x'ff'.
01 bad-length redefines bad-raw pic 9.
01 bad-packed-raw pic xxx value x'2f001f'.
01 invalid-packed redefines bad-packed-raw pic 9(5) comp-3.
01 sign-group sign trailing.
 02 inherited-sign-a pic s9v9 value -2.5.
01 leading-group sign leading separate.
 02 inherited-leading-a pic s9v9 value 2.5.
'''
    calls = []
    for label, operand in SCALAR_CASES:
        calls.append('move all "abcdefgh" to buffer-a\n'
                     f'call "C$TOUPPER" using buffer-a by value {operand} end-call\n'
                     f'display "{label}:" function hex-of(buffer-a(1:32))\n')
    return program(storage, ''.join(calls))


def alias_program():
    return program('''01 bytes-a pic x(6).
01 source-a pic x(4) value 'abcd'.
01 literal-result pic x(4).
01 adjacent-a.
 02 head-a pic xx.
 02 tail-a pic xxx.
01 call-name pic x(16).
''', '''move x'010204081020' to bytes-a
call 'CBL_OR' using bytes-a(1:5) bytes-a(2:5) by value 5 end-call
display 'forward:' function hex-of(bytes-a)
move x'010204081020' to bytes-a
call 'CBL_XOR' using bytes-a(2:5) bytes-a(1:5) by value 5 end-call
display 'backward:' function hex-of(bytes-a)
move x'010204081020' to bytes-a
call 'CBL_NOR' using bytes-a bytes-a by value 6 end-call
display 'same:' function hex-of(bytes-a)
call 'C$TOUPPER' using by content source-a by value 4 end-call
display 'content:' source-a
call 'CBL_OR' using 'abcd' by content source-a by value 4 end-call
display 'content-target:' source-a
move low-values to literal-result
call 'CBL_OR' using 'wxyz' literal-result by value 4 end-call
display 'constant-source:' literal-result
move 'abcde' to adjacent-a
call 'C$TOUPPER' using head-a by value 3 end-call
display 'past-picture:' adjacent-a
move 'abcde' to adjacent-a
call 'C$TOUPPER' using adjacent-a(2:1) by value 3 end-call
display 'past-refmod:' adjacent-a
move 'C$TOLOWER' to call-name
call call-name using adjacent-a by value 5
 on exception display 'bad exception' end-display
 not on exception display 'dynamic:' adjacent-a end-display
end-call
''')


class SystemCallFrontendTests(unittest.TestCase):
    def test_literal_system_calls_require_the_native_minimum_arity(self):
        for body in ['call "CBL_TOUPPER".', 'call "CBL_TOUPPER" using data-a.',
                     'call "CBL_AND" using data-a by value 1.']:
            with self.subTest(body=body), self.assertRaisesRegex(CobolError, 'arguments'):
                Parser(program('01 data-a pic xxxx.', body)).parse()

    def test_unmodelled_intrinsic_field_descriptions_are_refused(self):
        for expr in ['function abs(length-a)', 'function max(length-a, length-a)',
                     'function mean(length-a)']:
            with self.subTest(expr=expr), self.assertRaisesRegex(CobolError, 'description conservée'):
                Emitter(Parser(program('01 data-a pic xxxx. 01 length-a pic 9v9 comp-3.',
                                       f'call "C$TOUPPER" using data-a by value {expr}.')).parse()).generate()

    def test_out_of_range_literal_sizes_are_refused(self):
        for args in ['data-a by value size 1 258', 'data-a by value size 2 65539',
                     'data-a by value size default 4294967298']:
            with self.subTest(args=args), self.assertRaises(CobolError):
                Emitter(Parser(program('01 data-a pic xxxx.',
                                       f'call "C$TOUPPER" using {args} end-call.')).parse()).generate()

    def test_invalid_size_and_modes_are_refused(self):
        for args in ['by reference size 1 data-a', 'by content size 4 data-a',
                     'data-a by value size 3 2', 'data-a by value size 16 2',
                     'data-a by value omitted']:
            with self.subTest(args=args), self.assertRaises(CobolError):
                Emitter(Parser(program('01 data-a pic xxxx.',
                                       f'call "C$TOUPPER" using {args} end-call.')).parse()).generate()

    def test_unsupported_user_value_abi_is_a_named_refusal(self):
        with self.assertRaisesRegex(CobolError, 'BY VALUE|ABI'):
            Emitter(Parser(program('01 data-a pic xxxx.', 'call "another-program" using by value 4 end-call.')).parse()).generate()


@unittest.skipUnless(find_tool('cobc') and find_tool('cargo'), 'GnuCOBOL and Cargo required')
class SystemCallNativeTests(unittest.TestCase):
    def test_literal_and_dynamic_system_name_normalization(self):
        text = program('01 data-a pic xxxx value "abcd". 01 call-name pic x(24).', '''
call ' /tmp/CBL_TOUPPER ' using data-a by value 1 end-call
call 'folder\\CBL_TOUPPER' using data-a(2:) by value 1 end-call
move ' /tmp/CBL_TOUPPER' to call-name
call call-name using data-a(3:) by value 1 end-call
move x'4324544f555050455200' to call-name
call call-name using data-a(4:) by value 1 end-call
display data-a
''')
        report = self.compare(text)
        self.assertEqual(report['cobol_stdout'], 'ABCD\n')
        self.assertIn('libcob: warning:', report['cobol_stderr'])

    def test_dynamic_contained_program_precedes_system_symbol(self):
        text = program('01 call-name pic x(12) value "CBL_AND". 01 data-a pic xxx value "bad". '
                       '01 mask-a pic xxx value low-values.',
                       'call call-name using data-a end-call display data-a '
                       'call "CBL_AND" using mask-a data-a by value 3 end-call '
                       'display function hex-of(data-a)')
        text += '''identification division. program-id. CBL_AND.
data division. linkage section. 01 arg-a pic xxx.
procedure division using arg-a. move 'ok!' to arg-a goback.
end program CBL_AND. end program system-call-case.
'''
        self.assertEqual(self.compare(text)['cobol_stdout'], 'ok!\n000000\n')

    def test_extra_static_scalar_does_not_read_unbound_linkage(self):
        text = program('01 data-a pic xxx value "abc".\nlinkage section. 01 absent-a pic 9(9) comp-5.',
                       'call "C$TOUPPER" using data-a by value 1 absent-a end-call display data-a')
        self.assertEqual(self.compare(text)['cobol_stdout'], 'Abc\n')

    def compare(self, text, **options):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'system-call.cob'
            path.write_text(text, encoding='utf-8')
            report = verify(path, fmt='free', **options)
        self.assertTrue(report['match'], report)
        self.assertTrue(report['stderr_match'], report)
        self.assertEqual(report['cobol_exit'], 0)
        return report

    def fixture(self, checks=False):
        with patch.dict(os.environ, {'LC_ALL': 'C'}):
            report = verify(FIXTURE, fmt='free', runtime_checks=checks)
        self.assertTrue(report['match'], report)
        self.assertTrue(report['stderr_match'], report)
        self.assertEqual(report['cobol_stdout'], 'byte calls OK\n')
        self.assertEqual(report['cobol_files']['system-bytes.bin'],
                         {'bytes': 3072, 'sha256': FIXTURE_DIGEST})
        self.assertEqual(report['cobol_exit'], 0)

    def test_all_byte_values_and_system_aliases_match_native(self):
        self.fixture()

    def test_raw_byte_operations_with_runtime_checks(self):
        self.fixture(checks=True)

    def test_live_overlaps_content_copies_constants_and_raw_addresses(self):
        report = self.compare(alias_program())
        self.assertEqual(report['cobol_stdout'], ALIAS_OUTPUT)

    def test_scalar_lengths_follow_native_c_casts_and_field_readers(self):
        for checks in [False, True]:
            with self.subTest(checks=checks):
                report = self.compare(scalar_program(), runtime_checks=checks)
                self.assertEqual(hashlib.sha256(report['cobol_stdout'].encode()).hexdigest(), SCALAR_DIGEST)

    def test_nonpositive_lengths_leave_null_addresses_untouched(self):
        text = program('01 text-a pic xxxx value "aBcD".', '''move 91 to return-code
call 'CBL_OR' using omitted omitted by value 0 end-call
if return-code not = 0 stop run returning 1 end-if
call 'CBL_NOT' using omitted by value -1 end-call
call 'C$TOUPPER' using omitted by value zero end-call
call 'C$TOLOWER' using text-a by value -1 end-call
display text-a
''')
        self.assertEqual(self.compare(text)['cobol_stdout'], 'aBcD\n')

    def test_unsupported_addresses_stop_before_accessing_foreign_memory(self):
        # These cases have undefined native memory accesses, so only Rust is
        # executed; this is a guard test, not a claim of native equivalence.
        text = program('01 text-a pic xxxx value "abcd". 01 selector-a pic xx.', '''accept selector-a
if selector-a = '0'
 call 'C$TOUPPER' using 'abcd' by value 4 end-call
else
 if selector-a = '-1'
  call 'C$TOUPPER' using omitted by value 1 end-call
 else
  call 'C$TOUPPER' using text-a by value 1000000 end-call
 end-if
end-if''')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'bounds.cob'
            path.write_text(text, encoding='utf-8')
            convert(path, root / 'rust', fmt='free')
            binary = build_rust(root / 'rust')
            for stdin, message in [(b'1000000\n', 'bounds|allocation|storage|mémoire|system'),
                                   (b'0\n', 'literal|read.only|const|littéral'),
                                   (b'-1\n', 'NULL|omitted|null|OMITTED')]:
                with self.subTest(stdin=stdin):
                    result = subprocess.run([str(binary)], input=stdin, capture_output=True,
                                            env=compiler_env(find_tool('rustc')), timeout=10)
                    self.assertEqual(result.returncode, 70)
                    self.assertRegex(result.stderr.decode(), message)


ALIAS_OUTPUT = ('forward:0103070F1F3F\nbackward:03060C183020\nsame:FEFDFBF7EFDF\n'
                'content:abcd\ncontent-target:abcd\nconstant-source:wxyz\n'
                'past-picture:ABCde\npast-refmod:aBCDe\ndynamic:abcde\n')
SCALAR_DIGEST = '4890e551b71bb9e9ac30ffe4c83e4fea159cd5b43ba54ff3edc0751285fec607'


if __name__ == '__main__':
    unittest.main()
