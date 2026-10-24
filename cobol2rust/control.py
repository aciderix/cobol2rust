"""Lower procedure control to explicit positions and PERFORM return checkpoints.

Procedure fallthrough and transfers share the same graph. A transfer never
implicitly unwinds a PERFORM: only its matching checkpoint can return it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .frontend import CobolError, Expr, ProcedureBlock, Program, Stmt


@dataclass
class Node:
    op: str
    args: tuple = ()
    stmt: Stmt | None = None


class ControlGraph:
    def __init__(self, program: Program, blocks: list[ProcedureBlock]):
        self.program = program
        self.blocks = blocks
        self.nodes: list[Node] = []
        self.times_slots = 0
        self._end = self._add("end")

        # Allocate all procedure positions before lowering any forward calls.
        self.block_entries = [self._add("jump", (self._end,)) for _ in blocks]
        self.paragraph_checkpoints = [self._add("checkpoint", (self._end,)) for _ in blocks]
        self.section_checkpoints = {
            name: self._add("checkpoint", (self._following(end),))
            for name, (_, end) in program.sections.items()
        }
        for index, block in enumerate(blocks):
            following = self._following(index + 1)
            if block.section is not None and program.sections[block.section][1] == index + 1:
                following = self.section_checkpoints[block.section]
            checkpoint = self.paragraph_checkpoints[index]
            self.nodes[checkpoint] = Node("checkpoint", (following,))

        for index, block in enumerate(blocks):
            # NEXT SENTENCE goes to the statement after the next separator
            # period; markers are seen in reverse, so this is the one ahead.
            self._sentence = self.paragraph_checkpoints[index]
            body = self._body(block.body, self.paragraph_checkpoints[index], index)
            self.nodes[self.block_entries[index]] = Node("jump", (body,))
        self.entry = self._following(program.main_block)

    def _add(self, op: str, args: tuple = (), stmt: Stmt | None = None) -> int:
        position = len(self.nodes)
        self.nodes.append(Node(op, args, stmt))
        return position

    def _following(self, block: int) -> int:
        return self.block_entries[block] if block < len(self.block_entries) else self._end

    def _target(self, name: str) -> tuple[int, int]:
        start, _ = self.program.procedure_range(name)
        if name in self.section_checkpoints:
            checkpoint = self.section_checkpoints[name]
        else:
            checkpoint = self.paragraph_checkpoints[start]
        return self.block_entries[start], checkpoint

    @staticmethod
    def _error(stmt: Stmt, message: str):
        raise CobolError(f"ligne {stmt.line}: {message}")

    def _kind(self, expr: Expr) -> str:
        if expr.op == "var":
            ref = expr.args[0]
            return "text" if ref.start is not None else self.program.fields[ref.name].kind
        if expr.op in {"number", "text"}:
            return expr.op
        if expr.op.startswith("cmp") or expr.op in {"and", "or", "not", "condition", "bool", "numeric_class", "switch", "user_class"}:
            return "bool"
        return "number"

    def _body(self, statements: list[Stmt], after: int, block: int) -> int:
        position = after
        for stmt in reversed(statements):
            position = self._statement(stmt, position, block)
        return position

    def _statement(self, stmt: Stmt, after: int, block: int) -> int:
        op, args = stmt.op, stmt.args
        if op == "sentence_end":
            self._sentence = after
            return after
        if op == "next_sentence":
            return self._add("jump", (self._sentence,), stmt)
        if op == "if":
            condition, yes, no = args
            return self._add("branch", (condition, self._body(yes, after, block),
                                        self._body(no, after, block)), stmt)
        if op == "evaluate":
            subject, branches, otherwise = args
            destinations = [(value, self._body(body, after, block)) for value, body in branches]
            return self._add("evaluate", (subject, destinations, self._body(otherwise, after, block)), stmt)
        if op == "read":
            name, into, exception, success, _ = args
            return self._add("read", (name, into, self._body(success, after, block),
                                      self._body(exception, after, block), after,
                                      self._declaratives(name, after)), stmt)
        if op in {"open", "close"} and len(args[0]) > 1:
            # cobc gives each file its own implicit statement and error check.
            position = after
            for part in reversed(args[0]):
                position = self._statement(Stmt(op, ([part],), stmt.line), position, block)
            return position
        if op in {"open", "close", "write", "rewrite", "delete", "start"}:
            name = args[0][0][1] if op == "open" else args[0][0][0] if op == "close" else args[0]
            invalid = valid = None
            if op in {"write", "rewrite", "delete", "start"} and (args[-2] or args[-1]):
                # INVALID KEY handles every 2x status; NOT INVALID KEY every 0x.
                invalid = self._body(args[-2], after, block) if args[-2] else None
                valid = self._body(args[-1], after, block)
            return self._add("io", (stmt, after, self._declaratives(name, after), invalid, valid), stmt)
        if op == "sequence":
            return self._body(args[0], after, block)
        if op == "string":
            return self._add("string", (self._body(args[3], after, block), self._body(args[4], after, block)), stmt)
        if op == "unstring":
            return self._add("unstring", (self._body(args[5], after, block), self._body(args[6], after, block), after), stmt)
        if op == "arithmetic":
            shared, items, error, success = args
            return self._add("arithmetic", (shared, items, self._body(error, after, block),
                                            self._body(success, after, block)), stmt)
        if op == "loop":
            return self._loop(stmt, after, block)
        if op == "sort":
            # cobc: init and keys, input (USING or PERFORM), output (GIVING or
            # PERFORM), then cob_file_sort_close.
            name, keys, source, target, merge = args
            position = self._add("sort_close", (name, after), stmt)
            if target[0] == "procedure":
                position = self._statement(Stmt("call", (target[1],), stmt.line), position, block)
            else:
                position = self._add("sort_giving", (name, target[1], position), stmt)
            if source[0] == "procedure":
                position = self._statement(Stmt("call", (source[1],), stmt.line), position, block)
            else:
                position = self._add("sort_using", (name, source[1], position), stmt)
            return self._add("sort_init", (name, keys, position), stmt)
        if op == "search":
            table, index, varying, at_end, whens = args
            # Loop: end test, the WHENs in order, then index + 1 (and the
            # VARYING item set from it) before testing again.
            step = self._add("search_step", (index, varying, None), stmt)
            position = step
            for condition, body in reversed(whens):
                position = self._add("branch", (condition, self._body(body, after, block), position), stmt)
            ending = self._body(at_end, after, block) if at_end is not None else after
            test = self._add("search_test", (table, index, ending, position), stmt)
            self.nodes[step] = Node("search_step", (index, varying, test), stmt)
            return test
        if op == "search_all":
            table, index, at_end, keys, body = args
            ending = self._body(at_end, after, block) if at_end is not None else after
            return self._add("search_all", (table, index, keys, self._body(body, after, block), ending), stmt)
        if op == "return_sort":
            name, into, at_end, not_at_end = args
            return self._add("return_sort", (name, into, self._body(at_end, after, block),
                                             self._body(not_at_end, after, block)), stmt)
        if op == "call":
            targets = args[0]
            entry, checkpoint = self._target(targets[0])
            if len(targets) == 2:
                _, checkpoint = self._target(targets[1])
            return self._add("call", (entry, checkpoint, after), stmt)
        if op == "goto":
            targets, controller = args
            return self._add("goto", ([self._target(name)[0] for name in targets], controller, after), stmt)
        if op == "exit_paragraph":
            return self._add("jump", (self.paragraph_checkpoints[block],), stmt)
        if op == "exit_section":
            section = self.blocks[block].section
            if section is None:
                self._error(stmt, "EXIT SECTION requiert une section explicite")
            return self._add("jump", (self.section_checkpoints[section],), stmt)
        if op == "stop":
            return self._add("stop_run", (), stmt)
        if op in {"goback", "exit_program"}:
            # A main program ignores EXIT PROGRAM; GOBACK there is STOP RUN.
            return self._add(op, (after,), stmt)
        if op == "call_program":
            target, arguments, exception, success = args
            return self._add("call_program", (target, arguments, after,
                                              self._body(exception, after, block) if exception else None,
                                              self._body(success, after, block)), stmt)
        return self._add("execute", (stmt, after), stmt)

    def _declaratives(self, file_name: str, after: int):
        """USE procedures run like a PERFORM of their section, then resume."""
        def call(section):
            entry, checkpoint = self._target(section)
            return self._add("call", (entry, checkpoint, after))
        if file_name in self.program.file_declaratives:
            return ("file", call(self.program.file_declaratives[file_name]))
        if self.program.mode_declaratives:
            return ("modes", {mode: call(section) for mode, section in self.program.mode_declaratives.items()})
        return None

    def _loop(self, stmt: Stmt, after: int, block: int) -> int:
        mode, control, body = stmt.args
        if mode == "once":
            return self._body(body, after, block)
        if mode == "times":
            count = control[0]
            if self._kind(count) != "number":
                self._error(stmt, "TIMES requiert un nombre")
            slot = self.times_slots
            self.times_slots += 1
            test = self._add("times_test", (), stmt)
            step = self._add("times_step", (slot, test), stmt)
            entry = self._body(body, step, block)
            self.nodes[test] = Node("times_test", (slot, entry, after), stmt)
            return self._add("times_init", (slot, count, test), stmt)
        if mode == "until":
            condition, test_after = control
            test = self._add("branch", (), stmt)
            entry = self._body(body, test, block)
            self.nodes[test] = Node("branch", (condition, after, entry), stmt)
            return entry if test_after else test
        if mode == "varying":
            levels, test_after = control
            for var, _, step, _ in levels:
                if var.start is not None or self.program.fields[var.name].kind != "number":
                    self._error(stmt, "PERFORM VARYING requiert un contrôle numérique non édité")
                if self._kind(step) != "number":
                    self._error(stmt, "BY requiert un nombre")

            def initialize(level, continuation):
                var, start, _, _ = levels[level]
                return self._add("execute", (Stmt("assign", (start, [var], False), stmt.line), continuation), stmt)

            # Mirror cobc's output_perform_until: each level is a loop whose
            # head first resets the next variable; TEST BEFORE tests before
            # the inner level, TEST AFTER after it; the step ends the level.
            def level_loop(level, exit_node):
                var, _, step, condition = levels[level]
                head = self._add("jump", (), stmt)
                test = self._add("branch", (), stmt)
                increment = self._add("varying_step", (), stmt)
                inner_exit = test if test_after else increment
                if level + 1 < len(levels):
                    inner = level_loop(level + 1, inner_exit)
                else:
                    inner = self._body(body, inner_exit, block)
                first = test if not test_after else inner
                self.nodes[head] = Node("jump", (initialize(level + 1, first) if level + 1 < len(levels) else first,), stmt)
                self.nodes[test] = Node("branch", (condition, exit_node, increment if test_after else inner), stmt)
                self.nodes[increment] = Node("varying_step", (var, step, head), stmt)
                return head

            return initialize(0, level_loop(0, after))
        self._error(stmt, f"mode PERFORM inconnu: {mode}")
