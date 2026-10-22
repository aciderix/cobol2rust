from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import find_tool
from cobol2rust.verification import verify


def program(configuration="", data="", body='display "CONFIG-OK" stop run.'):
    return ("identification division.\nprogram-id. configuration-case.\n"
            "environment division.\n" + configuration + "\n" + data +
            "procedure division.\n" + body + "\n")


class ConfigurationTests(unittest.TestCase):
    def test_machine_names_and_empty_sections_preserve_emission(self):
        bare = Parser(program()).parse()
        reference = Emitter(bare).generate()[0]
        for configuration in [
            "configuration section.",
            "configuration section. source-computer. GNU-Linux.",
            "configuration section. object-computer. IBM-370.",
            "configuration section. source-computer. GNU-Linux. object-computer. GNU-Linux.",
            "configuration section. object-computer. IBM-370. source-computer. GNU-Linux.",
        ]:
            with self.subTest(configuration=configuration):
                result = Emitter(Parser(program(configuration)).parse()).generate()[0]
                self.assertEqual(result, reference)

    def test_configuration_precedes_existing_file_control(self):
        configuration = '''configuration section.
source-computer. GNU-Linux.
object-computer. GNU-Linux.
input-output section.
file-control.
select records-file assign to "records.txt" organization line sequential.
'''
        data = "data division. file section. fd records-file. 01 record-a pic x(3).\n"
        parsed = Parser(program(configuration, data)).parse()
        self.assertEqual(parsed.files["RECORDS-FILE"].path.text, "records.txt")
        self.assertIn("fn main", Emitter(parsed).generate()[0])

    def test_semantic_configuration_is_never_silently_ignored(self):
        cases = [
            "source-computer. GNU-Linux with debugging mode.",
            "object-computer. GNU-Linux memory size 1024 words.",
            "object-computer. GNU-Linux program collating sequence is alphabet-a.",
            "object-computer. GNU-Linux segment-limit is 20.",
            "special-names. decimal-point is comma.",
            "special-names. currency sign is '$'.",
            "special-names. alphabet alphabet-a is native.",
            "repository. function all intrinsic.",
            "source-computer. GNU-Linux. source-computer. GNU-Linux.",
            "object-computer. GNU-Linux. object-computer. GNU-Linux.",
        ]
        for configuration in cases:
            with self.subTest(configuration=configuration), self.assertRaises(CobolError):
                Parser(program("configuration section. " + configuration)).parse()

    def test_incomplete_and_misplaced_paragraphs_fail(self):
        for configuration in [
            "configuration section. source-computer.",
            "configuration section. source-computer. GNU-Linux",
            "source-computer. GNU-Linux.",
            "configuration section. object-computer. GNU-Linux. unknown-paragraph.",
            "input-output section. file-control. configuration section.",
        ]:
            with self.subTest(configuration=configuration), self.assertRaises(CobolError):
                Parser(program(configuration)).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ConfigurationNativeTests(unittest.TestCase):
    def test_native_and_generated_programs_match_with_configuration_and_files(self):
        configuration = '''configuration section.
source-computer. GNU-Linux.
object-computer. GNU-Linux.
input-output section.
file-control.
select records-file assign to "records.txt" organization line sequential.
'''
        data = "data division. file section. fd records-file. 01 record-a pic x(3).\n"
        body = '''open output records-file
move "OK" to record-a
write record-a
close records-file
display "CONFIG-OK"
stop run.'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "configuration.cob"
            source.write_text(program(configuration, data, body), encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "CONFIG-OK\n")
        self.assertEqual(set(report["cobol_files"]), {"records.txt"})
        self.assertEqual(report["cobol_files"]["records.txt"]["bytes"], 3)


if __name__ == "__main__":
    unittest.main()
