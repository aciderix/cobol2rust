from __future__ import annotations

from .frontend import CobolError, Program, ProcedureBlock, DataRef, Expr
from .layout import leaves
from .control import ControlGraph


def quoted(text):
    escapes = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    return '"' + ''.join(escapes.get(c, f"\\x{ord(c):02x}" if ord(c) < 32 or ord(c) == 127 else c) for c in text) + '"'


class Emitter:
    def __init__(self, program: Program):
        self.program = program
        self.names = {name: f"f{i}" for i, name in enumerate(program.fields)}
        self.blocks = program.blocks or [ProcedureBlock(None, None, program.entry),
                                        *(ProcedureBlock(name, None, body) for name, body in program.paragraphs.items())]
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
                if self.kind(value) != self.kind(left) or self.kind(value) != self.kind(right):
                    raise CobolError("valeurs de niveau 88 de catégorie différente du parent non prises en charge")
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
            operator = {"=": "==", "<>": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}[op[3:]]
            return f"({self.comparison_order(*args)}) {operator} std::cmp::Ordering::Equal"
        raise CobolError(f"expression inconnue: {op}")

    def comparison_order(self, left, right):
        kinds = self.kind(left), self.kind(right)
        if "edited" in kinds:
            raise CobolError("comparaison de champ édité non prise en charge; copier vers PIC X pour comparer les octets")
        if kinds[0] == kinds[1]:
            return f"({self.expression(left)}).compare(&({self.expression(right)}))"
        if set(kinds) != {"number", "text"}:
            raise CobolError("comparaison entre catégories non prise en charge")
        number, text = (left, right) if kinds[0] == "number" else (right, left)
        # GnuCOBOL treats an empty alphanumeric literal as one SPACE.
        text_value = 'Value::text(" ")' if text.op == "text" and not text.args[0] else self.expression(text)
        if number.figurative_zero:
            result = f"({text_value}).compare_zero()"
            return result + ".reverse()" if kinds[0] == "number" else result
        if number.op == "var":
            ref = number.args[0]
            descriptor = self.program.fields[ref.name]
            if descriptor.usage == "INDEX":
                raise CobolError("comparaison mixte d'index non prise en charge")
            if text.op == "text" and (descriptor.scale or not text.args[0].isascii() or
                                      not text.args[0].isdigit() or len(text.args[0]) != descriptor.digits):
                raise CobolError("comparaison mixte avec littéral texte limitée aux entiers et chiffres de même largeur; copier le littéral vers PIC X pour éviter les optimisations natives non modélisées")
            number_value = self.reference(ref) + ".comparison_text()"
        elif number.op == "number":
            number_value = f"Value::text({quoted(number.args[0].replace('.', ''))})"
        else:
            raise CobolError("comparaison mixte limitée aux champs numériques, littéraux non signés et ZERO; signes explicites et calculs non modélisés")
        a, b = (number_value, text_value) if kinds[0] == "number" else (text_value, number_value)
        return f"({a}).compare(&({b}))"

    def move_literal_digits(self, expr):
        if expr.op == "number" and not expr.figurative_zero:
            return expr.args[0].replace(".", "")
        if expr.op in {"unary+", "unary-"} and expr.args[0].op == "number":
            return self.move_literal_digits(expr.args[0])
        return None

    def assignment(self, expr, targets, rounded, move=False):
        targets = [DataRef(r) if isinstance(r, str) else r for r in targets]
        source_kind = self.kind(expr)
        conversions = []
        for ref in targets:
            conversions.append(None)
            field = self.program.fields[ref.name]
            destination = "text" if ref.start is not None else field.kind
            if move and source_kind == "text" and destination in {"number", "edited"}:
                if expr.figurative_space:
                    raise CobolError("MOVE de la constante figurative SPACE vers nombre ou champ édité non pris en charge")
                if destination == "number" and field.usage == "INDEX":
                    raise CobolError("MOVE texte vers index non pris en charge")
                if destination == "number" and expr.op != "var":
                    raise CobolError("MOVE littéral texte vers nombre non pris en charge; optimisations natives distinctes des champs PIC X")
                source_ref = expr.args[0] if expr.op == "var" else None
                raw_group = (source_ref is not None and source_ref.start is None and
                             not self.program.fields[source_ref.name].picture)
                conversions[-1] = "raw_text" if raw_group else "parsed_text"
                continue
            if move and destination == "text" and source_kind == "number":
                group = not field.picture and ref.start is None
                if expr.figurative_zero:
                    conversion = "zero"
                elif self.move_literal_digits(expr) is not None:
                    conversion = "literal"
                elif expr.op == "var":
                    source_field = self.program.fields[expr.args[0].name]
                    if group and source_field.usage == "INDEX":
                        raise CobolError("MOVE index vers groupe non pris en charge; stockage natif non modélisé")
                    if not group and source_field.scale:
                        raise CobolError("MOVE numérique non entier vers PIC X ou sous-chaîne invalide; utiliser un groupe pour copier le stockage brut")
                    conversion = "group" if group else "integer"
                else:
                    raise CobolError("MOVE numérique vers texte requiert un champ ou un littéral simple")
                conversions[-1] = conversion
                continue
            if destination == "edited" and source_kind == "number":
                continue
            if destination == "text" and source_kind == "edited":
                continue
            if destination == "edited" or destination != source_kind:
                raise CobolError(f"conversion implicite numérique/texte non prise en charge: {ref.name}")
        # A numeric MOVE truncates instead of raising SIZE ERROR. Index senders
        # keep the stricter assignment: their native transfer is not modelled.
        truncating = (move and source_kind == "number" and not
                      (expr.op == "var" and self.program.fields[expr.args[0].name].usage == "INDEX"))
        temp = self.unique()
        # COBOL resolves a variable's source address once, but each receiver reads
        # that storage again. This matters when group/redefine receivers overlap it.
        source = self.reference(expr.args[0]) + ".clone()" if expr.op == "var" else self.expression(expr)
        self.write(f"let {temp} = {source};")
        for ref, conversion in zip(targets, conversions):
            if conversion in {"raw_text", "parsed_text"}:
                self.write(f"{self.reference(ref)}.assign_text_move(&{temp}, {str(conversion == 'raw_text').lower()});")
            elif conversion == "zero":
                receiver = self.unique()
                self.write(f"let mut {receiver} = {self.reference(ref)}.clone();")
                self.write(f"let zeros = Value::Bytes(vec![b'0'; {receiver}.text_size()]);")
                self.write(f"{receiver}.assign(&zeros, false);")
            else:
                value = (f"{temp}.numeric_move_text({str(conversion == 'group').lower()})"
                         if conversion in {"group", "integer"} else
                         f"Value::text({quoted(self.move_literal_digits(expr))})" if conversion == "literal" else temp)
                field = self.program.fields[ref.name]
                if conversion is None and truncating and ref.start is None and field.kind == "number":
                    method = "move_number"
                    if self.storage_usage(field) == "Packed":
                        self.check_packed_literal_move(expr, field)
                        if (expr.op == "var" and
                                self.storage_usage(self.program.fields[expr.args[0].name]) == "Binary"):
                            method = "move_binary_to_packed"
                    self.write(f"{self.reference(ref)}.{method}(&{value});")
                else:
                    self.write(f"{self.reference(ref)}.assign(&{value}, {str(rounded).lower()});")

    def check_packed_literal_move(self, expr, field):
        """cobc stores a small integer literal with cob_set_packed_int, which
        fills every physical nibble. Refuse a digit landing in the pad nibble."""
        digits = self.move_literal_digits(expr)
        if digits is None:
            return
        number = expr if expr.op == "number" else expr.args[0]
        if "." in number.args[0] or len(digits) + field.scale > 9 or field.digits % 2:
            return
        if (int(digits) * 10 ** field.scale // 10 ** field.digits) % 10:
            raise CobolError("MOVE littéral vers COMP-3 à nombre pair de chiffres remplissant le quartet "
                             "de tête natif non pris en charge")

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
            name, record, value, advancing = a
            if value:
                self.assignment(value, [record], False)
            control = "None"
            if advancing is not None:
                direction, count = advancing
                variant = direction.title() + ("Page" if count is None else "Lines")
                argument = "" if count is None else f"({count})"
                control = f"Some(file_runtime::Advance::{variant}{argument})"
            self.write(f"let status = self.{self.files[name]}.write(&self.{self.names[record]}, {control});")
            self.file_status(name, "status")
        elif op == "display":
            values = []
            for e in a[0]:
                if e.op not in {"text", "number", "var"}:
                    raise CobolError("DISPLAY accepte uniquement champs et littéraux simples")
                # Preserve the spelling of numeric literals (leading zeros, trailing fractional zeros).
                values.append(f"Value::text({quoted(e.args[0])})" if e.op == "number" else self.expression(e))
            self.write(f"display(&[{', '.join(values)}], {str(a[1]).lower()});")
        elif op in {"assign", "move"}:
            self.assignment(*a, move=op == "move")
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
        elif op == "continue":
            self.write("{}")
        else:
            raise CobolError(f"instruction inconnue: {op}")

    def control_node(self, index, node):
        op, a = node.op, node.args
        if op == "end":
            self.write("break;")
        elif op == "jump":
            self.write(f"pc = {a[0]};")
        elif op == "checkpoint":
            # A jump may leave PERFORM frames dormant. Only the top frame's
            # exact paragraph/section checkpoint can resume its continuation.
            self.write(f"pc = if stack.last().is_some_and(|frame| frame.through == {index}) {{")
            self.indent += 1
            self.write("stack.pop().unwrap().return_pc")
            self.indent -= 1
            self.write(f"}} else {{ {a[0]} }};")
        elif op == "execute":
            self.statement(a[0])
            self.write(f"pc = {a[1]};")
        elif op == "branch":
            self.write(f"pc = if {self.expression(a[0])} {{ {a[1]} }} else {{ {a[2]} }};")
        elif op == "call":
            target, through, continuation = a
            self.write(f"stack.push(PerformFrame {{ through: {through}, return_pc: {continuation} }});")
            self.write(f"pc = {target};")
        elif op == "goto":
            targets, controller, continuation = a
            if controller is None:
                self.write(f"pc = {targets[0]};")
            else:
                self.write(f'pc = match {self.reference(controller)}.integer("GO TO DEPENDING ON") {{')
                self.indent += 1
                for choice, target in enumerate(targets, 1):
                    self.write(f"{choice} => {target},")
                self.write(f"_ => {continuation},")
                self.indent -= 1
                self.write("};")
        elif op == "times_init":
            slot, expr, continuation = a
            if self.kind(expr) != "number":
                raise CobolError("TIMES requiert un nombre")
            self.write(f"times[{slot}] = ({self.expression(expr)}).count();")
            self.write(f"pc = {continuation};")
        elif op == "times_test":
            slot, body, continuation = a
            self.write(f"pc = if times[{slot}] > 0 {{ {body} }} else {{ {continuation} }};")
        elif op == "times_step":
            slot, continuation = a
            self.write(f"times[{slot}] -= 1;")
            self.write(f"pc = {continuation};")
        elif op == "varying_step":
            var, step, continuation = a
            if self.kind(step) != "number":
                raise CobolError("BY requiert un nombre")
            name = self.reference(var)
            self.write(f"let step = {name}.plus(&({self.expression(step)}));")
            self.write(f"{name}.assign(&step, false);")
            self.write(f"pc = {continuation};")
        elif op == "evaluate":
            subject, branches, otherwise = a
            if self.kind(subject) == "edited":
                raise CobolError("EVALUATE de champ édité non pris en charge")
            temp = self.unique()
            self.write(f"let {temp} = {self.expression(subject)};")
            for i, (case, target) in enumerate(branches):
                if self.kind(case) == "edited":
                    raise CobolError("EVALUATE avec cas édité non pris en charge")
                if self.kind(case) != self.kind(subject):
                    raise CobolError("EVALUATE: types incompatibles")
                comparison = f"{temp} == ({self.expression(case)})" if self.kind(case) == "bool" else f"{temp}.compare(&({self.expression(case)})) == std::cmp::Ordering::Equal"
                self.write(f"{'if' if i == 0 else '} else if'} {comparison} {{")
                self.indent += 1
                self.write(f"pc = {target};")
                self.indent -= 1
            self.write("} else {")
            self.indent += 1
            self.write(f"pc = {otherwise};")
            self.indent -= 1
            self.write("}")
        elif op == "read":
            name, into, success, eof, continuation = a
            record = self.names[self.program.files[name].record]
            status = self.unique()
            self.write(f"let {status} = self.{self.files[name]}.read(&mut self.{record});")
            self.file_status(name, status, bool(node.stmt.args[2]))
            self.write(f"if matches!({status}, 0 | 4 | 6 | 9) {{")
            self.indent += 1
            if into:
                if self.program.files[name].organization == "SEQUENTIAL":
                    self.write(f"let record = Value::Bytes(self.{record}.bytes()[..self.{self.files[name]}.last_read_size()].to_vec());")
                else:
                    self.write(f"let record = self.{record}.snapshot();")
                self.write(f"{self.reference(into)}.assign(&record, false);")
            self.write(f"pc = {success};")
            self.indent -= 1
            self.write(f"}} else if {status} == 10 {{")
            self.indent += 1
            self.write(f"pc = {eof};")
            self.indent -= 1
            self.write(f"}} else {{ pc = {continuation}; }}")
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
            self.write(f"pc = if {result}.is_err() {{ {error} }} else {{ {success} }};")
        else:
            raise CobolError(f"nœud de contrôle inconnu: {op}")

    @staticmethod
    def storage_usage(f):
        if f.usage in {"INDEX", "DISPLAY"}:
            return f.usage.capitalize()
        return "Packed" if f.usage in {"COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL"} else "Binary"

    def storage_kind(self, f):
        if f.kind == "text":
            return "storage_runtime::Kind::Text"
        if f.kind == "edited":
            return f"storage_runtime::Kind::Edited {{ picture: {quoted(f.editing)}, digits: {f.digits}, scale: {f.scale} }}"
        usage = self.storage_usage(f)
        return f"storage_runtime::Kind::Numeric {{ digits: {f.digits}, scale: {f.scale}, signed: {str(f.signed).lower()}, usage: storage_runtime::Usage::{usage} }}"

    def dimensions(self, dimensions):
        return "vec![" + ", ".join(f"({stride}, {count})" for stride, count in dimensions) + "]"

    def initializers(self, f):
        items = [f] if f.picture else [leaf for child in f.children for leaf in leaves(self.program.fields, child)]
        return "vec![" + ", ".join(
            f"storage_runtime::Initializer {{ offset: {leaf.offset - f.offset}, size: {leaf.size}, kind: {self.storage_kind(leaf)}, dimensions: {self.dimensions(leaf.dimensions[len(f.dimensions):])}, filler: {str(leaf.filler).lower()} }}"
            for leaf in items) + "]"

    def generate(self):
        graph = ControlGraph(self.program, self.blocks)
        self.write("// Generated by cobol2rust. Edit the COBOL input and regenerate.")
        self.write("#![allow(unreachable_code, dead_code, unused_parens)]")
        self.write("mod runtime;")
        self.write("mod storage_runtime;")
        if self.files:
            self.write("mod file_runtime;")
        self.write("use runtime::{Value, display};")
        self.write("struct PerformFrame { through: usize, return_pc: usize }")
        self.write("struct Program {")
        self.indent += 1
        for name in self.names:
            self.write(f"{self.names[name]}: Value, // {name} PIC {self.program.fields[name].picture}")
        for name, rust_name in self.files.items():
            self.write(f"{rust_name}: file_runtime::CobolFile, // {name}")
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
            self.write(f"{rust_name}: file_runtime::CobolFile::new({quoted(spec.path.text)}, {str(spec.optional).lower()}, {quoted(spec.organization)}),")
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
            constructor = "text" if field.initial.string else "number"
            self.write(f"result.{self.names[name]}.declare(&Value::{constructor}({quoted(field.initial.text)}));")
        self.write("result")
        self.indent -= 1
        self.write("}")
        self.write("fn run(&mut self) {")
        self.indent += 1
        self.write(f"let mut pc: usize = {graph.entry};")
        self.write("let mut stack: Vec<PerformFrame> = Vec::new();")
        # Like GnuCOBOL's n0/n1 counters, TIMES state belongs to its source
        # site, including when PERFORM re-enters that site recursively.
        self.write(f"let mut times = vec![0i128; {graph.times_slots}];")
        self.write("loop {")
        self.indent += 1
        self.write("match pc {")
        self.indent += 1
        for index, node in enumerate(graph.nodes):
            self.write(f"{index} => {{")
            self.indent += 1
            stmt = node.stmt
            if stmt is not None:
                self.mapping.append({"cobol_line": stmt.line, "rust_line": len(self.lines) + 1,
                                     "operation": stmt.op})
                self.write(f"// COBOL line {stmt.line}: {stmt.op}")
                self.write(f"runtime::set_line({stmt.line});")
            try:
                self.control_node(index, node)
            except CobolError as exc:
                if stmt is not None:
                    raise CobolError(f"ligne {stmt.line}: {exc}") from exc
                raise
            self.indent -= 1
            self.write("}")
        self.write('_ => unreachable!("invalid procedure position"),')
        self.indent -= 1
        self.write("}")
        self.indent -= 1
        self.write("}")
        self.indent -= 1
        self.write("}")
        self.indent -= 1
        self.write("}")
        self.write("fn main() { Program::new().run(); }")
        return "\n".join(self.lines) + "\n", self.mapping
