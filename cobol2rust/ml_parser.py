"""XML GENERATE and JSON GENERATE: parser.y xml_generate_statement and
json_generate_statement, the syntax checks of typeck.c (cb_emit_xml_generate,
cb_emit_json_generate), tree.c cb_build_ml_tree and codegen.c
output_ml_suppress_checks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import frontend
from .frontend import DataRef, Expr, Stmt

ELEMENT, ATTRIBUTE, CONTENT, ANY = "ELEMENT", "ATTRIBUTE", "CONTENT", "ANY"
FIGURATIVES = {"SPACE": "SPACE", "SPACES": "SPACE", "ZERO": "ZERO", "ZEROS": "ZERO", "ZEROES": "ZERO",
               "HIGH-VALUE": "HIGH", "HIGH-VALUES": "HIGH", "LOW-VALUE": "LOW", "LOW-VALUES": "LOW"}


@dataclass
class Suppress:
    """cb_ml_suppress_clause: target ALL, IDENTIFIER or TYPE."""
    target: str = "ALL"
    identifier: DataRef | None = None
    category: str = "ANY"
    ml_type: str = ANY
    when: list | None = None


@dataclass
class Node:
    """cb_ml_generate_tree: `value` is the item key (None for an element
    with children), `slot` its is_suppressed flag in the program."""
    kind: str
    name: bytes | None
    value: str | None
    slot: int
    attrs: list = field(default_factory=list)
    children: list = field(default_factory=list)
    parent: Node | None = None
    prev: Node | None = None
    cond: Expr | None = None


def is_name_start(c):
    """cob_is_xml_namestartchar ("C" locale isalpha)."""
    return chr(c).isascii() and chr(c).isalpha() or c == 0x5f or 0xc0 <= c <= 0xd6 or 0xd8 <= c <= 0xf6 or c >= 0xf8


def is_name_char(c):
    return is_name_start(c) or c in b"-." or 0x30 <= c <= 0x39 or c == 0xb7


def is_valid_xml_name(data: bytes):
    """typeck.c is_valid_xml_name: every byte of the literal."""
    return bool(data) and is_name_start(data[0]) and all(is_name_char(c) for c in data[1:])


def is_valid_uri(data: bytes):
    """cob_is_valid_uri (xmlParseURI), on the literal up to its first NUL."""
    from . import uri
    return uri.is_valid(data.split(b"\0")[0])


class MlParser:
    def __init__(self, p, verb, line):
        self.p, self.xml, self.line = p, verb == "XML", line
        self.verb = verb
        self.suppress: list[Suppress] = []

    # Grammar

    def literal_bytes(self, token):
        return token.text.encode("latin-1")

    def value(self, clause):
        """simple_value of NAMESPACE / NAMESPACE-PREFIX: ("lit", bytes) or ("ref", DataRef)."""
        p = self.p
        t = p.t
        if t.string:
            p.take()
            return ("lit", self.literal_bytes(t))
        if t.key in FIGURATIVES or t.key in {"QUOTE", "QUOTES", "ALL"} and not p.candidates(t.key):
            p.error(f"{clause} may not be a figurative constant")
        if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", t.text):
            p.error(f"{clause} must be alphanumeric or national")
        if t.key == "FUNCTION":
            p.error(f"{clause} FUNCTION non pris en charge")
        return ("ref", p.variable())

    def at_identifier(self):
        p = self.p
        return not p.t.string and bool(p.candidates(p.t.key))

    def ml_type(self, required=True):
        p = self.p
        for kind in (ATTRIBUTE, ELEMENT, CONTENT):
            if p.accept(kind):
                return kind
        if required:
            p.error("ATTRIBUTE, ELEMENT ou CONTENT attendu")
        return ANY

    def following_every(self):
        """error_if_following_every_clause."""
        if self.suppress and self.suppress[-1].target == "TYPE":
            self.p.error("WHEN clause must follow EVERY clause")

    def when_list(self):
        p = self.p
        values = []
        while True:
            if p.t.string or p.t.key not in FIGURATIVES:
                p.error("ZERO, SPACE, HIGH-VALUE ou LOW-VALUE attendu")
            values.append(FIGURATIVES[p.take().key])
            if not p.accept("OR"):
                return values

    def add_when(self, values):
        """add_when_to_ml_suppress_conds: the WHEN of the preceding
        identifier or EVERY phrase, else of the entire record."""
        if self.suppress and self.suppress[-1].target in {"IDENTIFIER", "TYPE"} and self.suppress[-1].when is None:
            self.suppress[-1].when = values
        else:
            self.suppress.append(Suppress(when=values))

    def suppress_list(self):
        p = self.p
        entries = 0
        while True:
            if self.xml and p.accept("EVERY"):
                self.following_every()
                if p.accept("NUMERIC"):
                    category, kind = "NUMERIC", self.ml_type(False)
                elif p.accept("NONNUMERIC"):
                    category, kind = "NONNUMERIC", self.ml_type(False)
                else:
                    category, kind = "ANY", self.ml_type()
                self.suppress.append(Suppress("TYPE", category=category, ml_type=kind))
            elif self.xml and p.accept("WHEN"):
                self.add_when(self.when_list())
            elif self.at_identifier():
                self.following_every()
                self.suppress.append(Suppress("IDENTIFIER", identifier=p.variable()))
            else:
                break
            entries += 1
        if not entries:
            p.error("SUPPRESS sans élément")

    def parse(self):
        p = self.p
        if p.at("PARSE"):
            p.error(f"{self.verb} PARSE non pris en charge")
        p.expect("GENERATE")
        if p.level:
            # cb_build_register_internal_code: no register in a contained program.
            p.error("missing register definition")
        out = p.variable()
        p.expect("FROM")
        source = p.variable()
        count = None
        if p.accept("COUNT"):
            p.accept("IN")
            count = p.variable()
        declaration = attributes = False
        namespace = prefix = None
        names, types = [], []
        if self.xml:
            while True:
                start = p.i
                p.accept("WITH")
                if p.accept("ENCODING"):
                    # CB_PENDING ("XML GENERATE ENCODING"): a warning, the
                    # simple_value ignored.
                    if p.t.string or re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", p.t.text):
                        p.take()
                    else:
                        p.variable()
                    if declaration:
                        p.error("ENCODING clause must come before XML-DECLARATION")
                    elif attributes:
                        p.error("ENCODING clause must come before ATTRIBUTES")
                elif p.accept("XML-DECLARATION"):
                    declaration = True
                    if attributes:
                        p.error("XML-DECLARATION clause must come before ATTRIBUTES")
                elif p.accept("ATTRIBUTES"):
                    attributes = True
                else:
                    p.i = start
                    break
            if p.accept("NAMESPACE"):
                p.accept("IS")
                namespace = self.value("NAMESPACE")
                if p.accept("NAMESPACE-PREFIX"):
                    p.accept("IS")
                    prefix = self.value("NAMESPACE-PREFIX")
        if p.accept("NAME"):
            p.accept("OF")
            while True:
                ref = p.variable()
                p.accept("IS")
                if not self.xml and p.accept("OMITTED"):
                    names.append((ref, None))
                elif p.t.string:
                    names.append((ref, self.literal_bytes(p.take())))
                elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", p.t.text):
                    names.append((ref, p.take().text.encode("latin-1")))
                else:
                    p.error("NAME OF requiert un littéral")
                if not self.at_identifier():
                    break
        if self.xml and p.accept("TYPE"):
            p.accept("OF")
            while True:
                ref = p.variable()
                p.accept("IS")
                types.append((ref, self.ml_type()))
                if not self.at_identifier():
                    break
        if p.accept("SUPPRESS"):
            self.suppress_list()
        exception, success = p.exception_phrases("END-" + self.verb, escape=False)
        p.accept("END-" + self.verb)
        self.check(out, source, count, namespace, prefix, names, types)
        # get_ml_name and get_ml_type take the first pair of the item.
        first_names, first_types = {}, {}
        for ref, name in names:
            first_names.setdefault(ref.name, name)
        for ref, kind in types:
            first_types.setdefault(ref.name, kind)
        tree = self.tree(source.name, attributes, False, first_names, first_types, True)
        if attributes and not tree.attrs:
            pass  # cb_warning: WITH ATTRIBUTES specified, but no attributes can be generated
        spec = {"xml": self.xml, "out": out, "count": count, "declaration": declaration,
                "namespace": namespace, "prefix": prefix if prefix else None,
                "tree": tree, "checks": self.suppress_checks(tree)}
        stmt = Stmt("ml_generate", (spec,), self.line)
        if exception is None and success is None:
            return stmt
        # output_stmt: cob_exception_code = 0, then output_level_2_ex_condition.
        stmt.handled = True
        check = Stmt("if", (Expr("ml_exception", ("EC-XML" if self.xml else "EC-JSON",)),
                            exception or [], success or []), self.line)
        result = Stmt("sequence", ([stmt, check],), self.line)
        result.takes_exception = success is None
        return result

    # typeck.c checks

    def field(self, ref):
        return self.p.fields[ref.name]

    def category(self, f):
        """CB_TREE_CATEGORY."""
        if f.children:
            return "ALPHANUMERIC"
        if f.alnum_edit:
            return "ALPHANUMERIC-EDITED"
        if f.kind == "edited":
            return "NUMERIC-EDITED"
        if f.kind == "number":
            return "NUMERIC"
        if f.kind == "pointer":
            return "POINTER"
        picture = re.sub(r"\(\d+\)", "", f.picture.upper())
        return "ALPHABETIC" if picture and set(picture) <= {"A", "B"} and "A" in picture else "ALPHANUMERIC"

    def ignored(self, f):
        """cb_field_is_ignored_in_ml_gen."""
        return f.filler or f.redefines is not None or f.level == 66

    def subordinate(self, key, parent):
        f = self.p.fields[key]
        while f.parent is not None:
            if f.parent == parent:
                return True
            f = self.p.fields[f.parent]
        return False

    def ignored_child(self, key, parent):
        """is_ignored_child_in_ml_gen."""
        while key is not None and key != parent:
            f = self.p.fields[key]
            if self.ignored(f):
                return True
            key = f.parent
        return False

    def plain(self, ref, what):
        """error_if_subscript_or_refmod."""
        if ref.indices:
            self.p.error(f"{what} may not be subscripted")
        if ref.start is not None:
            self.p.error(f"{what} may not be reference modified")

    def child(self, ref, source, what):
        if not self.subordinate(ref.name, source.name):
            self.p.error(f"{what} must be a child of the input record")
        if self.ignored_child(ref.name, source.name):
            self.p.error(f"{what} may not be an ignored item in JSON/XML GENERATE")

    def all_ignored(self, key):
        """all_children_are_ignored."""
        for child in self.p.fields[key].children:
            f = self.p.fields[child]
            if not self.ignored(f) and not (f.children and self.all_ignored(child)):
                return False
        return True

    def descendants(self, key):
        for child in self.p.fields[key].children:
            yield child
            yield from self.descendants(child)

    def check(self, out, source, count, namespace, prefix, names, types):
        p = self.p
        # syntax_check_ml_gen_receiving_item
        what = "JSON/XML GENERATE receiving item"
        if self.category(self.field(out)) not in {"ALPHANUMERIC", "NATIONAL"}:
            p.error(f"{what} must be alphanumeric or national")
        if self.field(out).justified:
            p.error("JSON/XML GENERATE receiving item may not have JUSTIFIED clause")
        self.plain(out, what)
        # syntax_check_ml_gen_input_rec
        root = self.field(source)
        if source.start is not None:
            p.error("JSON/XML GENERATE input record may not be reference modified")
        if root.level == 66 and getattr(root, "rename_thru", False):
            p.error("JSON/XML GENERATE input record may not have RENAMES clause")
        if root.level == 66 and root.picture != p.fields[root.redefines].picture:
            p.error("RENAMES d'un groupe dans JSON/XML GENERATE non pris en charge")
        if root.children and self.all_ignored(source.name):
            p.error(f"all the children of '{root.label}' are ignored in JSON/XML GENERATE")
        # all_children_ok_qualified_by_only: each name outside FILLER groups
        # must be unique when qualified by the record (cb_try_ref).
        counts = {}
        for key in self.descendants(source.name):
            if not p.fields[key].filler:
                counts[p.fields[key].label] = counts.get(p.fields[key].label, 0) + 1

        def checked(key):
            for child in p.fields[key].children:
                if not p.fields[child].filler:
                    yield child
                    yield from checked(child)
        if any(counts[p.fields[key].label] > 1 for key in checked(source.name)):
            p.error("JSON/XML GENERATE input record has subrecords with non-unique names")
        # syntax_check_ml_gen_count_in (error_if_not_int_field_or_has_pic_p)
        if count is not None:
            f = self.field(count)
            if self.category(f) != "NUMERIC" or f.usage in {"COMP-1", "COMP-2"} or f.scale > 0:
                p.error(f"COUNT IN item '{f.label}' must be an integer")
            if f.scale < 0:
                p.error(f"COUNT IN item '{f.label}' may not have PICTURE with P in it")
        # syntax_check_xml_gen_namespace and syntax_check_xml_gen_prefix
        for clause, value in (("NAMESPACE", namespace), ("NAMESPACE-PREFIX", prefix)):
            if value is None:
                continue
            if value[0] == "ref" and self.category(self.field(value[1])) not in {"ALPHANUMERIC", "NATIONAL"}:
                p.error(f"{clause} must be alphanumeric or national")
            if value[0] == "lit" and clause == "NAMESPACE" and not is_valid_uri(value[1]):
                p.error("NAMESPACE must be a valid URI")
            if value[0] == "lit" and clause == "NAMESPACE-PREFIX" and not is_valid_xml_name(value[1]):
                p.error("NAMESPACE-PREFIX must be a valid XML name")
        # syntax_check_ml_gen_name_list
        for ref, name in names:
            self.plain(ref, "NAME OF item")
            if ref.name != source.name and not self.subordinate(ref.name, source.name):
                p.error("NAME OF item must be the input record or a child of it")
            if self.ignored_child(ref.name, source.name):
                p.error("NAME OF item may not be an ignored item in JSON/XML GENERATE")
            if name is None:
                if ref.name != source.name:
                    p.error("NAME OF ... OMITTED only valid for source identifier")
                continue
            if not is_valid_xml_name(name):
                p.error(f"NAME OF literal must be a valid {'XML' if self.xml else 'JSON'} identifier")
        # syntax_check_ml_gen_type_list
        for ref, _ in types:
            self.plain(ref, "TYPE OF item")
            if self.field(ref).children:
                p.error("TYPE OF item must be elementary")
            self.child(ref, source, "TYPE OF item")
        # syntax_check_ml_gen_suppress_list
        for clause in self.suppress:
            if clause.identifier is None:
                continue
            ref = clause.identifier
            f = self.field(ref)
            self.plain(ref, "SUPPRESS item")
            if clause.when and f.children:
                p.error("SUPPRESS item with WHEN clause must be elementary")
            self.child(ref, source, "SUPPRESS item")
            for value in clause.when or ():
                if value in {"SPACE", "LOW", "HIGH"}:
                    name = {"SPACE": "SPACE", "LOW": "LOW-VALUE", "HIGH": "HIGH-VALUE"}[value]
                    if f.usage != "DISPLAY":
                        p.error(f"SUPPRESS WHEN {name} item must be USAGE DISPLAY or NATIONAL")
                    if value != "SPACE" and f.kind == "number" and f.scale > 0:
                        p.error(f"SUPPRESS WHEN {name} item must be an integer")

    # tree.c cb_build_ml_tree

    def unconditional(self, key):
        """is_unconditionally_suppressed."""
        return any(c.when is None and c.target == "IDENTIFIER" and c.identifier.name == key for c in self.suppress)

    def ml_type_of(self, key, types, default_to_attr):
        """get_ml_type."""
        if key in types:
            return types[key]
        f = self.p.fields[key]
        if default_to_attr and not f.children and not f.filler and not f.table:
            return ATTRIBUTE
        return ELEMENT

    def ml_name(self, key, names, kind):
        """get_ml_name: the NAME OF literal, else cb_name."""
        if kind == CONTENT:
            return None
        if key in names:
            return names[key]
        f = self.p.fields[key]
        return getattr(f, "spelling", f.label).encode("latin-1")

    def applies(self, clause, key, kind):
        """is_target_of_suppress_type."""
        if clause.target != "TYPE":
            return False
        if clause.ml_type != ANY and clause.ml_type != kind:
            return False
        numeric = self.category(self.p.fields[key]) == "NUMERIC"
        return {"NUMERIC": numeric, "NONNUMERIC": not numeric}.get(clause.category, True)

    def condition(self, key, values):
        """build_condition_token_list: item = v1 OR = v2 ..., through cb_build_cond."""
        if not values:
            return None
        p = self.p
        figurative = {"ZERO": lambda: Expr("number", ("0",), figurative_zero=True),
                      "SPACE": lambda: Expr("text", (" ",), figurative_space=True),
                      "HIGH": lambda: Expr("all", (p.high_value,), memset=p.high_value == "\xff"),
                      "LOW": lambda: Expr("all", (p.low_value,), memset=p.low_value == "\x00")}
        tokens = [("x", Expr("var", (self.item_ref(key),)))]
        for index, value in enumerate(values):
            if index:
                tokens.append(("|", None))
            tokens += [("=", None), ("x", figurative[value]())]
        from .conditions import build
        return build(tokens, p.error)

    def suppress_cond(self, key, kind):
        """get_suppress_cond: the first SUPPRESS identifier phrase (the list
        is in reverse order of the source) for the item, else the first
        applicable generic phrase."""
        if key is None:
            return None
        reverse = list(reversed(self.suppress))
        chosen = None
        for clause in reverse:
            if clause.target == "IDENTIFIER" and clause.identifier.name == key:
                chosen = clause
        if chosen is not None:
            return self.condition(key, chosen.when)
        cond = None
        for clause in reverse:
            if clause.target == "ALL" or self.applies(clause, key, kind):
                cond = self.condition(key, clause.when)
        return cond

    def item_ref(self, key):
        """cb_build_field_reference without subscripts: the first occurrence."""
        f = self.p.fields[key]
        return DataRef(key, tuple(Expr("number", ("1",)) for _ in f.dimensions))

    def tree(self, key, children_are_attrs, default_to_attr, names, types, root=False):
        p = self.p
        if self.unconditional(key):
            return None
        f = p.fields[key]
        if f.depending or any(p.fields[k].depending for k in self.descendants(key)):
            p.error("OCCURS DEPENDING dans JSON/XML GENERATE non pris en charge")
        if f.kind == "pointer" or f.usage in {"POINTER", "PROGRAM-POINTER"}:
            p.error("article POINTER dans JSON/XML GENERATE non pris en charge")
        kind = self.ml_type_of(key, types, default_to_attr)
        slot = p.ml_slots
        p.ml_slots += 1
        node = Node(kind, self.ml_name(key, names, kind), None, slot)
        last = {ATTRIBUTE: None, ELEMENT: None}
        for child in f.children:
            if self.ignored(p.fields[child]):
                continue
            sub = self.tree(child, False, children_are_attrs, names, types)
            if sub is None:
                continue
            sub.parent = node
            group = node.attrs if sub.kind == ATTRIBUTE else node.children
            bucket = ATTRIBUTE if sub.kind == ATTRIBUTE else ELEMENT
            sub.prev = last[bucket]
            last[bucket] = sub
            group.append(sub)
        node.value = None if f.children and kind == ELEMENT else key
        node.cond = self.suppress_cond(node.value, kind)
        return node

    # codegen.c output_ml_suppress_checks

    def suppress_checks(self, tree):
        """The is_suppressed assignments in cobc's order: ("cond", node) and
        ("parent", node, flags) for `|=` of all its attributes and children."""
        def last_attr(s):
            return s.attrs[-1]

        def last_child(s):
            child = s.children[-1]
            return last_child(child) if child.children else child

        def prev_entry(s):
            if s.prev is not None:
                if s.prev.children:
                    return last_child(s.prev)
                if s.prev.attrs:
                    return last_attr(s.prev)
                return s.prev
            if s.attrs:
                return last_attr(s)
            return s.parent

        checks, seen = [], set()
        node = last_child(tree) if tree.children else last_attr(tree) if tree.attrs else tree
        while True:
            if id(node) in seen:
                # get_prev_ml_tree_entry goes back to an element whose
                # attributes lead to it again: cobc does not end.
                self.p.error("JSON/XML GENERATE d'un élément à attributs sans frère précédent: cobc ne termine pas")
            seen.add(id(node))
            if node.cond is not None:
                checks.append(("cond", node))
            if (node.children or node.attrs) and node is not tree:
                members = node.attrs + node.children
                if all(m.cond is not None for m in members):
                    checks.append(("parent", node, members))
            if node is tree:
                return checks
            node = prev_entry(node)


def ml_statement(p, verb, line):
    if frontend.STD == "cobol85":
        p.error(f"instruction non prise en charge: {verb}")
    return MlParser(p, verb, line).parse()
