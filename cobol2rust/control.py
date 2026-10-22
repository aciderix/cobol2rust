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
            body = self._body(block.body, self.paragraph_checkpoints[index], index)
            self.nodes[self.block_entries[index]] = Node("jump", (body,))
        self.entry = self._following(0)

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
        if expr.op.startswith("cmp") or expr.op in {"and", "or", "not", "condition", "bool", "numeric_class"}:
            return "bool"
        return "number"

    def _body(self, statements: list[Stmt], after: int, block: int) -> int:
        position = after
        for stmt in reversed(statements):
            position = self._statement(stmt, position, block)
        return position

    def _statement(self, stmt: Stmt, after: int, block: int) -> int:
        op, args = stmt.op, stmt.args
        if op == "if":
            condition, yes, no = args
            return self._add("branch", (condition, self._body(yes, after, block),
                                        self._body(no, after, block)), stmt)
        if op == "evaluate":
            subject, branches, otherwise = args
            destinations = [(value, self._body(body, after, block)) for value, body in branches]
            return self._add("evaluate", (subject, destinations, self._body(otherwise, after, block)), stmt)
        if op == "read":
            name, into, at_end, not_end = args
            return self._add("read", (name, into, self._body(not_end, after, block),
                                      self._body(at_end, after, block), after), stmt)
        if op == "arithmetic":
            expr, targets, rounded, error, success = args
            return self._add("arithmetic", (expr, targets, rounded, self._body(error, after, block),
                                            self._body(success, after, block)), stmt)
        if op == "loop":
            return self._loop(stmt, after, block)
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
            return self._add("end", (), stmt)
        return self._add("execute", (stmt, after), stmt)

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
            var, start, step, condition, test_after = control
            if var.start is not None or self.program.fields[var.name].kind != "number":
                self._error(stmt, "PERFORM VARYING requiert un contrôle numérique non édité")
            if self._kind(step) != "number":
                self._error(stmt, "BY requiert un nombre")
            test = self._add("branch", (), stmt)
            increment = self._add("varying_step", (), stmt)
            # TEST AFTER checks before incrementing. A successful final test
            # leaves the control value untouched, matching the native loop.
            entry = self._body(body, test if test_after else increment, block)
            self.nodes[test] = Node("branch", (condition, after, increment if test_after else entry), stmt)
            self.nodes[increment] = Node("varying_step", (var, step, entry if test_after else test), stmt)
            initialize = Stmt("assign", (start, [var], False), stmt.line)
            return self._add("execute", (initialize, entry if test_after else test), stmt)
        self._error(stmt, f"mode PERFORM inconnu: {mode}")
