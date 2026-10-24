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
        # cobc's static label_N of each paragraph modified by ALTER.
        self.alter_slots = {name: slot for slot, name in enumerate(program.alters)}
        self._fall_entries = {}
        # USE FOR DEBUGGING (cobc flag_gen_debug): blocks of the debugging
        # sections, whose statements and labels trigger no debugging.
        self.debug = getattr(program, "gen_debug", False)
        self.debug_blocks = {index for section in getattr(program, "debug_sections", {})
                             for index in range(*program.sections[section])}

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
            if block.name in self.alter_slots:
                # output_alter_check: an ALTERed label goes to its target.
                body = self._add("alter_check", (self.alter_slots[block.name], body))
            label = block.name if block.name is not None else block.section if block.section is not None else None
            if self.debug and block.name is None and block.section in program.debug_sections:
                # A debugging section runs only with the runtime switch on.
                body = self._add("debug_gate", (body, self.section_checkpoints[block.section]))
            elif label is not None and self._monitored(label):
                # output_label: DEBUG-NAME, then PERFORM of the debugging section.
                body = self._debug_call(label, index, body)
                body = self._add("debug_name", (self._label_text(label), body))
            self.nodes[self.block_entries[index]] = Node("jump", (body,))
        self.entry = self._following(program.main_block, fall=False)
        if self.debug:
            self.entry = self._add("debug_contents", ("START PROGRAM", self.entry))

    def _add(self, op: str, args: tuple = (), stmt: Stmt | None = None) -> int:
        position = len(self.nodes)
        self.nodes.append(Node(op, args, stmt))
        return position

    def _following(self, block: int, fall: bool = True) -> int:
        """Fall-through into a block. Falling into a SECTION header (and only
        that: GO TO and PERFORM go past it) zaps its independent labels; with
        DEBUGGING MODE it first sets DEBUG-CONTENTS to "FALL THROUGH"."""
        if block >= len(self.block_entries):
            return self._end
        if (block, fall) in self._fall_entries:
            return self._fall_entries[(block, fall)]
        position = self.block_entries[block]
        header = self.blocks[block]
        if header.name is None and header.section is not None:
            slots = self._independent(header.section)
            if slots:
                position = self._add("alter_zap", (slots, position))
        if fall and block in getattr(self.program, "fall_through", ()):
            position = self._add("debug_contents", ("FALL THROUGH", position))
        self._fall_entries[(block, fall)] = position
        return position

    def _monitored(self, name: str) -> str | None:
        """The debugging section a real label triggers, if any."""
        if not self.debug:
            return None
        if name in self.program.debug_sections:
            return None
        index = self.program.procedure_range(name)[0]
        if index in self.debug_blocks:
            return None
        return self.program.all_procedure or self.program.debug_labels.get(name)

    def _label_text(self, name: str) -> str:
        if name not in self.program.sections:
            name = self.blocks[self.program.procedure_range(name)[0]].label or name
        return self.program.spelling.get(name, name)

    def _debug_call(self, name: str, block: int, after: int) -> int:
        """PERFORM of the debugging section for the label `name`."""
        section = self._monitored(name)
        entry, checkpoint = self._target(section)
        return self._perform(section, entry, checkpoint, after, block)

    def _independent(self, section: str | None) -> list[int]:
        """Slots of the ALTERed paragraphs of an independent segment (> 49)."""
        if section is None or self.program.segments.get(section, 0) <= 49:
            return []
        start, end = self.program.sections[section]
        return [self.alter_slots[b.name] for b in self.blocks[start:end] if b.name in self.alter_slots]

    def _section_of(self, name: str) -> str | None:
        if name in self.program.sections:
            return name
        return self.blocks[self.program.procedure_range(name)[0]].section

    def _segment(self, section: str | None) -> int:
        return self.program.segments.get(section, 0) if section else 0

    def _goto(self, name: str, block: int) -> int:
        """output_goto_1: a GO TO into another segment zaps the target
        section's independent labels; a debugged target gets DEBUG-NAME and
        a blank DEBUG-CONTENTS."""
        entry = self._target(name)[0]
        if self._monitored(name):
            entry = self._add("debug_contents", (None, entry))
            entry = self._add("debug_name", (self._label_text(name), entry))
        there = self._section_of(name)
        slots = self._independent(there)
        if slots and self._segment(self.blocks[block].section) != self._segment(there):
            return self._add("alter_zap", (slots, entry))
        return entry

    def _perform(self, target: str, entry: int, checkpoint: int, after: int, block: int) -> int:
        """output_perform_call: around a PERFORM into another section, save and
        restore the independent labels of the current one; entering another
        segment zaps the target section's independent labels."""
        here, there = self.blocks[block].section, self._section_of(target)
        segment = self._segment
        other_section = here != there
        after_nodes, before_nodes = [], []
        if other_section:
            if self._independent(here):
                before_nodes.append(("alter_save", self._independent(here)))
                after_nodes.append(("alter_restore", self._independent(here)))
            if self._independent(there):
                after_nodes.append(("alter_zap", self._independent(there)))
        if segment(here) != segment(there) and self._independent(there):
            before_nodes.append(("alter_zap", self._independent(there)))
        if self._monitored(target):
            # "Update debugging name" before entering the procedure.
            before_nodes.append(("debug_name", self._label_text(target)))
        position = after
        for op, slots in reversed(after_nodes):
            position = self._add(op, (slots, position))
        position = self._add("call", (entry, checkpoint, position))
        for op, slots in reversed(before_nodes):
            position = self._add(op, (slots, position))
        return position

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
        position = self._lower(stmt, after, block)
        # The "call" of a PERFORM or SORT procedure belongs to that statement.
        if self.debug and block not in self.debug_blocks and stmt.op not in {"sentence_end", "debug_contents", "call"}:
            # output_stmt: DEBUG-LINE takes the line of each statement begun.
            position = self._add("debug_line", (stmt.line, position))
        return position

    def _file_debug(self, name: str, block: int, after: int, contents=None) -> int | None:
        """DEBUG-NAME (the file), DEBUG-CONTENTS and its debugging section."""
        section = getattr(self.program, "debug_files", {}).get(name) if self.debug else None
        if section is None or block in self.debug_blocks:
            return None
        entry, checkpoint = self._target(section)
        position = self._perform(section, entry, checkpoint, after, block)
        position = self._add("debug_contents", (contents, position))
        return self._add("debug_name", (self.program.spelling.get(name, name), position))

    def _lower(self, stmt: Stmt, after: int, block: int) -> int:
        op, args = stmt.op, stmt.args
        if op == "debug_contents":
            return self._add("debug_contents", (args[0], after), stmt) if self.debug else after
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
            success_body = self._body(success, after, block)
            # cb_emit_read: on success, after INTO, the record as DEBUG-CONTENTS.
            success_body = self._file_debug(name, block, success_body, ("record", name)) or success_body
            return self._add("read", (name, into, success_body,
                                      self._body(exception, after, block), after,
                                      self._declaratives(name, after, block)), stmt)
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
            debug = None
            if op in {"open", "close", "delete", "start"} and isinstance(name, str):
                # OPEN/CLOSE debug in the statement body, DELETE/START in the
                # callback after the I/O: both before the status handling.
                resume = self._add("debug_resume", ())
                debug = self._file_debug(name, block, resume)
            return self._add("io", (stmt, after, self._declaratives(name, after, block), invalid, valid, debug), stmt)
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
            debugged = self.debug and block not in self.debug_blocks
            if target[0] == "procedure":
                position = self._statement(Stmt("call", (target[1],), stmt.line), position, block)
                if debugged:
                    # cb_emit_sort_output: DEBUG-CONTENTS before the procedure.
                    position = self._add("debug_contents", ("MERGE OUTPUT" if merge else "SORT OUTPUT", position))
            else:
                position = self._add("sort_giving", (name, target[1], position), stmt)
            if source[0] == "procedure":
                position = self._statement(Stmt("call", (source[1],), stmt.line), position, block)
                if debugged:
                    position = self._add("debug_contents", ("SORT INPUT", position))
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
            position = self._perform(targets[0], entry, checkpoint, after, block)
            if self.nodes[position].op == "call":
                self.nodes[position].stmt = stmt
            else:
                position = self._add("jump", (position,), stmt)
            return position
        if op == "goto":
            targets, controller = args
            if not targets:
                return after
            return self._add("goto", ([self._goto(name, block) for name in targets], controller, after), stmt)
        if op == "alter":
            source, target = args
            if self._monitored(source):
                # output_alter: DEBUG-NAME the altered label, DEBUG-CONTENTS its target.
                after = self._debug_call(source, block, after)
                after = self._add("debug_contents", (self._label_text(target), after))
                after = self._add("debug_name", (self._label_text(source), after))
            return self._add("alter", (self.alter_slots[source], self._target(target)[0], after), stmt)
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

    def _declaratives(self, file_name: str, after: int, block: int):
        """USE procedures run like a PERFORM of their section, then resume."""
        def call(section):
            entry, checkpoint = self._target(section)
            position = self._perform(section, entry, checkpoint, after, block)
            if self.debug:
                # output_file_error: DEBUG-CONTENTS "USE PROCEDURE".
                position = self._add("debug_contents", ("USE PROCEDURE", position))
            return position
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
