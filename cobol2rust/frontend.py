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
    return "\n".join(result)


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
            match = re.match(r"\d+(?:\.\d+)?|[A-Za-z_][A-Za-z_0-9-]*|>=|<=|<>|[.(),:+*/=<>-]", source[i:])
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
    offset: int = 0
    size: int = 0
    dimensions: list[tuple[int, int]] = field(default_factory=list)
    occurs_min: int = 1
    depending: str | None = None
    index_for: str | None = None
    editing: str = ""


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


VERBS = set("DISPLAY ACCEPT MOVE ADD SUBTRACT MULTIPLY DIVIDE COMPUTE IF PERFORM STOP GOBACK CONTINUE EVALUATE INITIALIZE EXIT OPEN READ WRITE CLOSE SET GO".split())
BOUNDARIES = VERBS | set("ELSE END-IF END-PERFORM END-EVALUATE WHEN END-DISPLAY END-ACCEPT END-ADD END-SUBTRACT END-MULTIPLY END-DIVIDE END-COMPUTE END-READ END-WRITE AT NOT ON . <EOF>".split())


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
        if self.t.string or not re.fullmatch(r"[A-Z_][A-Z_0-9-]*", self.t.key):
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
                            if spec.organization != "SEQUENTIAL":
                                self.error("plusieurs enregistrements FD limités à SEQUENTIAL de taille fixe égale")
                            descriptor.redefines = spec.record
                        else:
                            spec.record = key
                        spec.records.append(key)
            if self.accept("WORKING-STORAGE"):
                self.expect("SECTION")
                self.expect(".")
                self.data_stack = []
                while not self.at("PROCEDURE"):
                    self.declaration()
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
        self.expect(".")
        entry, paragraphs = [], {}
        blocks = [ProcedureBlock(None, None, entry)]
        sections = {}
        current_body, current_section = entry, None
        while not self.at("<EOF>"):
            if self.accept("."):
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
            elif self.t.key not in VERBS and self.tokens[self.i + 1].key == ".":
                paragraph = self.name()
                if paragraph in paragraphs or paragraph in sections:
                    self.error(f"nom de procédure dupliqué: {paragraph}; les homonymes ne sont pas pris en charge")
                self.expect(".")
                current_body = []
                paragraphs[paragraph] = current_body
                blocks.append(ProcedureBlock(paragraph, current_section, current_body))
            else:
                current_body.append(self.statement())
        if current_section is not None:
            sections[current_section] = (sections[current_section][0], len(blocks))
        program = Program(name, self.fields, entry, paragraphs, self.files, self.conditions, memory_size,
                          blocks, sections)
        self.validate_calls(program)
        return program

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
        if not (self.at("DATA") or self.at("PROCEDURE")):
            self.error("clause ENVIRONMENT DIVISION non prise en charge")

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
        organization, organization_seen, status, access = "SEQUENTIAL", False, None, False
        while not self.at("."):
            if self.accept("ORGANIZATION") and not organization_seen:
                organization_seen = True
                self.accept("IS")
                organization = "LINE SEQUENTIAL" if self.accept("LINE") else "SEQUENTIAL"
                self.expect("SEQUENTIAL")
            elif self.accept("ACCESS") and not access:
                access = True
                self.accept("MODE")
                self.accept("IS")
                self.expect("SEQUENTIAL")
            elif self.accept("FILE") and status is None:
                self.expect("STATUS")
                self.accept("IS")
                status = self.name()
            else:
                self.error("clause SELECT non prise en charge")
        self.expect(".")
        self.files[name] = FileSpec(name, path, optional, status, organization=organization)

    def validate_files(self):
        paths = set()
        for spec in self.files.values():
            if spec.path.text in paths:
                self.error("plusieurs SELECT vers le même chemin ne sont pas pris en charge")
            paths.add(spec.path.text)
            if not spec.record:
                self.error(f"FD manquant pour {spec.name}")
            if spec.name in self.fields:
                self.error(f"nom ambigu entre fichier et donnée: {spec.name}")
            if spec.status:
                spec.status = self.resolve(spec.status)
                status = self.fields.get(spec.status)
                if not status or status.kind not in {"text", "number"} or status.digits != 2 or status.scale or status.signed or status.usage != "DISPLAY" or status.dimensions:
                    self.error(f"FILE STATUS {spec.status} doit être PIC XX ou PIC 99 DISPLAY")
                if status.file_record:
                    self.error("FILE STATUS ne peut pas être une donnée FD")
            from .layout import leaves
            if any(self.fields[key].size != self.fields[spec.record].size for key in spec.records):
                self.error("enregistrements FD de tailles différentes non pris en charge; format variable requis")
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
        elif re.fullmatch(r"\d+(?:\.\d+)?", t.text):
            left = Expr("number", (t.text,))
        elif t.key in {"ZERO", "ZEROS", "ZEROES"}:
            left = Expr("number", ("0",), figurative_zero=True)
        elif t.key in {"SPACE", "SPACES"}:
            left = Expr("text", (" ",), figurative_space=True)
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
            while self.t.key in {"INPUT", "OUTPUT", "EXTEND"} | self.files.keys():
                if self.t.key in {"INPUT", "OUTPUT", "EXTEND"}:
                    mode = self.take().key
                    actions.append((mode, self.file_name()))
                elif mode:
                    actions.append((mode, self.file_name()))
                else:
                    self.error("mode INPUT, OUTPUT ou EXTEND attendu avant le fichier")
            if not actions:
                self.error("OPEN requiert INPUT, OUTPUT ou EXTEND et un fichier déclaré")
            return Stmt("open", (actions,), line)
        if verb == "CLOSE":
            names = [self.file_name()]
            while self.t.key in self.files and not self.t.string:
                names.append(self.file_name())
            return Stmt("close", (names,), line)
        if verb == "READ":
            name = self.file_name()
            if self.accept("NEXT"):
                self.accept("RECORD")
            into = self.variable() if self.accept("INTO") else None
            if into and self.fields[into.name].kind != "text" and into.start is None:
                self.error("READ INTO requiert un champ alphanumérique")
            at_end, not_end = [], []
            if self.accept("AT"):
                self.expect("END")
                at_end = self.block({"NOT", "END-READ"})
            if self.accept("NOT"):
                self.expect("AT")
                self.expect("END")
                not_end = self.block({"END-READ"})
            self.accept("END-READ")
            return Stmt("read", (name, into, at_end, not_end), line)
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
            self.accept("END-WRITE")
            return Stmt("write", (files[0], record.name, value, advancing), line)
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
            name = self.variable()
            rounded = self.accept("ROUNDED")
            self.expect("=")
            value = self.expr()
            return self.arithmetic(verb, value, [name], rounded, line)
        if verb in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}:
            values = [self.expr()]
            separator = {"ADD": "TO", "SUBTRACT": "FROM", "MULTIPLY": "BY", "DIVIDE": "INTO"}[verb]
            while verb in {"ADD", "SUBTRACT"} and not self.at(separator):
                values.append(self.expr())
            self.expect(separator)
            receiver = self.variable()
            op = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}[verb]
            value = values[0]
            for extra in values[1:]:
                value = Expr("+", (value, extra))
            value = Expr(op, (Expr("var", (receiver,)), value))
            targets = [receiver]
            if self.accept("GIVING"):
                targets = [self.variable()]
            rounded = self.accept("ROUNDED")
            return self.arithmetic(verb, value, targets, rounded, line)
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
                var = self.variable()
                self.expect("FROM")
                start = self.expr()
                self.expect("BY")
                step = self.expr()
                self.expect("UNTIL")
                mode, control = "varying", (var, start, step, self.condition(), test_after)
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
            return Stmt("stop", (), line)
        if verb == "CONTINUE":
            return Stmt("continue", (), line)
        if verb == "EXIT":
            if self.accept("PARAGRAPH"):
                return Stmt("exit_paragraph", (), line)
            if self.accept("SECTION"):
                return Stmt("exit_section", (), line)
            if self.at("PERFORM") or self.at("CYCLE"):
                self.error(f"EXIT {self.t.key} non pris en charge")
            if not self.t.string and self.t.key in BOUNDARIES:
                return Stmt("continue", (), line)
            self.error("EXIT nu, EXIT PARAGRAPH ou EXIT SECTION attendu")
        self.error(f"instruction non prise en charge: {verb}")

    def arithmetic(self, verb, value, targets, rounded, line):
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
        return Stmt("arithmetic", (value, targets, rounded, error, success), line) if handled else Stmt("assign", (value, targets, rounded), line)

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
                    walk(s.args[3], section); walk(s.args[4], section)
        if program.blocks:
            for block in program.blocks:
                walk(block.body, block.section)
        else:
            walk(program.entry)
            for body in program.paragraphs.values():
                walk(body)
