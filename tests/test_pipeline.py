from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cobol2rust.cli import analysis_cache, convert, parse_cached
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser, TokenList, lex
from cobol2rust.toolchain import ROOT, build_rust, find_tool

sys.path.insert(0, str(ROOT / "tools"))
from gap_inventory import inventory_source, plan  # noqa: E402


SOURCE = ("identification division.\nprogram-id. outer.\ndata division.\nworking-storage section.\n"
          "78 local-size value 3.\n01 c constant global as 7.\n01 x pic 9(local-size).\nprocedure division.\n"
          "display local-size c x.\nstop run.\nidentification division.\nprogram-id. inner.\n"
          "procedure division.\ndisplay c.\nend program inner.\nend program outer.\n")


class AnalysisCacheTests(unittest.TestCase):
    def test_parse_copies_are_independent_and_identical(self):
        with analysis_cache():
            first = parse_cached(SOURCE)
            first.name = "changed"
            second = parse_cached(SOURCE)
        self.assertEqual(second.name, Parser(SOURCE).parse().name)
        self.assertEqual(Emitter(second).generate()[0], Emitter(Parser(SOURCE).parse()).generate()[0])

    def test_refusals_are_cached_as_refusals(self):
        source = SOURCE.replace("display local-size c x.", "move zz-undefined to x.")
        with analysis_cache():
            for _ in range(2):
                with self.assertRaisesRegex(CobolError, "zz-undefined"):
                    parse_cached(source)

    def test_without_the_context_nothing_is_kept(self):
        program = parse_cached(SOURCE)
        program.name = "changed"
        self.assertNotEqual(parse_cached(SOURCE).name, "changed")


class ConstantScopeTests(unittest.TestCase):
    def test_constant_substitution_keeps_cb_reset_78_scope(self):
        # The level 78 constant ends with its program; the GLOBAL one reaches
        # the contained program.
        program = Parser(SOURCE).parse()
        self.assertEqual(program.fields["X"].size, 3)
        inner = Parser(SOURCE.replace("display c.", "display local-size."))
        with self.assertRaisesRegex(CobolError, "local-size"):
            inner.parse()

    def test_index_follows_changes(self):
        tokens = TokenList(lex("a b a . a"))
        self.assertEqual(tokens.positions("A"), [0, 2, 4])
        tokens.insert(0, lex("z")[0])
        self.assertEqual(tokens.positions("A"), [1, 3, 5])
        tokens.substitute("A", 2, tokens.scope_end(2, False), lambda token: lex("'q'")[0])
        self.assertEqual(tokens.positions("A"), [1])
        self.assertEqual([token.text for token in tokens][:6], ["z", "a", "b", "q", ".", "q"])


def inventory(body, storage="01 x pic 9.\n"):
    source = ("identification division.\nprogram-id. inventory-case.\ndata division.\nworking-storage section.\n"
              f"{storage}procedure division.\n{body}\nstop run.\n")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "case.cob"
        path.write_text(source, encoding="utf-8")
        try:
            Parser(source).parse()
        except CobolError as error:
            first = str(error)
        else:
            first = None
        return first, inventory_source(str(path), "free", [], first or "")


class GapInventoryTests(unittest.TestCase):
    def test_recovery_lists_later_refusals_and_keeps_the_first(self):
        first, result = inventory("move zz-undefined to x.\ndisplay x.\ngoback returning 0.")
        self.assertIn("zz-undefined", first)
        self.assertTrue(result["matches_measure"] and result["complete"])
        self.assertEqual(result["diagnostics"], ["expression non prise en charge: zz-undefined",
                                                 "GOBACK RETURNING non pris en charge"])

    def test_uses_of_a_skipped_declaration_are_not_repeated(self):
        first, result = inventory("display bad.\nmove 1 to bad.", "01 x pic 9.\n01 bad usage float-decimal-16.\n")
        self.assertEqual(result["diagnostics"], ["USAGE/clause non pris en charge: float-decimal-16"])

    def test_the_terminator_of_a_refused_statement_is_consumed(self):
        first, result = inventory("perform 2 times\n call 'sub' using by value 1 end-call\n end-perform.\ndisplay x.")
        self.assertEqual(len(result["diagnostics"]), 1, result)
        self.assertTrue(result["complete"])

    def test_plan_counts_only_complete_inventories(self):
        entries = [{"diagnostics": ["a"], "complete": True, "matches_measure": True},
                   {"diagnostics": ["a", "b"], "complete": True, "matches_measure": True},
                   {"diagnostics": ["b"], "complete": False, "matches_measure": True},
                   {"diagnostics": ["c"], "complete": True, "matches_measure": False}]
        summary = plan(entries)
        self.assertEqual((summary["matching"], summary["complete"]), (3, 2))
        self.assertEqual([(step["diagnostic"], step["cumulative"]) for step in summary["greedy"]], [("a", 1), ("b", 2)])


@unittest.skipUnless(find_tool("cargo"), "Cargo required")
class ParallelBuildTests(unittest.TestCase):
    def test_programs_with_one_name_built_in_parallel_keep_their_executable(self):
        # Cargo's fingerprint of a root package ignores its path: without the
        # clean of build_rust, a second crate of the same name reused the first
        # executable while the first project still existed.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(6):
                source = root / f"p{index}.cob"
                source.write_text(f'identification division.\nprogram-id. prog.\nprocedure division.\n'
                                  f'display "v{index}".\nstop run.\n', encoding="utf-8")
                convert(source, root / f"r{index}", fmt="free")

            def run(index):
                binary = build_rust(root / f"r{index}")
                return subprocess.run([str(binary)], capture_output=True, text=True, timeout=30).stdout.strip()
            with ThreadPoolExecutor(3) as pool:
                self.assertEqual(list(pool.map(run, range(6))), [f"v{index}" for index in range(6)])
            self.assertEqual([run(index) for index in range(6)], [f"v{index}" for index in range(6)])


if __name__ == "__main__":
    unittest.main()
