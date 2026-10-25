from __future__ import annotations

import os
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


# cobc -fdebugging-line: fixed-format 'D' lines are compiled as source lines.
DEBUGGING_LINES = False
# cobc -std: the dialect whose options this frontend models. "default"
# ignores SECTION segment numbers (section-segments: ignore) and initializes
# items without VALUE (defaultbyte: init); "cobol85" keeps segment numbers
# and leaves such items as allocated (defaultbyte: none).
STD = "default"
# cobc -fno-ec=data-incompatible: MOVE from DISPLAY data without cob_check_numeric.
NO_EC_DATA_INCOMPATIBLE = False
# cobc -debug: runtime checks (EC-ALL); without them, libcob computes with
# invalid numeric data (COB_D2I) instead of stopping.
RUNTIME_CHECKS = False
STANDARDS = ("default", "cobol85")


def normalize(source: str, fmt: str = "auto") -> str:
    from .documentary import DocumentaryFilter

    lines = source.splitlines()
    fmt = source_format(source, fmt)
    documentary = DocumentaryFilter()
    result = []
    previous = None
    quotation = None
    consecutive = False
    # pplex.l: "[WITH] DEBUGGING MODE" activates the debugging lines read
    # after it, as -fdebugging-line does for the whole source.
    debugging_lines = DEBUGGING_LINES
    recent = []
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
            # The sequence area (columns 1-6) is ignored whatever it holds;
            # a line ending inside it is blank.
            if len(line) < 7:
                result.append("")
                continue
            indicator = line[6]
            if indicator in "*/":
                result.append("")
                continue
            if indicator in "Dd" and not debugging_lines:
                # Without DEBUGGING MODE, GnuCOBOL drops debugging lines.
                result.append("")
                continue
            if indicator in "Dd":
                indicator = " "
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
            if indicator != "-" and COMPILER_OPTIONS.match(line):
                result.append("")
                continue
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
                # Literals cannot hold the pplex pattern; it may span lines.
                recent = (recent + [re.sub(r"\"[^\"]*\"?|'[^']*'?", " ", fragment)])[-3:]
                if not debugging_lines and re.search(r"(?<![\w-])DEBUGGING[\s,;]+MODE(?![\w-])", "\n".join(recent), re.I):
                    debugging_lines = True
            continue
        result.append("" if COMPILER_OPTIONS.match(line) or documentary.is_comment(line, fmt, line=number) else line)
    return "\n".join(result)


def lex(source: str, decimal_comma: bool = False) -> list[Token]:
    """With DECIMAL-POINT IS COMMA a numeric literal is written 1,5; its
    token text keeps the internal form 1.5."""
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
            # One character per source byte (decode_source): a non-ASCII
            # literal holds the bytes of its source text, as for cobc.
            tokens.append(Token(value, start, True, token_start, i))
        elif c in "xX" and i + 1 < len(source) and source[i + 1] in "\"'":
            # X"hex": two hexadecimal digits per byte (scanner.l).
            quote, start = source[i + 1], line
            end = source.find(quote, i + 2)
            newline = source.find("\n", i + 2)
            if end < 0 or (0 <= newline < end):
                raise CobolError(f"ligne {start}: littéral hexadécimal non terminé")
            digits = source[i + 2:end]
            if not digits or len(digits) % 2 or not all(d in "0123456789abcdefABCDEF" for d in digits):
                raise CobolError(f"ligne {start}: littéral hexadécimal invalide: {digits!r}")
            value = bytes.fromhex(digits).decode("latin-1")
            i = end + 1
            tokens.append(Token(value, start, True, token_start, i))
        else:
            # A COBOL word may start with digits when it holds a letter (3-DIMENSION-TBL);
            # a numeric literal may start with its decimal point after a separator.
            point = (not decimal_comma and c == "." and i + 1 < len(source) and source[i + 1].isdigit()
                     and (i == 0 or source[i - 1].isspace() or source[i - 1] in "(+-*/=<>,"))
            dp = "," if decimal_comma else r"\."
            # cobc scans a sign followed by digits as a signed literal, so in
            # a list "(I +1)" holds two subscripts. After an operand that
            # matters only inside parentheses; elsewhere cobc rejects it.
            signed = (c in "+-" and parentheses and tokens and i + 1 < len(source)
                      and (source[i + 1].isdigit() or source[i + 1] == "." and source[i + 2:i + 3].isdigit())
                      and (tokens[-1].string or tokens[-1].text == ")"
                           or re.fullmatch(r"[+-]?[A-Za-z0-9_.][A-Za-z0-9_.-]*", tokens[-1].text)))
            match = re.match(rf"[+-](?:\d+(?:{dp}\d+)?|\.\d+)" if signed else r"\.\d+" if point else
                             rf"\d+[A-Za-z0-9-]*[A-Za-z][A-Za-z_0-9-]*|\d+(?:{dp}\d+)?|[A-Za-z_][A-Za-z_0-9-]*|>=|<=|<>|\*\*|[.(),:+*/=<>-]",
                             source[i:])
            if not match and c == "&":
                tokens.append(Token("&", line, False, i, i + 1))
                i += 1
                continue
            if not match:
                raise CobolError(f"ligne {line}: caractère non pris en charge {c!r}")
            text = match[0]
            if decimal_comma and re.fullmatch(r"[+-]?\d+,\d+", text):
                text = text.replace(",", ".")
            tokens.append(Token(text, line, False, i, i + len(match[0])))
            i += len(match[0])
            if match[0].upper() in {"PIC", "PICTURE"} and not (len(tokens) > 1 and tokens[-2].key == "COPY"):
                picture_pending = True
            elif match[0] == "(":
                parentheses += 1
            elif match[0] == ")" and parentheses:
                parentheses -= 1
    tokens.append(Token("<EOF>", line, False, len(source), len(source)))
    # literal: literal TOK_AMPER basic_literal, concatenated by cobc.
    merged = []
    for token in tokens:
        if (token.string and len(merged) > 1 and merged[-1].text == "&" and not merged[-1].string
                and merged[-2].string):
            merged.pop()
            first = merged.pop()
            token = Token(first.text + token.text, first.line, True, first.start, token.end)
        merged.append(token)
    return merged


def load_source(path: Path, include_dirs: list[Path], fmt="auto", stack=()) -> tuple[str, list[str]]:
    from .copy_replace import apply, parse_replacing, statement_texts
    path = path.resolve()
    if path in stack:
        raise CobolError(f"COPY cyclique: {path}")
    source = decode_source(path.read_bytes())
    # The format detected on the main source also applies to its copybooks.
    fmt = source_format(source, fmt)
    text = normalize(source, fmt)
    # COPY is expanded at token boundaries; strings and comments cannot become directives.
    toks = lex(text)
    copies = []
    pieces, cursor = [], 0
    i = 0
    while i < len(toks) - 1:
        if toks[i].string or toks[i].key != "COPY":
            i += 1
            continue
        start = toks[i].line
        # The statement ends at the first period outside pseudo-text.
        from .copy_replace import statement_end
        stop = statement_end(text, toks[i].end)
        if stop < 0:
            raise CobolError(f"ligne {start}: COPY sans point final")
        words = statement_texts(text[toks[i].start:stop - 1])
        if len(words) < 2:
            raise CobolError(f"ligne {start}: nom de copybook attendu")
        name = words[1]
        if name[:1] in "\"'":
            name = name[1:-1]
        rest = words[2:]
        library = None
        if rest and rest[0].upper() in {"OF", "IN"}:
            if len(rest) < 2:
                raise CobolError(f"ligne {start}: nom de bibliothèque COPY attendu")
            library = rest[1][1:-1] if rest[1][:1] in "\"'" else rest[1]
            if library[:1] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" and os.environ.get(f"COB_COPY_LIB_{library}") is not None:
                raise CobolError(f"ligne {start}: COB_COPY_LIB_{library} non pris en charge")
            rest = rest[2:]
        if rest and rest[0].upper() == "SUPPRESS":
            rest = rest[1:]
        replacements = []
        if rest:
            if rest[0].upper() != "REPLACING":
                raise CobolError(f"ligne {start}: COPY: REPLACING ou point attendu")
            replacements = parse_replacing(rest[1:], start)
        roots = [path.parent, *include_dirs]
        extensions = ("", ".cpy", ".CPY", ".cob", ".cbl")
        candidates = [root / (name + ext) for root in roots for ext in extensions]
        if library is not None:
            # ppcopy: library/name first (as is, then in each copybook
            # directory), else the name alone, with a warning.
            candidates = [root / library / (name + ext) for root in roots for ext in extensions] + candidates
        found = next((p for p in candidates if p.is_file()), None)
        if found is None:
            raise CobolError(f"ligne {start}: copybook introuvable: {name}")
        expanded, children = load_source(found, include_dirs, fmt, (*stack, path))
        if replacements:
            if children:
                # cobc applies the outer REPLACING with the inner list in one pass.
                raise CobolError(f"ligne {start}: COPY REPLACING d'un copybook contenant COPY non pris en charge")
            expanded = apply(expanded, replacements, start)
        copies.extend([str(found.resolve()), *children])
        pieces += [text[cursor:toks[i].start], "\n", expanded, "\n"]
        cursor = stop
        i += 1
        while i < len(toks) and toks[i].start < stop:
            i += 1
    pieces.append(text[cursor:])
    result = "".join(pieces)
    # A REPLACE statement may also come from a copybook.
    if not stack and re.search(r"(?<![\w-])REPLACE(?![\w-])", result, re.IGNORECASE):
        from .copy_replace import replace_statements
        result = replace_statements(result, lex(result))
    return result, list(dict.fromkeys(copies))


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
    # Numeric-edited: cobc's symbol groups and storage size.
    edit_symbols: list = field(default_factory=list)
    edit_size: int = 0
    blank_zero: bool = False
    # Alphanumeric-edited picture, one symbol per position.
    alnum_edit: str = ""
    justified: bool = False
    # SIGN clause of a signed DISPLAY item; a group's clause for its items.
    sign_leading: bool = False
    sign_separate: bool = False
    group_sign: tuple | None = None
    synchronized: bool = False
    # OCCURS ... ASCENDING/DESCENDING KEY: (descending, key) in declaration order.
    search_keys: list = field(default_factory=list)
    group_value: tuple[str, str | None] | None = None  # (literal, ZERO/SPACE fill)
    group_usage: str | None = None
    # 01/77 EXTERNAL (run-unit storage by name) and GLOBAL items.
    external: bool = False
    is_global: bool = False


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
    literal_all: bool = False
    # HIGH-VALUE / LOW-VALUE of the native collating sequence (cb_norm_high,
    # cb_norm_low): a MOVE to any numeric item is a memset.
    memset: bool = False


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
    # SD: a sort/merge file, with no physical file of its own.
    sort: bool = False
    # INDEXED: RECORD KEY, then ALTERNATE RECORD KEYs as (key, WITH DUPLICATES).
    record_key: object = None
    alternate_keys: list = field(default_factory=list)
    # FD LINAGE: part (lines, footing, top, bottom) -> ("literal", n) or ("field", name).
    linage: dict | None = None
    # FD EXTERNAL / GLOBAL; global_owner: the containing program that declared it.
    external: bool = False
    is_global: bool = False
    global_owner: str | None = None
    # ASSIGN data-name: (label, qualifiers) until validate_files, then the
    # field key read at each OPEN; `path` is then None.
    assign_field: object = None
    # The SELECT name as written: libcob's select_name in its messages.
    select_text: str = ""


@dataclass
class ProcedureBlock:
    name: str | None
    section: str | None
    body: list[Stmt]
    # The paragraph name as written; `name` is made unique for homonyms.
    label: str | None = None


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
    # Programs following this one in the same source (END PROGRAM then a new
    # IDENTIFICATION DIVISION); nested programs are refused.
    siblings: list = field(default_factory=list)
    # ALTER: alterable paragraph -> its possible targets (cobc alter_gotos),
    # and SECTION segment numbers (independent segments are 50-99).
    alters: dict[str, list[str]] = field(default_factory=dict)
    segments: dict[str, int] = field(default_factory=dict)

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


VERBS = set("ALTER DISPLAY ACCEPT MOVE ADD SUBTRACT MULTIPLY DIVIDE COMPUTE IF PERFORM STOP GOBACK CONTINUE EVALUATE INITIALIZE EXIT OPEN READ WRITE REWRITE DELETE START CLOSE SET GO CALL CANCEL NEXT SORT MERGE RELEASE RETURN SEARCH INSPECT STRING UNSTRING INITIATE GENERATE TERMINATE ENTRY ENABLE DISABLE RECEIVE SEND PURGE".split())
INSPECT_FIGURATIVES = {"ZERO": "0", "ZEROS": "0", "ZEROES": "0", "SPACE": " ", "SPACES": " ",
                       "QUOTE": '"', "QUOTES": '"', "HIGH-VALUE": "\xff", "HIGH-VALUES": "\xff",
                       "LOW-VALUE": "\x00", "LOW-VALUES": "\x00"}
BOUNDARIES = VERBS | set("ELSE END-IF END-PERFORM END-EVALUATE WHEN END-DISPLAY END-ACCEPT END-ADD END-SUBTRACT END-MULTIPLY END-DIVIDE END-COMPUTE END-READ END-WRITE END-REWRITE END-DELETE END-START END-CALL END-RETURN END-SEARCH END-STRING END-UNSTRING END-RECEIVE EXCEPTION OVERFLOW AT NOT ON INVALID . <EOF>".split())


# pplex.l: an IBM CBL/PROCESS statement of compiler options is ignored to
# the end of its line (with only separators, or a space after the word).
COMPILER_OPTIONS = re.compile(r"[ ]*(?:PROCESS|CBL)(?:[ ,;]*$|[ ])", re.I)


def decode_source(data: bytes) -> str:
    """cobc reads sources as bytes (columns are byte columns) and skips a
    UTF-8 BOM (ppopen_get_file): one latin-1 character per byte."""
    return data[3:].decode("latin-1") if data.startswith(b"\xef\xbb\xbf") else data.decode("latin-1")


def source_format(source: str, fmt="auto"):
    """ppopen_get_file: in reference-format auto, the character in column 7 of
    the first source line within the first 20 bytes decides; a non-indicator
    switches to free format. -std=cobol85 has the cobol85 (fixed) format."""
    if fmt != "auto":
        return fmt
    if STD == "cobol85":
        return "fixed"
    try:
        data = source.encode("latin-1")
    except UnicodeEncodeError:
        data = source.lstrip("\ufeff").encode("utf-8")
    buffer = bytearray(data[:20])
    last, line_pos, pos = " ", 0, 0
    while len(buffer) - pos > 7:
        if buffer[pos] == 10:
            line_pos = 0
        elif buffer[pos] == 9:
            buffer[pos] = 32
            line_pos += 1
            while line_pos % 8:
                line_pos += 1
        elif buffer[pos] != 13:
            line_pos += 1
        if line_pos >= 7:
            last = chr(buffer[pos])
            break
        pos += 1
    return "fixed" if last in " -dD*/\\$" else "free"


class Parser:
    def __init__(self, source: str):
        self.tokens = lex(source)
        # DECIMAL-POINT IS COMMA changes the scanner: read the source again.
        keys = [None if t.string else t.key for t in self.tokens]
        self.decimal_comma = any(keys[k:k + 3] == ["DECIMAL-POINT", "IS", "COMMA"] or keys[k:k + 2] == ["DECIMAL-POINT", "COMMA"]
                                 for k in range(len(keys)))
        if self.decimal_comma:
            self.tokens = lex(source, True)
        self.currency = "$"
        self.i = 0
        self.fields = {}
        self.files = {}
        self.conditions = {}
        self.data_stack = []
        self.last_data = None
        self.filler_count = 0
        self.indexes = {}
        # SPECIAL-NAMES: mnemonic -> device, switch condition -> (number, on),
        # alphabet -> identity?, class -> allowed bytes, symbolic -> byte.
        self.mnemonics = {}
        self.switch_conditions = {}
        self.alphabets = {}
        self.classes = {}
        self.symbolic = {}
        self.same_records = []
        self.renames = []
        # Level 88 of a group with a figurative or ALL value: (condition,
        # value index, text) filled to the group's size after layout.
        self.group_fills = []
        # SOURCE-COMPUTER ... WITH DEBUGGING MODE (current_program->flag_debugging).
        self.debugging_mode = False
        # PROGRAM COLLATING SEQUENCE with a literal alphabet: its weights, and
        # the HIGH-VALUE/LOW-VALUE it implies (cb_validate_collating).
        self.collating = None
        self.high_value, self.low_value = "\xff", "\x00"
        self.in_debugging = False
        # REPORT SECTION: RD name -> ReportSpec, in FD REPORT clause order.
        self.reports = {}
        # COMMUNICATION SECTION: CD name -> its record keys.
        self.cds = {}
        self.debugged_cds = set()
        # USE FOR DEBUGGING on data items: key -> (section, ALL REFERENCES),
        # start_debug after END DECLARATIVES, and the statements being parsed
        # (cb_check_field_debug fills each one's debug_check list).
        self.debug_fields = {}
        self.start_debug = False
        self.debug_frames = []
        # USE GLOBAL AFTER ERROR on an OPEN mode: mode -> section.
        self.global_uses = {}
        # cb_build_program: nest_level, and the programs of the source in
        # PROGRAM-ID order (cobc's next_program chain, reversed).
        self.level = 0
        self.chain = []
        self.containers = []

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

    def procedure_reference(self):
        """A procedure name in a statement, maybe qualified by its section
        (encoded "NAME\0SECTION" until resolve_procedures); all-digit names
        are words too."""
        def word():
            if not self.t.string and re.fullmatch(r"\d+", self.t.key):
                return self.take().key
            return self.name()
        name = word()
        if self.accept("OF") or self.accept("IN"):
            qualifier = word()
            # parser.y label: integer_label IN integer_label, or a word chain.
            if name.isdigit() != qualifier.isdigit():
                self.error("nom de procédure entier qualifié par un mot, ou l'inverse (syntaxe cobc)")
            name += "\0" + qualifier
            if self.at("OF") or self.at("IN"):
                self.error("nom de procédure qualifié deux fois")
        return name

    def resolve_procedures(self, blocks, sections):
        """cb_ref for labels: an unqualified paragraph name used inside its
        own section is that paragraph; otherwise the name, or name IN/OF
        section, must designate a single procedure. Homonym paragraphs get a
        unique internal name. Returns the paragraphs by internal name."""
        counts = {}
        for block in blocks:
            if block.label:
                counts[block.label] = counts.get(block.label, 0) + 1
        used = set()
        for block in blocks:
            if block.label and counts[block.label] > 1:
                key = f"{block.label} OF {block.section or 'MAIN SECTION'}"
                n = 1
                while key in used:
                    n += 1
                    key = f"{block.label} OF {block.section or 'MAIN SECTION'} #{n}"
                used.add(key)
                block.name = key
        outside = object()

        def resolve(reference, context, line):
            name, _, qualifier = reference.partition("\0")
            if name in sections:
                if qualifier:
                    raise CobolError(f"ligne {line}: '{name} IN {qualifier}' is not defined")
                return name
            candidate, ambiguous = None, False
            matches = [b for b in blocks if b.label == name]
            for position, block in enumerate(matches):
                if not qualifier and context is not outside and block.section == context:
                    if any(other.section == context for other in matches[position + 1:]):
                        raise CobolError(f"ligne {line}: '{name}' is ambiguous; needs qualification")
                    return block.name
                if not qualifier or qualifier == block.section:
                    if candidate is None:
                        candidate = block
                    else:
                        ambiguous = True
            if candidate is None:
                shown = f"{name} IN {qualifier}" if qualifier else name
                raise CobolError(f"ligne {line}: procédure inconnue: {shown}")
            if ambiguous:
                raise CobolError(f"ligne {line}: '{name}' is ambiguous; needs qualification")
            return candidate.name

        def rewrite(item, context):
            if isinstance(item, (list, tuple)):
                for element in item:
                    rewrite(element, context)
                return
            if not isinstance(item, Stmt):
                return
            s, line = item, item.line
            if s.op in {"call", "goto"}:
                s.args = ([resolve(n, context, line) for n in s.args[0]], *s.args[1:])
            elif s.op == "alter":
                s.args = tuple(resolve(n, context, line) for n in s.args)
                self.resolved_alters.append((*s.args, line))
            elif s.op == "sort":
                args = list(s.args)
                for index in (2, 3):
                    kind, targets = args[index]
                    if kind == "procedure":
                        args[index] = (kind, [resolve(n, context, line) for n in targets])
                s.args = tuple(args)
            rewrite(s.args, context)

        self.resolved_alters = []
        self.resolve_procedure = lambda reference, line: resolve(reference, outside, line)
        for block in blocks:
            # Statements before any paragraph header have no section offset.
            context = outside if block.label is None and block.section is None else block.section
            rewrite(block.body, context)
        return {block.name: block.body for block in blocks if block.label}

    def variable(self):
        return self.reference()

    def candidates(self, label, conditions=False):
        registry = self.conditions if conditions else self.fields
        return [key for key, value in registry.items() if value.label == label and not getattr(value, "filler", False)]

    def validate_assign_name(self, spec):
        """validate_assign_name of typeck.c, on ASSIGN [TO] data-name."""
        label, qualifiers, required, word = spec.assign_field
        if label in self.files:
            self.error(f"ASSIGN {label} : redéfinition d'un nom de fichier")
        if self.candidates(label, True):
            self.error(f"ASSIGN data item '{label}' is invalid")
        if label in self.indexes:
            self.error(f"ASSIGN vers un index non pris en charge: {label}")
        if not self.candidates(label):
            if required:
                self.error(f"ASSIGN DYNAMIC/USING : donnée non déclarée {label}")
            # implicit-assign-dynamic-var: a PIC X(4096) item holding the word
            # as written; nothing else can name it, so it is that literal.
            spec.path, spec.assign_field = Token(word.text, word.line, True), None
            return
        key = self.resolve(label, qualifiers)
        field = self.fields[key]
        if field.dimensions:
            self.error(f"ASSIGN vers une donnée de table non pris en charge: {label}")
        spec.assign_field = key

    def resolve(self, label, qualifiers=(), conditions=False):
        registry = self.conditions if conditions else self.fields
        candidates = self.candidates(label, conditions)
        valid = []
        for key in candidates:
            parent = registry[key].parent
            ancestors = []
            root = key if registry is self.fields else None
            while parent:
                ancestors.append(self.fields[parent].label)
                root = parent
                parent = self.fields[parent].parent
            # A file name qualifies the records of its FD (cb_ref).
            ancestors += [spec.name for spec in self.files.values() if root in spec.records]
            position = 0
            for qualifier in qualifiers:
                try:
                    position = ancestors.index(qualifier, position) + 1
                except ValueError:
                    break
            else:
                valid.append(key)
        if len(valid) > 1:
            # A name of the program hides the GLOBAL names of its containers.
            own = [key for key in valid if not getattr(registry[key], "global_owner", None)]
            valid = own if own else valid
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
        deferred = getattr(self, "deferred_subscripts", None)
        if deferred is not None and not conditions:
            # REPORT SECTION: dimensions are known after the storage layout.
            deferred.append((label, key, len(indices), self.t.line))
        elif len(indices) != len(descriptor.dimensions):
            self.error(f"{label} requiert {len(descriptor.dimensions)} sous-script(s), reçu {len(indices)}")
        if start is not None and (conditions or (descriptor.kind == "number" and descriptor.usage != "DISPLAY")):
            self.error("modification de référence limitée aux groupes, PIC X et numériques DISPLAY")
        bound = getattr(descriptor, "parse_size", None)
        if bound is not None and start is not None:
            # cb_build_identifier's check of constant positions.
            if start.op == "number" and int(start.args[0]) > bound or (
                    length is not None and length.op == "number" and start.op == "number"
                    and int(start.args[0]) + int(length.args[0]) - 1 > bound):
                self.error(f"length of '{descriptor.label}' out of bounds")
        ref = DataRef(key, tuple(indices), start, length)
        if self.debug_frames and not conditions and not self.debug_frames[-1]["suspended"]:
            self.debug_frames[-1]["refs"].append((key, tuple(qualifiers), ref, False))
        return ref

    def program_end(self):
        """_procedure_division may be empty: the program ends here."""
        return self.at("<EOF>") or (self.at("END") and self.tokens[self.i + 1].key == "PROGRAM")

    def parse(self):
        # _identification_header: the header itself is optional.
        if self.accept("IDENTIFICATION") or self.accept("ID"):
            self.expect("DIVISION")
            self.expect(".")
        elif not self.at("PROGRAM-ID"):
            self.error("IDENTIFICATION DIVISION attendue")
        self.expect("PROGRAM-ID")
        self.expect(".")
        entry_name = self.program_name = self.t.text
        name = self.name()
        self.chain.append({"name": entry_name, "level": self.level, "uses": self.global_uses})
        # PROGRAM-ID name [IS] {COMMON | INITIAL} [PROGRAM].
        common = initial = False
        if self.accept("IS") or self.at("COMMON") or self.at("INITIAL"):
            while self.at("COMMON") or self.at("INITIAL"):
                if self.take().key == "INITIAL":
                    initial = True
                else:
                    common = True
            self.accept("PROGRAM")
        if common and not self.level:
            self.error("COMMON may only be used in a contained program")
        self.expect(".")
        if self.accept("ENVIRONMENT"):
            self.environment_division()
        if self.accept("DATA"):
            self.expect("DIVISION")
            self.expect(".")
            if self.accept("FILE"):
                self.expect("SECTION")
                self.expect(".")
                while self.at("FD") or self.at("SD"):
                    sort_file = self.take().key == "SD"
                    file_name = self.file_name()
                    spec = self.files[file_name]
                    if spec.record:
                        self.error("FD dupliqué")
                    if sort_file:
                        if spec.status or spec.optional or spec.relative_key or spec.organization == "RELATIVE":
                            self.error("SELECT d'un fichier SD limité à ASSIGN")
                        spec.sort, spec.organization = True, "SORT"
                    from .file_parser import parse_fd_clauses
                    parse_fd_clauses(self, spec)
                    if "reports" in spec.fd_clauses:
                        # parser.y file_description: the records of a report
                        # file are not kept; finalize_report sizes its record.
                        if self.t.key.isdigit() and not self.t.string:
                            self.error("enregistrement dans un FD avec REPORT non pris en charge")
                        from .report_parser import ReportSpec
                        for report in spec.fd_clauses["reports"]:
                            if report in self.reports or report in self.files:
                                self.error(f"nom de rapport dupliqué: {report}")
                            self.reports[report] = ReportSpec(report, file_name)
                        continue
                    while not spec.records or (self.t.key.isdigit() and self.t.key in {"01", "1", "77"}):
                        self.data_stack = []
                        record = self.t
                        key = self.declaration(file_record=True)
                        while self.t.key.isdigit() and self.t.key not in {"01", "1", "77"}:
                            self.declaration(file_record=True)
                        descriptor = self.fields[key]
                        # The record area holds the bytes; a numeric or edited
                        # record is a view of them like any other.
                        if record.key not in {"01", "1"} or descriptor.table or descriptor.redefines or (
                                descriptor.kind == "number" and descriptor.usage == "INDEX"):
                            self.error("FD requiert un enregistrement 01 sans OCCURS ni REDEFINES explicite à la racine")
                        if spec.records:
                            # LINE SEQUENTIAL records must also share one size (validate_files).
                            if spec.organization not in {"SEQUENTIAL", "LINE SEQUENTIAL", "RELATIVE", "INDEXED", "SORT"}:
                                self.error("plusieurs enregistrements FD limités à SEQUENTIAL/RELATIVE de taille fixe égale")
                            descriptor.redefines = spec.record
                        else:
                            spec.record = key
                        spec.records.append(key)
                    self.fd_records(spec)
            if self.accept("WORKING-STORAGE"):
                self.expect("SECTION")
                self.expect(".")
                self.data_stack = []
                while not self.at("PROCEDURE") and not self.at("LINKAGE") and not self.at("REPORT") \
                        and not self.at("COMMUNICATION") and not self.at("LOCAL-STORAGE") and not self.program_end():
                    self.declaration()
            if self.accept("LOCAL-STORAGE"):
                # Allocated and initialized at each entry of the program
                # (codegen.c: cob_cache_malloc and initialization of LOCAL).
                self.expect("SECTION")
                self.expect(".")
                self.data_stack = []
                before = set(self.fields)
                while not self.at("PROCEDURE") and not self.at("LINKAGE") and not self.at("REPORT") \
                        and not self.at("COMMUNICATION") and not self.program_end():
                    self.declaration()
                for key in set(self.fields) - before:
                    if self.fields[key].external:
                        self.error("EXTERNAL invalide en LOCAL-STORAGE")
                    self.fields[key].local = True
            if self.accept("LINKAGE"):
                self.expect("SECTION")
                self.expect(".")
                self.data_stack = []
                self.in_linkage = True
                while not self.at("PROCEDURE") and not self.at("REPORT") and not self.at("COMMUNICATION") \
                        and not self.program_end():
                    self.declaration()
                self.in_linkage = False
            if self.accept("COMMUNICATION"):
                self.communication_section()
            if self.accept("REPORT"):
                self.report_section()
        self.report_records()
        for label, owner in self.indexes.items():
            if self.candidates(label) or self.candidates(label, True):
                self.error(f"index dupliqué avec une donnée: {label}")
            self.fields[label] = Field(label, "S9(9)", "number", 9, 0, True, Token("1", 0),
                                       "INDEX", label, 77, index_for=owner)
            # cb_build_index: INDEXED BY starts at 1 only with defaultbyte init.
            self.fields[label].explicit_value = STD != "cobol85"

        for descriptor in self.fields.values():
            if descriptor.depending:
                label, *qualifiers = descriptor.depending.split("\0")
                descriptor.depending = self.resolve(label, tuple(qualifiers))
        # SAME RECORD AREA (finalize_file): the records of the later FDs
        # redefine the record area of the first FD of the group.
        order = list(self.fields)
        for group in self.same_records:
            specs = sorted((self.files[name] for name in group if self.files[name].record),
                           key=lambda spec: order.index(spec.record))
            for spec in specs[1:]:
                self.fields[spec.record].redefines = specs[0].record
        from .layout import layout_fields
        memory_size = layout_fields(self.fields)
        for label, key, count, line in getattr(self, "report_subscripts", []):
            if count != len(self.fields[key].dimensions):
                raise CobolError(f"ligne {line}: {label} requiert {len(self.fields[key].dimensions)} sous-script(s), reçu {count}")
        for key, index, text in self.group_fills:
            condition = self.conditions[key]
            size = self.fields[condition.parent].size
            token = Token((text * size)[:size], self.t.line, True)
            condition.values[index] = (token, token)
        self.apply_renames()
        self.validate_files()
        memory_size = self.debug_item(memory_size)
        self.return_code_register()
        # GLOBAL items of the containing programs (copies of their
        # descriptions, storage owned by the declaring program).
        for key, item in getattr(self, "inherited", {}).items():
            self.fields[key] = item
        for file_name, spec in getattr(self, "inherited_files", {}).items():
            if file_name in self.files:
                self.error(f"fichier homonyme d'un fichier GLOBAL non pris en charge: {file_name}")
            self.files[file_name] = spec
        using = []
        procedure = not self.program_end()
        if procedure:
            self.expect("PROCEDURE")
            self.expect("DIVISION")
        if procedure and self.accept("USING"):
            using = self.using_list(lambda: self.at("."))
        if procedure:
            self.expect(".")
        self.entries = []
        entry, paragraphs = [], {}
        blocks = [ProcedureBlock(None, None, entry)]
        sections, segments = {}, {}
        current_body, current_section = entry, None
        file_declaratives, mode_declaratives = {}, {}
        declaratives, main_block = self.accept("DECLARATIVES"), 0
        if declaratives:
            self.expect(".")
        # USE FOR DEBUGGING: debugging sections by name, and the blocks a
        # fall-through enters after cobc's "FALL THROUGH" DEBUG-CONTENTS.
        # cobc emits it when a paragraph ends (current_paragraph) and, at a
        # SECTION header, also when only a section was open.
        debug_sections, fall_through, labelled, paragraph_open = {}, set(), False, False
        self.in_debugging = False
        nested_start = ended = False
        while not self.at("<EOF>"):
            if self.at("."):
                # The separator period ends a sentence: the target of NEXT SENTENCE.
                line = self.take().line
                if current_body and current_body[-1].op != "sentence_end":
                    current_body.append(Stmt("sentence_end", (), line))
                continue
            if declaratives and self.at("END") and self.tokens[self.i + 1].key == "DECLARATIVES":
                self.take(); self.take(); self.expect(".")
                # needs_field_debug: field debugging starts after the declaratives.
                self.start_debug = bool(self.debug_fields)
                if current_section is None:
                    self.error("DECLARATIVES requiert au moins une section USE")
                sections[current_section] = (sections[current_section][0], len(blocks))
                # Execution starts after END DECLARATIVES, outside every section.
                declaratives, current_section, current_body = False, None, []
                # The program starts here: no "FALL THROUGH" into what follows.
                self.in_debugging, labelled, paragraph_open = False, False, False
                main_block = len(blocks)
                blocks.append(ProcedureBlock(None, None, current_body))
                continue
            if (self.at("IDENTIFICATION") or self.at("ID")) and self.tokens[self.i + 1].key == "DIVISION":
                # Contained programs end the PROCEDURE DIVISION.
                nested_start = True
                break
            if self.accept("END"):
                self.expect("PROGRAM")
                # cobc compares the names as written, case included.
                if self.t.text != entry_name or self.name() != name:
                    self.error("END PROGRAM ne correspond pas au PROGRAM-ID")
                self.expect(".")
                ended = True
                if not self.at("<EOF>") and not (self.at("IDENTIFICATION") or self.at("ID") or self.at("END")):
                    self.expect("<EOF>")
                break
            if self.t.key not in VERBS and self.tokens[self.i + 1].key == "SECTION":
                section = self.procedure_header()
                if section in sections or section in paragraphs:
                    self.error(f"nom de procédure dupliqué: {section}; les homonymes ne sont pas pris en charge")
                self.expect("SECTION")
                if self.t.key.isdigit() and not self.t.string:
                    # Segment numbers only matter to paragraphs modified by
                    # ALTER: codegen.c zaps the labels of independent ones.
                    segment = int(self.take().text)
                    if segment > 99 or (declaratives and segment >= 50):
                        self.error("numéro de segment SECTION hors limites (0-99, moins de 50 en DECLARATIVES)")
                    if not declaratives and STD == "cobol85":
                        segments[section] = segment
                self.expect(".")
                if current_section is not None:
                    sections[current_section] = (sections[current_section][0], len(blocks))
                if self.debugging_mode and not self.in_debugging and labelled:
                    fall_through.add(len(blocks))
                labelled, paragraph_open = True, False
                current_section = section
                sections[section] = (len(blocks), len(blocks) + 1)
                current_body = []
                blocks.append(ProcedureBlock(None, section, current_body))
                if declaratives:
                    targets = self.use_statement(section, file_declaratives, mode_declaratives)
                    # use_statement resets in_debugging; USE FOR DEBUGGING sets it.
                    self.in_debugging = targets is not None
                    if targets is not None:
                        debug_sections[section] = targets
                elif self.at("USE"):
                    self.error("USE hors des DECLARATIVES")
            elif self.t.key not in VERBS and self.tokens[self.i + 1].key == ".":
                paragraph = self.procedure_header()
                # cb_build_section_name: a paragraph may not reuse a section
                # name; homonym paragraphs are allowed until referenced.
                if paragraph in sections:
                    self.error(f"nom de procédure dupliqué: {paragraph}")
                self.expect(".")
                if self.debugging_mode and not self.in_debugging and paragraph_open:
                    fall_through.add(len(blocks))
                labelled = paragraph_open = True
                current_body = []
                paragraphs.setdefault(paragraph, current_body)
                blocks.append(ProcedureBlock(paragraph, current_section, current_body, paragraph))
            else:
                if declaratives and current_section is None:
                    self.error("section USE attendue après DECLARATIVES")
                current_body.append(self.statement())
        if declaratives:
            self.error("END DECLARATIVES attendu")
        if current_section is not None:
            sections[current_section] = (sections[current_section][0], len(blocks))
        if not self.debugging_mode:
            # Without DEBUGGING MODE the USE FOR DEBUGGING sections are not
            # compiled (skip_statements).
            for section in debug_sections:
                start, end = sections[section]
                for block in blocks[start:end]:
                    block.body[:] = []
            debug_sections = {}
        paragraphs = self.resolve_procedures(blocks, sections)
        program = Program(name, self.fields, entry, paragraphs, self.files, self.conditions, memory_size,
                          blocks, sections, file_declaratives, mode_declaratives, main_block, using)
        program.entry_name = entry_name
        program.entries = self.entries
        program.segments = segments
        program.collating = self.collating
        program.decimal_comma, program.currency = self.decimal_comma, self.currency
        program.reports = self.reports
        program.global_uses, program.inherited_uses = dict(self.global_uses), self.inherited_uses(mode_declaratives)
        program.unchecked_data = NO_EC_DATA_INCOMPATIBLE
        program.runtime_checks = RUNTIME_CHECKS
        program.debug_fields = self.debug_fields if self.debugging_mode else {}
        self.debugging_program(program, debug_sections, fall_through)
        # defaultbyte: init (default.conf) sets items without VALUE from
        # their PICTURE; none (cobol85.conf) leaves the storage as allocated.
        program.default_byte_init = STD != "cobol85"
        self.validate_calls(program)
        self.validate_alters(program)
        self.validate_global_uses(program, blocks, sections)
        program.common, program.parent, program.nested = common, None, []
        # INITIAL: an implicit CANCEL when the program returns (codegen.c).
        program.initial = initial
        if nested_start:
            # Nested programs, then END PROGRAM of this one (parser.y nested_list).
            if self.reports:
                self.error("REPORT SECTION avec programmes contenus non pris en charge")
            inherited = self.global_items(entry_name)
            inherited_files = self.global_files(entry_name)
            while self.at("IDENTIFICATION") or self.at("ID"):
                child_parser = Parser.__new__(Parser)
                child_parser.__init__("")
                child_parser.tokens, child_parser.i = self.tokens, self.i
                child_parser.decimal_comma = self.decimal_comma
                child_parser.inherited, child_parser.inherited_files = inherited, inherited_files
                child_parser.level, child_parser.chain = self.level + 1, self.chain
                child_parser.containers = [*self.containers, entry_name]
                child = child_parser.parse()
                self.i = child_parser.i
                for item in [child, *child.siblings]:
                    item.parent = entry_name
                    program.nested.append(item)
                child.siblings = []
            self.expect("END")
            self.expect("PROGRAM")
            if self.t.text != entry_name or self.name() != name:
                self.error("END PROGRAM ne correspond pas au PROGRAM-ID")
            self.expect(".")
            if not self.at("<EOF>") and not (self.at("IDENTIFICATION") or self.at("ID") or self.at("END")):
                self.expect("<EOF>")
        if self.at("IDENTIFICATION") or self.at("ID"):
            # A sibling program after END PROGRAM: same source, separate names.
            sibling = Parser.__new__(Parser)
            sibling.__init__("")
            sibling.tokens, sibling.i = self.tokens, self.i
            # Programs contained in the same program see the same GLOBAL items.
            sibling.inherited = getattr(self, "inherited", {})
            sibling.inherited_files = getattr(self, "inherited_files", {})
            sibling.level, sibling.chain, sibling.containers = self.level, self.chain, self.containers
            sibling.decimal_comma = self.decimal_comma
            following = sibling.parse()
            self.i = sibling.i
            program.siblings = [following, *following.siblings]
            following.siblings = []
            if any(other.entry_name == entry_name for other in program.siblings):
                raise CobolError(f"PROGRAM-ID dupliqué dans le source: {entry_name}")
        return program

    def communication_section(self):
        """_communication_section: cobc parses the CD entries but implements
        none of them (CB_PENDING); outside -std=cobol85 the section is
        unconformable. Each CD's 01 records are static storage that cobc never
        initializes (their VALUE clauses are ignored); the later ones redefine
        the first (cb_finalize_cd)."""
        self.expect("SECTION")
        self.expect(".")
        if STD != "cobol85":
            self.error("COMMUNICATION SECTION non conforme hors -std=cobol85")
        while self.accept("CD"):
            name = self.user_word(self.name())
            if name in self.cds or name in self.files or self.candidates(name):
                self.error(f"nom de CD dupliqué: {name}")
            self.accept("FOR")
            initial = self.accept("INITIAL")
            if self.accept("I-O"):
                pass
            elif not (self.accept("INPUT") or (not initial and self.accept("OUTPUT"))):
                self.error("CD FOR [INITIAL] INPUT, OUTPUT ou I-O attendu")
            if not self.at("."):
                self.error("clauses de CD non prises en charge")
            self.expect(".")
            records = []
            self.in_communication = True
            while not self.t.string and self.t.key in {"01", "1"}:
                self.data_stack = []
                key = self.declaration(file_record=True)
                while not self.t.string and self.t.key.isdigit() and self.t.key not in {"01", "1", "77"}:
                    self.declaration(file_record=True)
                if records:
                    self.fields[key].redefines = records[0]
                records.append(key)
            self.in_communication = False
            if not records:
                self.error("CD record missing")
            self.cds[name] = records

    def cd_name(self):
        name = self.name()
        if name not in self.cds:
            self.error(f"nom de CD attendu: {name}")
        return name

    def communication_statement(self, verb, line):
        """ENABLE, DISABLE, PURGE, RECEIVE and SEND: begin_statement only, so
        each sets DEBUG-LINE and does nothing else; the NO DATA and WITH DATA
        statements of RECEIVE are parsed and dropped."""
        if verb in {"ENABLE", "DISABLE"}:
            if self.accept("INPUT"):
                self.accept("TERMINAL")
            elif self.accept("I-O"):
                self.expect("TERMINAL")
            else:
                self.accept("OUTPUT")
            self.cd_name()
            if self.accept("WITH") or self.at("KEY"):
                self.expect("KEY")
                self.take() if self.t.string else self.variable()
        elif verb == "PURGE":
            self.cd_name()
        elif verb == "RECEIVE":
            self.cd_name()
            if not (self.accept("MESSAGE") or self.accept("SEGMENT")):
                self.error("RECEIVE requiert MESSAGE ou SEGMENT")
            self.expect("INTO")
            self.variable()
            seen = set()
            while True:
                if self.at("NO") and self.tokens[self.i + 1].key == "DATA":
                    phrase = "NO"
                    self.take()
                elif self.at("DATA") or (self.at("WITH") and self.tokens[self.i + 1].key == "DATA"):
                    phrase = "WITH"
                    self.accept("WITH")
                else:
                    break
                if phrase in seen:
                    self.error(f"{phrase} DATA dupliqué")
                seen.add(phrase)
                self.expect("DATA")
                self.block({"END-RECEIVE", "NO", "DATA", "WITH"})
            self.accept("END-RECEIVE")
        else:
            self.cd_name()
            if self.accept("FROM"):
                self.variable()
            if self.at("WITH") or self.at("ESI") or self.at("EMI") or self.at("EGI"):
                self.accept("WITH")
                if not (self.accept("ESI") or self.accept("EMI") or self.accept("EGI")):
                    self.variable()
                if self.at("BEFORE") or self.at("AFTER"):
                    self.take()
                    self.accept("ADVANCING")
                    if not self.accept("PAGE"):
                        if self.t.string:
                            self.error("ADVANCING de SEND requiert un entier, un identificateur ou un mnémonique")
                        if self.t.key in self.mnemonics:
                            self.take()
                        else:
                            self.take() if self.t.text.isdigit() else self.variable()
                            self.accept("LINE") or self.accept("LINES")
                if self.accept("REPLACING"):
                    self.accept("LINE")
        return Stmt("continue", (), line)

    def inherited_uses(self, own_modes):
        """cobc.c "Set up USE GLOBAL handlers": for each OPEN mode without a
        USE of its own, a contained program takes the GLOBAL USE of the first
        program defined before it at a lower nesting level, up to level 0."""
        inherited = {}
        if not self.level:
            return inherited
        index = next(i for i, entry in enumerate(self.chain) if entry["uses"] is self.global_uses)
        for entry in reversed(self.chain[:index]):
            if entry["level"] >= self.level:
                continue
            for mode, section in entry["uses"].items():
                if mode not in own_modes and mode not in inherited:
                    if entry["name"] not in self.containers:
                        # The walk also finds programs that do not contain this one.
                        self.error(f"USE GLOBAL de {entry['name']}, qui ne contient pas ce programme, non pris en charge")
                    inherited[mode] = (entry["name"], section)
            if not entry["level"]:
                break
        return inherited

    def validate_global_uses(self, program, blocks, sections):
        """A GLOBAL USE procedure runs with the declaring program's data from
        a contained program (entry 2 of the program's function)."""
        if not program.global_uses:
            return
        if program.alters:
            self.error("ALTER dans un programme avec USE GLOBAL non pris en charge")

        def walk(item):
            if isinstance(item, Stmt):
                if item.op in {"goback", "exit_program"}:
                    raise CobolError(f"ligne {item.line}: GOBACK ou EXIT PROGRAM dans une procédure USE GLOBAL non pris en charge")
                walk(item.args)
            elif isinstance(item, (list, tuple)):
                for element in item:
                    walk(element)
        for section in set(program.global_uses.values()):
            start, end = sections[section]
            for block in blocks[start:end]:
                walk(block.body)

    def fd_records(self, spec):
        """cb_build_field and finalize_file: the 01 records of an EXTERNAL
        FD are external, those of a GLOBAL FD global; all of them redefine
        the file's record area (fd_file)."""
        records = [self.fields[key] for key in spec.records]
        for record in records:
            record.fd_file, record.fd_external = spec.name, spec.external
            if spec.is_global:
                record.is_global = True
        if not spec.is_global and len({record.is_global for record in records}) > 1:
            self.error("GLOBAL sur une partie des enregistrements d'un FD non pris en charge")

    def global_files(self, owner):
        """The GLOBAL files of this program and those it inherits, as its
        contained programs see them: records and keys named like the copies
        made by global_items."""
        import copy
        inherited = dict(getattr(self, "inherited_files", {}))
        prefix = f"^{owner}^"
        for name, spec in self.files.items():
            if not spec.is_global or spec.global_owner:
                continue
            if any(name in group for group in self.same_records):
                self.error("SAME RECORD AREA avec un FD GLOBAL non pris en charge")
            clone = copy.copy(spec)
            clone.global_owner = owner
            clone.record, clone.records = prefix + spec.record, [prefix + key for key in spec.records]
            for attribute in ("status", "relative_key", "depending"):
                key = getattr(spec, attribute)
                if key is None:
                    continue
                root = self.fields[key]
                while root.parent:
                    root = self.fields[root.parent]
                if not root.is_global:
                    self.error(f"FD GLOBAL dont la clause {attribute} désigne une donnée non GLOBAL non pris en charge")
                setattr(clone, attribute, prefix + key)
            if spec.record_key:
                clone.record_key = (prefix + spec.record_key[0], *spec.record_key[1:])
                clone.alternate_keys = [(prefix + key[0], *key[1:]) for key in spec.alternate_keys]
            inherited[name] = clone
        return inherited

    def global_items(self, owner):
        """Descriptions of this program's GLOBAL items and of those it
        inherits, as its contained programs see them."""
        import copy
        inherited = dict(getattr(self, "inherited", {}))
        prefix = f"^{owner}^"
        rename = lambda key: None if key is None else prefix + key
        for key, item in self.fields.items():
            root = item
            while root.parent:
                root = self.fields[root.parent]
            if not root.is_global or getattr(item, "global_owner", None):
                continue
            # The records of a FD redefine its first one (the record area).
            if not getattr(root, "fd_file", None) and (
                    root.redefines or any(f.redefines == root.name for f in self.fields.values())):
                self.error("REDEFINES d'un article GLOBAL non pris en charge")
            clone = copy.copy(item)
            clone.name, clone.parent, clone.redefines = rename(item.name), rename(item.parent), rename(item.redefines)
            clone.children = [rename(child) for child in item.children]
            clone.depending = rename(item.depending) if item.depending and item.depending.startswith(root.name) else None
            if item.depending and clone.depending is None:
                self.error("OCCURS DEPENDING d'un article GLOBAL hors de son groupe non pris en charge")
            clone.global_owner, clone.global_root = owner, root.label
            inherited[clone.name] = clone
        return inherited

    def return_code_register(self):
        """cb_build_register_return_code: RETURN-CODE, "GLOBAL USAGE
        BINARY-LONG VALUE ZERO", in each outermost program; contained programs
        share it as a GLOBAL item. It is held apart from the program's storage
        (Field.register), so the other offsets do not move."""
        if self.level or self.candidates("RETURN-CODE"):
            return
        saved = self.tokens, self.i, self.data_stack, self.last_data
        self.tokens, self.i, self.data_stack = lex("01 RETURN-CODE GLOBAL USAGE BINARY-LONG VALUE ZERO."), 0, []
        self.building_register = True
        try:
            key = self.declaration()
        finally:
            self.building_register = False
            self.tokens, self.i, self.data_stack, self.last_data = saved
        from .layout import layout_fields
        layout_fields({key: self.fields[key]})
        self.fields[key].register = True

    def debug_item(self, memory_size):
        """cb_build_debug_item, at the first USE FOR DEBUGGING: DEBUG-ITEM in
        WORKING-STORAGE after the other items, DEBUG-CONTENTS sized like
        cb_resolve_debug_refs (30, or the largest file record or item)."""
        tokens, uses = self.tokens, []
        for k in range(self.i, len(tokens) - 2):
            if tokens[k].key == "USE" and not tokens[k].string:
                j = k + 1 + (tokens[k + 1].key == "FOR")
                if tokens[j].key == "DEBUGGING" and not tokens[j].string:
                    uses.append(j + 1)
        if not uses:
            return memory_size
        size = 30
        if self.debugging_mode:
            for j in uses:
                while tokens[j].key != "." or tokens[j].string:
                    word = tokens[j].key
                    if not tokens[j].string and word in self.files:
                        size = max(size, self.files[word].record_max)
                    elif not tokens[j].string and word in self.cds:
                        # cb_resolve_debug_refs: the CD's record size.
                        size = max(size, self.fields[self.cds[word][0]].size)
                    elif not tokens[j].string and tokens[j - 1].key not in {"OF", "IN"}:
                        keys = self.candidates(word)
                        if len(keys) == 1:
                            size = max(size, self.fields[keys[0]].size)
                    j += 1
        text = ("01 DEBUG-ITEM VALUE SPACE. 03 DEBUG-LINE PIC X(6). 03 FILLER PIC X."
                " 03 DEBUG-NAME PIC X(30). 03 FILLER PIC X."
                + "".join(f" 03 DEBUG-SUB-{n} PIC S9(4) SIGN LEADING SEPARATE. 03 FILLER PIC X." for n in (1, 2, 3))
                + f" 03 DEBUG-CONTENTS PIC X({size}).")
        if self.candidates("DEBUG-ITEM"):
            self.error("DEBUG-ITEM est défini par USE FOR DEBUGGING")
        before = set(self.fields)
        self.tokens[self.i:self.i] = lex(text)[:-1]
        self.data_stack, self.in_linkage = [], False
        # The register's names are reserved words of cobol85.words.
        self.building_register = True
        while not self.at("PROCEDURE"):
            self.declaration()
        self.building_register = False
        from .layout import layout_fields
        added = {key: f for key, f in self.fields.items() if key not in before}
        extent = layout_fields(added)
        # The procedure division is parsed with DFLT_DEBUG_CONTENTS_SIZE (30):
        # cb_resolve_debug_refs only resizes DEBUG-CONTENTS afterwards, so the
        # LENGTH of the register and literal reference modifications use it.
        for f in added.values():
            if f.label in {"DEBUG-ITEM", "DEBUG-CONTENTS"}:
                f.parse_size = f.size - (size - 30)
        for f in added.values():
            f.offset += memory_size
        return memory_size + extent

    def use_statement(self, section, by_file, by_mode):
        """USE AFTER STANDARD ERROR/EXCEPTION PROCEDURE ON files or an OPEN
        mode, or USE FOR DEBUGGING ON targets (returned as a list)."""
        self.expect("USE")
        # _use_global: the section's flag_global; contained programs take it
        # for the OPEN modes they have no USE of their own for.
        use_global = self.accept("GLOBAL")
        if use_global and (self.at("FOR") or self.at("DEBUGGING")):
            self.error("USE GLOBAL FOR DEBUGGING non pris en charge")
        if self.at("FOR") or self.at("DEBUGGING"):
            self.accept("FOR")
            self.expect("DEBUGGING")
            self.accept("ON")
            targets = []
            while not self.at("."):
                line = self.t.line
                if self.accept("ALL"):
                    if self.accept("PROCEDURES"):
                        targets.append(("all", None, line))
                        continue
                    if self.accept("REFERENCES"):
                        self.accept("OF")
                    else:
                        self.accept("OF")
                    targets.append(("references", self.debugging_item(section, True), line))
                elif not self.t.string and self.t.key in self.files:
                    targets.append(("file", self.file_name(), line))
                elif not self.t.string and self.t.key in self.cds:
                    # flag_field_debug of the CD: its statements generate
                    # nothing, so the section is never performed for it.
                    name = self.take().key
                    if name in self.debugged_cds:
                        self.error(f"duplicate DEBUGGING target: '{name}'")
                    self.debugged_cds.add(name)
                    targets.append(("cd", name, line))
                elif not self.t.string and self.candidates(self.t.key):
                    targets.append(("item", self.debugging_item(section, False), line))
                else:
                    targets.append(("procedure", self.procedure_reference(), line))
            self.expect(".")
            if not targets:
                self.error("USE FOR DEBUGGING requiert une cible")
            return targets
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
            if use_global:
                self.global_uses[mode] = section
        else:
            if use_global:
                # setup_use_file: a GLOBAL file's handler goes through the
                # programs' global_file_list, inherited by its contained programs.
                self.error("USE GLOBAL sur un fichier non pris en charge")
            names = [self.file_name()]
            while not self.t.string and self.t.key in self.files:
                names.append(self.file_name())
            for name in names:
                if name in by_file:
                    self.error(f"USE dupliqué pour le fichier {name}")
                by_file[name] = section
        self.expect(".")
        return None

    def debugging_item(self, section, all_references):
        """debugging_target on a data item (flag_field_debug, flag_all_debug
        with ALL REFERENCES): its section, known before the statements."""
        # identifier_1 without its subscript check: a table item is named alone.
        label, qualifiers = self.name(), []
        while self.accept("OF") or self.accept("IN"):
            qualifiers.append(self.name())
        ref = DataRef(self.resolve(label, qualifiers))
        if self.at("("):
            self.error("USE FOR DEBUGGING sur un article indicé ou modifié non pris en charge")
        if self.debugging_mode:
            if ref.name in self.debug_fields:
                self.error(f"duplicate DEBUGGING target: '{self.fields[ref.name].label}'")
            self.debug_fields[ref.name] = (section, all_references)
        return ref.name

    def apply_renames(self):
        """compute_size and cb_validate_renames_item for level 66 items."""
        import dataclasses
        founder = lambda key: key.split(".")[0]
        order = list(self.fields)
        for key, label, first, thru, record, line in self.renames:
            def check(name):
                f = self.fields[name]
                if founder(name) != record:
                    raise CobolError(f"ligne {line}: '{label}' must immediately follow the record '{founder(name)}'")
                if f.dimensions:
                    raise CobolError(f"ligne {line}: RENAMES d'un élément de table interdit: {f.label}")
                return f
            start = check(first)
            if thru is not None:
                end = check(thru)
                if thru == first:
                    raise CobolError(f"ligne {line}: THRU item must be different to '{start.label}'")
                if order.index(thru) < order.index(first) or thru.startswith(first + "."):
                    raise CobolError(f"ligne {line}: THRU {end.label} invalide pour {start.label}")
                size = end.offset + end.size - start.offset
            else:
                size = start.size
            last = thru or first
            span = [name for name in order[order.index(first):] if name == last or order.index(name) <= order.index(last)
                    or name.startswith(last + ".")]
            if any(self.fields[name].depending for name in span if name in self.fields):
                raise CobolError(f"ligne {line}: RENAMES may not contain an OCCURS DEPENDING table")
            if thru is None and start.picture:
                if start.usage != "DISPLAY":
                    raise CobolError(f"ligne {line}: RENAMES d'un élément non DISPLAY non pris en charge")
                alias = dataclasses.replace(start, name=key, label=label, level=66, parent=record, children=[],
                                            occurs=1, table=False, redefines=first, filler=False, size=size,
                                            dimensions=[], search_keys=[], group_value=None)
            else:
                # A THRU range or a renamed group is one alphanumeric item.
                alias = Field(key, f"X({size})", "text", size, 0, False, Token("", line, True), "DISPLAY",
                              label, 66, record, [], 1, False, first)
                alias.offset, alias.size = start.offset, size
            alias.offset = start.offset
            self.fields[key] = alias

    def user_word(self, name):
        """cobc refuses a reserved word as a user-defined name."""
        from .reserved import RESERVED, RESERVED_COBOL85
        if name in (RESERVED_COBOL85 if STD == "cobol85" else RESERVED) and not getattr(self, "building_register", False):
            raise CobolError(f"ligne {self.tokens[self.i - 1].line}: mot réservé de GnuCOBOL utilisé comme nom: {name}")
        return name

    def integer_value(self, x):
        """cb_check_integer_value: a numeric item without decimal places, an
        unsigned integer literal or ZERO; expressions are not checked."""
        if x.op == "var":
            ref = x.args[0]
            f = self.fields[ref.name]
            if ref.start is not None or f.kind != "number" or f.scale > 0:
                self.error(f"'{f.label}' is not an integer")
        elif x.op == "number" or (x.op in {"unary-", "unary+"} and x.args[0].op == "number"):
            # A sign next to the digits makes one signed literal in cobc.
            text = x.args[0] if x.op == "number" else x.args[0].args[0]
            if x.op == "unary-" or text.startswith("-") or "." in text or "," in text:
                self.error("positive numeric integer is required here")
        elif x.op in {"text", "all"}:
            self.error("valeur entière requise ici")

    def procedure_header(self):
        """A section or paragraph name; cobc accepts all-digit names."""
        if not self.t.string and re.fullmatch(r"\d+", self.t.key):
            return self.take().key
        name = self.name()
        self.procedure_name_check(name)
        return name

    def debugging_program(self, program, debug_sections, fall_through):
        """cb_validate_labels for DEBUGGING targets: procedures (real labels,
        outside the debugging sections), ALL PROCEDURES and files."""
        program.debugging_mode = self.debugging_mode
        # cobc's word table keeps the spelling of a name's first occurrence:
        # DEBUG-NAME shows labels and files that way.
        program.spelling = {}
        for token in self.tokens:
            if not token.string:
                program.spelling.setdefault(token.key, token.text)
        program.debug_sections = debug_sections
        program.gen_debug = bool(debug_sections)
        program.fall_through = fall_through if program.gen_debug else set()
        program.all_procedure, program.debug_labels, program.debug_files = None, {}, {}
        inside = {block.name for section in debug_sections
                  for block in program.blocks[program.sections[section][0]:program.sections[section][1]]
                  if block.name}
        for section, targets in debug_sections.items():
            for kind, value, line in targets:
                if kind == "all":
                    if program.all_procedure:
                        raise CobolError(f"ligne {line}: duplicate USE DEBUGGING ON ALL PROCEDURES")
                    program.all_procedure = section
                elif kind == "file":
                    if value in program.debug_files:
                        raise CobolError(f"ligne {line}: duplicate DEBUGGING target: '{value}'")
                    program.debug_files[value] = section
        for section, targets in debug_sections.items():
            for kind, value, line in targets:
                if kind != "procedure":
                    continue
                key = self.resolve_procedure(value, line)
                label = value.partition("\0")[0]
                if key in inside or key in debug_sections:
                    raise CobolError(f"ligne {line}: DEBUGGING target invalid: '{label}'")
                if key in program.debug_labels:
                    raise CobolError(f"ligne {line}: duplicate DEBUGGING target: '{label}'")
                if program.all_procedure:
                    raise CobolError(f"ligne {line}: DEBUGGING target already specified with ALL PROCEDURES: '{label}'")
                program.debug_labels[key] = section

    def validate_alters(self, program):
        """typeck.c: the source of an ALTER must be a paragraph whose first
        statement is a GO TO; duplicate pairs are kept once."""
        for source, target, line in self.resolved_alters:
            for name in (source, target):
                try:
                    program.procedure_range(name)
                except CobolError as error:
                    raise CobolError(f"ligne {line}: {error}") from None
            block = next((b for b in program.blocks if b.name == source), None)
            first = next((s for s in block.body if s.op != "sentence_end"), None) if block else None
            if first is None or first.op != "goto":
                raise CobolError(f"ligne {line}: '{source}' is not an alterable paragraph")
            targets = program.alters.setdefault(source, [])
            if target not in targets:
                targets.append(target)

    def procedure_name_check(self, name):
        self.user_word(name)
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
            collating = None
            while self.at("SOURCE-COMPUTER") or self.at("OBJECT-COMPUTER"):
                paragraph = self.take().key
                if paragraph in computers:
                    self.error(f"paragraphe {paragraph} dupliqué")
                computers.add(paragraph)
                self.expect(".")
                if not (paragraph == "SOURCE-COMPUTER" and (self.at("WITH") or self.at("DEBUGGING"))):
                    self.name()
                if paragraph == "SOURCE-COMPUTER" and (self.at("WITH") or self.at("DEBUGGING")):
                    self.accept("WITH")
                    self.expect("DEBUGGING")
                    self.expect("MODE")
                    self.debugging_mode = True
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
                    elif self.accept("PROGRAM"):
                        self.accept("COLLATING")
                        self.expect("SEQUENCE")
                        self.accept("IS")
                        collating = (self.t, self.name())
                    else:
                        break
                if not self.accept("."):
                    self.error(f"clause {paragraph} non prise en charge; seul le nom de machine est accepté")
            if self.accept("SPECIAL-NAMES"):
                self.expect(".")
                self.special_names()
            if collating:
                token, alphabet = collating
                if isinstance(self.alphabets.get(alphabet), tuple):
                    # cb_validate_collating: the module collating sequence and
                    # its HIGH-VALUE / LOW-VALUE.
                    weights, low, high = self.alphabets[alphabet]
                    self.collating = weights
                    if low:
                        self.low_value = chr(low)
                    if high != 255:
                        self.high_value = chr(high)
                else:
                    self.check_identity_alphabet(token, alphabet, "PROGRAM COLLATING SEQUENCE")
            if not any(self.at(word) for word in ("INPUT-OUTPUT", "DATA", "PROCEDURE")) and not self.program_end():
                self.error("paragraphe CONFIGURATION non pris en charge")
        if self.accept("INPUT-OUTPUT"):
            self.expect("SECTION")
            self.expect(".")
            # _file_control_header: optional when no SELECT follows (a SELECT
            # without it is "FILE-CONTROL header missing", an error).
            if self.at("FILE-CONTROL") or self.at("SELECT"):
                self.expect("FILE-CONTROL")
                self.expect(".")
            while self.at("SELECT"):
                self.file_control()
            if self.accept("I-O-CONTROL"):
                self.expect(".")
                self.io_control()
        if not (self.at("DATA") or self.at("PROCEDURE") or self.program_end()):
            self.error("clause ENVIRONMENT DIVISION non prise en charge")

    DEVICES = {"SYSIN": "stdin", "CONSOLE": "console", "SYSOUT": "stdout", "SYSLIST": "stdout", "SYSLST": "stdout",
               "SYSERR": "stderr", "PRINTER": "printer", "SYSPCH": "punch", "FORMFEED": "formfeed",
               **{f"C{n:02d}": "channel" for n in range(1, 13)},
               **{f"S{n:02d}": "formfeed" for n in range(1, 6)}, "CSP": "formfeed", "TOP": "formfeed"}

    def figurative_value(self, key):
        """A figurative constant's byte; HIGH/LOW-VALUE follow the program
        collating sequence (cb_high / cb_low)."""
        if key.startswith("HIGH-VALUE"):
            return self.high_value
        if key.startswith("LOW-VALUE"):
            return self.low_value
        return INSPECT_FIGURATIVES[key]

    @staticmethod
    def alphabet_table(items, line):
        """validate_alphabet for a literal alphabet: the weight of each byte
        (listed characters first, ALSO sharing a weight, the others after in
        native order), its LOW-VALUE and HIGH-VALUE characters."""
        weights, seen = [-1] * 256, [False] * 256
        charvals = [-1] * 256
        tableval = count = lastval = 0
        low, high = 0, 255
        duplicates = False

        def value(item):
            # get_value: a literal's first byte, an ordinal minus one.
            return ord(item[1][0]) if item[0] == "lit" else item[1]

        def mark(n, weight, first=True):
            nonlocal duplicates
            if seen[n]:
                duplicates = True
            seen[n] = True
            if first:
                charvals[n] = n
            weights[n] = weight

        for item in items:
            if item[0] == "pair":
                lower, upper = value(item[1]), value(item[2])
                lastval = upper
                if not count:
                    low = lower
                if not (0 <= lower <= 255 and 0 <= upper <= 255):
                    raise CobolError(f"ligne {line}: invalid character values in alphabet")
                step = 1 if lower <= upper else -1
                for n in range(lower, upper + step, step):
                    mark(n, tableval)
                    tableval += 1
                    count += 1
            elif item[0] == "also":
                values = [value(v) for v in item[1]]
                if not count:
                    low = values[0]
                lastval = values[-1]
                for position, n in enumerate(values):
                    if not 0 <= n <= 255:
                        raise CobolError(f"ligne {line}: invalid character values in alphabet")
                    mark(n, tableval, position == 0)
                    count += 1
                tableval += 1
            elif item[0] == "lit":
                data = item[1]
                if not count:
                    low = ord(data[0])
                lastval = ord(data[-1])
                for c in data:
                    mark(ord(c), tableval)
                    tableval += 1
                    count += 1
            else:
                lastval = item[1]
                if not count:
                    low = lastval
                if not 0 <= lastval <= 255:
                    raise CobolError(f"ligne {line}: invalid character values in alphabet")
                mark(lastval, tableval)
                tableval += 1
                count += 1
        if duplicates:
            raise CobolError(f"ligne {line}: duplicate character values in alphabet")
        if count == 256:
            high = lastval
        elif seen[255]:
            high = 0
            for n in range(254, 0, -1):
                if not seen[n]:
                    high = n
                    break
        for n in range(256):
            if weights[n] < 0:
                weights[n] = tableval
                tableval += 1
        return weights, low, high

    def check_identity_alphabet(self, token, name, clause):
        """On an ASCII machine NATIVE, STANDARD-1, STANDARD-2 and ASCII give
        cobc's identity cob_native table; other alphabets are not modelled."""
        if name not in self.alphabets:
            raise CobolError(f"ligne {token.line}: alphabet inconnu pour {clause}: {name}")
        if self.alphabets[name] is not True:
            raise CobolError(f"ligne {token.line}: {clause} avec alphabet non natif non pris en charge")

    def special_names(self):
        """SPECIAL-NAMES entries with a GnuCOBOL 3.2 meaning on an ASCII machine."""
        def ordinal_or_text():
            if self.t.string:
                return [ord(c) for c in self.take().text]
            if not self.t.string and self.t.key in {"HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES",
                                                     "QUOTE", "QUOTES", "SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES"}:
                key = self.take().key
                return [255 if key.startswith("HIGH") else 0 if key.startswith("LOW") else 34 if key.startswith("QUOTE")
                        else 32 if key.startswith("SPACE") else 48]
            value = self.integer_literal("ordinal")
            if not 1 <= value <= 256:
                self.error("position ordinale limitée à 1..256")
            return [value - 1]

        while not self.at("."):
            key = self.t.key
            if self.t.string:
                self.error("entrée SPECIAL-NAMES attendue")
            if key in self.DEVICES:
                self.take()
                self.accept("IS")
                if self.at("CRT"):
                    self.error("CONSOLE IS CRT (entrées-sorties écran) non pris en charge")
                self.mnemonics[self.name()] = self.DEVICES[key]
            elif re.fullmatch(r"SWITCH-(\d+)", key) and int(key[7:]) <= 36:
                number = int(self.take().key[7:])
                if self.accept("IS") or not (self.at("ON") or self.at("OFF")):
                    self.mnemonics[self.name()] = ("switch", number)
                while self.at("ON") or self.at("OFF"):
                    on = self.take().key == "ON"
                    self.accept("STATUS")
                    self.accept("IS")
                    self.switch_conditions[self.name()] = (number, on)
            elif self.accept("ALPHABET"):
                name = self.user_word(self.name())
                if self.accept("FOR"):
                    self.expect("ALPHANUMERIC")
                self.accept("IS")
                if self.t.key in {"NATIVE", "STANDARD-1", "STANDARD-2", "ASCII"} and not self.t.string:
                    self.take()
                    self.alphabets[name] = True
                elif self.accept("EBCDIC"):
                    self.alphabets[name] = False
                else:
                    # alphabet_literal_list: lits [THRU lits | ALSO lits ...].
                    line = self.t.line

                    def lits():
                        if self.t.string:
                            return ("lit", self.take().text)
                        key = self.t.key
                        if key in {"HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES", "QUOTE", "QUOTES",
                                   "SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES"}:
                            self.take()
                            return ("val", 255 if key.startswith("HIGH") else 0 if key.startswith("LOW")
                                    else 34 if key.startswith("QUOTE") else 32 if key.startswith("SPACE") else 48)
                        return ("val", self.integer_literal("ordinal") - 1)

                    items = []
                    while self.t.string or self.t.key[:1].isdigit() or self.t.key in {
                            "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES",
                            "QUOTE", "QUOTES", "SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES"}:
                        first = lits()
                        if self.accept("THRU") or self.accept("THROUGH"):
                            items.append(("pair", first, lits()))
                        elif self.at("ALSO"):
                            group = [first]
                            while self.accept("ALSO"):
                                group.append(lits())
                            items.append(("also", group))
                        else:
                            items.append(first)
                        self.accept(",")
                    if not items:
                        self.error("ALPHABET requiert des littéraux")
                    self.alphabets[name] = self.alphabet_table(items, line)
            elif self.accept("CLASS"):
                name = self.name()
                if self.accept("FOR"):
                    self.expect("ALPHANUMERIC")
                self.accept("IS")
                members = set()
                while self.t.string or self.t.key[:1].isdigit() or self.t.key in INSPECT_FIGURATIVES:
                    low = ordinal_or_text()
                    if self.accept("THRU") or self.accept("THROUGH"):
                        high = ordinal_or_text()
                        if len(low) != 1 or len(high) != 1:
                            self.error("CLASS THRU requiert des caractères isolés")
                        members |= set(range(min(low[0], high[0]), max(low[0], high[0]) + 1))
                    else:
                        members |= set(low)
                if not members:
                    self.error("CLASS requiert au moins un caractère")
                self.classes[name] = frozenset(members)
            elif self.accept("SYMBOLIC"):
                self.accept("CHARACTERS")
                while not self.at(".") and not self.t.string and self.t.key not in {
                        "ALPHABET", "CLASS", "SYMBOLIC", "IN", "CURRENCY", "DECIMAL-POINT"} | set(self.DEVICES):
                    names = []
                    while not self.t.string and not self.t.key[:1].isdigit() and self.t.key not in {"IS", "ARE"}:
                        names.append(self.name())
                    self.accept("IS") or self.accept("ARE")
                    values = []
                    while not self.t.string and self.t.key[:1].isdigit():
                        values.append(ordinal_or_text()[0])
                    if not names or len(names) != len(values):
                        self.error("SYMBOLIC CHARACTERS requiert autant de positions que de noms")
                    self.symbolic.update(zip(names, values))
                if self.accept("IN"):
                    self.check_identity_alphabet(self.t, self.name(), "SYMBOLIC CHARACTERS IN")
            elif self.accept("CURRENCY"):
                # currency_sign_clause / set_currency_picture_symbol.
                self.accept("SIGN")
                self.accept("IS")
                if not self.t.string:
                    self.error("CURRENCY SIGN requiert un littéral")
                symbol = self.take().text
                if self.at("WITH") or self.at("PICTURE"):
                    self.error("CURRENCY ... PICTURE SYMBOL non pris en charge")
                if len(symbol) != 1:
                    self.error("currency symbol must be one character long")
                if symbol in "0123456789ABCDENPRSVXZabcdenprsvxz+-,.*/;()='\" " or not symbol.isascii():
                    self.error(f"invalid character '{symbol}' in currency symbol")
                self.currency = symbol
            elif self.accept("DECIMAL-POINT"):
                self.accept("IS")
                self.expect("COMMA")
            else:
                self.error(f"entrée SPECIAL-NAMES non prise en charge: {key}")
        self.expect(".")

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
                record = self.accept("RECORD")
                if not record:
                    self.accept("SORT") or self.accept("SORT-MERGE")
                self.accept("AREA")
                self.accept("FOR")
                group = [self.file_name()]
                while not self.t.string and self.t.key in self.files:
                    group.append(self.file_name())
                if record:
                    self.same_records.append(group)
            else:
                self.error("clause I-O-CONTROL non prise en charge")
        # _i_o_control_entries: an empty paragraph has no closing period.
        if not (self.at("DATA") or self.at("PROCEDURE")) or self.tokens[self.i - 1].key != ".":
            self.expect(".")

    def file_name(self):
        name = self.name()
        if name not in self.files:
            self.error(f"fichier non déclaré: {name}")
        return name

    def file_control(self):
        self.expect("SELECT")
        optional = self.accept("OPTIONAL")
        name = self.user_word(self.name())
        select_text = self.tokens[self.i - 1].text
        if name in self.files or name in VERBS:
            self.error(f"nom de fichier réservé ou dupliqué: {name}")
        path, assign_field = None, None
        organization, organization_seen, status, access = "SEQUENTIAL", False, None, None
        relative_key, record_key, alternate_keys = None, None, []

        def organization_word():
            # [ORGANIZATION [IS]] {LINE SEQUENTIAL | [RECORD] [BINARY] SEQUENTIAL | RELATIVE | INDEXED}
            if self.accept("RELATIVE"):
                return "RELATIVE"
            if self.accept("INDEXED"):
                return "INDEXED"
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
            if self.at("ASSIGN") and path is None and assign_field is None:
                # SELECT clauses come in any order (file_control_entry).
                self.take()
                path, assign_field, assign_organization = self.assign_clause(name, select_text)
                if assign_organization and not organization_seen:
                    organization = assign_organization
            elif self.accept("PADDING"):
                # Obsolete in default.conf: cobc warns and ignores it.
                self.accept("CHARACTER")
                self.accept("IS")
                if self.t.string:
                    self.take()
                else:
                    reference()
            elif self.at("RECORD") and self.tokens[self.i + 1].key == "DELIMITER":
                self.take(); self.take()
                self.accept("IS")
                word = self.take()
                if word.string:
                    self.error("RECORD DELIMITER attend un mot")
                if word.key == "LINE-SEQUENTIAL":
                    if organization not in {"SEQUENTIAL", "LINE SEQUENTIAL"}:
                        self.error("RECORD DELIMITER LINE-SEQUENTIAL only allowed with (LINE) SEQUENTIAL files")
                    organization = "LINE SEQUENTIAL"
                elif organization != "SEQUENTIAL" and (word.key in {"STANDARD-1", "BINARY-SEQUENTIAL"}
                                                       or organization != "LINE SEQUENTIAL"):
                    self.error("RECORD DELIMITER only allowed with SEQUENTIAL files")
                # STANDARD-1 and other names are ignored, as by cobc.
            elif self.accept("ORGANIZATION") and not organization_seen:
                organization_seen = True
                self.accept("IS")
                organization = organization_word()
            elif (not organization_seen and not self.t.string and (self.at("LINE") or self.at("SEQUENTIAL")
                    or self.at("BINARY") or self.at("INDEXED")
                    or (self.at("RELATIVE") and self.tokens[self.i + 1].key in clause_words))):
                organization_seen = True
                organization = organization_word()
            elif self.at("RECORD") and record_key is None:
                # RECORD [KEY] [IS] data-name (SOURCE IS split keys are refused).
                self.take()
                self.accept("KEY")
                self.accept("IS")
                record_key = reference()
                if self.at("SOURCE") or self.at("="):
                    self.error("clé INDEXED composée (SOURCE IS) non prise en charge")
            elif self.accept("ALTERNATE"):
                self.expect("RECORD")
                self.accept("KEY")
                self.accept("IS")
                key = reference()
                if self.at("SOURCE") or self.at("="):
                    self.error("clé INDEXED composée (SOURCE IS) non prise en charge")
                duplicates = False
                if self.at("WITH") or self.at("DUPLICATES"):
                    self.accept("WITH")
                    self.expect("DUPLICATES")
                    duplicates = True
                if self.at("SUPPRESS"):
                    self.error("ALTERNATE KEY SUPPRESS non pris en charge")
                alternate_keys.append((key, duplicates))
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
        if path is None and assign_field is None:
            self.error("ASSIGN attendu")
        self.expect(".")
        if organization != "RELATIVE" and relative_key:
            self.error("RELATIVE KEY requiert ORGANIZATION RELATIVE")
        if organization not in {"RELATIVE", "INDEXED"} and access not in {None, "SEQUENTIAL"}:
            self.error("ACCESS RANDOM/DYNAMIC requiert ORGANIZATION RELATIVE ou INDEXED")
        if (organization == "INDEXED") != (record_key is not None) or (alternate_keys and organization != "INDEXED"):
            self.error("RECORD KEY requise par ORGANIZATION INDEXED, et réservée à elle")
        if organization == "RELATIVE" and access in {"RANDOM", "DYNAMIC"} and not relative_key:
            self.error("ACCESS RANDOM/DYNAMIC requiert RELATIVE KEY")
        self.files[name] = FileSpec(name, path, optional, status, organization=organization,
                                    access=access or "SEQUENTIAL", relative_key=relative_key,
                                    record_key=record_key, alternate_keys=alternate_keys,
                                    assign_field=assign_field, select_text=select_text)

    # assign_device of parser.y: general devices keep the SELECT name as file
    # name when no name follows (flag_fileid); line devices are LINE SEQUENTIAL.
    GENERAL_DEVICES = {"DISC", "DISK", "TAPE", "RANDOM"}
    LINE_DEVICES = {"CARD-PUNCH", "CARD-READER", "CASSETTE", "INPUT", "INPUT-OUTPUT", "MAGNETIC-TAPE", "OUTPUT"}

    def assign_clause(self, file_name, select_text):
        """assign_clause of parser.y, after ASSIGN: returns (literal token or
        None, (label, qualifiers, required) of a data item or None, organization
        forced by the device or None)."""
        from .reserved import RESERVED
        self.accept("TO")
        # _ext_clause: EXTERNAL makes the word a file name, DYNAMIC a variable;
        # without it, assign-clause (dynamic, external with -std=cobol85).
        kind = "external" if self.accept("EXTERNAL") else "dynamic" if self.accept("DYNAMIC") else None
        explicit = kind is not None
        kind = kind or ("external" if STD == "cobol85" else "default")
        if explicit and STD == "cobol85":
            self.error("ASSIGN EXTERNAL/DYNAMIC non conforme à -std=cobol85")
        if self.at("LINE") and self.tokens[self.i + 1].key == "ADVANCING":
            self.error("ASSIGN LINE ADVANCING FILE non pris en charge")
        organization, device = None, None
        if not self.t.string and self.t.key in {"DISPLAY", "KEYBOARD", "PRINTER", "PRINTER-1", "PRINT"}:
            self.error(f"ASSIGN TO {self.t.key} (périphérique spécial) non pris en charge")
        if not self.t.string and self.t.key in self.GENERAL_DEVICES | self.LINE_DEVICES:
            device = self.take().key
            if device in self.LINE_DEVICES:
                organization = "LINE SEQUENTIAL"
            if device == "DISK" and self.at("FROM"):
                self.error("ASSIGN DISK FROM non pris en charge")
        if self.at("USING") or self.at("VARYING"):
            if explicit:
                self.error("EXTERNAL/DYNAMIC cannot be used with USING/VARYING")
            self.take()
            if STD == "cobol85":
                self.error("ASSIGN USING/VARYING non conforme à -std=cobol85")
            kind = "required"
        if self.t.string:
            if explicit:
                self.error("EXTERNAL/DYNAMIC cannot be used with literals")
            path = self.take()
            if not path.text or any(ord(c) < 32 for c in path.text):
                self.error("chemin ASSIGN vide ou invalide")
            return path, None, organization
        if self.t.key in RESERVED or self.t.key in {".", "SELECT"}:
            if kind == "required" or device is None:
                self.error("nom ASSIGN attendu")
            # flag_fileid: the file name is the SELECT name (cb_validate_one).
            return Token(select_text, self.t.line, True), None, organization
        word = self.t
        label, qualifiers = self.name(), []
        while self.accept("OF") or self.accept("IN"):
            qualifiers.append(self.name())
        if kind == "external":
            if qualifiers:
                self.error("ASSIGN EXTERNAL qualifié non pris en charge")
            # build_external_assignment_name: labels before the last '-' are dropped.
            return Token(word.text.rsplit("-", 1)[-1], word.line, True), None, organization
        if label == file_name and not qualifiers:
            # cb_build_assignment_name: the file's own name is a literal.
            return Token(word.text, word.line, True), None, organization
        return None, (label, tuple(qualifiers), kind == "required" or kind == "dynamic", word), organization

    def validate_files(self):
        for spec in self.files.values():
            if not spec.record:
                self.error(f"FD manquant pour {spec.name}")
            if spec.assign_field:
                self.validate_assign_name(spec)
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
            if spec.record_key:
                keys = [(spec.record_key, False), *spec.alternate_keys]
                spec.record_key, spec.alternate_keys = None, []
                resolved = []
                for (label, qualifiers), duplicates in keys:
                    name = self.resolve(label, qualifiers)
                    root = name.split(".")[0]
                    key = self.fields[name]
                    if root not in spec.records or key.dimensions or key.depending:
                        self.error(f"clé INDEXED {key.label} hors de l'enregistrement de {spec.name} ou dans une table")
                    if key.size > 255:
                        self.error(f"clé INDEXED {key.label} limitée à 255 octets")
                    resolved.append((name, key.offset - self.fields[root].offset, key.size, duplicates))
                if len({(offset, size) for _, offset, size, _ in resolved}) != len(resolved):
                    self.error("clés INDEXED de même position non prises en charge")
                spec.record_key, spec.alternate_keys = resolved[0], resolved[1:]
            if "linage" in spec.fd_clauses:
                # file_linage_check reads each value with cob_get_int.
                spec.linage = {}
                for part, value in spec.fd_clauses["linage"].items():
                    if value[0] == "name":
                        name = self.resolve(value[1], value[2])
                        item = self.fields[name]
                        if item.kind != "number" or item.scale or item.dimensions or item.usage == "INDEX":
                            self.error(f"LINAGE {part.upper()} limité à un entier numérique: {item.label}")
                        value = ("field", name)
                    spec.linage[part] = value
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
            for key in spec.records:
                # finalize_file: a record with OCCURS DEPENDING may be as short
                # as its table at the minimum count.
                for item in self.fields.values():
                    if item.depending and item.name.startswith(key + "."):
                        if spec.sort:
                            # cob_file_sort_using/giving move each record at the
                            # sort record's maximum size; RELEASE and RETURN of
                            # its current length are not modelled.
                            spec.variable_sort = True
                        low = min(low, item.offset - self.fields[key].offset + item.size * item.occurs_min)
            spec.record_min, spec.record_max = min([low, *sizes]), max([high, *sizes])
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

    def expr(self, minimum=0, primary=False):
        t = self.take()
        if t.string:
            left = Expr("text", (t.text,))
        elif re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", t.text):
            left = Expr("number", (t.text,))
        elif t.key in {"ZERO", "ZEROS", "ZEROES"}:
            left = Expr("number", ("0",), figurative_zero=True)
        elif t.key in {"SPACE", "SPACES"}:
            left = Expr("text", (" ",), figurative_space=True)
        elif t.key in {"QUOTE", "QUOTES"}:
            # Like ALL '"': a figurative constant fills its receiver.
            left = Expr("all", ('"',))
        elif t.key in {"HIGH-VALUE", "HIGH-VALUES"}:
            left = Expr("all", (self.high_value,), memset=self.high_value == "\xff")
        elif t.key in {"LOW-VALUE", "LOW-VALUES"}:
            left = Expr("all", (self.low_value,), memset=self.low_value == "\x00")
        elif t.key == "ALL" and self.t.string:
            # ALL "literal" repeats the literal over the receiver; MOVE only.
            left = Expr("all", (self.take().text,), literal_all=True)
        elif t.key == "ALL" and not self.t.string and self.t.key in INSPECT_FIGURATIVES:
            # ALL with a figurative constant is that constant (parser.y literal).
            return self.expr(minimum, primary)
        elif t.key in {"+", "-"}:
            # exp_unary applies to an atom; ** binds the signed atom (parser.y).
            left = Expr("unary" + t.key, (self.expr(50),))
        elif re.fullmatch(r"[+-](?:\d+(?:\.\d+)?|\.\d+)", t.text):
            # A signed literal token (see lex): the same as a unary sign.
            left = Expr("unary" + t.text[0], (Expr("number", (t.text[1:],)),))
        elif t.key == "(":
            left = self.expr()
            self.expect(")")
        elif t.key == "FUNCTION" and not t.string:
            left = self.function_call()
        elif t.key in {"TRUE", "FALSE"}:
            left = Expr("bool", (t.key == "TRUE",))
        elif not t.string and t.key in self.switch_conditions and not self.candidates(t.key):
            left = Expr("switch", self.switch_conditions[t.key])
        elif not t.string and t.key in self.symbolic and not self.candidates(t.key):
            # A symbolic character is a figurative constant.
            left = Expr("all", (chr(self.symbolic[t.key]),))
        elif not t.string and t.key == "LINAGE-COUNTER":
            left = Expr("linage", (self.linage_file(),))
        elif not t.string and t.key in {"LINE-COUNTER", "PAGE-COUNTER"}:
            left = Expr("report_counter", (self.counter_report(t.key), t.key))
        elif not t.string and t.key == "LENGTH" and not self.candidates(t.key):
            left = self.length_of()
        elif self.candidates(t.key, True):
            self.i -= 1
            left = Expr("condition", (self.reference(True),))
        elif self.candidates(t.key):
            self.i -= 1
            left = Expr("var", (self.variable(),))
        else:
            self.error(f"expression non prise en charge: {t.text}")
        if primary:
            return left
        while not self.t.string and self.t.key in {"+", "-", "*", "/", "**"}:
            op = self.t.key
            precedence = 40 if op == "**" else 20 if op in {"*", "/"} else 10
            if precedence < minimum:
                break
            self.take()
            # exp_factor: exponentiation is right associative.
            left = Expr(op, (left, self.expr(precedence if op == "**" else precedence + 1)))
        return left

    def picture_symbols(self, picture):
        """A PICTURE in the internal symbols: '$' for the currency sign and
        '.' for the decimal point (DECIMAL-POINT IS COMMA swaps . and ,)."""
        if self.currency != "$":
            if "$" in picture:
                self.error(f"PICTURE invalide avec CURRENCY SIGN {self.currency}: {picture}")
            picture = picture.replace(self.currency.upper(), "$")
        if self.decimal_comma:
            picture = picture.translate(str.maketrans(".,", ",."))
        return picture

    def counter_report(self, word):
        """line_linage_page_counter: LINE-COUNTER/PAGE-COUNTER [IN|OF report];
        unqualified, the only report, or inside an RD the report described."""
        if self.accept("IN") or self.accept("OF"):
            name = self.name()
            if name not in self.reports:
                self.error(f"'{name}' is not a report name")
            return name
        if len(self.reports) == 1:
            return next(iter(self.reports))
        if getattr(self, "current_report", None) is not None:
            return self.current_report
        self.error(f"{word} must be qualified here" if self.reports else f"invalid {word} usage")

    def report_section(self):
        """REPORT SECTION: an RD for each report named in an FD REPORT clause."""
        from .report_parser import report_description
        self.expect("SECTION")
        self.expect(".")
        while self.accept("RD"):
            name = self.name()
            if name not in self.reports:
                self.error(f"RD {name} sans clause REPORT dans un FD")
            report = self.reports[name]
            if report.entries:
                self.error(f"RD dupliqué: {name}")
            self.current_report = name
            self.deferred_subscripts = []
            try:
                report_description(self, report)
            finally:
                self.report_subscripts = getattr(self, "report_subscripts", []) + self.deferred_subscripts
                self.deferred_subscripts = None
        self.current_report = None
        if not self.at("PROCEDURE"):
            self.error("PROCEDURE DIVISION attendue après la REPORT SECTION")

    def hidden_item(self, tokens, key, file_record=False):
        """An item of cobc's own (report storage, report record) declared
        from `tokens`, then renamed so that no source name reaches it."""
        line = self.t.line
        self.tokens[self.i:self.i] = [Token("01", line), Token("C2R-HIDDEN-ITEM", line), *tokens, Token(".", line)]
        self.data_stack, self.last_data = [], None
        self.building_register = True
        try:
            declared = self.declaration(file_record)
        finally:
            self.building_register = False
        item = self.fields.pop(declared)
        if item.children or declared in self.conditions:
            self.error("article de rapport invalide")
        item.name, item.label = key, key
        self.fields[key] = item
        # Its size is needed before the storage layout (finalize_report).
        from .layout import layout_fields
        layout_fields({key: item})
        return key

    def report_item(self, report, picture):
        """The storage of a report item (CB_STORAGE_REPORT): its PICTURE."""
        key = f"^report^{report.name}^{sum(1 for k in self.fields if k.startswith(f'^report^{report.name}^'))}"
        return self.hidden_item(list(picture), key)

    def sum_counter(self, report, picture):
        """build_sum_counter: a WORKING-STORAGE DISPLAY counter, VALUE ZERO."""
        key = f"^sum^{report.name}^{sum(1 for k in self.fields if k.startswith(f'^sum^{report.name}^'))}"
        line = self.t.line
        return self.hidden_item([Token("PIC", line), Token(picture, line), Token("VALUE", line), Token("0", line)], key)

    def report_records(self):
        """finalize_report: the report file's record has the report's line
        size (record_min = record_max = rcsz)."""
        for report in self.reports.values():
            if not report.entries:
                self.error(f"RD manquant pour le rapport {report.name}")
            if self.candidates(report.name):
                self.error(f"nom de rapport également nom de donnée: {report.name}")
            spec = self.files[report.file]
            key = self.hidden_item([Token("PIC", 0), Token(f"X({report.size})", 0)], f"^record^{report.file}", True)
            spec.record, spec.records = key, [key]

    def linage_file(self):
        """line_linage_page_counter: LINAGE-COUNTER [IN|OF file], the counter
        register cobc defines for each FD with LINAGE."""
        if self.accept("IN") or self.accept("OF"):
            name = self.name()
            if name not in self.files:
                self.error(f"'{name}' is not a file name")
            if self.files[name].fd_clauses.get("linage") is None:
                self.error(f"LINAGE-COUNTER: {name} sans clause LINAGE")
            return name
        files = [f.name for f in self.files.values() if "linage" in f.fd_clauses]
        if len(files) != 1:
            self.error("LINAGE-COUNTER must be qualified here" if files else "invalid LINAGE-COUNTER usage")
        return files[0]

    # Intrinsic functions modelled after libcob/intrinsic.c: name -> (arguments, result).
    FUNCTIONS = {
        "INTEGER": (1, "number"), "INTEGER-PART": (1, "number"), "MOD": (2, "number"),
        "REM": (2, "number"), "FACTORIAL": (1, "number"), "SUM": (-1, "number"),
        "MEAN": (-1, "number"), "MEDIAN": (-1, "number"), "MIDRANGE": (-1, "number"),
        "RANGE": (-1, "number"), "VARIANCE": (-1, "number"), "ORD-MAX": (-1, "number"),
        "ORD-MIN": (-1, "number"), "MAX": (-1, "args"), "MIN": (-1, "args"),
        "ANNUITY": (2, "number"), "PRESENT-VALUE": (-2, "number"), "CHAR": (1, "text"),
        "ORD": (1, "number"), "UPPER-CASE": (1, "text"), "LOWER-CASE": (1, "text"),
        "REVERSE": (1, "text"), "INTEGER-OF-DATE": (1, "number"), "INTEGER-OF-DAY": (1, "number"),
        "DATE-OF-INTEGER": (1, "number"), "DAY-OF-INTEGER": (1, "number"),
        "NUMVAL": (1, "number"), "NUMVAL-C": (-1, "number"), "LENGTH": (1, "number"),
        "SQRT": (1, "number"), "LOG": (1, "number"), "LOG10": (1, "number"), "EXP": (1, "number"),
        "SIN": (1, "number"), "COS": (1, "number"), "TAN": (1, "number"), "ASIN": (1, "number"),
        "ACOS": (1, "number"), "ATAN": (1, "number"), "STANDARD-DEVIATION": (-1, "number"),
        "PI": (0, "number"), "E": (0, "number"), "CURRENT-DATE": (0, "text"), "WHEN-COMPILED": (0, "text"),
        "RANDOM": (0, "number"),
    }

    def function_call(self):
        """FUNCTION name [(exp_list)] [(start:[length])]: a reference
        modification of an alphanumeric result (func_args _func_refmod)."""
        result = self.function_value()
        if not self.at("("):
            return result
        self.take()
        start = self.expr()
        self.expect(":")
        length = None if self.at(")") else self.expr()
        self.expect(")")
        if not (result.op == "text" or (result.op == "function" and self.FUNCTIONS[result.args[0]][1] == "text")):
            self.error("modification de référence d'une FUNCTION numérique non prise en charge")
        return Expr("refmod", (result, start, length))

    def function_value(self):
        """FUNCTION name [(exp_list)]: arguments separated by spaces or commas."""
        name = self.take()
        if name.string or name.key not in self.FUNCTIONS:
            self.error(f"FUNCTION {name.text} non prise en charge")
        count, _ = self.FUNCTIONS[name.key]
        args = []
        # A function without arguments: "(" starts a reference modification.
        if self.at("(") and (count != 0 or name.key == "RANDOM" or self.tokens[self.i + 1].key == ")") and self.accept("("):
            while not self.accept(")"):
                self.accept(",")
                if self.at(")"):
                    continue
                args.append(self.expr())
        if name.key == "RANDOM":
            count = len(args) if len(args) <= 1 else 0
        if (count >= 0 and len(args) != count) or (count < 0 and len(args) < -count) \
                or (name.key == "NUMVAL-C" and len(args) > 2):
            self.error(f"FUNCTION '{name.key}' has wrong number of arguments")
        if name.key == "WHEN-COMPILED":
            # cb_set_intr_when_compiled: a literal of the compilation time,
            # hundredths and local UTC offset included.
            if os.environ.get("COB_CURRENT_DATE") is not None:
                self.error("COB_CURRENT_DATE à la compilation non pris en charge")
            if not hasattr(Parser, "compile_time"):
                import time
                stamp = time.time()
                now = time.localtime(stamp)
                offset = now.tm_gmtoff // 60
                hundredths = f"{int(stamp * 100) % 100:02d}"
                Parser.compile_time = (time.strftime("%Y%m%d%H%M%S", now) + hundredths + ("-" if offset < 0 else "+")
                                       + f"{abs(offset) // 60:02d}{abs(offset) % 60:02d}")
            return Expr("text", (Parser.compile_time,))
        if name.key == "LENGTH":
            # cb_build_intrinsic: the length of a fixed item or literal is a literal.
            arg = args[0]
            if arg.op in {"text", "all"} and arg.op == "text":
                return Expr("number", (str(len(arg.args[0])),))
            if arg.op == "var" and arg.args[0].start is None:
                f = self.fields[arg.args[0].name]
                if not f.depending and not any(self.fields[k].depending for k in self.fields
                                                if k.startswith(arg.args[0].name + ".")):
                    return Expr("number", (str(getattr(f, "parse_size", f.size)),))
            if arg.op != "function":
                self.error("FUNCTION LENGTH d'un élément variable non prise en charge")
        return Expr("function", (name.key, tuple(args)))

    def using_list(self, ended):
        """PROCEDURE DIVISION / ENTRY USING: distinct 01/77 LINKAGE items."""
        using = []
        while not ended():
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
        return using

    def entry_statement(self, line):
        """ENTRY literal [USING ...] (entry_body, emit_entry): another entry
        point of the program, a label where the program runs through it."""
        if self.level:
            self.error("ENTRY is invalid in nested program")
        if STD == "cobol85":
            self.error("ENTRY statement does not conform to COBOL 85")
        if not self.t.string:
            self.error("ENTRY limité à un littéral sans convention d'appel ni FOR GO TO")
        name = self.take().text
        if not name or name in {self.program_name, *(entry for entry, _ in self.entries)}:
            self.error(f"ENTRY '{name}' duplicated")
        using = []
        if self.accept("USING"):
            using = self.using_list(lambda: self.t.string or self.t.key in BOUNDARIES
                                    or not (self.at("BY") or self.candidates(self.t.key)))
        self.entries.append((name, using))
        return Stmt("entry", (name,), line)

    def length_of(self):
        """LENGTH [OF] (length_of_register): cb_build_length, a literal for a
        fixed item or literal, FUNCTION LENGTH for a reference modification
        or a function, otherwise the cb_build_length_1 sum over the ODO."""
        self.accept("OF")
        if self.t.string:
            return Expr("number", (str(len(self.take().text.encode("latin-1"))),))
        if not self.t.string and self.t.key == "FUNCTION":
            self.take()
            return Expr("function", ("LENGTH", (self.function_call(),)))
        ref = self.variable()
        if ref.start is not None:
            return Expr("function", ("LENGTH", (Expr("var", (ref,)),)))
        return self.field_length(ref.name)

    def field_length(self, name):
        """cb_build_length_1: the size of a fixed item; the sizes of the
        children of a variable one, an ODO table counted by its object."""
        f = self.fields[name]

        def variable(item):  # cb_field_variable_size
            return any(self.fields[c].depending or variable(self.fields[c]) for c in item.children)
        if not variable(f):
            return Expr("number", (str(getattr(f, "parse_size", f.size)),))
        total = None
        for child in f.children:
            c = self.fields[child]
            size = self.field_length(child)
            if c.depending:
                size = Expr("*", (size, Expr("var", (DataRef(c.depending),))))
            elif c.occurs > 1:
                size = Expr("*", (size, Expr("number", (str(c.occurs),))))
            total = size if total is None else Expr("+", (total, size))
        return total

    def operand_start(self):
        """An 'x' of parser.y expr_tokens: identifier, literal or figurative."""
        t = self.t
        if t.string or re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", t.text):
            return not (t.text[:1] in "+-" and not t.string and len(t.text) == 1)
        k = t.key
        if k in {"FUNCTION", "LINAGE-COUNTER", "LINE-COUNTER", "PAGE-COUNTER"}:
            return True
        if k == "LENGTH" and not self.candidates(k):
            return True
        following = self.tokens[self.i + 1] if k == "ALL" else None
        return (k in INSPECT_FIGURATIVES or (k == "ALL" and (following.string or following.key in INSPECT_FIGURATIVES))
                or k in self.switch_conditions or k in self.symbolic
                or bool(self.candidates(k, True)) or bool(self.candidates(k)))

    def expression_tokens(self):
        """The token list of parser.y expr_tokens, for conditions.build."""
        tokens, depth = [], 0
        while True:
            t = self.t
            k = None if t.string else t.key
            following = self.tokens[min(self.i + 1, len(self.tokens) - 1)]
            if k in {"+", "-"} and not following.string and following.start == t.end \
                    and re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", following.text):
                # The scanner reads a sign touching digits as a signed literal.
                self.take(); self.take()
                tokens.append(("x", Expr("unary" + k, (Expr("number", (following.text,)),))))
            elif t.string or (k not in {"+", "-"} and self.operand_start()):
                tokens.append(("x", self.expr(primary=True)))
            elif k == "IS":
                self.take()
            elif k == "NOT":
                self.take()
                tokens.append(("!", None))
            elif k in {"=", "<", ">", "<=", ">=", "<>"}:
                self.take()
                tokens.append(({"=": "=", "<": "<", ">": ">", "<=": "[", ">=": "]", "<>": "~"}[k], None))
            elif k in {"EQUAL", "EQUALS"}:
                self.take()
                self.accept("TO")
                tokens.append(("=", None))
            elif k in {"GREATER", "LESS"}:
                self.take()
                self.accept("THAN")
                op = ">" if k == "GREATER" else "<"
                # The scanner reads GREATER [THAN] OR EQUAL [TO] as one token.
                if self.at("OR") and self.tokens[self.i + 1].key in {"EQUAL", "EQUALS"} and not self.tokens[self.i + 1].string:
                    self.take(); self.take()
                    self.accept("TO")
                    op = "]" if k == "GREATER" else "["
                tokens.append((op, None))
            elif k == "NUMERIC":
                self.take()
                tokens.append(("class", lambda x: Expr("numeric_class", (x,))))
            elif k in {"ALPHABETIC", "ALPHABETIC-LOWER", "ALPHABETIC-UPPER"}:
                self.take()
                tokens.append(("class", lambda x, k=k: self.alpha_class(x, k)))
            elif k in {"POSITIVE", "NEGATIVE"}:
                self.take()
                tokens.append(("P" if k == "POSITIVE" else "N", None))
            elif k in self.classes and not self.candidates(k):
                members = tuple(sorted(self.classes[self.take().key]))
                tokens.append(("class", lambda x, members=members: self.user_class(x, members)))
            elif k == "(":
                self.take()
                depth += 1
                tokens.append(("(", None))
            elif k == ")" and depth:
                self.take()
                depth -= 1
                tokens.append((")", None))
            elif k in {"+", "-", "*", "/", "**"}:
                self.take()
                tokens.append(("^" if k == "**" else k, None))
            elif k in {"AND", "OR"}:
                self.take()
                tokens.append(("&" if k == "AND" else "|", None))
            else:
                break
        if not tokens:
            self.error("expression attendue")
        return tokens

    def alpha_class(self, x, kind):
        if x.op != "var" or (self.fields[x.args[0].name].kind != "text" and x.args[0].start is None):
            self.error(f"condition {kind} limitée aux champs alphanumériques")
        return Expr("alpha_class", (x, kind))

    def user_class(self, x, members):
        # A user CLASS: every byte of the item belongs to the class.
        if x.op != "var" or (self.fields[x.args[0].name].kind != "text" and x.args[0].start is None):
            self.error("condition CLASS limitée aux champs alphanumériques")
        return Expr("user_class", (x, members))

    def cobc_expression(self):
        from .conditions import build
        return build(self.expression_tokens(), self.error)

    def condition(self):
        from .conditions import is_boolean
        result = self.cobc_expression()
        if not is_boolean(result):
            self.error("invalid expression: condition expected")
        return result

    def evaluate_subject(self):
        if self.at("TRUE") or self.at("FALSE"):
            return ("truth", self.take().key == "TRUE")
        from .conditions import is_boolean
        result = self.cobc_expression()
        return ("condition" if is_boolean(result) else "value", result)

    def evaluate_object(self, subject):
        """evaluate_test for one subject and one object."""
        kind, value = subject
        as_condition = Expr("bool", (value,)) if kind == "truth" else value if kind == "condition" else None
        if self.accept("ANY"):
            return Expr("bool", (True,))
        if self.at("TRUE") or self.at("FALSE"):
            truth = self.take().key == "TRUE"
            if as_condition is None:
                self.error("objet TRUE/FALSE avec un sujet non conditionnel non pris en charge")
            return as_condition if truth else Expr("not", (as_condition,))
        if kind == "truth":
            condition = self.condition()
            return condition if value else Expr("not", (condition,))
        if kind == "condition":
            self.error("objet d'un sujet conditionnel: TRUE, FALSE ou ANY attendu")
        negate = self.accept("NOT")
        x = self.expr()
        if x.op == "condition":
            self.error("invalid use of 88 level in WHEN expression")
        if self.accept("THRU") or self.accept("THROUGH"):
            y = self.expr()
            test = Expr("and", (Expr("cmp<=", (x, value)), Expr("cmp<=", (value, y))))
            return Expr("not", (test,)) if negate else test
        return Expr("cmp<>" if negate else "cmp=", (value, x))

    def block(self, stops):
        # A scope terminator also ends the conditional statements it encloses
        # (END-PERFORM after READ ... AT END without END-READ).
        # ELSE and WHEN end them too, for the IF or EVALUATE around them.
        stops = stops | {key for key in BOUNDARIES if key.startswith("END-")} | {"ELSE", "WHEN"}
        result = []
        while self.t.string or self.t.key not in stops | {".", "<EOF>"}:
            result.append(self.statement())
        return result

    # parser.y turns field debugging off while these statements are parsed
    # (PERFORM until its inline statements); their own code generation
    # handles the debugged items.
    DEBUG_SUSPENDED = {"GO", "PERFORM", "WRITE", "REWRITE"}
    # Statements whose receiving operands are marked (target_identifier):
    # elsewhere a debugged item is refused.
    DEBUG_STATEMENTS = {"move", "compute", "arithmetic", "if", "display", "accept_clock"}

    def statement(self):
        if not self.start_debug:
            return self.statement_body()
        parent = self.debug_frames[-1] if self.debug_frames else None
        inherited = False if parent is None else parent["inherited"] if parent["verb"] == "PERFORM" else parent["suspended"]
        verb = None if self.t.string else self.t.key
        frame = {"verb": verb, "inherited": inherited, "suspended": inherited or verb in self.DEBUG_SUSPENDED, "refs": []}
        self.debug_frames.append(frame)
        try:
            stmt = self.statement_body()
        finally:
            self.debug_frames.pop()
        debugged = [r for r in frame["refs"] if r[0] in self.debug_fields]
        if not debugged:
            return stmt
        if stmt.op not in self.DEBUG_STATEMENTS or (stmt.op == "arithmetic" and (stmt.args[2] or stmt.args[3])):
            raise CobolError(f"ligne {stmt.line}: USE FOR DEBUGGING : article débogué dans cette instruction non pris en charge")
        # cb_check_field_debug: an ALL REFERENCES item at each reference, the
        # others as receiving operands; each item once per statement.
        checks, seen = [], set()
        for key, qualifiers, ref, target in debugged:
            if not (target or self.debug_fields[key][1]) or key in seen:
                continue
            if ref.start is not None:
                raise CobolError(f"ligne {stmt.line}: USE FOR DEBUGGING d'une référence modifiée non pris en charge")
            seen.add(key)
            name = self.spelling(self.fields[key].label)
            for qualifier in qualifiers:
                if len(name) >= 30:
                    break
                if qualifier in self.files:
                    raise CobolError(f"ligne {stmt.line}: USE FOR DEBUGGING d'un enregistrement qualifié par son fichier non pris en charge")
                name += f" OF {self.spelling(qualifier)}"
            checks.append((name, ref, self.debug_fields[key][0]))
        if checks:
            stmt.debug_checks = checks
        return stmt

    def spelling(self, key):
        """A name as cobc's word table keeps it: its first occurrence."""
        for token in self.tokens:
            if not token.string and token.key == key:
                return token.text
        return key

    def debug_target(self):
        """target_identifier: the reference just parsed is a receiving operand."""
        if self.debug_frames and self.debug_frames[-1]["refs"]:
            key, qualifiers, ref, _ = self.debug_frames[-1]["refs"][-1]
            self.debug_frames[-1]["refs"][-1] = (key, qualifiers, ref, True)

    def debug_source(self):
        """Undo debug_target when a GIVING phrase shows an operand was a source."""
        if self.debug_frames and self.debug_frames[-1]["refs"]:
            key, qualifiers, ref, _ = self.debug_frames[-1]["refs"][-1]
            self.debug_frames[-1]["refs"][-1] = (key, qualifiers, ref, False)

    def statement_body(self):
        line = self.t.line
        verb = self.take().key
        if verb == "SET":
            if not self.t.string and isinstance(self.mnemonics.get(self.t.key), tuple):
                # SET {switch-mnemonic ... TO ON|OFF} ... (cob_set_switch).
                groups = []
                while not self.t.string and isinstance(self.mnemonics.get(self.t.key), tuple):
                    switches = []
                    while not self.t.string and isinstance(self.mnemonics.get(self.t.key), tuple):
                        switches.append(self.mnemonics[self.take().key][1])
                    self.expect("TO")
                    if not (self.at("ON") or self.at("OFF")):
                        self.error("SET commutateur TO ON ou OFF attendu")
                    groups.append(Stmt("set_switch", (switches, self.take().key == "ON"), line))
                return groups[0] if len(groups) == 1 else Stmt("sequence", (groups,), line)
            if self.candidates(self.t.key) and not self.candidates(self.t.key, True):
                refs = [self.variable()]
                while not self.at("TO") and not self.at("UP") and not self.at("DOWN"):
                    refs.append(self.variable())
                index_like = lambda ref: bool(self.fields[ref.name].index_for) or self.fields[ref.name].usage == "INDEX"
                if all(not index_like(ref) for ref in refs) and self.accept("TO"):
                    # SET integer-items TO index-name stores the occurrence number.
                    source = self.variable()
                    if not index_like(source):
                        self.error("SET donnée TO requiert un index INDEXED BY ou USAGE INDEX")
                    for ref in refs:
                        field = self.fields[ref.name]
                        if ref.start is not None or field.kind != "number" or field.scale or field.usage == "INDEX":
                            self.error("SET donnée TO index requiert un entier numérique")
                    return Stmt("compute", (None, [(ref, Expr("var", (source,)), False) for ref in refs]), line)
                if any(not index_like(ref) for ref in refs):
                    # Mixed receivers: each one is set in turn from an index.
                    if not self.accept("TO") or not self.candidates(self.t.key):
                        self.error("SET numérique requiert des index INDEXED BY ou USAGE INDEX")
                    source = self.variable()
                    if not index_like(source):
                        self.error("SET donnée TO requiert un index INDEXED BY ou USAGE INDEX")
                    for ref in refs:
                        field = self.fields[ref.name]
                        if not index_like(ref) and (ref.start is not None or field.kind != "number" or field.scale):
                            self.error("SET donnée TO index requiert un entier numérique")
                    return Stmt("set_index", (refs, "to", Expr("var", (source,))), line)
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
                # cobc parses OPEN ... WITH NO REWIND and REVERSED and ignores
                # them (CB_PENDING): the file opens as usual.
                if self.accept("WITH") or self.at("NO"):
                    self.expect("NO")
                    self.expect("REWIND")
                else:
                    self.accept("REVERSED")
            if not actions:
                self.error("OPEN requiert INPUT, OUTPUT, I-O ou EXTEND et un fichier déclaré")
            return Stmt("open", (actions,), line)
        if verb == "CLOSE":
            names = []
            while not names or (self.t.key in self.files and not self.t.string):
                name = self.file_name()
                mode = "normal"
                if self.accept("WITH") or self.at("LOCK") or self.at("NO"):
                    if self.accept("NO"):
                        self.expect("REWIND")
                        mode = "no_rewind"
                    else:
                        self.expect("LOCK")
                        mode = "lock"
                elif self.accept("REEL") or self.accept("UNIT"):
                    if self.accept("FOR"):
                        self.expect("REMOVAL")
                    mode = "reel"
                if mode in {"no_rewind", "reel"} and self.files[name].organization not in {"SEQUENTIAL", "LINE SEQUENTIAL"}:
                    self.error("CLOSE REEL/UNIT/NO REWIND limité aux fichiers séquentiels")
                names.append((name, mode))
            return Stmt("close", (names,), line)
        if verb in {"SORT", "MERGE"}:
            return self.sort_statement(verb, line)
        if verb == "SEARCH":
            return self.search_statement(line)
        if verb == "RELEASE":
            record = self.variable()
            files = [f.name for f in self.files.values() if f.sort and record.name in f.records]
            if not files or record.indices or record.start is not None:
                self.error("RELEASE requiert un enregistrement SD")
            if getattr(self.files[files[0]], "variable_sort", False):
                self.error("RELEASE d'un SD avec OCCURS DEPENDING ON non pris en charge")
            value = self.expr() if self.accept("FROM") else None
            return Stmt("release", (files[0], record, value), line)
        if verb == "RETURN":
            name = self.file_name()
            if not self.files[name].sort:
                self.error("RETURN requiert un fichier SD")
            if getattr(self.files[name], "variable_sort", False):
                self.error("RETURN d'un SD avec OCCURS DEPENDING ON non pris en charge")
            self.accept("RECORD")
            into = self.variable() if self.accept("INTO") else None
            if into and self.fields[into.name].kind != "text" and into.start is None:
                self.error("RETURN INTO requiert un champ alphanumérique")
            self.accept("AT")
            self.expect("END")
            at_end = self.block({"NOT", "END-RETURN"})
            not_at_end = []
            if self.accept("NOT"):
                self.accept("AT")
                self.expect("END")
                not_at_end = self.block({"END-RETURN"})
            self.accept("END-RETURN")
            return Stmt("return_sort", (name, into, at_end, not_at_end), line)
        if verb == "READ":
            name = self.file_name()
            if "reports" in self.files[name].fd_clauses:
                self.error("READ d'un fichier de rapport non pris en charge")
            # GnuCOBOL: READ file [NEXT] [RECORD] [INTO x] [[AT] END] [NOT [AT] END].
            spec = self.files[name]
            next_record = self.accept("NEXT")
            if self.at("PREVIOUS"):
                self.error("READ PREVIOUS non pris en charge")
            self.accept("RECORD")
            into = self.variable() if self.accept("INTO") else None
            if into and self.fields[into.name].kind != "text" and into.start is None:
                self.error("READ INTO requiert un champ alphanumérique")
            key_item = None
            if self.accept("KEY"):
                self.accept("IS")
                key_item = self.variable()
            if self.at("WITH"):
                self.error("READ LOCK non pris en charge")
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
            random = (spec.organization in {"RELATIVE", "INDEXED"} and not next_record and spec.access != "SEQUENTIAL"
                      and not (spec.access == "DYNAMIC" and handler == "end"))
            if key_item is not None and spec.organization != "INDEXED":
                self.error("READ KEY requiert un fichier INDEXED")
            if random and spec.organization == "INDEXED":
                # cob_read with KEY IS item, or the RECORD KEY (cob_findkey_attr).
                random = self.index_key(spec, key_item) if key_item else (0, spec.record_key[2])
            if handler == ("end" if random else "key"):
                self.error("READ " + ("direct requiert INVALID KEY, pas AT END" if random else "séquentiel requiert AT END, pas INVALID KEY"))
            return Stmt("read", (name, into, exception, success, random), line)
        if verb == "REWRITE":
            record = self.variable()
            files = [f.name for f in self.files.values() if record.name in f.records and not record.indices and record.start is None]
            if not files:
                self.error(f"REWRITE requiert un enregistrement FD: {record}")
            if self.files[files[0]].organization == "LINE SEQUENTIAL":
                self.error("REWRITE limité aux fichiers SEQUENTIAL/RELATIVE/INDEXED; réécriture LINE SEQUENTIAL non modélisée")
            value = self.expr() if self.accept("FROM") else None
            invalid, valid = self.key_handlers(files[0], "END-REWRITE")
            return Stmt("rewrite", (files[0], record.name, value, invalid, valid), line)
        if verb == "DELETE":
            name = self.file_name()
            if self.files[name].organization not in {"RELATIVE", "INDEXED"}:
                self.error("DELETE limité aux fichiers RELATIVE et INDEXED")
            self.accept("RECORD")
            invalid, valid = self.key_handlers(name, "END-DELETE")
            return Stmt("delete", (name, None, None, invalid, valid), line)
        if verb == "START":
            name = self.file_name()
            spec = self.files[name]
            if spec.organization not in {"RELATIVE", "INDEXED"} or spec.access == "RANDOM":
                self.error("START limité aux fichiers RELATIVE/INDEXED en accès SEQUENTIAL ou DYNAMIC")
            condition = "Equal"
            if self.accept("KEY"):
                self.accept("IS")
                if self.accept("=") or (self.accept("EQUAL") and (self.accept("TO") or True)):
                    condition = "Equal"
                elif self.accept(">="):
                    condition = "NotLess"
                elif self.accept(">") or (self.accept("GREATER") and (self.accept("THAN") or True)):
                    condition = "Greater"
                    # >= and GREATER OR EQUAL are COB_GE, as NOT LESS.
                    if self.accept("="):
                        condition = "NotLess"
                    elif self.accept("OR"):
                        self.expect("EQUAL")
                        self.accept("TO")
                        condition = "NotLess"
                elif self.accept("NOT"):
                    if not (self.accept("<") or (self.accept("LESS") and (self.accept("THAN") or True))):
                        self.error("START KEY NOT < attendu")
                    condition = "NotLess"
                else:
                    self.error("START KEY limité à =, > ou NOT <")
                key = self.variable()
                if spec.organization == "INDEXED":
                    index = self.index_key(spec, key)
                elif key.name != spec.relative_key or key.indices or key.start is not None:
                    self.error("START KEY doit désigner la RELATIVE KEY du fichier")
            elif spec.organization == "INDEXED":
                index = (0, spec.record_key[2])
            elif not spec.relative_key:
                self.error("START requiert une RELATIVE KEY")
            invalid, valid = self.key_handlers(name, "END-START")
            return Stmt("start", (name, index if spec.organization == "INDEXED" else None, condition, invalid, valid), line)
        if verb == "WRITE":
            record = self.variable()
            files = [f.name for f in self.files.values() if record.name in f.records and not record.indices and record.start is None]
            if not files:
                self.error(f"WRITE requiert un enregistrement FD: {record}")
            value = self.expr() if self.accept("FROM") else None
            advancing = None
            if self.at("BEFORE") or self.at("AFTER"):
                direction = self.take().key
                self.accept("ADVANCING")  # optional word in WRITE BEFORE/AFTER
                if self.accept("PAGE"):
                    count = None
                elif not self.t.string and self.mnemonics.get(self.t.key) in {"formfeed", "channel"}:
                    # cb_build_write_advancing_mnemonic: FORMFEED (S01-S05, CSP,
                    # TOP) and the channels C01-C12 all advance to a new page.
                    self.take()
                    count = None
                else:
                    if not self.t.string and self.t.key in {"ZERO", "ZEROS", "ZEROES"}:
                        self.take()
                        count = 0
                    elif not self.t.string and self.t.text.isascii() and self.t.text.isdigit():
                        if not 0 <= int(self.t.text) <= 65535:
                            self.error("ADVANCING requiert un entier littéral de 0 à 65535")
                        count = int(self.take().text)
                    elif not self.t.string and self.candidates(self.t.key):
                        # cb_build_write_advancing_lines: cob_get_int of the item.
                        ref = self.variable()
                        if self.fields[ref.name].kind != "number" or ref.start is not None \
                                or self.fields[ref.name].usage == "INDEX":
                            self.error("ADVANCING requiert un identificateur numérique")
                        count = Expr("var", (ref,))
                    else:
                        self.error("ADVANCING requiert PAGE, un mnémonique, un entier ou un identificateur")
                    self.accept("LINE") or self.accept("LINES")
                if self.files[files[0]].organization not in {"SEQUENTIAL", "LINE SEQUENTIAL"}:
                    self.error("WRITE ADVANCING limité aux fichiers SEQUENTIAL et LINE SEQUENTIAL")
                advancing = (direction, count)
            if self.files[files[0]].organization in {"SEQUENTIAL", "LINE SEQUENTIAL"}:
                # at_eop_clauses take the place of INVALID KEY for these files.
                invalid, valid = self.eop_handlers()
            else:
                invalid, valid = self.key_handlers(files[0], "END-WRITE")
            return Stmt("write", (files[0], record.name, value, advancing, invalid, valid), line)
        if verb == "DISPLAY":
            values = []
            while self.t.string or self.t.key not in BOUNDARIES | {"WITH", "UPON"}:
                if self.at("NO") and self.tokens[self.i + 1].key == "DATA":
                    break  # scanner.l folds NO DATA (RECEIVE) into one token
                values.append(self.expr())
            if not values:
                self.error("DISPLAY sans opérande")
            device = "stdout"
            if self.accept("UPON"):
                # cb_build_display_mnemonic: CONSOLE and SYSOUT are stdout, SYSERR stderr.
                target = self.take().key
                device = self.mnemonics.get(target, self.DEVICES.get(target))
                device = {"console": "stdout"}.get(device, device)
                if device not in {"stdout", "stderr"}:
                    self.error(f"DISPLAY UPON {target} non pris en charge")
            newline = True
            if self.accept("WITH"):
                self.expect("NO")
                self.expect("ADVANCING")
                newline = False
            self.accept("END-DISPLAY")
            return Stmt("display", (values, newline, device), line)
        if verb == "ACCEPT":
            if not self.t.string and self.t.key in self.cds:
                # ACCEPT cd-name [MESSAGE] COUNT: CB_PENDING, nothing generated.
                self.take()
                self.accept("MESSAGE")
                self.expect("COUNT")
                self.accept("END-ACCEPT")
                return Stmt("continue", (), line)
            # parser.y accept_body: an identifier, not a target_identifier.
            name = self.variable()
            if self.accept("FROM"):
                if not self.t.string and self.t.key in {"DATE", "DAY", "DAY-OF-WEEK", "TIME"}:
                    # cb_emit_accept_date/day/day_of_week/time: the clock moved
                    # as a binary field (DAY-OF-WEEK a one-character alphanumeric).
                    kind = self.take().key
                    if kind == "DATE" and self.accept("YYYYMMDD"):
                        kind = "DATE YYYYMMDD"
                    elif kind == "DAY" and self.accept("YYYYDDD"):
                        kind = "DAY YYYYDDD"
                    field = self.fields[name.name]
                    if field.usage == "INDEX" or field.index_for:
                        self.error(f"ACCEPT FROM {kind} vers un index non pris en charge")
                    self.accept("END-ACCEPT")
                    return Stmt("accept_clock", (name, kind), line)
                # cb_emit_accept_mnemonic: CONSOLE and SYSIN read as plain ACCEPT.
                source = self.take().key
                if self.mnemonics.get(source, self.DEVICES.get(source)) not in {"stdin", "console"}:
                    self.error(f"ACCEPT FROM {source} non pris en charge")
            if self.fields[name.name].kind == "edited" and name.start is None:
                self.error("ACCEPT vers une PICTURE éditée non pris en charge")
            self.accept("END-ACCEPT")
            return Stmt("accept", (name,), line)
        if verb == "MOVE" and (self.at("CORRESPONDING") or self.at("CORR")):
            # cb_emit_move_corresponding: one MOVE per matching pair.
            self.take()
            source = self.corresponding_group()
            self.expect("TO")
            moves = []
            while True:
                target = self.corresponding_group()
                moves += [Stmt("move", (Expr("var", (a,)), [b], False), line)
                          for a, b in self.corresponding_pairs(source, target, False)]
                if self.t.string or not self.candidates(self.t.key):
                    break
            return Stmt("sequence", (moves,), line)
        if verb in {"ADD", "SUBTRACT"} and (self.at("CORRESPONDING") or self.at("CORR")):
            # cb_emit_corresponding: the receiver's items lead the pairing.
            self.take()
            source = self.corresponding_group()
            self.expect("TO" if verb == "ADD" else "FROM")
            target = self.corresponding_group()
            rounded = self.accept("ROUNDED")
            op = "+" if verb == "ADD" else "-"
            pairs = self.corresponding_pairs(target, source, True)
            items = [(t, Expr(op, (Expr("var", (t,)), Expr("var", (u,)))), rounded) for t, u in pairs]
            stmt = self.arithmetic(verb, None, items, line)
            if stmt.op == "compute":
                # cb_build_optim_add for int operands without ROUNDED/SIZE ERROR.
                stmt = Stmt("compute", (None, [
                    (t, Expr("p_int_add", (t, Expr("var", (u,)), -self.fields[t.name].scale, verb == "SUBTRACT")), r)
                    if not r and self.fields[t.name].scale < 0 and self.fits_int(Expr("var", (u,)))
                    else (t, e, r) for (t, e, r), (_, u) in zip(items, pairs)]), line)
            return stmt
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
            while verb in {"ADD", "SUBTRACT"} and not self.at(separator) and not (verb == "ADD" and self.at("GIVING")):
                values.append(self.expr())
            op = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}[verb]
            operand = values[0]
            for extra in values[1:]:
                operand = Expr("+", (operand, extra))
            if verb == "ADD" and self.accept("GIVING"):
                # ADD a b GIVING c: TO is optional when GIVING is present.
                items = [(ref, Expr("shared", ()), rounded) for ref, rounded in self.rounded_receivers()]
                return self.arithmetic(verb, operand, items, line)
            if verb == "DIVIDE" and self.accept("BY"):
                divisor = self.expr()
                self.expect("GIVING")
                return self.divide_giving(operand, divisor, line)
            self.expect(separator)
            if verb == "DIVIDE":
                # DIVIDE a INTO b GIVING c [REMAINDER r]
                start = self.i
                dividend = self.expr()
                if self.accept("GIVING"):
                    return self.divide_giving(dividend, operand, line)
                self.i = start
            if self.t.string or not self.candidates(self.t.key):
                # Only a GIVING form can take a literal second operand.
                second = self.expr()
                self.expect("GIVING")
                giving = True
            else:
                receivers = self.rounded_receivers()
                giving = self.accept("GIVING")
                if giving:
                    # ADD a TO b GIVING c: b is an x, not an arithmetic_x.
                    self.debug_source()
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
            stmt = self.arithmetic(verb, shared, items, line)
            if stmt.op == "compute" and verb in {"ADD", "SUBTRACT"} and shared is None and self.fits_int(operand):
                # cb_build_optim_add: without ROUNDED or SIZE ERROR an int
                # operand goes through cob_add_int, which first truncates it
                # to the receiver's trailing P positions (15 TO 99P adds 10).
                stmt = Stmt("compute", (None, [
                    (ref, Expr("p_int_add", (ref, operand, -self.fields[ref.name].scale, verb == "SUBTRACT")), rounded)
                    if not rounded and self.fields[ref.name].kind == "number" and self.fields[ref.name].scale < 0
                    else (ref, expr, rounded) for ref, expr, rounded in items]), line)
            return stmt
        if verb == "IF":
            cond = self.condition()
            self.accept("THEN")
            yes = self.block({"ELSE", "END-IF"})
            # if_else_statements: each branch needs a statement; an empty true
            # branch before ELSE is a missing-statement (an error with -std=cobol85).
            otherwise = self.accept("ELSE")
            if not yes and (not otherwise or STD == "cobol85"):
                self.error("IF without imperative statement")
            # Without END-IF, a further ELSE belongs to an enclosing IF.
            no = self.block({"END-IF", "ELSE"}) if otherwise else []
            if otherwise and not no:
                self.error("ELSE without imperative statement")
            # Without END-IF, the IF also ends where its branch does: at the
            # scope terminator or WHEN of an enclosing statement (block).
            ended = self.at(".") or self.at("ELSE") or self.at("WHEN") or (
                not self.t.string and self.t.key.startswith("END-") and self.t.key in BOUNDARIES)
            if not self.accept("END-IF") and not ended:
                self.error("END-IF ou point attendu")
            return Stmt("if", (cond, yes, no), line)
        if verb == "ALTER":
            # ALTER procedure-name TO [PROCEED TO] procedure-name, repeated.
            pairs = []
            while True:
                source = self.procedure_reference()
                self.expect("TO")
                if self.accept("PROCEED"):
                    self.expect("TO")
                pairs.append((source, self.procedure_reference()))
                self.accept(",")
                if self.t.string or self.t.key in BOUNDARIES or self.t.key in VERBS \
                        or not re.fullmatch(r"[A-Z0-9_][A-Z_0-9-]*", self.t.key):
                    break
            return Stmt("sequence", ([Stmt("alter", pair, line) for pair in pairs],), line)
        if verb == "GO":
            self.accept("TO")
            targets = []
            while not self.at("DEPENDING") and (self.t.string or self.t.key not in BOUNDARIES):
                targets.append(self.procedure_reference())
            controller = None
            if not targets:
                # GO TO without procedure-name (obsolete): no code of its
                # own, only the target an ALTER gives its paragraph.
                if self.at("DEPENDING"):
                    self.error("GO TO DEPENDING ON requiert des cibles")
                return Stmt("goto", ([], None), line)
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
            # An all-digit word is a procedure name unless TIMES follows it.
            numeric_name = (not self.t.string and re.fullmatch(r"\d+", self.t.key)
                            and self.tokens[self.i + 1].key != "TIMES")
            if numeric_name or (self.t.key not in {"UNTIL", "VARYING", "WITH", "TEST", "FOREVER"} | VERBS and not self.t.string
                                and not self.candidates(self.t.key)
                                and re.fullmatch(r"[A-Z_][A-Z_0-9-]*|\d[A-Z0-9-]*[A-Z][A-Z_0-9-]*", self.t.key)):
                target = [self.procedure_reference()]
                if self.accept("THRU") or self.accept("THROUGH"):
                    target.append(self.procedure_reference())
            test_after = False
            # perform_test: [WITH] TEST BEFORE|AFTER.
            if self.accept("WITH") or self.at("TEST"):
                self.expect("TEST")
                if self.accept("AFTER"):
                    test_after = True
                else:
                    self.expect("BEFORE")
            mode, control = "once", ()
            if self.at("UNTIL") and self.tokens[self.i + 1].key == "EXIT" and not self.tokens[self.i + 1].string:
                # cond_or_exit: UNTIL EXIT is cb_build_perform_forever.
                self.take(); self.take()
                mode = "forever"
            elif self.at("FOREVER") and self.tokens[self.i + 1].key != "TIMES" and self.accept("FOREVER"):
                if test_after:
                    self.error("WITH TEST requiert UNTIL ou VARYING")
                mode = "forever"
            elif self.accept("UNTIL"):
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
                self.integer_value(count)
                mode, control = "times", (count,)
            elif test_after:
                self.error("WITH TEST requiert UNTIL ou VARYING")
            if target:
                body = [Stmt("call", (target,), line)]
                if self.debugging_mode and not self.in_debugging:
                    # cb_emit_perform: DEBUG-CONTENTS for a PERFORM of procedures.
                    return Stmt("sequence", ([Stmt("debug_contents", ("PERFORM LOOP",), line),
                                              Stmt("loop", (mode, control, body), line)],), line)
            else:
                # An inline PERFORM without TIMES/UNTIL/VARYING runs once.
                # perform_stack: EXIT PERFORM is only valid inside one.
                self.inline_performs = getattr(self, "inline_performs", 0) + 1
                try:
                    body = self.block({"END-PERFORM"})
                finally:
                    self.inline_performs -= 1
                self.expect("END-PERFORM")
            return Stmt("loop", (mode, control, body), line)
        if verb == "EVALUATE":
            # cb_emit_evaluate: each WHEN group is one IF whose condition ORs
            # its WHEN lines, each the AND of evaluate_test over ALSO positions.
            subjects = [self.evaluate_subject()]
            while self.accept("ALSO"):
                subjects.append(self.evaluate_subject())
            branches, otherwise = [], []
            stops = {"WHEN", "END-EVALUATE", "ELSE", "END-IF", "END-PERFORM"}
            while self.at("WHEN"):
                self.take()
                if self.accept("OTHER"):
                    otherwise = self.block(stops - {"WHEN"})
                    break
                condition = None
                while True:
                    tests = [self.evaluate_object(subjects[0])]
                    while self.accept("ALSO"):
                        if len(tests) >= len(subjects):
                            self.error("wrong number of WHEN parameters")
                        tests.append(self.evaluate_object(subjects[len(tests)]))
                    if len(tests) != len(subjects):
                        self.error("wrong number of WHEN parameters")
                    line_test = tests[0]
                    for test in tests[1:]:
                        line_test = Expr("and", (line_test, test))
                    condition = line_test if condition is None else Expr("or", (condition, line_test))
                    if self.at("WHEN") and not self.tokens[self.i + 1].string and self.tokens[self.i + 1].key != "OTHER":
                        self.take()
                        continue
                    break
                branches.append((condition, self.block(stops)))
            if not branches and not otherwise:
                self.error("EVALUATE requiert au moins un WHEN")
            self.accept("END-EVALUATE")
            return Stmt("evaluate", (None, branches, otherwise), line)
        if verb == "INITIALIZE":
            targets = self.targets()
            with_filler = False
            if self.accept("WITH"):
                self.expect("FILLER")
                with_filler = True
            # REPLACING {category [DATA] BY value} ...: without DEFAULT only
            # the items of these categories change (cb_emit_initialize).
            replacing = []
            if self.accept("REPLACING"):
                categories = {"ALPHABETIC", "ALPHANUMERIC", "NUMERIC", "ALPHANUMERIC-EDITED", "NUMERIC-EDITED"}
                while not self.t.string and self.t.key in categories:
                    category = self.take().key
                    self.accept("DATA")
                    self.expect("BY")
                    if any(category == c for c, _ in replacing):
                        self.error(f"INITIALIZE REPLACING {category} dupliqué")
                    replacing.append((category, self.expr(primary=True)))
                if not replacing:
                    self.error("INITIALIZE REPLACING requiert une catégorie")
            if self.at("DEFAULT") or self.at("ALL") or self.at("TO") or self.at("THEN"):
                self.error("INITIALIZE VALUE/DEFAULT non pris en charge")
            self.accept("END-INITIALIZE")
            return Stmt("initialize", (targets, with_filler, replacing), line)
        if verb == "STOP":
            if self.t.string or re.fullmatch(r"[+-]?\d*\.?\d+", self.t.key) \
                    or self.t.key in {"SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES", "QUOTE", "QUOTES"}:
                # STOP literal (obsolete): DISPLAY the literal, then ACCEPT
                # OMITTED waits for a line, as cb_emit_display/cb_emit_accept.
                value = self.expr()
                return Stmt("sequence", ([Stmt("display", ([value], True, "stdout"), line),
                                          Stmt("accept_omitted", (), line)],), line)
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
        if verb in {"INITIATE", "GENERATE", "TERMINATE"}:
            # cb_emit_initiate/generate/terminate: report names, or for
            # GENERATE one report name or DETAIL report group.
            names = []
            while not self.t.string and (self.t.key in self.reports or (verb == "GENERATE" and not names and any(
                    self.t.key in report.groups for report in self.reports.values()))):
                names.append(self.take().key)
                if verb == "GENERATE":
                    break
            if not names:
                self.error(f"{verb} requiert un nom de rapport" + (" ou de groupe DETAIL" if verb == "GENERATE" else ""))
            if verb != "GENERATE":
                return Stmt(verb.lower(), (names,), line)
            name = names[0]
            if self.accept("IN") or self.accept("OF"):
                self.error("GENERATE de groupe qualifié non pris en charge")
            if name in self.reports:
                return Stmt("generate", (name, None), line)
            owners = [report for report in self.reports.values() if name in report.groups]
            if len(owners) != 1:
                self.error(f"groupe de rapport ambigu: {name}")
            index = owners[0].groups[name]
            from .report_parser import DETAIL
            if not owners[0].report_lines[index].flags & DETAIL:
                self.error(f"GENERATE {name}: groupe de rapport qui n'est pas DETAIL")
            return Stmt("generate", (owners[0].name, index), line)
        if verb == "CANCEL":
            targets = []
            while self.t.string or (self.t.key not in BOUNDARIES and self.candidates(self.t.key)):
                targets.append(("literal", self.take().text) if self.t.string else ("dynamic", self.variable()))
            if not targets:
                self.error("CANCEL requiert un programme")
            return Stmt("cancel", (targets,), line)
        if verb == "INSPECT":
            return self.inspect_statement(line)
        if verb == "STRING":
            return self.string_statement(line)
        if verb == "UNSTRING":
            return self.unstring_statement(line)
        if verb == "CONTINUE":
            return Stmt("continue", (), line)
        if verb == "ENTRY":
            return self.entry_statement(line)
        if verb in {"ENABLE", "DISABLE", "PURGE", "RECEIVE", "SEND"}:
            return self.communication_statement(verb, line)
        if verb == "NEXT":
            self.expect("SENTENCE")
            return Stmt("next_sentence", (), line)
        if verb == "EXIT":
            if self.accept("PARAGRAPH"):
                return Stmt("exit_paragraph", (), line)
            if self.accept("SECTION"):
                return Stmt("exit_section", (), line)
            if self.accept("PROGRAM"):
                return Stmt("exit_program", (), line)
            if self.accept("PERFORM"):
                cycle = self.accept("CYCLE")
                if not getattr(self, "inline_performs", 0):
                    self.error("EXIT PERFORM is only valid with inline PERFORM")
                if self.debugging_mode:
                    self.error("EXIT PERFORM sous DEBUGGING MODE non modélisé")
                return Stmt("exit_perform", (bool(cycle),), line)
            if not self.t.string and self.t.key in BOUNDARIES:
                return Stmt("continue", (), line)
            self.error("EXIT nu, EXIT PARAGRAPH ou EXIT SECTION attendu")
        self.error(f"instruction non prise en charge: {verb}")

    def eop_start(self, offset=0):
        """The scanner's EOP token: [AT] END-OF-PAGE or [AT] EOP."""
        t = self.tokens[min(self.i + offset, len(self.tokens) - 1)]
        if not t.string and t.key == "AT":
            t = self.tokens[min(self.i + offset + 1, len(self.tokens) - 1)]
        return not t.string and t.key in {"END-OF-PAGE", "EOP"}

    def eop_handlers(self):
        """at_eop_clauses: AT END-OF-PAGE [NOT AT END-OF-PAGE], or the
        reverse order, which cobol85.conf rejects (unconformable)."""
        bodies = {}
        while len(bodies) < 2:
            negated = self.at("NOT") and self.eop_start(1)
            if not (negated or self.eop_start()) or negated in bodies:
                break
            if not negated and bodies and STD == "cobol85":
                self.error("NOT AT END-OF-PAGE before AT END-OF-PAGE")
            if negated:
                self.take()
            self.accept("AT")
            self.take()
            bodies[negated] = self.block({"NOT", "END-WRITE"})
            if not bodies[negated]:
                self.error(f"{'NOT AT' if negated else 'AT'} END OF PAGE without imperative statement")
        if self.at("INVALID") or (self.at("NOT") and self.tokens[self.i + 1].key == "INVALID"):
            self.error("INVALID KEY limité aux fichiers RELATIVE et INDEXED")
        self.accept("END-WRITE")
        return bodies.get(False, []), bodies.get(True, [])

    def invalid_key(self, stops):
        self.expect("INVALID")
        self.accept("KEY")
        body = self.block(stops)
        if not body:
            self.error("instruction attendue après INVALID KEY")
        return body

    def index_key(self, spec, ref):
        """cob_findkey_attr: the key whose field starts where the KEY item
        starts; the item's size is the compared (partial) length."""
        f = self.fields[ref.name]
        root = ref.name.split(".")[0]
        if ref.indices or ref.start is not None or f.dimensions or root not in spec.records:
            self.error(f"KEY {f.label} doit être un champ de l'enregistrement de {spec.name}")
        offset = f.offset - self.fields[root].offset
        for index, (_, key_offset, size, _) in enumerate([spec.record_key, *spec.alternate_keys]):
            if key_offset == offset:
                if f.size > size:
                    self.error(f"KEY {f.label} plus longue que la clé du fichier")
                return index, f.size
        self.error(f"KEY {f.label} ne désigne pas une clé de {spec.name}")

    def key_handlers(self, file_name, ending):
        """[INVALID KEY ...] [NOT INVALID KEY ...] [END-x], RELATIVE files only."""
        invalid, valid = [], []
        if self.at("INVALID"):
            invalid = self.invalid_key({"NOT", ending})
        if self.at("NOT") and self.tokens[self.i + 1].key == "INVALID":
            self.take()
            valid = self.invalid_key({ending})
        if (invalid or valid) and self.files[file_name].organization not in {"RELATIVE", "INDEXED"}:
            self.error("INVALID KEY limité aux fichiers RELATIVE et INDEXED")
        self.accept(ending)
        return invalid, valid

    def corresponding_group(self):
        ref = self.variable()
        f = self.fields[ref.name]
        if ref.start is not None or f.picture or not f.children:
            self.error(f"'{f.label}' is not a group name")
        return ref

    def corresponding_pairs(self, first, second, arithmetic):
        """emit_corresponding / emit_move_corresponding: children of `first`
        in order, matched by name with children of `second`; REDEFINES, OCCURS
        and FILLER items never match."""
        pairs = []
        for c1 in self.fields[first.name].children:
            f1 = self.fields[c1]
            if f1.redefines or f1.table or f1.filler:
                continue
            for c2 in self.fields[second.name].children:
                f2 = self.fields[c2]
                if f2.redefines or f2.table or f2.filler or f1.label != f2.label:
                    continue
                r1, r2 = DataRef(c1, first.indices), DataRef(c2, second.indices)
                if f1.children and f2.children:
                    pairs += self.corresponding_pairs(r1, r2, arithmetic)
                elif not arithmetic or (not f1.children and not f2.children
                                        and f1.kind == "number" and f2.kind == "number"):
                    pairs.append((r1, r2))
        return pairs

    def rounded_receivers(self):
        receivers = [(self.target_variable(), self.accept("ROUNDED"))]
        while not self.t.string and self.candidates(self.t.key):
            receivers.append((self.target_variable(), self.accept("ROUNDED")))
        return receivers

    def target_variable(self):
        ref = self.variable()
        self.debug_target()
        return ref

    def string_operand(self, delimiter=False):
        """An x of STRING / UNSTRING: identifier, alphanumeric or unsigned integer literal, figurative."""
        t = self.t
        if not t.string and t.key in INSPECT_FIGURATIVES:
            self.take()
            return Expr("all", (self.figurative_value(t.key),))
        if not t.string and t.key in self.symbolic and not self.candidates(t.key):
            self.take()
            return Expr("all", (chr(self.symbolic[t.key]),))
        if not t.string and t.key == "ALL" and self.tokens[self.i + 1].string:
            self.take()
            return Expr("all", (self.take().text,), literal_all=True)
        if t.string:
            self.take()
            return Expr("text", (t.text,))
        if re.fullmatch(r"\d+", t.text):
            self.take()
            return Expr("text", (t.text,))
        if not self.candidates(t.key):
            self.error("opérande STRING/UNSTRING attendu")
        ref = self.variable()
        f = self.fields[ref.name]
        if ref.start is None and f.kind == "number" and f.usage != "DISPLAY":
            self.error(f"'{f.label}' is not USAGE DISPLAY")
        return Expr("var", (ref,))

    def integer_item(self, clause):
        ref = self.variable()
        f = self.fields[ref.name]
        if ref.start is not None or f.children or f.kind != "number" or f.scale != 0 or f.usage == "INDEX":
            self.error(f"{clause} requiert un entier numérique élémentaire sans P")
        return ref

    def overflow_handlers(self, ending):
        stops = {ending, "ELSE", "END-IF", "END-PERFORM", "WHEN", "END-EVALUATE"}
        overflow, success = [], []
        if self.at("ON") or self.at("OVERFLOW"):
            self.accept("ON")
            self.expect("OVERFLOW")
            overflow = self.block(stops | {"NOT"})
        if self.at("NOT"):
            self.take()
            self.accept("ON")
            self.expect("OVERFLOW")
            success = self.block(stops)
        self.accept(ending)
        return overflow, success

    def string_statement(self, line):
        groups, items = [], []
        while not self.at("INTO"):
            items.append(self.string_operand())
            if self.accept("DELIMITED"):
                self.accept("BY")
                delimiter = None if self.accept("SIZE") else self.string_operand()
                groups.append((tuple(items), delimiter))
                items = []
        if items:
            groups.append((tuple(items), None))
        if not groups:
            self.error("STRING requiert des sources")
        self.expect("INTO")
        target = self.variable()
        f = self.fields[target.name]
        if target.start is not None or f.kind != "text" or f.alnum_edit or f.justified:
            self.error("STRING INTO limité aux champs alphanumériques ou groupes")
        pointer = None
        if self.at("WITH") or self.at("POINTER"):
            self.accept("WITH")
            self.expect("POINTER")
            pointer = self.integer_item("POINTER")
        overflow, success = self.overflow_handlers("END-STRING")
        return Stmt("string", (tuple(groups), target, pointer, overflow, success), line)

    def unstring_statement(self, line):
        if self.t.string or not self.candidates(self.t.key):
            self.error("UNSTRING d'un littéral non pris en charge")
        source = self.variable()
        delimiters = []
        if self.accept("DELIMITED"):
            self.accept("BY")
            while True:
                all_flag = self.accept("ALL")
                operand = self.string_operand()
                if operand.op == "all" and operand.literal_all:
                    self.error("ALL littéral non admis comme délimiteur")
                delimiters.append((operand, all_flag))
                if not self.accept("OR"):
                    break
        self.expect("INTO")
        targets = []
        while not self.t.string and self.candidates(self.t.key):
            target = self.variable()
            delimiter = count = None
            if self.accept("DELIMITER"):
                self.accept("IN")
                delimiter = self.variable()
            if self.accept("COUNT"):
                self.accept("IN")
                count = self.integer_item("COUNT")
            targets.append((target, delimiter, count))
        if not targets:
            self.error("UNSTRING INTO requiert un receveur")
        pointer = tallying = None
        if self.at("WITH") or self.at("POINTER"):
            self.accept("WITH")
            self.expect("POINTER")
            pointer = self.integer_item("POINTER")
        if self.accept("TALLYING"):
            self.accept("IN")
            tallying = self.variable()
            if self.fields[tallying.name].kind != "number":
                self.error("TALLYING requiert un compteur numérique")
        overflow, success = self.overflow_handlers("END-UNSTRING")
        return Stmt("unstring", (source, tuple(delimiters), tuple(targets), pointer, tallying, overflow, success), line)

    def inspect_operand(self, all_allowed=False):
        """An INSPECT operand: a DISPLAY identifier, an alphanumeric literal or
        a figurative constant (an "all" Expr, COB_TYPE_ALPHANUMERIC_ALL)."""
        t = self.t
        if t.string:
            self.take()
            return Expr("text", (t.text,))
        if t.key == "ALL":
            if not all_allowed:
                self.error("ALL littéral non admis ici")
            self.take()
            operand = self.inspect_operand()
            if operand.op == "var":
                self.error("ALL requiert un littéral")
            return Expr("all", operand.args, literal_all=True) if operand.op == "text" else operand
        if t.key in INSPECT_FIGURATIVES:
            self.take()
            value = self.figurative_value(t.key)
            native = {"HIGH": "\xff", "LOW-": "\x00"}.get(t.key[:4])
            return Expr("all", (value,), memset=value == native)
        if t.key in self.symbolic and not self.candidates(t.key):
            self.take()
            return Expr("all", (chr(self.symbolic[t.key]),))
        if re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)", t.text):
            self.error("littéral numérique non admis dans INSPECT (cobc: is not an alphanumeric literal)")
        if not self.candidates(t.key):
            self.error("opérande INSPECT attendu")
        ref = self.variable()
        f = self.fields[ref.name]
        if f.kind == "number" and f.usage not in {"DISPLAY"} and ref.start is None:
            self.error(f"'{f.label}' is not USAGE DISPLAY")
        return Expr("var", (ref,))

    def tallying_counter_ahead(self):
        """identifier FOR: a counter, not a value to count."""
        if self.t.string or not self.candidates(self.t.key):
            return False
        position = self.i
        try:
            self.variable()
            return self.at("FOR")
        except CobolError:
            return False
        finally:
            self.i = position

    def inspect_operand_start(self):
        t = self.t
        return t.string or t.key in INSPECT_FIGURATIVES or (t.key in self.symbolic and not self.candidates(t.key)) \
            or (t.key not in BOUNDARIES and bool(self.candidates(t.key)))

    def operand_size(self, e):
        """calc_reference_size / literal size for validate_inspect; 0 if unknown."""
        if e.op == "text":
            return len(e.args[0])
        if e.op == "all":
            return 0
        ref = e.args[0]
        size = self.fields[ref.name].size
        if ref.start is None:
            return size
        if ref.length is not None:
            return int(ref.length.args[0]) if ref.length.op == "number" else 0
        return size - int(ref.start.args[0]) + 1 if ref.start.op == "number" else 0

    def inspect_region(self):
        region = []
        for _ in range(2):
            word = "BEFORE" if self.at("BEFORE") else "AFTER" if self.at("AFTER") else None
            if word is None or any(w == word.lower() for w, _ in region):
                break
            self.take()
            self.accept("INITIAL")
            region.append((word.lower(), self.inspect_operand()))
        return tuple(region)

    def inspect_statement(self, line):
        if self.at("BACKWARD"):
            self.error("INSPECT BACKWARD non pris en charge (cobc: PENDING)")
        if self.t.string or (self.at("FUNCTION") and not self.candidates("FUNCTION")):
            # send_identifier: a literal or an alphanumeric function, for
            # TALLYING only (cb_emit_inspect).
            target = self.expr(primary=True)
            if target.op == "function" and self.FUNCTIONS[target.args[0]][1] != "text":
                self.error("cible INSPECT fonction numérique invalide")
            if target.op not in {"text", "function"}:
                self.error("cible INSPECT littérale ou fonction non prise en charge")
        elif not self.candidates(self.t.key):
            self.error("cible INSPECT littérale ou fonction non prise en charge")
        else:
            target = self.variable()
        clauses = []
        if self.accept("TALLYING"):
            items, counter, previous = [], None, None
            while True:
                if self.at("CHARACTERS"):
                    # check_preceding_tallying_phrases lets ALL/LEADING/TRAILING
                    # precede CHARACTERS, which then counts characters.
                    if previous is None:
                        self.error("missing FOR phrase before CHARACTERS/ALL/LEADING/TRAILING phrase")
                    self.take()
                    items.append((counter, "characters", None, self.inspect_region()))
                    previous = "characters"
                elif self.at("ALL") or self.at("LEADING") or self.at("TRAILING"):
                    if previous is None:
                        self.error("missing FOR phrase before CHARACTERS/ALL/LEADING/TRAILING phrase")
                    if previous in {"characters", "keyword"}:
                        self.error("missing value between ALL/LEADING/TRAILING words")
                    mode = self.take().key.lower()
                    previous = "keyword"
                elif self.tallying_counter_ahead():
                    if previous == "keyword":
                        self.error("FOR phrase cannot immediately follow ALL/LEADING/TRAILING")
                    if previous == "for":
                        self.error("missing CHARACTERS/ALL/LEADING/TRAILING phrase after FOR phrase")
                    counter = self.variable()
                    self.expect("FOR")
                    f = self.fields[counter.name]
                    if f.kind != "number" or counter.start is not None or f.usage == "INDEX" or f.index_for:
                        self.error("compteur TALLYING numérique requis")
                    previous = "for"
                elif previous in {"keyword", "value"} and self.inspect_operand_start():
                    value = self.inspect_operand()
                    items.append((counter, mode, value, self.inspect_region()))
                    previous = "value"
                else:
                    break
            if previous not in {"characters", "value"}:
                self.error("TALLYING clause is incomplete")
            clauses.append(("tallying", tuple(items)))
        if isinstance(target, Expr) and (self.at("REPLACING") or self.at("CONVERTING")):
            self.error(f"invalid target for {self.t.key}")
        if self.accept("REPLACING"):
            items, mode = [], None
            while True:
                if self.accept("CHARACTERS"):
                    self.expect("BY")
                    to = self.inspect_operand()
                    if to.op == "text" and len(to.args[0]) != 1:
                        self.error("operand has wrong size")
                    items.append(("characters", None, to, self.inspect_region()))
                    mode = None
                    continue
                keyword = next((w for w in ("ALL", "LEADING", "FIRST", "TRAILING") if self.at(w)), None)
                if keyword:
                    self.take()
                    mode = keyword.lower()
                elif not self.inspect_operand_start():
                    break
                if mode is None:
                    self.error("INSPECT missing ALL/FIRST/LEADING/TRAILING")
                source = self.inspect_operand()
                self.expect("BY")
                to = self.inspect_operand(all_allowed=True)
                self.inspect_sizes(source, to, "REPLACING")
                items.append((mode, source, to, self.inspect_region()))
            if not items:
                self.error("REPLACING incomplet")
            clauses.append(("replacing", tuple(items)))
        if not clauses:
            if not self.accept("CONVERTING"):
                self.error("TALLYING, REPLACING ou CONVERTING attendu")
            source = self.inspect_operand()
            self.expect("TO")
            to = self.inspect_operand(all_allowed=True)
            self.inspect_sizes(source, to, "CONVERTING")
            clauses.append(("converting", source, to, self.inspect_region()))
        return Stmt("inspect", (target, tuple(clauses)), line)

    def inspect_sizes(self, source, to, clause):
        """validate_inspect: a figurative source counts as size 1, a figurative target is unchecked."""
        size1 = 1 if source.op == "all" else self.operand_size(source)
        # An ALL literal target keeps its literal size; a figurative has none.
        size2 = self.operand_size(to) if to.op != "all" else (len(to.args[0]) if to.literal_all else 0)
        if size1 and size2 and size1 != size2:
            self.error(f"{clause} operands differ in size")

    def table_indexes(self, table):
        return [name for name, field in self.fields.items() if field.index_for == table]

    def search_statement(self, line):
        """SEARCH [ALL] table, as cobc's output_search_whens/output_search_all."""
        search_all = self.accept("ALL")
        label = self.name()
        qualifiers = []
        while self.accept("OF") or self.accept("IN"):
            qualifiers.append(self.name())
        table = DataRef(self.resolve(label, qualifiers))
        field = self.fields[table.name]
        if self.at("(") or not field.table:
            self.error("SEARCH requiert une table OCCURS sans indice")
        indexes = self.table_indexes(table.name)
        if not indexes:
            self.error("SEARCH requiert une table INDEXED BY")
        varying = None
        if not search_all and self.accept("VARYING"):
            varying = self.variable()
            var = self.fields[varying.name]
            if varying.indices or varying.start is not None or not (
                    var.index_for or var.usage == "INDEX" or (var.kind == "number" and var.scale == 0)):
                self.error("SEARCH VARYING requiert un index ou un entier")
        index = varying.name if varying is not None and varying.name in indexes else indexes[0]
        at_end = None
        if self.accept("AT") or self.at("END"):
            self.expect("END")
            at_end = self.block({"WHEN"})
        whens = []
        while self.accept("WHEN"):
            condition = self.condition()
            whens.append((condition, self.block({"WHEN", "END-SEARCH"})))
        if not whens:
            self.error("SEARCH requiert au moins un WHEN")
        self.accept("END-SEARCH")
        if not search_all:
            return Stmt("search", (table.name, index, varying, at_end, whens), line)
        if len(whens) != 1:
            self.error("SEARCH ALL requiert un seul WHEN")
        # cb_build_search_all: one comparison per declared key, in key order;
        # ascending KEY = value, descending value = KEY.
        bound = {}

        def collect(expr):
            if expr.op == "condition":
                # build_cond_88: one VALUE gives parent = value; more is an OR.
                ref = expr.args[0]
                condition = self.conditions[ref.name]
                if len(condition.values) != 1 or condition.values[0][0] is not condition.values[0][1]:
                    self.error("invalid SEARCH ALL condition")
                token = condition.values[0][0]
                if not token.string and not re.fullmatch(r"[+-]?\d+(\.\d+)?", token.text):
                    self.error("condition SEARCH ALL avec constante figurative non prise en charge")
                expr = Expr("cmp=", (Expr("var", (DataRef(condition.parent, ref.indices),)),
                                     Expr("text" if token.string else "number", (token.text,))))
            if expr.op == "and":
                collect(expr.args[0]); collect(expr.args[1])
            elif expr.op == "cmp=":
                left, right = expr.args
                for key, other in ((left, right), (right, left)):
                    if key.op == "var" and any(self.key_field(table.name, label) == key.args[0].name
                                               for _, label in field.search_keys):
                        bound[key.args[0].name] = (key, other)
                        return
                self.error("condition SEARCH ALL: une clé ASCENDING/DESCENDING est requise")
            else:
                self.error("condition SEARCH ALL limitée à clé = valeur [AND ...]")
        collect(whens[0][0])
        keys = []
        for descending, label in field.search_keys:
            name = self.key_field(table.name, label)
            if name in bound:
                key, value = bound[name]
                keys.append((value, key) if descending else (key, value))
        return Stmt("search_all", (table.name, index, at_end, keys, whens[0][1]), line)

    def table_sort_statement(self, line):
        """SORT table [ON ASCENDING|DESCENDING KEY [names]]... (sort_merge_body,
        cb_emit_sort_init): without KEY the first OCCURS KEY, with KEY and no
        names the element itself; each key read at its offset in its parent."""
        def qualified_name():  # qualified_word
            label, qualifiers = self.name(), []
            while self.accept("OF") or self.accept("IN"):
                qualifiers.append(self.name())
            return DataRef(self.resolve(label, tuple(qualifiers)))
        ref = qualified_name()
        table = self.fields[ref.name]
        if self.at("(") or len(table.dimensions) != 1 or not table.table:
            self.error("SORT limité à une table à une dimension, sans indice")
        keys, phrase = [], False
        while self.accept("ON") or self.at("ASCENDING") or self.at("DESCENDING"):
            if not (self.at("ASCENDING") or self.at("DESCENDING")):
                self.error("ASCENDING ou DESCENDING attendu")
            phrase = True
            descending = self.take().key == "DESCENDING"
            self.accept("KEY")
            self.accept("IS")
            named = False
            while not self.t.string and self.candidates(self.t.key) and not self.at("ON"):
                key = qualified_name()
                if not (key.name == ref.name or key.name.startswith(ref.name + ".")):
                    self.error("clé de SORT de table requise dans l'élément, sans indice")
                keys.append((descending, key.name))
                named = True
            if not named:
                keys.append((descending, ref.name))
        if not phrase:
            if not table.search_keys:
                self.error("table SORT requires KEY phrase")
            descending, label = table.search_keys[0]
            keys.append((descending, self.key_field(ref.name, label)))
        if self.accept("WITH") or self.at("DUPLICATES"):
            # glibc's qsort is a merge sort: equal keys keep their order.
            self.expect("DUPLICATES")
            self.accept("IN")
            self.accept("ORDER")
        if self.accept("COLLATING") or self.at("SEQUENCE"):
            self.expect("SEQUENCE")
            self.accept("IS")
            self.check_identity_alphabet(self.t, self.name(), "SORT COLLATING SEQUENCE")
        if self.at("INPUT") or self.at("USING") or self.at("OUTPUT") or self.at("GIVING"):
            self.error("USING invalid with table SORT")
        sort_keys = []
        for descending, name in keys:
            f = self.fields[name]
            # cb_emit_sort_init: the key's offset in its parent, not in the element.
            offset = f.offset - (self.fields[f.parent].offset if f.parent else 0)
            if f.kind == "number" and f.usage == "INDEX":
                self.error("clé de SORT de table USAGE INDEX non prise en charge")
            if offset + f.size > table.size:
                self.error("clé de SORT de table lue hors de l'élément non prise en charge")
            sort_keys.append((descending, name, offset))
        return Stmt("table_sort", (ref.name, sort_keys), line)

    def key_field(self, table, label):
        names = [name for name, f in self.fields.items()
                 if f.label == label and (name == table or name.startswith(table + "."))]
        if len(names) != 1:
            self.error(f"clé de table introuvable ou ambiguë: {label}")
        return names[0]

    def sort_statement(self, verb, line):
        """SORT/MERGE sd ON ASCENDING/DESCENDING KEY ... as cobc emits it:
        cob_file_sort_init and keys, USING files or a PERFORM of the input
        procedure, GIVING files or a PERFORM of the output procedure, close."""
        if verb == "SORT" and not self.t.string and self.t.key not in self.files and self.candidates(self.t.key):
            return self.table_sort_statement(line)
        name = self.file_name()
        spec = self.files[name]
        if not spec.sort:
            self.error(f"{verb} requiert un fichier SD")
        keys = []
        while self.accept("ON") or self.at("ASCENDING") or self.at("DESCENDING"):
            if not (self.at("ASCENDING") or self.at("DESCENDING")):
                self.error("ASCENDING ou DESCENDING attendu")
            descending = self.take().key == "DESCENDING"
            self.accept("KEY")
            self.accept("IS")
            while not self.t.string and self.candidates(self.t.key):
                key = self.variable()
                field = self.fields[key.name]
                record = next((r for r in spec.records if key.name == r or key.name.startswith(r + ".")), None)
                if record is None or key.indices or key.start is not None or field.dimensions:
                    self.error("clé de tri requise dans l'enregistrement SD, sans indice")
                if field.kind not in {"text", "number"} or (field.kind == "number" and field.usage == "INDEX"):
                    self.error("clé de tri limitée aux champs alphanumériques et numériques")
                keys.append((descending, key))
        if not keys:
            self.error(f"{verb} requiert au moins une clé")
        if self.accept("WITH") or self.at("DUPLICATES"):
            # libcob's sort is stable: records with equal keys keep their order.
            self.expect("DUPLICATES")
            self.accept("IN")
            self.accept("ORDER")
        if self.accept("COLLATING") or self.at("SEQUENCE"):
            self.expect("SEQUENCE")
            self.accept("IS")
            self.check_identity_alphabet(self.t, self.name(), f"{verb} COLLATING SEQUENCE")

        def procedure():
            self.accept("IS")
            target = [self.name()]
            if self.accept("THRU") or self.accept("THROUGH"):
                target.append(self.name())
            return ("procedure", target)

        def files(word):
            names = []
            while not self.t.string and self.t.key in self.files:
                names.append(self.file_name())
            if not names:
                self.error(f"{word} requiert au moins un fichier")
            for file_name in names:
                other = self.files[file_name]
                if other.sort or other.organization not in {"SEQUENTIAL", "LINE SEQUENTIAL"}:
                    self.error(f"{word} limité aux fichiers SEQUENTIAL et LINE SEQUENTIAL")
                # A variable SEQUENTIAL file: cob_copy_check of the size read
                # (USING) or of record_max (GIVING), as libcob does.
                if other.depending or (other.record_min != other.record_max and other.organization != "SEQUENTIAL"):
                    self.error(f"{word} limité aux fichiers à enregistrements fixes ou SEQUENTIAL variables sans DEPENDING")
            return (word.lower(), names)

        if self.accept("INPUT"):
            if verb == "MERGE":
                self.error("MERGE n'admet pas INPUT PROCEDURE")
            self.expect("PROCEDURE")
            source = procedure()
        else:
            self.expect("USING")
            source = files("USING")
            if verb == "MERGE" and len(source[1]) < 2:
                self.error("MERGE requiert au moins deux fichiers USING")
        if self.accept("OUTPUT"):
            self.expect("PROCEDURE")
            target = procedure()
        else:
            self.expect("GIVING")
            target = files("GIVING")
        return Stmt("sort", (name, keys, source, target, verb == "MERGE"), line)

    def divide_giving(self, dividend, divisor, line):
        """DIVIDE ... GIVING receivers [REMAINDER r], as cob_div_quotient and
        cob_div_remainder: the remainder is the dividend less the divisor
        times the quotient truncated to the quotient item's scale."""
        receivers = self.rounded_receivers()
        shared = Expr("/", (dividend, divisor))
        items = [(ref, Expr("shared", ()), rounded) for ref, rounded in receivers]
        if self.accept("REMAINDER"):
            if len(receivers) != 1:
                self.error("REMAINDER requiert un seul quotient GIVING")
            quotient = receivers[0][0]
            remainder = self.target_variable()
            q = self.fields[quotient.name]
            if q.kind not in {"number", "edited"} or quotient.start is not None:
                self.error("REMAINDER requiert un quotient numérique")
            # libcob reads both operands before storing the quotient.
            for operand in (dividend, divisor):
                if operand.op == "var" and self.overlaps(operand.args[0], quotient):
                    self.error("REMAINDER avec un quotient recouvrant un opérande non pris en charge")
            items.append((remainder, Expr("remainder", (dividend, divisor, q.scale)), False))
        return self.arithmetic("DIVIDE", shared, items, line)

    def overlaps(self, a, b):
        fa, fb = self.fields[a.name], self.fields[b.name]
        span = lambda f: (f.offset, f.offset + f.size * max(1, f.occurs) if f.table else f.offset + f.size)
        (a0, a1), (b0, b1) = span(fa), span(fb)
        return a0 < b1 and b0 < a1

    def fits_int(self, e):
        """cobc's cb_fits_int for an ADD/SUBTRACT operand."""
        if e.op in {"unary+", "unary-"}:
            e = e.args[0]
            if e.op != "number":
                return False
        if e.op == "number":
            text = e.args[0]
            if "." in text:
                return False
            digits = text.lstrip("0")
            return len(digits) < 10 or (len(digits) == 10 and digits <= "2147483647")
        if e.op != "var" or e.args[0].start is not None:
            return False
        field = self.fields[e.args[0].name]
        if field.children or field.kind != "number":
            return False
        if field.usage == "INDEX":
            return True
        if field.scale > 0:
            return False
        if field.usage == "DISPLAY":
            return field.digits + field.sign_separate < 10
        if field.usage in {"COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL"}:
            return field.digits < 10
        return field.digits <= 9

    def arithmetic(self, verb, shared, items, line):
        ending = "END-" + verb
        error, success, handled = [], [], False
        stops = {ending, "ELSE", "END-IF", "END-PERFORM", "WHEN", "END-EVALUATE"}
        # [ON] SIZE ERROR and NOT [ON] SIZE ERROR; another NOT ON phrase
        # (NOT ON EXCEPTION) belongs to an enclosing statement.
        def size_phrase(offset):
            words = [self.tokens[min(self.i + k, len(self.tokens) - 1)] for k in range(offset, offset + 2)]
            return any(not t.string and t.key == "SIZE" for t in (words if words[0].key == "ON" else words[:1]))
        if size_phrase(0):
            handled = True
            self.accept("ON")
            self.expect("SIZE"); self.expect("ERROR")
            error = self.block(stops | {"NOT"})
            if not error:
                self.error("instruction attendue après ON SIZE ERROR")
        if self.at("NOT") and size_phrase(1):
            self.take()
            handled = True
            self.accept("ON"); self.expect("SIZE"); self.expect("ERROR")
            success = self.block(stops)
            if not success:
                self.error("instruction attendue après NOT ON SIZE ERROR")
        self.accept(ending)
        if handled:
            return Stmt("arithmetic", (shared, items, error, success), line)
        return Stmt("compute", (shared, items), line)

    def targets(self):
        names = [self.target_variable()]
        while not self.t.string and self.candidates(self.t.key):
            names.append(self.target_variable())
        return names

    def validate_calls(self, program):
        def walk(stmts, section=None):
            for s in stmts:
                if s.op == "sort":
                    for kind, targets in (s.args[2], s.args[3]):
                        if kind == "procedure":
                            try:
                                ranges = [program.procedure_range(name) for name in targets]
                            except CobolError as error:
                                raise CobolError(f"ligne {s.line}: {error}") from None
                elif s.op in {"open", "close", "read", "write", "rewrite", "delete", "start"}:
                    names = ([mode_name[1] for mode_name in s.args[0]] if s.op == "open" else
                             [name_lock[0] for name_lock in s.args[0]] if s.op == "close" else [s.args[0]])
                    for name in names:
                        if isinstance(name, str) and name in program.files and program.files[name].sort:
                            raise CobolError(f"ligne {s.line}: entrée-sortie ordinaire sur le fichier SD {name}")
                if s.op in {"call", "goto"}:
                    targets = s.args[0]
                    try:
                        ranges = [program.procedure_range(name) for name in targets]
                    except CobolError as error:
                        raise CobolError(f"ligne {s.line}: {error}") from None
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
                elif s.op == "sequence":
                    walk(s.args[0], section)
                elif s.op in {"string", "unstring"}:
                    walk(s.args[-2], section); walk(s.args[-1], section)
                elif s.op in {"write", "rewrite", "delete", "start", "call_program", "return_sort"}:
                    walk(s.args[-2], section); walk(s.args[-1], section)
                elif s.op == "search":
                    walk(s.args[3] or [], section)
                    for _, body in s.args[4]:
                        walk(body, section)
                elif s.op == "search_all":
                    walk(s.args[2] or [], section); walk(s.args[4], section)
        if program.blocks:
            for block in program.blocks:
                walk(block.body, block.section)
        else:
            walk(program.entry)
            for body in program.paragraphs.values():
                walk(body)
