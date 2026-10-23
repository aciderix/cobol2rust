from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class CobolError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    text: str
    line: int
    string: bool = False
    start: int = field(default=0, compare=False, repr=False)
    end: int = field(default=0, compare=False, repr=False)

    @property
    def key(self):
        return self.text if self.string else self.text.upper()


def fixed_fragment(area: str, quotation=None):
    """Read columns 8..72, retaining GnuCOBOL's column-72 quote state."""
    consecutive = False
    end = len(area)
    for index, char in enumerate(area):
        if quotation is None and area.startswith("*>", index):
            end = index
            break
        if char in "\"'":
            if quotation is None:
                quotation = char
            elif char == quotation:
                if index == 64:
                    consecutive = True
                else:
                    quotation = None
    text = area[:end]
    if quotation is not None:
        text = text.ljust(65)
    else:
        text = text.rstrip()
        # A closed literal must not merge with the next opening delimiter.
        if text.endswith(("'", '"')):
            text += " "
    return text, quotation, consecutive


def normalize(source: str, fmt: str = "auto") -> str:
    from .documentary import DocumentaryFilter

    lines = source.splitlines()
    fmt = source_format(source, fmt)
    documentary = DocumentaryFilter()
    result = []
    previous = None
    quotation = None
    consecutive = False
    debugging_lines = False
    for number, line in enumerate(lines, 1):
        directive = re.fullmatch(r"\s*>>SOURCE\s+FORMAT\s+(?:IS\s+)?(FREE|FIXED)\s*", line, re.I)
        if directive:
            if quotation is not None and not consecutive:
                raise CobolError(f"ligne {number}: directive au milieu d'un littéral fixe continué")
            fmt = directive[1].lower()
            documentary.format_changed(fmt)
            previous, quotation, consecutive = None, None, False
            result.append("")
            continue
        if fmt == "fixed":
            # Default GnuCOBOL tab width, applied before counting source columns.
            line = line.expandtabs(8)
            if not line.strip():
                result.append("")
                continue
            if len(line) < 7 or not re.fullmatch(r"[ 0-9]{6}", line[:6]):
                raise CobolError(f"ligne {number}: format fixe invalide (colonnes 1-7)")
            indicator = line[6]
            if indicator in "*/":
                result.append("")
                continue
            if indicator in "Dd":
                # Without DEBUGGING MODE, GnuCOBOL drops debugging lines.
                debugging_lines = True
                result.append("")
                continue
            if indicator not in " -":
                raise CobolError(f"ligne {number}: indicateur fixe {indicator!r} non pris en charge")
            line = line[7:72]
            directive = re.fullmatch(r"\s*>>SOURCE\s+FORMAT\s+(?:IS\s+)?(FREE|FIXED)\s*", line, re.I)
            if directive:
                if quotation is not None and not consecutive:
                    raise CobolError(f"ligne {number}: directive au milieu d'un littéral fixe continué")
                if indicator == "-":
                    raise CobolError(f"ligne {number}: directive sur une ligne de continuation")
                fmt = directive[1].lower()
                documentary.format_changed(fmt)
                previous, quotation, consecutive = None, None, False
                result.append("")
                continue
            if indicator != "-" and quotation is not None and not consecutive and line.strip():
                raise CobolError(f"ligne {number}: littéral fixe non terminé; indicateur '-' attendu")
            # Documentary prose may contain arbitrary quotes and COPY words.
            # Filter it before literal continuation and token processing, while
            # keeping genuine literal continuations outside the filter.
            if not (quotation is not None and indicator == "-") and documentary.is_comment(line, fmt, indicator, number):
                previous, quotation, consecutive = None, None, False
                result.append("")
                continue
            if not line.strip():
                result.append("")
                continue
            if indicator == "-":
                if previous is None:
                    raise CobolError(f"ligne {number}: continuation fixe sans ligne précédente")
                start = len(line) - len(line.lstrip(" "))
                prefix = quotation * (2 if consecutive else 1) if quotation else ""
                if prefix and not line[start:].startswith(prefix):
                    raise CobolError(f"ligne {number}: délimiteur de littéral continué attendu: {prefix!r}")
                if quotation:
                    # Keep original column positions for padding and the col-72 rule.
                    line = " " * (start + 1) + line[start + 1:]
                    if consecutive:
                        quotation = None
                    start += 1
                fragment, quotation, consecutive = fixed_fragment(line, quotation)
                result[previous] += fragment[start:]
                result.append("")
                continue
            if quotation is not None and not consecutive:
                raise CobolError(f"ligne {number}: littéral fixe non terminé; indicateur '-' attendu")
            fragment, quotation, consecutive = fixed_fragment(line)
            result.append(fragment)
            if fragment.strip():
                previous = len(result) - 1
            continue
        result.append("" if documentary.is_comment(line, fmt, line=number) else line)
    text = "\n".join(result)
    # GnuCOBOL's preprocessor activates debugging lines on WITH DEBUGGING MODE.
    if debugging_lines and re.search(r"\bDEBUGGING[\s,;]+MODE\b", text, re.I):
        raise CobolError("lignes de débogage 'D' actives avec DEBUGGING MODE non prises en charge")
    return text


def lex(source: str) -> list[Token]:
    tokens = []
    i, line = 0, 1
    picture_pending = False
    parentheses = 0
    while i < len(source):
        c = source[i]
        token_start = i
        if c.isspace():
            line += c == "\n"
            i += 1
        elif source.startswith("*>", i):
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
        elif picture_pending:
            # A PICTURE is one contiguous word, not ordinary COBOL tokens.
            # Keep commas of editing images; return one terminal comma/period
            # to the normal scanner, matching the reference compiler.
            end = i
            while (end < len(source) and not source[end].isspace() and source[end] != ";"
                   and not source.startswith("*>", end)):
                end += 1
            word = source[i:end]
            if word.upper() == "IS":
                tokens.append(Token(word, line, False, i, end))
                i = end
                continue
            if word.endswith((".", ",")):
                end -= 1
                word = source[i:end]
            if not word or not word.isascii():
                raise CobolError(f"ligne {line}: mot PICTURE ASCII contigu attendu")
            tokens.append(Token(word, line, False, i, end))
            i = end
            picture_pending = False
        elif c in ",;":
            # Parenthesized lists need a delimiter: dropping it would merge
            # t(1,+2) into the single arithmetic subscript t(1+2).
            end = i + 1
            while end < len(source) and source[end] == c:
                end += 1
            if parentheses:
                tokens.append(Token(c, line, False, i, end))
            i = end
        elif c in "\"'":
            quote, start, value = c, line, ""
            i += 1
            while i < len(source):
                if source[i] == "\n":
                    raise CobolError(f"ligne {start}: littéral multiligne non pris en charge")
                if source[i] == quote:
                    i += 1
                    if i < len(source) and source[i] == quote:
                        value += quote
                        i += 1
                        continue
                    break
                value += source[i]
                i += 1
            else:
                raise CobolError(f"ligne {start}: littéral non terminé")
            if not value.isascii():
                raise CobolError(f"ligne {start}: seuls les littéraux ASCII sont pris en charge")
            tokens.append(Token(value, start, True, token_start, i))
        else:
            # A COBOL word may start with digits when it holds a letter (3-DIMENSION-TBL);
            # a numeric literal may start with its decimal point after a separator.
            point = (c == "." and i + 1 < len(source) and source[i + 1].isdigit()
                     and (i == 0 or source[i - 1].isspace() or source[i - 1] in "(+-*/=<>,"))
            match = re.match(r"\.\d+" if point else
                             r"\d+[A-Za-z0-9-]*[A-Za-z][A-Za-z_0-9-]*|\d+(?:\.\d+)?|[A-Za-z_][A-Za-z_0-9-]*|>=|<=|<>|[.(),:+*/=<>-]",
                             source[i:])
            if not match:
                raise CobolError(f"ligne {line}: caractère non pris en charge {c!r}")
            tokens.append(Token(match[0], line, False, i, i + len(match[0])))
            i += len(match[0])
            if match[0].upper() in {"PIC", "PICTURE"} and not (len(tokens) > 1 and tokens[-2].key == "COPY"):
                picture_pending = True
            elif match[0] == "(":
                parentheses += 1
            elif match[0] == ")" and parentheses:
                parentheses -= 1
    tokens.append(Token("<EOF>", line, False, len(source), len(source)))
    return tokens


def load_source(path: Path, include_dirs: list[Path], fmt="auto", stack=()) -> tuple[str, list[str]]:
    path = path.resolve()
    if path in stack:
        raise CobolError(f"COPY cyclique: {path}")
    text = normalize(path.read_text(encoding="utf-8-sig"), fmt)
    # COPY is expanded at token boundaries; strings and comments cannot become directives.
    toks = lex(text)
    lines = text.splitlines()
    copies = []
    replacements = []
    i = 0
    while i < len(toks) - 1:
        if not toks[i].string and toks[i].key == "COPY":
            start = toks[i].line
            if i + 2 >= len(toks) or toks[i + 2].key != ".":
                raise CobolError(f"ligne {start}: COPY REPLACING/multiligne non pris en charge")
            name = toks[i + 1].text
            end = toks[i + 2].line
            if start != end or any(t.line == start for t in toks[:i]) or (toks[i + 3].key != "<EOF>" and toks[i + 3].line == end):
                raise CobolError(f"ligne {start}: COPY doit occuper une ligne entière")
            # The COPY preprocessor has its own separator grammar. Do not
            # admit extra punctuation just because the ordinary lexer skips it.
            declaration_line = lines[start - 1]
            first, name_token, period = toks[i:i + 3]
            line_start = text.rfind("\n", 0, first.start) + 1
            pieces = [declaration_line[:first.start - line_start],
                      text[first.end:name_token.start], text[name_token.end:period.start],
                      declaration_line[period.end - line_start:].split("*>", 1)[0]]
            if any("," in piece or ";" in piece for piece in pieces):
                raise CobolError(f"ligne {start}: séparateurs supplémentaires dans COPY non pris en charge")
            roots = [path.parent, *include_dirs]
            candidates = [root / (name + ext) for root in roots for ext in ("", ".cpy", ".CPY", ".cob", ".cbl")]
            found = next((p for p in candidates if p.is_file()), None)
            if found is None:
                raise CobolError(f"ligne {start}: copybook introuvable: {name}")
            expanded, children = load_source(found, include_dirs, fmt, (*stack, path))
            copies.extend([str(found.resolve()), *children])
            replacements.append((start - 1, expanded))
            i += 3
        else:
            i += 1
    for index, expanded in reversed(replacements):
        lines[index] = expanded
    return "\n".join(lines), list(dict.fromkeys(copies))


@dataclass
class Field:
    name: str
    picture: str
    kind: str
    digits: int
    scale: int
    signed: bool
    initial: Token
    usage: str = "DISPLAY"
    label: str = ""
    level: int = 1
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    occurs: int = 1
    table: bool = False
    redefines: str | None = None
    filler: bool = False
    file_record: bool = False
    linkage: bool = False
    offset: int = 0
    size: int = 0
    dimensions: list[tuple[int, int]] = field(default_factory=list)
    occurs_min: int = 1
    depending: str | None = None
    index_for: str | None = None
    editing: str = ""
    group_value: tuple[str, str | None] | None = None  # (literal, ZERO/SPACE fill)
    group_usage: str | None = None


@dataclass(frozen=True)
class DataRef:
    name: str
    indices: tuple = ()
    start: object | None = None
    length: object | None = None


@dataclass
class Condition:
    name: str
    label: str
    parent: str
    values: list[tuple[Token, Token]]
    false_value: Token | None = None


@dataclass
class Expr:
    op: str
    args: tuple
    figurative_zero: bool = False
    figurative_space: bool = False


@dataclass
class Stmt:
    op: str
    args: tuple = ()
    line: int = 0


@dataclass
class FileSpec:
    name: str
    path: Token
    optional: bool = False
    status: str | None = None
    record: str | None = None
    organization: str = "LINE SEQUENTIAL"
    records: list[str] = field(default_factory=list)
    fd_clauses: dict = field(default_factory=dict)
    access: str = "SEQUENTIAL"
    relative_key: str | None = None
    record_min: int = 0
    record_max: int = 0
    depending: str | None = None


@dataclass
class ProcedureBlock:
    name: str | None
    section: str | None
    body: list[Stmt]


@dataclass
class Program:
    name: str
    fields: dict[str, Field]
    entry: list[Stmt]
    paragraphs: dict[str, list[Stmt]] = field(default_factory=dict)
    files: dict[str, FileSpec] = field(default_factory=dict)
    conditions: dict[str, Condition] = field(default_factory=dict)
    memory_size: int = 0
    blocks: list[ProcedureBlock] = field(default_factory=list)
    sections: dict[str, tuple[int, int]] = field(default_factory=dict)
    # USE AFTER ERROR sections: by file name, and by OPEN mode.
    file_declaratives: dict[str, str] = field(default_factory=dict)
    mode_declaratives: dict[str, str] = field(default_factory=dict)
    main_block: int = 0
    # PROCEDURE DIVISION USING: linkage 01/77 items bound to CALL arguments.
    using: list[str] = field(default_factory=list)
    # PROGRAM-ID as written: the entry point name a CALL literal must match.
    entry_name: str = ""

    def procedure_range(self, name: str) -> tuple[int, int]:
        if name in self.sections:
            return self.sections[name]
        if self.blocks:
            for index, block in enumerate(self.blocks):
                if block.name == name:
                    return index, index + 1
        elif name in self.paragraphs:
            index = list(self.paragraphs).index(name) + 1
            return index, index + 1
        raise CobolError(f"procédure inconnue: {name}")


VERBS = set("DISPLAY ACCEPT MOVE ADD SUBTRACT MULTIPLY DIVIDE COMPUTE IF PERFORM STOP GOBACK CONTINUE EVALUATE INITIALIZE EXIT OPEN READ WRITE REWRITE DELETE START CLOSE SET GO CALL CANCEL".split())
BOUNDARIES = VERBS | set("ELSE END-IF END-PERFORM END-EVALUATE WHEN END-DISPLAY END-ACCEPT END-ADD END-SUBTRACT END-MULTIPLY END-DIVIDE END-COMPUTE END-READ END-WRITE END-REWRITE END-DELETE END-START END-CALL EXCEPTION OVERFLOW AT NOT ON INVALID . <EOF>".split())


def source_format(source: str, fmt="auto"):
    return ("fixed" if any(re.match(r"^\d{6}[ */-]", x) for x in source.splitlines()) else "free") if fmt == "auto" else fmt


class Parser:
    def __init__(self, source: str):
        self.tokens = lex(source)
        self.i = 0
        self.fields = {}
        self.files = {}
        self.conditions = {}
        self.data_stack = []
        self.last_data = None
        self.filler_count = 0
        self.indexes = {}

    @property
    def t(self):
        return self.tokens[self.i]

    def error(self, message):
        raise CobolError(f"ligne {self.t.line}: {message} (près de {self.t.text!r})")

    def at(self, word):
        return not self.t.string and self.t.key == word

    def take(self):
        t = self.t
        if t.key != "<EOF>" or t.string:
            self.i += 1
        return t

    def accept(self, word):
        if self.at(word):
            self.take()
            return True
        return False

    def expect(self, word):
        if not self.accept(word):
            self.error(f"{word} attendu")

    def name(self):
        if self.t.string or not re.fullmatch(r"[A-Z_][A-Z_0-9-]*|\d[A-Z0-9-]*[A-Z][A-Z_0-9-]*", self.t.key):
            self.error("identifiant attendu")
        if self.t.key in {"PIC", "PICTURE"}:
            self.error("nom réservé: " + self.t.key)
        return self.take().key

    def variable(self):
        return self.reference()

    def candidates(self, label, conditions=False):
        registry = self.conditions if conditions else self.fields
        return [key for key, value in registry.items() if value.label == label and not getattr(value, "filler", False)]

    def resolve(self, label, qualifiers=(), conditions=False):
        registry = self.conditions if conditions else self.fields
        candidates = self.candidates(label, conditions)
        valid = []
        for key in candidates:
            parent = registry[key].parent
            ancestors = []
            while parent:
                ancestors.append(self.fields[parent].label)
                parent = self.fields[parent].parent
            position = 0
            for qualifier in qualifiers:
                try:
                    position = ancestors.index(qualifier, position) + 1
                except ValueError:
                    break
            else:
                valid.append(key)
        if len(valid) != 1:
            self.error(f"{'nom ambigu' if valid else 'nom inconnu'}: {label}; qualifier avec OF/IN si nécessaire")
        return valid[0]

    def reference(self, conditions=False):
        label = self.name()
        qualifiers = []
        while self.accept("OF") or self.accept("IN"):
            qualifiers.append(self.name())
        key = self.resolve(label, qualifiers, conditions)
        indices = []
        start, length = None, None
        if self.accept("("):
            first = self.expr()
            if self.accept(":"):
                start = first
                length = None if self.at(")") else self.expr()
                self.expect(")")
            else:
                indices.append(first)
                while not self.accept(")"):
                    self.accept(",") or self.accept(";")
                    if self.at("<EOF>"):
                        self.error("sous-script non terminé")
                    indices.append(self.expr())
                if self.accept("("):
                    start = self.expr()
                    self.expect(":")
                    length = None if self.at(")") else self.expr()
                    self.expect(")")
        descriptor = self.fields[self.conditions[key].parent] if conditions else self.fields[key]
        if len(indices) != len(descriptor.dimensions):
            self.error(f"{label} requiert {len(descriptor.dimensions)} sous-script(s), reçu {len(indices)}")
        if start is not None and (conditions or (descriptor.kind == "number" and descriptor.usage != "DISPLAY")):
            self.error("modification de référence limitée aux groupes, PIC X et numériques DISPLAY")
        return DataRef(key, tuple(indices), start, length)

    def parse(self):
        if not (self.accept("IDENTIFICATION") or self.accept("ID")):
            self.error("IDENTIFICATION DIVISION attendue")
        self.expect("DIVISION")
        self.expect(".")
        self.expect("PROGRAM-ID")
        self.expect(".")
        entry_name = self.t.text
        name = self.name()
        self.expect(".")
        if self.accept("ENVIRONMENT"):
            self.environment_division()
        if self.accept("DATA"):
            self.expect("DIVISION")
            self.expect(".")
            if self.accept("FILE"):
                self.expect("SECTION")
                self.expect(".")
                while self.accept("FD"):
                    file_name = self.file_name()
                    spec = self.files[file_name]
                    if spec.record:
                        self.error("FD dupliqué")
                    from .file_parser import parse_fd_clauses
                    parse_fd_clauses(self, spec)
                    while not spec.records or (self.t.key.isdigit() and self.t.key in {"01", "1", "77"}):
                        self.data_stack = []
                        record = self.t
                        key = self.declaration(file_record=True)
                        while self.t.key.isdigit() and self.t.key not in {"01", "1", "77"}:
                            self.declaration(file_record=True)
                        descriptor = self.fields[key]
                        if record.key not in {"01", "1"} or descriptor.kind != "text" or descriptor.table or descriptor.redefines:
                            self.error("FD requiert un enregistrement 01 texte ou groupe sans OCCURS ni REDEFINES explicite à la racine")
                        if spec.records:
                            if spec.organization not in {"SEQUENTIAL", "RELATIVE"}:
                                self.error("plusieurs enregistrements FD limités à SEQUENTIAL/RELATIVE de taille fixe égale")
                            descriptor.redefines = spec.record
                        else:
                            spec.record = key
                        spec.records.append(key)
            if self.accept("WORKING-STORAGE"):
                self.expect("SECTION")
                self.expect(".")
                self.data_stack = []
                while not self.at("PROCEDURE") and not self.at("LINKAGE"):
                    self.declaration()
            if self.accept("LINKAGE"):
                self.expect("SECTION")
                self.expect(".")
                self.data_stack = []
                self.in_linkage = True
                while not self.at("PROCEDURE"):
                    self.declaration()
                self.in_linkage = False
        for label, owner in self.indexes.items():
            if self.candidates(label) or self.candidates(label, True):
                self.error(f"index dupliqué avec une donnée: {label}")
            self.fields[label] = Field(label, "S9(9)", "number", 9, 0, True, Token("1", 0),
                                       "INDEX", label, 77, index_for=owner)
        for descriptor in self.fields.values():
            if descriptor.depending:
                descriptor.depending = self.resolve(descriptor.depending)
        from .layout import layout_fields
        memory_size = layout_fields(self.fields)
        self.validate_files()
        self.expect("PROCEDURE")
        self.expect("DIVISION")
        using = []
        if self.accept("USING"):
            while not self.at("."):
                if self.accept("BY"):
                    if not self.accept("REFERENCE"):
                        self.error("PROCEDURE DIVISION USING limité à BY REFERENCE")
                if self.at("RETURNING") or self.at("VALUE") or self.at("OPTIONAL"):
                    self.error("PROCEDURE DIVISION USING limité à BY REFERENCE sans RETURNING")
                key = self.resolve(self.name())
                field = self.fields[key]
                if not field.linkage or field.parent is not None or field.redefines or key in using:
                    self.error("USING requiert des articles 01/77 distincts de la LINKAGE SECTION")
                using.append(key)
            if not using:
                self.error("USING requiert au moins un paramètre")
        self.expect(".")
        entry, paragraphs = [], {}
        blocks = [ProcedureBlock(None, None, entry)]
        sections = {}
        current_body, current_section = entry, None
        file_declaratives, mode_declaratives = {}, {}
        declaratives, main_block = self.accept("DECLARATIVES"), 0
        if declaratives:
            self.expect(".")
        while not self.at("<EOF>"):
            if self.accept("."):
                continue
            if declaratives and self.at("END") and self.tokens[self.i + 1].key == "DECLARATIVES":
                self.take(); self.take(); self.expect(".")
                if current_section is None:
                    self.error("DECLARATIVES requiert au moins une section USE")
                sections[current_section] = (sections[current_section][0], len(blocks))
                # Execution starts after END DECLARATIVES, outside every section.
                declaratives, current_section, current_body = False, None, []
                main_block = len(blocks)
                blocks.append(ProcedureBlock(None, None, current_body))
                continue
            if self.accept("END"):
                self.expect("PROGRAM")
                if self.name() != name:
                    self.error("END PROGRAM ne correspond pas au PROGRAM-ID")
                self.expect(".")
                self.expect("<EOF>")
                break
            if self.t.key not in VERBS and self.tokens[self.i + 1].key == "SECTION":
                section = self.name()
                self.procedure_name_check(section)
                if section in sections or section in paragraphs:
                    self.error(f"nom de procédure dupliqué: {section}; les homonymes ne sont pas pris en charge")
                self.expect("SECTION")
                if self.t.key.isdigit():
                    self.error("numéro de segment SECTION non pris en charge")
                self.expect(".")
                if current_section is not None:
                    sections[current_section] = (sections[current_section][0], len(blocks))
                current_section = section
                sections[section] = (len(blocks), len(blocks) + 1)
                current_body = []
                blocks.append(ProcedureBlock(None, section, current_body))
                if declaratives:
                    self.use_statement(section, file_declaratives, mode_declaratives)
                elif self.at("USE"):
                    self.error("USE hors des DECLARATIVES")
            elif self.t.key not in VERBS and self.tokens[self.i + 1].key == ".":
                paragraph = self.name()
                self.procedure_name_check(paragraph)
                if paragraph in paragraphs or paragraph in sections:
                    self.error(f"nom de procédure dupliqué: {paragraph}; les homonymes ne sont pas pris en charge")
                self.expect(".")
                current_body = []
                paragraphs[paragraph] = current_body
                blocks.append(ProcedureBlock(paragraph, current_section, current_body))
            else:
                if declaratives and current_section is None:
                    self.error("section USE attendue après DECLARATIVES")
                current_body.append(self.statement())
        if declaratives:
            self.error("END DECLARATIVES attendu")
        if current_section is not None:
            sections[current_section] = (sections[current_section][0], len(blocks))
        unbound = [f.label for f in self.fields.values()
                   if f.linkage and f.parent is None and not f.redefines and f.name not in using]
        if unbound:
            self.error(f"article LINKAGE absent de PROCEDURE DIVISION USING non pris en charge: {unbound[0]}")
        program = Program(name, self.fields, entry, paragraphs, self.files, self.conditions, memory_size,
                          blocks, sections, file_declaratives, mode_declaratives, main_block, using)
        program.entry_name = entry_name
        self.validate_calls(program)
        return program

    def use_statement(self, section, by_file, by_mode):
        """USE AFTER STANDARD ERROR/EXCEPTION PROCEDURE ON files or an OPEN mode."""
        self.expect("USE")
        if self.at("GLOBAL") or self.at("FOR"):
            self.error("USE GLOBAL et USE FOR DEBUGGING non pris en charge")
        self.expect("AFTER")
        self.accept("STANDARD")
        if not (self.accept("EXCEPTION") or self.accept("ERROR")):
            self.error("USE AFTER requiert EXCEPTION ou ERROR")
        self.expect("PROCEDURE")
        self.accept("ON")
        if self.t.key in {"INPUT", "OUTPUT", "I-O", "EXTEND"} and not self.t.string:
            mode = self.take().key
            if mode in by_mode:
                self.error(f"USE dupliqué pour {mode}")
            by_mode[mode] = section
        else:
            names = [self.file_name()]
            while not self.t.string and self.t.key in self.files:
                names.append(self.file_name())
            for name in names:
                if name in by_file:
                    self.error(f"USE dupliqué pour le fichier {name}")
                by_file[name] = section
        self.expect(".")

    def procedure_name_check(self, name):
        # A data name followed by a period is a receiver, not a header.
        if (self.candidates(name) or self.candidates(name, True) or name in self.files
                or name in self.indexes):
            self.error(f"nom de procédure homonyme d'une donnée non pris en charge: {name}")

    def environment_division(self):
        self.expect("DIVISION")
        self.expect(".")
        if self.accept("CONFIGURATION"):
            self.expect("SECTION")
            self.expect(".")
            computers = set()
            while self.at("SOURCE-COMPUTER") or self.at("OBJECT-COMPUTER"):
                paragraph = self.take().key
                if paragraph in computers:
                    self.error(f"paragraphe {paragraph} dupliqué")
                computers.add(paragraph)
                self.expect(".")
                self.name()
                # GnuCOBOL 3.2 parses and ignores MEMORY SIZE and SEGMENT-LIMIT.
                while paragraph == "OBJECT-COMPUTER" and not self.at("."):
                    if self.accept("MEMORY"):
                        self.accept("SIZE")
                        self.accept("IS")
                        self.integer_literal("MEMORY SIZE")
                        if not any(self.accept(unit) for unit in ("WORDS", "CHARACTERS", "MODULES")):
                            self.error("MEMORY SIZE requiert WORDS, CHARACTERS ou MODULES")
                    elif self.accept("SEGMENT-LIMIT"):
                        self.accept("IS")
                        if not 1 <= self.integer_literal("SEGMENT-LIMIT") <= 49:
                            self.error("SEGMENT-LIMIT limité à 1..49")
                    else:
                        break
                if not self.accept("."):
                    self.error(f"clause {paragraph} non prise en charge; seul le nom de machine est accepté")
            if not any(self.at(word) for word in ("INPUT-OUTPUT", "DATA", "PROCEDURE")):
                self.error("paragraphe CONFIGURATION non pris en charge")
        if self.accept("INPUT-OUTPUT"):
            self.expect("SECTION")
            self.expect(".")
            self.expect("FILE-CONTROL")
            self.expect(".")
            while self.at("SELECT"):
                self.file_control()
            if self.accept("I-O-CONTROL"):
                self.expect(".")
                self.io_control()
        if not (self.at("DATA") or self.at("PROCEDURE")):
            self.error("clause ENVIRONMENT DIVISION non prise en charge")

    def integer_literal(self, clause):
        if self.t.string or not re.fullmatch(r"\d{1,9}", self.t.text):
            self.error(f"{clause} requiert un entier littéral non signé")
        return int(self.take().text)

    def io_control(self):
        """Accept the I-O-CONTROL entries GnuCOBOL 3.2 parses without effect."""
        while not self.at(".") and not self.at("DATA") and not self.at("PROCEDURE"):
            if self.accept("MULTIPLE"):
                self.accept("FILE")
                self.accept("TAPE")
                self.accept("CONTAINS")
                self.file_name()
                if self.accept("POSITION"):
                    self.integer_literal("POSITION")
                while not self.t.string and self.t.key in self.files:
                    self.file_name()
                    if self.accept("POSITION"):
                        self.integer_literal("POSITION")
            elif self.accept("SAME"):
                if self.at("RECORD"):
                    self.error("SAME RECORD AREA non pris en charge; enregistrements partagés non modélisés")
                self.accept("SORT") or self.accept("SORT-MERGE")
                self.accept("AREA")
                self.accept("FOR")
                self.file_name()
                while not self.t.string and self.t.key in self.files:
                    self.file_name()
            else:
                self.error("clause I-O-CONTROL non prise en charge")
        self.expect(".")

    def file_name(self):
        name = self.name()
        if name not in self.files:
            self.error(f"fichier non déclaré: {name}")
        return name

    def file_control(self):
        self.expect("SELECT")
        optional = self.accept("OPTIONAL")
        name = self.name()
        if name in self.files or name in VERBS:
            self.error(f"nom de fichier réservé ou dupliqué: {name}")
        self.expect("ASSIGN")
        self.accept("TO")
        path = self.take()
        if not path.string:
            self.error("ASSIGN requiert un chemin littéral entre guillemets")
        if not path.text or any(ord(c) < 32 for c in path.text):
            self.error("chemin ASSIGN vide ou invalide")
        organization, organization_seen, status, access = "SEQUENTIAL", False, None, None
        relative_key = None

        def organization_word():
            # [ORGANIZATION [IS]] {LINE SEQUENTIAL | [RECORD] [BINARY] SEQUENTIAL | RELATIVE}
            if self.accept("RELATIVE"):
                return "RELATIVE"
            if self.accept("LINE"):
                self.expect("SEQUENTIAL")
                return "LINE SEQUENTIAL"
            self.accept("RECORD")
            self.accept("BINARY")
            self.expect("SEQUENTIAL")
            return "SEQUENTIAL"

        def reference():
            # Data names are declared later: keep the qualifiers for resolution.
            label, qualifiers = self.name(), []
            while self.accept("OF") or self.accept("IN"):
                qualifiers.append(self.name())
            return label, tuple(qualifiers)

        clause_words = {"ACCESS", "FILE", "STATUS", "RESERVE", "RECORD", "LOCK", "SHARING",
                        "ORGANIZATION", "PADDING", "ALTERNATE", "COLLATING", ".", "SORT"}
        while not self.at("."):
            if self.accept("ORGANIZATION") and not organization_seen:
                organization_seen = True
                self.accept("IS")
                organization = organization_word()
            elif (not organization_seen and not self.t.string and (self.at("LINE") or self.at("SEQUENTIAL")
                    or self.at("BINARY") or (self.at("RELATIVE") and self.tokens[self.i + 1].key in clause_words))):
                organization_seen = True
                organization = organization_word()
            elif self.accept("ACCESS") and access is None:
                self.accept("MODE")
                self.accept("IS")
                if not any(self.at(word) for word in ("SEQUENTIAL", "RANDOM", "DYNAMIC")):
                    self.error("ACCESS limité à SEQUENTIAL, RANDOM ou DYNAMIC")
                access = self.take().key
            elif self.accept("RELATIVE") and relative_key is None:
                self.accept("KEY")
                self.accept("IS")
                relative_key = reference()
            elif (self.at("FILE") or self.at("STATUS")) and status is None:
                self.accept("FILE")
                self.expect("STATUS")
                self.accept("IS")
                status = reference()
                if not self.t.string and self.t.key not in clause_words | {"RELATIVE", "SEQUENTIAL", "LINE", "BINARY", "INDEXED"}:
                    self.error("statut VSAM supplémentaire de FILE STATUS non pris en charge")
            elif self.accept("RESERVE"):
                # GnuCOBOL 3.2 checks and ignores RESERVE {NO | integer} [AREA | AREAS].
                if not self.accept("NO"):
                    self.integer_literal("RESERVE")
                self.accept("AREA") or self.accept("AREAS")
            else:
                self.error("clause SELECT non prise en charge")
        self.expect(".")
        if organization != "RELATIVE" and (relative_key or access not in {None, "SEQUENTIAL"}):
            self.error("RELATIVE KEY et ACCESS RANDOM/DYNAMIC requièrent ORGANIZATION RELATIVE")
        if organization == "RELATIVE" and access in {"RANDOM", "DYNAMIC"} and not relative_key:
            self.error("ACCESS RANDOM/DYNAMIC requiert RELATIVE KEY")
        self.files[name] = FileSpec(name, path, optional, status, organization=organization,
                                    access=access or "SEQUENTIAL", relative_key=relative_key)

    def validate_files(self):
        for spec in self.files.values():
            if not spec.record:
                self.error(f"FD manquant pour {spec.name}")
            if spec.name in self.fields:
                self.error(f"nom ambigu entre fichier et donnée: {spec.name}")
            if spec.status:
                spec.status = self.resolve(*spec.status)
                status = self.fields.get(spec.status)
                # A two-byte group receives the status characters as raw bytes.
                group = status is not None and not status.picture and status.size == 2
                if not status or status.dimensions or not group and (
                        status.kind not in {"text", "number"} or status.digits != 2 or status.scale
                        or status.signed or status.usage != "DISPLAY"):
                    self.error(f"FILE STATUS {spec.status} doit être PIC XX, PIC 99 DISPLAY ou un groupe de 2 octets")
                if status.file_record:
                    self.error("FILE STATUS ne peut pas être une donnée FD")
            if spec.relative_key:
                spec.relative_key = self.resolve(*spec.relative_key)
                key = self.fields.get(spec.relative_key)
                # libcob reads it with cob_get_int: keep it an unsigned integer of 9 digits at most.
                if (not key or key.kind != "number" or key.scale or key.signed or key.digits > 9
                        or key.dimensions or key.usage == "INDEX"):
                    self.error("RELATIVE KEY limitée à un entier non signé de 9 chiffres au plus")
                if any(key.name == r or key.name.startswith(r + ".") for r in spec.records):
                    self.error("RELATIVE KEY dans l'enregistrement de son propre fichier non prise en charge")
            from .layout import leaves
            sizes = [self.fields[key].size for key in spec.records]
            varying = spec.fd_clauses.get("record_varying")
            # cobc's finalize_file: clause limits widened by the 01 sizes; the
            # minimum defaults to the first record, then the smallest one.
            low = (varying or {}).get("minimum") or 0
            high = (varying or {}).get("maximum") or 0
            if varying and low and high and high <= low:
                self.error("RECORD VARYING invalide: maximum inférieur ou égal au minimum")
            for size in sizes:
                if low and size < low:
                    low = size
                if high and size > high:
                    high = size
            low = low or sizes[0]
            spec.record_min, spec.record_max = min([low, *sizes]), max([high, *sizes])
            if spec.record_min != spec.record_max and spec.organization == "LINE SEQUENTIAL":
                self.error("enregistrements LINE SEQUENTIAL de tailles différentes non pris en charge")
            if varying and varying["depending"]:
                spec.depending = self.resolve(varying["depending"])
                dep = self.fields[spec.depending]
                if (dep.kind != "number" or dep.scale or dep.signed or dep.digits > 9 or dep.dimensions
                        or dep.usage == "INDEX" or any(dep.name == r or dep.name.startswith(r + ".") for r in spec.records)):
                    self.error("RECORD DEPENDING ON limité à un entier non signé de 9 chiffres hors de l'enregistrement")
            if "record_contains" in spec.fd_clauses and any(self.fields[key].size != spec.fd_clauses["record_contains"] for key in spec.records):
                self.error("RECORD CONTAINS doit égaler la taille physique de chaque description FD; format variable non pris en charge")
            if spec.organization == "LINE SEQUENTIAL" and any(f.usage != "DISPLAY" for f in leaves(self.fields, spec.record, True)):
                self.error("LINE SEQUENTIAL requiert des colonnes DISPLAY")

    def declaration(self, file_record=False):
        from .data_parser import declaration
        return declaration(self, file_record)

    def expr(self, minimum=0):
        t = self.take()
        if t.string:
            left = Expr("text", (t.text,))
        elif re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", t.text):
            left = Expr("number", (t.text,))
        elif t.key in {"ZERO", "ZEROS", "ZEROES"}:
            left = Expr("number", ("0",), figurative_zero=True)
        elif t.key in {"SPACE", "SPACES"}:
            left = Expr("text", (" ",), figurative_space=True)
        elif t.key == "ALL" and self.t.string:
            # ALL "literal" repeats the literal over the receiver; MOVE only.
            left = Expr("all", (self.take().text,))
        elif t.key in {"+", "-"}:
            left = Expr("unary" + t.key, (self.expr(30),))
        elif t.key == "(":
            left = self.expr()
            self.expect(")")
        elif t.key in {"TRUE", "FALSE"}:
            left = Expr("bool", (t.key == "TRUE",))
        elif self.candidates(t.key, True):
            self.i -= 1
            left = Expr("condition", (self.reference(True),))
        elif self.candidates(t.key):
            self.i -= 1
            left = Expr("var", (self.variable(),))
        else:
            self.error(f"expression non prise en charge: {t.text}")
        while not self.t.string and self.t.key in {"+", "-", "*", "/"}:
            op = self.t.key
            precedence = 20 if op in {"*", "/"} else 10
            if precedence < minimum:
                break
            self.take()
            left = Expr(op, (left, self.expr(precedence + 1)))
        return left

    def condition(self):
        return self.disjunction()

    def disjunction(self):
        left = self.conjunction()
        while self.accept("OR"):
            left = Expr("or", (left, self.conjunction()))
        return left

    def conjunction(self):
        left = self.comparison()
        while self.accept("AND"):
            left = Expr("and", (left, self.comparison()))
        return left

    def comparison(self):
        if self.accept("NOT"):
            return Expr("not", (self.comparison(),))
        # Parenthesized arithmetic is handled by expr; boolean grouping is explicit.
        if self.at("("):
            saved = self.i
            try:
                self.take()
                result = self.condition()
                self.expect(")")
                return result
            except CobolError:
                self.i = saved
        left = self.expr()
        if left.op in {"condition", "bool"}:
            return left
        self.accept("IS")
        negate = self.accept("NOT")
        if self.accept("NUMERIC"):
            result = Expr("numeric_class", (left,))
            return Expr("not", (result,)) if negate else result
        if self.t.key in {"=", "<>", "<", ">", "<=", ">="}:
            op = self.take().key
        elif self.accept("EQUAL"):
            self.accept("TO")
            op = "="
        elif self.accept("GREATER"):
            self.accept("THAN")
            op = ">=" if self.accept("OR") and self.accept("EQUAL") else ">"
            self.accept("TO")
        elif self.accept("LESS"):
            self.accept("THAN")
            op = "<=" if self.accept("OR") and self.accept("EQUAL") else "<"
            self.accept("TO")
        else:
            self.error("comparaison explicite attendue (conditions abrégées non prises en charge)")
        result = Expr("cmp" + op, (left, self.expr()))
        return Expr("not", (result,)) if negate else result

    def block(self, stops):
        result = []
        while self.t.string or self.t.key not in stops | {".", "<EOF>"}:
            result.append(self.statement())
        return result

    def statement(self):
        line = self.t.line
        verb = self.take().key
        if verb == "SET":
            if self.candidates(self.t.key) and not self.candidates(self.t.key, True):
                refs = [self.variable()]
                while not self.at("TO") and not self.at("UP") and not self.at("DOWN"):
                    refs.append(self.variable())
                if all(not self.fields[ref.name].index_for for ref in refs) and self.accept("TO"):
                    # SET integer-items TO index-name stores the occurrence number.
                    source = self.variable()
                    if not self.fields[source.name].index_for:
                        self.error("SET donnée TO requiert un index INDEXED BY")
                    for ref in refs:
                        field = self.fields[ref.name]
                        if ref.start is not None or field.kind != "number" or field.scale or field.usage == "INDEX":
                            self.error("SET donnée TO index requiert un entier numérique")
                    return Stmt("compute", (None, [(ref, Expr("var", (source,)), False) for ref in refs]), line)
                if any(not self.fields[ref.name].index_for for ref in refs):
                    self.error("SET numérique requiert des index INDEXED BY")
                if self.accept("TO"):
                    mode = "to"
                elif self.accept("UP"):
                    mode = "up"; self.expect("BY")
                else:
                    self.expect("DOWN"); self.expect("BY"); mode = "down"
                return Stmt("set_index", (refs, mode, self.expr()), line)
            refs = [self.reference(True)]
            while not self.at("TO"):
                refs.append(self.reference(True))
            self.expect("TO")
            if self.accept("TRUE"):
                truth = True
            else:
                self.expect("FALSE")
                truth = False
            return Stmt("set_condition", (refs, truth), line)
        if verb == "OPEN":
            actions, mode = [], None
            modes = {"INPUT", "OUTPUT", "EXTEND", "I-O"}
            while self.t.key in modes | self.files.keys():
                if self.t.key in modes:
                    mode = self.take().key
                elif not mode:
                    self.error("mode INPUT, OUTPUT, I-O ou EXTEND attendu avant le fichier")
                name = self.file_name()
                if mode == "I-O" and self.files[name].organization == "LINE SEQUENTIAL":
                    self.error("OPEN I-O limité aux fichiers SEQUENTIAL; réécriture LINE SEQUENTIAL non modélisée")
                actions.append((mode, name))
            if not actions:
                self.error("OPEN requiert INPUT, OUTPUT, I-O ou EXTEND et un fichier déclaré")
            return Stmt("open", (actions,), line)
        if verb == "CLOSE":
            names = []
            while not names or (self.t.key in self.files and not self.t.string):
                name = self.file_name()
                lock = False
                if self.accept("WITH") or self.at("LOCK") or self.at("NO"):
                    if not self.accept("LOCK"):
                        self.error("CLOSE limité à WITH LOCK; NO REWIND, REEL et UNIT non pris en charge")
                    lock = True
                elif self.at("REEL") or self.at("UNIT"):
                    self.error("CLOSE limité à WITH LOCK; NO REWIND, REEL et UNIT non pris en charge")
                names.append((name, lock))
            return Stmt("close", (names,), line)
        if verb == "READ":
            name = self.file_name()
            # GnuCOBOL: READ file [NEXT] [RECORD] [INTO x] [[AT] END] [NOT [AT] END].
            spec = self.files[name]
            next_record = self.accept("NEXT")
            if self.at("PREVIOUS"):
                self.error("READ PREVIOUS non pris en charge")
            self.accept("RECORD")
            into = self.variable() if self.accept("INTO") else None
            if into and self.fields[into.name].kind != "text" and into.start is None:
                self.error("READ INTO requiert un champ alphanumérique")
            if self.at("KEY") or self.at("WITH"):
                self.error("READ KEY/LOCK non pris en charge")
            handler, exception, success = None, [], []
            if self.accept("AT") or self.at("END"):
                self.expect("END")
                handler, exception = "end", self.block({"NOT", "END-READ"})
            elif self.at("INVALID"):
                handler, exception = "key", self.invalid_key({"NOT", "END-READ"})
            if self.at("NOT") and self.tokens[self.i + 1].key == "INVALID":
                self.take()
                if handler == "end":
                    self.error("AT END et INVALID KEY ne peuvent pas être mêlés")
                handler, success = "key", self.invalid_key({"END-READ"})
            elif self.accept("NOT"):
                self.accept("AT")
                self.expect("END")
                if handler == "key":
                    self.error("AT END et INVALID KEY ne peuvent pas être mêlés")
                handler, success = "end", self.block({"END-READ"})
            self.accept("END-READ")
            # cobc: NEXT, SEQUENTIAL access, or DYNAMIC with AT END read the next
            # record; otherwise a RELATIVE KEY selects the record.
            random = (spec.organization == "RELATIVE" and not next_record and spec.access != "SEQUENTIAL"
                      and not (spec.access == "DYNAMIC" and handler == "end"))
            if handler == ("end" if random else "key"):
                self.error("READ " + ("direct requiert INVALID KEY, pas AT END" if random else "séquentiel requiert AT END, pas INVALID KEY"))
            return Stmt("read", (name, into, exception, success, random), line)
        if verb == "REWRITE":
            record = self.variable()
            files = [f.name for f in self.files.values() if record.name in f.records and not record.indices and record.start is None]
            if not files:
                self.error(f"REWRITE requiert un enregistrement FD: {record}")
            if self.files[files[0]].organization == "LINE SEQUENTIAL":
                self.error("REWRITE limité aux fichiers SEQUENTIAL/RELATIVE; réécriture LINE SEQUENTIAL non modélisée")
            value = self.expr() if self.accept("FROM") else None
            invalid, valid = self.key_handlers(files[0], "END-REWRITE")
            return Stmt("rewrite", (files[0], record.name, value, invalid, valid), line)
        if verb == "DELETE":
            name = self.file_name()
            if self.files[name].organization != "RELATIVE":
                self.error("DELETE limité aux fichiers RELATIVE")
            self.accept("RECORD")
            invalid, valid = self.key_handlers(name, "END-DELETE")
            return Stmt("delete", (name, None, None, invalid, valid), line)
        if verb == "START":
            name = self.file_name()
            spec = self.files[name]
            if spec.organization != "RELATIVE" or spec.access == "RANDOM":
                self.error("START limité aux fichiers RELATIVE en accès SEQUENTIAL ou DYNAMIC")
            condition = "Equal"
            if self.accept("KEY"):
                self.accept("IS")
                if self.accept("=") or (self.accept("EQUAL") and (self.accept("TO") or True)):
                    condition = "Equal"
                elif self.accept(">") or (self.accept("GREATER") and (self.accept("THAN") or True)):
                    condition = "Greater"
                    if self.at("OR") or self.at("="):
                        self.error("START >= non pris en charge; utiliser NOT LESS")
                elif self.accept("NOT"):
                    if not (self.accept("<") or (self.accept("LESS") and (self.accept("THAN") or True))):
                        self.error("START KEY NOT < attendu")
                    condition = "NotLess"
                else:
                    self.error("START KEY limité à =, > ou NOT <")
                key = self.variable()
                if key.name != spec.relative_key or key.indices or key.start is not None:
                    self.error("START KEY doit désigner la RELATIVE KEY du fichier")
            elif not spec.relative_key:
                self.error("START requiert une RELATIVE KEY")
            invalid, valid = self.key_handlers(name, "END-START")
            return Stmt("start", (name, None, condition, invalid, valid), line)
        if verb == "WRITE":
            record = self.variable()
            files = [f.name for f in self.files.values() if record.name in f.records and not record.indices and record.start is None]
            if not files:
                self.error(f"WRITE requiert un enregistrement FD: {record}")
            value = self.expr() if self.accept("FROM") else None
            advancing = None
            if self.at("BEFORE") or self.at("AFTER"):
                direction = self.take().key
                self.expect("ADVANCING")
                if self.accept("PAGE"):
                    count = None
                else:
                    if self.t.string or not self.t.text.isdigit() or not 0 <= int(self.t.text) <= 65535:
                        self.error("ADVANCING requiert PAGE ou un entier littéral de 0 à 65535")
                    count = int(self.take().text)
                    self.accept("LINE") or self.accept("LINES")
                if self.files[files[0]].organization != "SEQUENTIAL":
                    self.error("WRITE ADVANCING limité à SEQUENTIAL dans le profil actuel")
                advancing = (direction, count)
            invalid, valid = self.key_handlers(files[0], "END-WRITE")
            return Stmt("write", (files[0], record.name, value, advancing, invalid, valid), line)
        if verb == "DISPLAY":
            values = []
            while self.t.string or self.t.key not in BOUNDARIES | {"WITH", "UPON"}:
                values.append(self.expr())
            if not values:
                self.error("DISPLAY sans opérande")
            newline = True
            if self.accept("WITH"):
                self.expect("NO")
                self.expect("ADVANCING")
                newline = False
            self.accept("END-DISPLAY")
            return Stmt("display", (values, newline), line)
        if verb == "ACCEPT":
            name = self.variable()
            if self.fields[name.name].kind == "edited" and name.start is None:
                self.error("ACCEPT vers une PICTURE éditée non pris en charge")
            self.accept("END-ACCEPT")
            return Stmt("accept", (name,), line)
        if verb == "MOVE":
            value = self.expr()
            self.expect("TO")
            targets = self.targets()
            return Stmt("move", (value, targets, False), line)
        if verb == "COMPUTE":
            receivers = self.rounded_receivers()
            if not (self.accept("=") or self.accept("EQUAL")):
                self.error("= attendu")
            # The expression is evaluated once, before any receiver is stored.
            items = [(ref, Expr("shared", ()), rounded) for ref, rounded in receivers]
            return self.arithmetic(verb, self.expr(), items, line)
        if verb in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}:
            values = [self.expr()]
            separator = {"ADD": "TO", "SUBTRACT": "FROM", "MULTIPLY": "BY", "DIVIDE": "INTO"}[verb]
            while verb in {"ADD", "SUBTRACT"} and not self.at(separator):
                values.append(self.expr())
            self.expect(separator)
            op = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}[verb]
            operand = values[0]
            for extra in values[1:]:
                operand = Expr("+", (operand, extra))
            if self.t.string or not self.candidates(self.t.key):
                # Only a GIVING form can take a literal second operand.
                second = self.expr()
                self.expect("GIVING")
                giving = True
            else:
                receivers = self.rounded_receivers()
                giving = self.accept("GIVING")
                if giving:
                    if len(receivers) != 1 or receivers[0][1]:
                        self.error(f"{verb} ... GIVING requiert un seul opérande sans ROUNDED avant GIVING")
                    second = Expr("var", (receivers[0][0],))
            if giving:
                shared = Expr(op, (second, operand))
                items = [(ref, Expr("shared", ()), rounded) for ref, rounded in self.rounded_receivers()]
                return self.arithmetic(verb, shared, items, line)
            # GnuCOBOL re-reads a single operand for each receiver, after the
            # previous ones were stored; several operands are summed once.
            shared = operand if len(values) > 1 else None
            term = Expr("shared", ()) if shared else operand
            items = [(ref, Expr(op, (Expr("var", (ref,)), term)), rounded) for ref, rounded in receivers]
            return self.arithmetic(verb, shared, items, line)
        if verb == "IF":
            cond = self.condition()
            self.accept("THEN")
            yes = self.block({"ELSE", "END-IF"})
            no = self.block({"END-IF"}) if self.accept("ELSE") else []
            if not self.accept("END-IF") and not self.at("."):
                self.error("END-IF ou point attendu")
            return Stmt("if", (cond, yes, no), line)
        if verb == "GO":
            self.accept("TO")
            targets = []
            while not self.at("DEPENDING") and (self.t.string or self.t.key not in BOUNDARIES):
                targets.append(self.name())
                if self.at("OF") or self.at("IN"):
                    self.error("nom de procédure qualifié non pris en charge")
            if not targets:
                self.error("GO TO requiert une cible; GO TO modifié par ALTER non pris en charge")
            controller = None
            if self.accept("DEPENDING"):
                self.accept("ON")
                controller = self.variable()
                field = self.fields[controller.name]
                if controller.start is not None or field.kind != "number" or field.scale != 0:
                    self.error("GO TO DEPENDING ON requiert une donnée numérique entière non éditée")
                if field.digits > 9:
                    self.error("GO TO DEPENDING ON limité aux contrôleurs de 9 chiffres au plus; conversions natives larges non modélisées")
            elif len(targets) != 1:
                self.error("GO TO à plusieurs cibles requiert DEPENDING ON")
            return Stmt("goto", (targets, controller), line)
        if verb == "PERFORM":
            target = None
            if self.t.key not in {"UNTIL", "VARYING", "WITH"} and not self.candidates(self.t.key) and re.fullmatch(r"[A-Z_][A-Z_0-9-]*", self.t.key):
                target = [self.name()]
                if self.at("OF") or self.at("IN"):
                    self.error("nom de procédure qualifié non pris en charge")
                if self.accept("THRU") or self.accept("THROUGH"):
                    target.append(self.name())
                    if self.at("OF") or self.at("IN"):
                        self.error("nom de procédure qualifié non pris en charge")
            test_after = False
            if self.accept("WITH"):
                self.expect("TEST")
                if self.accept("AFTER"):
                    test_after = True
                else:
                    self.expect("BEFORE")
            mode, control = "once", ()
            if self.accept("UNTIL"):
                mode, control = "until", (self.condition(), test_after)
            elif self.accept("VARYING"):
                # VARYING ... [AFTER ...]: one level per identifier, BY 1 by default.
                levels = []
                while True:
                    var = self.variable()
                    self.expect("FROM")
                    start = self.expr()
                    step = self.expr() if self.accept("BY") else Expr("number", ("1",))
                    self.expect("UNTIL")
                    levels.append((var, start, step, self.condition()))
                    if not self.accept("AFTER"):
                        break
                mode, control = "varying", (levels, test_after)
            elif self.t.key not in BOUNDARIES:
                count = self.expr()
                self.expect("TIMES")
                mode, control = "times", (count,)
            elif test_after:
                self.error("WITH TEST requiert UNTIL ou VARYING")
            if target:
                body = [Stmt("call", (target,), line)]
            else:
                if mode == "once":
                    self.error("PERFORM inline requiert TIMES, UNTIL ou VARYING")
                body = self.block({"END-PERFORM"})
                self.expect("END-PERFORM")
            return Stmt("loop", (mode, control, body), line)
        if verb == "EVALUATE":
            subject = self.expr()
            branches = []
            otherwise = []
            while self.accept("WHEN"):
                if self.accept("OTHER"):
                    otherwise = self.block({"END-EVALUATE"})
                    break
                case = self.condition() if subject.op in {"bool", "condition"} else self.expr()
                body = self.block({"WHEN", "END-EVALUATE"})
                branches.append((case, body))
            if not branches:
                self.error("EVALUATE requiert au moins un WHEN")
            self.expect("END-EVALUATE")
            return Stmt("evaluate", (subject, branches, otherwise), line)
        if verb == "INITIALIZE":
            targets = self.targets()
            with_filler = False
            if self.accept("WITH"):
                self.expect("FILLER")
                with_filler = True
            return Stmt("initialize", (targets, with_filler), line)
        if verb == "STOP":
            self.expect("RUN")
            return Stmt("stop", (), line)
        if verb == "GOBACK":
            return Stmt("goback", (), line)
        if verb == "CALL":
            if self.t.string:
                target = ("literal", self.take().text)
            else:
                ref = self.variable()
                if self.fields[ref.name].kind != "text" and ref.start is None:
                    self.error("CALL identifiant requiert un champ alphanumérique")
                target = ("dynamic", ref)
            arguments, mode = [], "REFERENCE"
            if self.accept("USING"):
                while True:
                    if self.accept("BY"):
                        if not (self.at("REFERENCE") or self.at("CONTENT")):
                            self.error("CALL USING limité à BY REFERENCE et BY CONTENT")
                    if self.accept("REFERENCE"):
                        mode = "REFERENCE"
                    elif self.accept("CONTENT"):
                        mode = "CONTENT"
                    if self.at("OMITTED") or self.at("VALUE") or self.t.string or (not self.t.string and self.t.text[:1].isdigit()):
                        self.error("CALL USING limité aux identifiants BY REFERENCE/CONTENT")
                    if self.t.string or not self.candidates(self.t.key):
                        break
                    arguments.append((mode, self.variable()))
                if not arguments:
                    self.error("CALL USING requiert au moins un argument")
            if self.at("RETURNING") or self.at("GIVING"):
                self.error("CALL RETURNING/GIVING non pris en charge")
            exception, success = [], []
            if self.accept("ON") or self.at("EXCEPTION") or self.at("OVERFLOW"):
                if not (self.accept("EXCEPTION") or self.accept("OVERFLOW")):
                    self.error("ON EXCEPTION ou ON OVERFLOW attendu")
                exception = self.block({"NOT", "END-CALL"})
            if self.at("NOT") and self.tokens[self.i + 1].key in {"ON", "EXCEPTION", "OVERFLOW"}:
                # GnuCOBOL gives NOT ON EXCEPTION to the innermost open statement
                # that takes one: a DISPLAY/ACCEPT/CALL ending ON EXCEPTION keeps it.
                last = exception[-1] if exception and not self.tokens[self.i - 1].key.startswith("END-") else None
                while last is not None and last.op in {"if", "evaluate"}:
                    bodies = [last.args[1], last.args[2]] if last.op == "if" else [*(b for _, b in last.args[1]), last.args[2]]
                    body = next((b for b in reversed(bodies) if b), None)
                    last = body[-1] if body else None
                if last is not None and last.op in {"display", "accept", "call_program"}:
                    self.error("NOT ON EXCEPTION rattaché par GnuCOBOL au DISPLAY/ACCEPT/CALL de ON EXCEPTION; non pris en charge")
                self.take()
                self.accept("ON")
                if not (self.accept("EXCEPTION") or self.accept("OVERFLOW")):
                    self.error("NOT ON EXCEPTION attendu")
                success = self.block({"END-CALL"})
            self.accept("END-CALL")
            return Stmt("call_program", (target, arguments, exception, success), line)
        if verb == "CANCEL":
            targets = []
            while self.t.string or (self.t.key not in BOUNDARIES and self.candidates(self.t.key)):
                targets.append(("literal", self.take().text) if self.t.string else ("dynamic", self.variable()))
            if not targets:
                self.error("CANCEL requiert un programme")
            return Stmt("cancel", (targets,), line)
        if verb == "CONTINUE":
            return Stmt("continue", (), line)
        if verb == "EXIT":
            if self.accept("PARAGRAPH"):
                return Stmt("exit_paragraph", (), line)
            if self.accept("SECTION"):
                return Stmt("exit_section", (), line)
            if self.accept("PROGRAM"):
                return Stmt("exit_program", (), line)
            if self.at("PERFORM") or self.at("CYCLE"):
                self.error(f"EXIT {self.t.key} non pris en charge")
            if not self.t.string and self.t.key in BOUNDARIES:
                return Stmt("continue", (), line)
            self.error("EXIT nu, EXIT PARAGRAPH ou EXIT SECTION attendu")
        self.error(f"instruction non prise en charge: {verb}")

    def invalid_key(self, stops):
        self.expect("INVALID")
        self.accept("KEY")
        body = self.block(stops)
        if not body:
            self.error("instruction attendue après INVALID KEY")
        return body

    def key_handlers(self, file_name, ending):
        """[INVALID KEY ...] [NOT INVALID KEY ...] [END-x], RELATIVE files only."""
        invalid, valid = [], []
        if self.at("INVALID"):
            invalid = self.invalid_key({"NOT", ending})
        if self.at("NOT") and self.tokens[self.i + 1].key == "INVALID":
            self.take()
            valid = self.invalid_key({ending})
        if (invalid or valid) and self.files[file_name].organization != "RELATIVE":
            self.error("INVALID KEY limité aux fichiers RELATIVE")
        self.accept(ending)
        return invalid, valid

    def rounded_receivers(self):
        receivers = [(self.variable(), self.accept("ROUNDED"))]
        while not self.t.string and self.candidates(self.t.key):
            receivers.append((self.variable(), self.accept("ROUNDED")))
        return receivers

    def arithmetic(self, verb, shared, items, line):
        ending = "END-" + verb
        error, success, handled = [], [], False
        stops = {ending, "ELSE", "END-IF", "END-PERFORM", "WHEN", "END-EVALUATE"}
        if self.accept("ON"):
            handled = True
            self.expect("SIZE"); self.expect("ERROR")
            error = self.block(stops | {"NOT"})
            if not error:
                self.error("instruction attendue après ON SIZE ERROR")
        if self.accept("NOT"):
            handled = True
            self.expect("ON"); self.expect("SIZE"); self.expect("ERROR")
            success = self.block(stops)
            if not success:
                self.error("instruction attendue après NOT ON SIZE ERROR")
        self.accept(ending)
        if handled:
            return Stmt("arithmetic", (shared, items, error, success), line)
        return Stmt("compute", (shared, items), line)

    def targets(self):
        names = [self.variable()]
        while not self.t.string and self.candidates(self.t.key):
            names.append(self.variable())
        return names

    def validate_calls(self, program):
        def walk(stmts, section=None):
            for s in stmts:
                if s.op in {"call", "goto"}:
                    targets = s.args[0]
                    try:
                        ranges = [program.procedure_range(name) for name in targets]
                    except CobolError as error:
                        raise CobolError(f"ligne {s.line}: {error}") from None
                    if s.op == "call" and len(ranges) == 2 and ranges[-1][1] <= ranges[0][0]:
                        raise CobolError(f"ligne {s.line}: intervalle THRU inversé")
                elif s.op == "exit_section" and section is None:
                    raise CobolError(f"ligne {s.line}: EXIT SECTION requiert une section de procédure")
                elif s.op == "loop":
                    walk(s.args[2], section)
                elif s.op == "if":
                    walk(s.args[1], section); walk(s.args[2], section)
                elif s.op == "evaluate":
                    for _, body in s.args[1]:
                        walk(body, section)
                    walk(s.args[2], section)
                elif s.op == "read":
                    walk(s.args[2], section); walk(s.args[3], section)
                elif s.op == "arithmetic":
                    walk(s.args[2], section); walk(s.args[3], section)
                elif s.op in {"write", "rewrite", "delete", "start", "call_program"}:
                    walk(s.args[-2], section); walk(s.args[-1], section)
        if program.blocks:
            for block in program.blocks:
                walk(block.body, block.section)
        else:
            walk(program.entry)
            for body in program.paragraphs.values():
                walk(body)
