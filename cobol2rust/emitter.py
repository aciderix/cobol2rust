from __future__ import annotations

from .frontend import CobolError, Program, DataRef, Expr
from .layout import leaves


def quoted(text):
    escapes = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    return '"' + ''.join(escapes.get(c, f"\\x{ord(c):02x}" if ord(c) < 32 or ord(c) == 127 else c) for c in text) + '"'


class Emitter:
    def __init__(self, program: Program):
        self.program = program
        self.names = {name: f"f{i}" for i, name in enumerate(program.fields)}
        self.paragraphs = {name: f"p{i}" for i, name in enumerate(program.paragraphs)}
        self.files = {name: f"file{i}" for i, name in enumerate(program.files)}
        self.lines = []
        self.mapping = []
        self.indent = 0
        self.counter = 0
        self.variable_groups = {}
        self.variable_dimensions = {}
        for field in program.fields.values():
            if not field.depending:
                continue
            dim = len(field.dimensions) - 1
            for leaf in program.fields.values():
                if leaf.name == field.name or leaf.name.startswith(field.name + "."):
                    self.variable_dimensions[leaf.name] = (field, dim)
            parent = field.parent
            while parent:
                self.variable_groups[parent] = field
                parent = program.fields[parent].parent

    def write(self, text=""):
        self.lines.append("    " * self.indent + text)

    def unique(self):
        self.counter += 1
        return f"temp{self.counter}"

    def kind(self, e):
        if e.op == "var":
            return "text" if e.args[0].start is not None else self.program.fields[e.args[0].name].kind
        if e.op in {"number", "text"}:
            return e.op
        if e.op.startswith("cmp") or e.op in {"and", "or", "not", "condition", "bool", "numeric_class"}:
            return "bool"
        return "number"

    def reference(self, ref):
        if isinstance(ref, str):
            ref = DataRef(ref)
        result = f"self.{self.names[ref.name]}"
        if ref.name in self.variable_groups:
            f = self.variable_groups[ref.name]
            prefix = self.program.fields[ref.name].size - f.size * f.occurs
            result += f".active_size(&self.{self.names[f.depending]}, {f.occurs_min}, {f.occurs}, {prefix}, {f.size})"
        if ref.name in self.variable_dimensions:
            f, dim = self.variable_dimensions[ref.name]
            result += f".active_count({dim}, &self.{self.names[f.depending]}, {f.occurs_min}, {f.occurs})"
        if ref.indices:
            if any(self.kind(index) != "number" for index in ref.indices):
                raise CobolError("sous-script numérique requis")
            result += f".at(&[{', '.join(self.expression(i) for i in ref.indices)}])"
        if ref.start is not None:
            if self.kind(ref.start) != "number" or (ref.length is not None and self.kind(ref.length) != "number"):
                raise CobolError("position et longueur numériques requises")
            length = f"Some(&({self.expression(ref.length)}))" if ref.length is not None else "None"
            result += f".slice(&({self.expression(ref.start)}), {length})"
        return result

    def literal(self, token):
        return Expr("text" if token.string else "number", (token.text,))

    def expression(self, e):
        op, args = e.op, e.args
        if op == "var":
            return self.reference(args[0]) + ".snapshot()"
        if op == "bool":
            return str(args[0]).lower()
        if op == "numeric_class":
            return f"({self.expression(args[0])}).is_numeric()" if args[0].op != "var" else self.reference(args[0].args[0]) + ".is_numeric()"
        if op == "condition":
            ref = args[0]
            condition = self.program.conditions[ref.name]
            value = Expr("var", (DataRef(condition.parent, ref.indices),))
            terms = []
            for low, high in condition.values:
                left, right = self.literal(low), self.literal(high)
                if low == high:
                    terms.append(self.expression(Expr("cmp=", (value, left))))
                else:
                    terms.append(f"({self.expression(Expr('cmp>=', (value, left)))} && {self.expression(Expr('cmp<=', (value, right)))})")
            return "(" + " || ".join(terms) + ")"
        if op in {"number", "text"}:
            return f"Value::{op}({quoted(args[0])})"
        if op in {"unary+", "unary-"}:
            if self.kind(args[0]) != "number":
                raise CobolError("opérateur numérique sur un champ texte")
            result = self.expression(args[0])
            return result if op == "unary+" else f"({result}).neg()"
        if op in {"+", "-", "*", "/"}:
            if any(self.kind(x) != "number" for x in args):
                raise CobolError("arithmétique sur champ texte non prise en charge")
            method = {"+": "plus", "-": "minus", "*": "times", "/": "divide"}[op]
            return f"({self.expression(args[0])}).{method}(&({self.expression(args[1])}))"
        if op in {"and", "or"}:
            return f"({self.expression(args[0])} {'&&' if op == 'and' else '||'} {self.expression(args[1])})"
        if op == "not":
            return f"!({self.expression(args[0])})"
        if op.startswith("cmp"):
            if self.kind(args[0]) != self.kind(args[1]):
                raise CobolError("comparaison entre nombre et texte non prise en charge")
            operator = {"=": "==", "<>": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}[op[3:]]
            return f"({self.expression(args[0])}).compare(&({self.expression(args[1])})) {operator} std::cmp::Ordering::Equal"
        raise CobolError(f"expression inconnue: {op}")

    def assignment(self, expr, targets, rounded):
        targets = [DataRef(r) if isinstance(r, str) else r for r in targets]
        for ref in targets:
            if ("text" if ref.start is not None else self.program.fields[ref.name].kind) != self.kind(expr):
                raise CobolError(f"conversion implicite numérique/texte non prise en charge: {ref.name}")
        temp = self.unique()
        # COBOL resolves a variable's source address once, but each receiver reads
        # that storage again. This matters when group/redefine receivers overlap it.
        source = self.reference(expr.args[0]) + ".clone()" if expr.op == "var" else self.expression(expr)
        self.write(f"let {temp} = {source};")
        for ref in targets:
            self.write(f"{self.reference(ref)}.assign(&{temp}, {str(rounded).lower()});")

    def checked_expression(self, expr):
        if self.kind(expr) != "number":
            raise CobolError("calcul avec SIZE ERROR requiert des nombres")
        op, args = expr.op, expr.args
        if op in {"+", "-", "*", "/"}:
            left, right = (f"({self.checked_expression(arg)}?)" for arg in args)
            if op == "/":
                return f"{left}.checked_divide(&{right})"
            method = {"+": "plus", "-": "minus", "*": "times"}[op]
            return f"Ok::<Value, runtime::SizeError>({left}.{method}(&{right}))"
        if op in {"unary+", "unary-"}:
            value = self.checked_expression(args[0])
            return value if op == "unary+" else f"Ok::<Value, runtime::SizeError>(({value}?).neg())"
        return f"Ok::<Value, runtime::SizeError>({self.expression(expr)})"

    def body(self, stmts):
        for stmt in stmts:
            self.mapping.append({"cobol_line": stmt.line, "rust_line": len(self.lines) + 1, "operation": stmt.op})
            self.write(f"// COBOL line {stmt.line}: {stmt.op}")
            self.write(f"runtime::set_line({stmt.line});")
            try:
                self.statement(stmt)
            except CobolError as exc:
                raise CobolError(f"ligne {stmt.line}: {exc}") from exc

    def file_status(self, file_name, status, eof_handled=False):
        name = self.program.files[file_name].status
        destination = f"Some(&mut self.{self.names[name]})" if name else "None"
        self.write(f"file_runtime::file_status({status}, {destination}, {str(eof_handled).lower()});")

    def statement(self, stmt):
        op, a = stmt.op, stmt.args
        if op == "set_index":
            refs, mode, expr = a
            if self.kind(expr) != "number":
                raise CobolError("SET d'index requiert un entier")
            for ref in refs:
                # SET ... UP/DOWN evaluates its operand for each receiver.
                # An earlier index receiver can itself be that operand.
                temp = self.unique()
                self.write(f"let {temp} = {self.expression(expr)};")
                self.write(f'{temp}.integer("SET index");')
                name = self.reference(ref)
                source = temp if mode == "to" else f"{name}.{'plus' if mode == 'up' else 'minus'}(&{temp})"
                self.write(f"{name}.assign(&{source}, false);")
        elif op == "set_condition":
            for ref in a[0]:
                condition = self.program.conditions[ref.name]
                token = condition.values[0][0] if a[1] else condition.false_value
                if token is None:
                    raise CobolError("SET TO FALSE requiert WHEN SET TO FALSE dans le niveau 88")
                self.assignment(self.literal(token), [DataRef(condition.parent, ref.indices)], False)
        elif op == "open":
            for mode, name in a[0]:
                self.write(f"let status = self.{self.files[name]}.open({quoted(mode)});")
                self.file_status(name, "status")
        elif op == "close":
            for name in a[0]:
                self.write(f"let status = self.{self.files[name]}.close();")
                self.file_status(name, "status")
        elif op == "write":
            name, value = a
            record = self.program.files[name].record
            if value:
                self.assignment(value, [record], False)
            self.write(f"let status = self.{self.files[name]}.write(&self.{self.names[record]});")
            self.file_status(name, "status")
        elif op == "read":
            name, into, at_end, not_end = a
            record = self.names[self.program.files[name].record]
            status = self.unique()
            self.write(f"let {status} = self.{self.files[name]}.read(&mut self.{record});")
            self.file_status(name, status, bool(at_end))
            self.write(f"if matches!({status}, 0 | 4 | 6 | 9) {{")
            self.indent += 1
            if into:
                self.write(f"let record = self.{record}.snapshot();")
                self.write(f"{self.reference(into)}.assign(&record, false);")
            self.body(not_end)
            self.indent -= 1
            self.write(f"}} else if {status} == 10 {{")
            self.indent += 1
            self.body(at_end)
            self.indent -= 1
            self.write("}")
        elif op == "display":
            values = []
            for e in a[0]:
                if e.op not in {"text", "number", "var"}:
                    raise CobolError("DISPLAY accepte uniquement champs et littéraux simples")
                # Preserve the spelling of numeric literals (leading zeros, trailing fractional zeros).
                values.append(f"Value::text({quoted(e.args[0])})" if e.op == "number" else self.expression(e))
            self.write(f"display(&[{', '.join(values)}], {str(a[1]).lower()});")
        elif op == "assign":
            self.assignment(*a)
        elif op == "arithmetic":
            expr, targets, rounded, error, success = a
            if any(ref.start is not None or self.program.fields[ref.name].kind != "number" for ref in targets):
                raise CobolError("destination numérique requise pour SIZE ERROR")
            result = self.unique()
            self.write(f"let {result} = (|| -> Result<(), runtime::SizeError> {{")
            self.indent += 1
            self.write(f"let value: Value = {self.checked_expression(expr)}?;")
            for ref in targets:
                self.write(f"{self.reference(ref)}.checked_assign(&value, {str(rounded).lower()})?;")
            self.write("Ok(())")
            self.indent -= 1
            self.write("})();")
            self.write(f"if {result}.is_err() {{")
            self.indent += 1
            self.body(error)
            self.indent -= 1
            self.write("} else {")
            self.indent += 1
            self.body(success)
            self.indent -= 1
            self.write("}")
        elif op == "accept":
            self.write(f"{self.reference(a[0])}.accept();")
        elif op == "initialize":
            for ref in a[0]:
                if ref.name in self.variable_groups and ref.start is None:
                    # GnuCOBOL 3.2's compound ODO initialization depends on its
                    # codegen strategy (including cob_init_table edge cases).
                    # Only the verified uniform-text case is supported here.
                    fields = leaves(self.program.fields, ref.name)
                    if self.variable_groups[ref.name].children or any(f.kind != "text" or (f.filler and not a[1]) for f in fields):
                        raise CobolError("INITIALIZE de groupe variable limité aux champs texte uniformes; initialiser les occurrences explicitement")
                self.write(f"{self.reference(ref)}.initialize_with_filler({str(a[1]).lower()});")
        elif op == "if":
            self.write(f"if {self.expression(a[0])} {{")
            self.indent += 1
            self.body(a[1])
            self.indent -= 1
            self.write("} else {")
            self.indent += 1
            self.body(a[2])
            self.indent -= 1
            self.write("}")
        elif op == "evaluate":
            temp = self.unique()
            self.write(f"let {temp} = {self.expression(a[0])};")
            for i, (case, body) in enumerate(a[1]):
                if self.kind(case) != self.kind(a[0]):
                    raise CobolError("EVALUATE: types incompatibles")
                comparison = f"{temp} == ({self.expression(case)})" if self.kind(case) == "bool" else f"{temp}.compare(&({self.expression(case)})) == std::cmp::Ordering::Equal"
                self.write(f"{'if' if i == 0 else '} else if'} {comparison} {{")
                self.indent += 1
                self.body(body)
                self.indent -= 1
            self.write("} else {")
            self.indent += 1
            self.body(a[2])
            self.indent -= 1
            self.write("}")
        elif op == "loop":
            mode, control, body = a
            if mode == "once":
                self.body(body)
                return
            if mode == "times":
                temp = self.unique()
                if self.kind(control[0]) != "number":
                    raise CobolError("TIMES requiert un nombre")
                self.write(f"let {temp} = ({self.expression(control[0])}).count();")
                self.write(f"for _ in 0..{temp} {{")
            else:
                if mode == "varying":
                    var, start, step, cond, test_after = control
                    self.assignment(start, [var], False)
                    if self.kind(step) != "number":
                        raise CobolError("BY requiert un nombre")
                else:
                    cond, test_after = control
                self.write("loop {")
            self.indent += 1
            if mode in {"until", "varying"} and not test_after:
                self.write(f"if {self.expression(cond)} {{ break; }}")
            self.body(body)
            if mode in {"until", "varying"} and test_after:
                self.write(f"if {self.expression(cond)} {{ break; }}")
            if mode == "varying":
                name = self.reference(var)
                self.write(f"let step = {name}.plus(&({self.expression(step)}));")
                self.write(f"{name}.assign(&step, false);")
            self.indent -= 1
            self.write("}")
        elif op == "call":
            targets = a[0]
            names = list(self.paragraphs)
            chosen = [targets[0]] if len(targets) == 1 else names[names.index(targets[0]):names.index(targets[1]) + 1]
            for name in chosen:
                self.write(f"if let Flow::Stop = self.{self.paragraphs[name]}() {{ return Flow::Stop; }}")
        elif op == "stop":
            self.write("return Flow::Stop;")
        elif op == "exit_paragraph":
            self.write("return Flow::Next;")
        elif op == "continue":
            self.write("{}")
        else:
            raise CobolError(f"instruction inconnue: {op}")

    def storage_kind(self, f):
        if f.kind == "text":
            return "storage_runtime::Kind::Text"
        usage = "Index" if f.usage == "INDEX" else "Display" if f.usage == "DISPLAY" else "Packed" if f.usage in {"COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL"} else "Binary"
        return f"storage_runtime::Kind::Numeric {{ digits: {f.digits}, scale: {f.scale}, signed: {str(f.signed).lower()}, usage: storage_runtime::Usage::{usage} }}"

    def dimensions(self, dimensions):
        return "vec![" + ", ".join(f"({stride}, {count})" for stride, count in dimensions) + "]"

    def initializers(self, f):
        items = [f] if f.picture else [leaf for child in f.children for leaf in leaves(self.program.fields, child)]
        return "vec![" + ", ".join(
            f"storage_runtime::Initializer {{ offset: {leaf.offset - f.offset}, size: {leaf.size}, kind: {self.storage_kind(leaf)}, dimensions: {self.dimensions(leaf.dimensions[len(f.dimensions):])}, filler: {str(leaf.filler).lower()} }}"
            for leaf in items) + "]"

    def generate(self):
        self.write("// Generated by cobol2rust. Edit the COBOL input and regenerate.")
        self.write("#![allow(unreachable_code, dead_code, unused_parens)]")
        self.write("mod runtime;")
        self.write("mod storage_runtime;")
        if self.files:
            self.write("mod file_runtime;")
        self.write("use runtime::{Value, display};")
        self.write("enum Flow { Next, Stop }")
        self.write("struct Program {")
        self.indent += 1
        for name in self.names:
            self.write(f"{self.names[name]}: Value, // {name} PIC {self.program.fields[name].picture}")
        for name, rust_name in self.files.items():
            self.write(f"{rust_name}: file_runtime::LineFile, // {name}")
        self.indent -= 1
        self.write("}")
        self.write("impl Program {")
        self.indent += 1
        self.write("fn new() -> Self {")
        self.indent += 1
        self.write(f"let memory = storage_runtime::memory({self.program.memory_size});")
        self.write("let mut result = Self {")
        self.indent += 1
        for name, field in self.program.fields.items():
            value = f"Value::View(storage_runtime::View {{ memory: memory.clone(), offset: {field.offset}, size: {field.size}, kind: {self.storage_kind(field)}, dimensions: {self.dimensions(field.dimensions)}, initializers: {self.initializers(field)} }})"
            self.write(f"{self.names[name]}: {value},")
        for name, rust_name in self.files.items():
            spec = self.program.files[name]
            self.write(f"{rust_name}: file_runtime::LineFile::new({quoted(spec.path.text)}, {str(spec.optional).lower()}),")
        self.indent -= 1
        self.write("};")
        for name, field in self.program.fields.items():
            if not field.picture or field.file_record:
                continue
            cursor = field
            while cursor and not cursor.redefines:
                cursor = self.program.fields.get(cursor.parent)
            if cursor:
                continue
            constructor = "text" if field.kind == "text" else "number"
            self.write(f"result.{self.names[name]}.declare(&Value::{constructor}({quoted(field.initial.text)}));")
        self.write("result")
        self.indent -= 1
        self.write("}")
        for name, body in [("entry", self.program.entry), *[(self.paragraphs[k], v) for k, v in self.program.paragraphs.items()]]:
            self.write(f"fn {name}(&mut self) -> Flow {{")
            self.indent += 1
            self.body(body)
            self.write("Flow::Next")
            self.indent -= 1
            self.write("}")
        self.write("fn run(&mut self) {")
        self.indent += 1
        for name in ["entry", *self.paragraphs.values()]:
            self.write(f"if let Flow::Stop = self.{name}() {{ return; }}")
        self.indent -= 1
        self.write("}")
        self.indent -= 1
        self.write("}")
        self.write("fn main() { Program::new().run(); }")
        return "\n".join(self.lines) + "\n", self.mapping
