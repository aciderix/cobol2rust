from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body):
    return ("identification division.\nprogram-id. getopt-unit.\ndata division.\nworking-storage section.\n"
            "01 so pic x(8).\n01 lo pic x(38).\n01 ind pic 99.\n01 lonly pic 9.\n01 rc pic x(4).\n01 ov pic x(4).\n"
            f"procedure division.\n{body}\nstop run.\n")


class GetoptFrontendTests(unittest.TestCase):
    def test_long_only_is_a_c_int_by_value(self):
        rust = Emitter(Parser(program("call 'CBL_GC_GETOPT' using so lo ind by value lonly by reference rc ov.")).parse()).generate()[0]
        self.assertIn("system_runtime::call", rust)

    def test_other_by_value_targets_stay_refused(self):
        with self.assertRaisesRegex(CobolError, "BY VALUE"):
            Parser(program("call 'not-a-routine' using by value lonly.")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class GetoptNativeTests(unittest.TestCase):
    directory = ROOT / "tests" / "fixtures" / "getopt"

    def run_case(self, name, arguments):
        report = verify(self.directory / "getopt.cob", fmt="free", stdin=(self.directory / f"{name}.txt").read_bytes(),
                        arguments=arguments)
        self.assertTrue(report["match"] and report["stderr_match"], report)
        return report

    def test_short_long_permutation_and_flags_match_native(self):
        # Permutation of x1/x2 behind the options, '--', optional and
        # required arguments, -W, abbreviations sharing one flag, *flag = val.
        report = self.run_case("short", ["-a", "-bfoo", "-b", "bar", "-c", "-cval", "x1", "--version", "--val=3",
                                         "--value", "4", "--opt", "--opt=5", "--fla", "--flag2", "-W", "verbose",
                                         "-Wversion", "--ver", "x2", "--", "-a", "z"])
        self.assertIn("11  000 [\x00   ] 04 [      ] [1   ]\n", report["cobol_stdout"])
        self.assertEqual(report["cobol_stderr"], "./getopt: option '--ver' is ambiguous; possibilities: '--version' '--verbose'\n")

    def test_long_only_and_silent_colon_match_native(self):
        report = self.run_case("colon-long-only", ["-version", "-verb", "-fl", "-z", "-a", "-exactly-twenty-five-chars0", "-b"])
        self.assertIn("07  058 [:   ] 06", report["cobol_stdout"])
        self.assertEqual(report["cobol_stderr"], "")

    def test_messages_match_native(self):
        report = self.run_case("errors", ["-z", "--unknown", "--version=3", "--ve", "-ab", "--value"])
        self.assertIn("doesn't allow an argument", report["cobol_stderr"])
        self.assertTrue(report["cobol_stderr"].endswith("./getopt: option '--value' requires an argument\n"))


if __name__ == "__main__":
    unittest.main()
