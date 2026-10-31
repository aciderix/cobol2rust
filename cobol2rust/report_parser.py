"""REPORT SECTION of GnuCOBOL 3.2 (parser.y report_description, tree.c
finalize_report, codegen.c output_report_define_lines/def_fields).

The modelled subset: RD with CONTROLS [FINAL] and a literal PAGE LIMIT,
HEADING, FIRST DETAIL, LAST DETAIL and FOOTING; report groups of TYPE REPORT
HEADING, PAGE HEADING, CONTROL HEADING/FOOTING [name | FINAL], DETAIL, PAGE
FOOTING and REPORT FOOTING with LINE [PLUS] n and NEXT GROUP; elementary
items with PICTURE, COLUMN n and either SOURCE (an identifier, LINE-COUNTER
or PAGE-COUNTER), SUM (build_sum_counter) or an alphanumeric VALUE literal.
GROUP INDICATE, PRESENT WHEN, OCCURS, COLUMN PLUS/LEFT/RIGHT/CENTER, CODE,
SUM UPON and PAGE limits given by data items are refused.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# libcob common.h COB_REPORT_* flags.
LINE, LINE_PLUS = 1 << 0, 1 << 1
RESET_FINAL = 1 << 3
HEADING, FOOTING, PAGE_HEADING, PAGE_FOOTING = 1 << 4, 1 << 5, 1 << 6, 1 << 7
CONTROL_HEADING, CONTROL_HEADING_FINAL, CONTROL_FOOTING, CONTROL_FOOTING_FINAL = 1 << 8, 1 << 9, 1 << 10, 1 << 11
DETAIL = 1 << 12
NEXT_GROUP_LINE, NEXT_GROUP_PLUS, NEXT_GROUP_PAGE = 1 << 13, 1 << 14, 1 << 15
GROUP_INDICATE = 1 << 18
GROUP_TYPES = DETAIL | PAGE_HEADING | PAGE_FOOTING | HEADING | FOOTING | CONTROL_HEADING | CONTROL_HEADING_FINAL \
    | CONTROL_FOOTING | CONTROL_FOOTING_FINAL

TYPES = {"DETAIL": DETAIL, "DE": DETAIL, "PH": PAGE_HEADING, "PF": PAGE_FOOTING,
         "RH": HEADING, "RF": FOOTING}
REFUSED_CLAUSES = {
    "PRESENT": "PRESENT WHEN",
    "ABSENT": "ABSENT WHEN", "OCCURS": "OCCURS", "VARYING": "VARYING", "USAGE": "USAGE",
    "SIGN": "SIGN", "JUSTIFIED": "JUSTIFIED", "JUST": "JUSTIFIED", "BLANK": "BLANK WHEN ZERO",
    "UPON": "SUM UPON",
}
# cob_field_to_string works in a COB_SMALL_BUFF buffer (COB_SMALL_MAX bytes).
SMALL_MAX = 1023
# reportio.c REPORT_MAX_COLS: write_rec cuts longer lines.
MAX_COLS = 999


@dataclass
class ReportEntry:
    level: int
    label: str | None
    flags: int = 0
    line: int = 0
    column: int = 0
    # COLUMN PLUS n (col_or_plus): relative to the previous item of the line.
    column_plus: bool = False
    picture: list = field(default_factory=list)
    source: Expr | None = None
    value: Token | None = None
    children: list = field(default_factory=list)
    item: str | None = None
    size: int = 0
    offset: int = 0
    # TYPE CH/CF identifier: the control item; NEXT GROUP value.
    control: str | None = None
    next_group: int = 0
    # SUM operands: (data item key or None, report item label or None).
    sum: list = field(default_factory=list)
    counter: str | None = None
    prepare_move: tuple | None = None


@dataclass
class ReportField:
    """cob_report_field: column, then a literal or a SOURCE moved to `item`."""
    column: int
    literal: bytes | None = None
    source: Expr | None = None
    item: str | None = None
    line: int = 0
    indicate: bool = False


@dataclass
class ReportLine:
    """cob_report_line: flags, LINE value, fields, child and sister lines."""
    flags: int
    line: int
    fields: list
    child: int | None = None
    sister: int | None = None
    label: str | None = None
    next_group: int = 0
    control: str | None = None


@dataclass
class ReportSpec:
    name: str
    file: str
    lines: int = 0
    columns: int = 0
    heading: int = 0
    first_detail: int = 0
    last_control: int = 0
    last_detail: int = 0
    footing: int = 0
    entries: list = field(default_factory=list)
    report_lines: list = field(default_factory=list)
    groups: dict = field(default_factory=dict)
    size: int = 0
    # CONTROLS in cobc's list order (CB_ADD_TO_CHAIN prepends: last first).
    controls: list = field(default_factory=list)
    control_final: bool = False
    # cob_report_sum_ctr list: (counter, operands, control, control_final, subtotal).
    sums: list = field(default_factory=list)
    move_passes: tuple | None = None


def prepare_sources(p):
    """finalize_report / cb_field_dup: typed WORKING-STORAGE copies for
    references whose address cannot remain in cob_report_field.source."""
    from .frontend import DataRef, Expr, Token
    from .report_positions import normalize
    created = False
    for report in p.reports.values():
        replacements = {}

        def walk(entries):
            nonlocal created
            for entry in entries:
                source = entry.source
                if source is not None and source.op == "var":
                    ref = source.args[0]
                    original = p.fields[ref.name]
                    literal_length = None
                    if ref.start is not None:
                        start, _ = normalize(p, ref.start)
                        length, literal_length = normalize(p, ref.length) if ref.length is not None else (None, None)
                        ref = DataRef(ref.name, ref.indices, start, length)
                        source = Expr("var", (ref,))
                    p.check_constant_positions(original.label, original, ref.indices, ref.start, ref.length)
                    if ref.indices or ref.start is not None or getattr(original, "local", False):
                        if not original.picture or original.usage == "INDEX":
                            p.error("SOURCE de rapport complexe d'un groupe ou USAGE INDEX non pris en charge")
                        if literal_length is not None:
                            picture = f"X({literal_length})"
                        elif original.kind in {"number", "edited"}:
                            digits = original.digits + (max(0, -original.scale) if original.kind == "number" else 0)
                            if original.scale > digits:
                                p.error("SOURCE de rapport complexe à PICTURE P initiale invalide pour cobc 3.2")
                            if original.scale > 0:
                                integer_digits = digits - original.scale
                                picture = (f"S9({integer_digits})V9({original.scale})" if integer_digits else
                                           f"SV9({original.scale})")
                            else:
                                picture = f"S9({digits})"
                        else:
                            picture = f"X({original.size})"
                        key = f"^source^{report.name}^{len(replacements)}"
                        line = p.t.line
                        value = Token("ZERO" if original.kind in {"number", "edited"} else "SPACE", line)
                        p.hidden_item([Token("PIC", line), Token(picture, line), Token("VALUE", line), value], key)
                        entry.prepare_move = (source, key)
                        entry.source = Expr("var", (DataRef(key),))
                        replacements[entry.item] = entry.source
                        created = True
                walk(entry.children)
        walk(report.entries)
        for line in report.report_lines:
            for item in line.fields:
                if item.item in replacements:
                    item.source = replacements[item.item]
    return created


def prepare_moves(report, state):
    """cb_emit_report_moves: two passes, preserving its sticky footing flag.
    Routine generation happens at the first INITIATE/GENERATE/TERMINATE."""
    if report.move_passes is not None:
        return
    footing = FOOTING | CONTROL_FOOTING | CONTROL_FOOTING_FINAL

    def walk(entries, phase, result):
        for entry in entries:
            if entry.flags & footing:
                state[0] = True
            if entry.prepare_move is not None and state[0] == phase:
                result.append(entry.prepare_move)
            if entry.children:
                walk(entry.children, phase, result)
                if entry.flags & footing:
                    state[0] = False
    first, last = [], []
    walk(report.entries, False, first)
    walk(report.entries, True, last)
    report.move_passes = (first, last)


def integer(p, clause):
    """integer_or_zero: a data item for the limit is refused."""
    token = p.t
    if token.string or not token.text.isascii() or not token.text.isdigit():
        p.error(f"{clause} limité à un entier littéral")
    return int(p.take().text)


def page_limits(p, report):
    """page_limit_clause and the defaults of its action."""
    if p.accept("LIMIT"):
        p.accept("IS")
    elif p.accept("LIMITS"):
        p.accept("ARE")
    report.lines = integer(p, "PAGE LIMIT")
    if report.lines > 999:
        p.error("PAGE LIMIT lines > 999")
    p.accept("LINE") or p.accept("LINES")
    if not p.t.string and p.t.text.isdigit() or p.at("COLUMNS") or p.at("COLS"):
        p.error("PAGE LIMIT ... COLUMNS non pris en charge")
    seen = set()
    while True:
        if p.at("HEADING"):
            part = "heading"
            p.take()
        elif p.at("FIRST") or p.at("LAST"):
            start = p.i
            first = p.take().key == "FIRST"
            if not (p.accept("DETAIL") or p.accept("DE")):
                p.i = start
                p.error("LAST CONTROL HEADING non pris en charge" if not first else "FIRST DETAIL attendu")
            part = "first_detail" if first else "last_detail"
        elif p.at("FOOTING"):
            part = "footing"
            p.take()
        elif p.at("LINE-LIMIT") or (p.at("LINE") and p.tokens[p.i + 1].key == "LIMIT"):
            p.error("LINE LIMIT non pris en charge")
        else:
            break
        if part in seen:
            p.error(f"clause RD {part.upper()} dupliquée")
        seen.add(part)
        p.accept("IS")
        setattr(report, part, integer(p, part.upper().replace("_", " ")))
    if not report.heading:
        report.heading = 1
    if not report.first_detail:
        report.first_detail = report.heading
    if report.last_detail:
        report.last_control = report.last_detail
    elif report.footing:
        report.last_control = report.footing
    else:
        report.last_control = report.lines
    if not report.last_detail and not report.footing:
        report.last_detail = report.footing = report.lines
    elif not report.last_detail:
        report.last_detail = report.footing
    elif not report.footing:
        report.footing = report.last_detail


def check_limits(p, report):
    """finalize_report's compile-time checks, then cob_report_initiate's
    PAGE LIMIT and limitCheck tests, refused here since every value is literal."""
    if report.first_detail < 1:
        report.first_detail = 1
    if not report.first_detail >= report.heading:
        p.error("PAGE LIMIT FIRST DETAIL should be >= HEADING")
    if report.footing > 0 and not report.footing >= report.heading:
        p.error("PAGE LIMIT FOOTING should be >= HEADING")
    elif report.last_detail > 0 and not report.last_detail >= report.first_detail:
        p.error("PAGE LIMIT LAST DETAIL should be >= FIRST DETAIL")
    elif report.footing > 0 and not report.footing >= report.last_detail:
        p.error("PAGE LIMIT FOOTING should be >= LAST DETAIL")
    elif not report.lines >= report.footing:
        p.error("PAGE LIMIT LINES should be >= FOOTING")
    if report.lines > 0 and not report.lines >= report.heading:
        p.error(f"INITIATE {report.name} PAGE LIMIT problem")
    # limitCheckOneLine: at run time INITIATE reports the first LINE beyond
    # the limit and leaves the report not initiated (GENERATE then fails).
    report.initiate_error = None
    for line in report.report_lines:
        if line.line > 0 and report.lines > 0 and line.line > report.lines:
            report.initiate_error = f"INITIATE {getattr(report, 'written', report.name)} LINE {line.line} exceeds PAGE LIMIT {report.lines}"
        else:
            beyond = [f.line for f in line.fields if f.line and f.line > report.lines]
            if beyond:
                report.initiate_error = f"INITIATE {getattr(report, 'written', report.name)} LINE {beyond[0]} exceeds PAGE LIMIT"
        if report.initiate_error:
            break


def group_entry(p, report):
    """report_group_description_entry: level, optional name and options."""
    if p.t.string or not p.t.key.isdigit():
        p.error("niveau de groupe de rapport attendu")
    level = int(p.take().key)
    if not 1 <= level <= 49:
        p.error("niveau de groupe de rapport limité à 01-49")
    label = None
    if not p.t.string and p.t.key not in {"TYPE", "LINE", "LINES", "COLUMN", "COL", "COLUMNS", "COLS",
                                          "PIC", "PICTURE", "SOURCE", "VALUE", ".", "FILLER"} | set(REFUSED_CLAUSES):
        label = p.user_word(p.name())
    else:
        p.accept("FILLER")
    entry = ReportEntry(level, label)
    seen = set()

    def once(clause):
        if clause in seen:
            p.error(f"clause {clause} dupliquée")
        seen.add(clause)

    while not p.at("."):
        if p.accept("TYPE"):
            once("TYPE")
            p.accept("IS")
            if p.at("PAGE") or p.at("REPORT"):
                page = p.take().key == "PAGE"
                if p.accept("HEADING"):
                    entry.flags |= PAGE_HEADING if page else HEADING
                elif p.accept("FOOTING"):
                    entry.flags |= PAGE_FOOTING if page else FOOTING
                else:
                    p.error("TYPE PAGE/REPORT HEADING ou FOOTING attendu")
            elif p.at("CONTROL") or p.at("CH") or p.at("CF"):
                word = p.take().key
                heading = word == "CH" or (word == "CONTROL" and p.at("HEADING"))
                if word == "CONTROL" and not (p.accept("HEADING") or p.accept("FOOTING")):
                    p.error("TYPE CONTROL HEADING ou FOOTING attendu")
                p.accept("ON") or p.accept("FOR")
                if p.accept("FINAL"):
                    entry.flags |= CONTROL_HEADING_FINAL if heading else CONTROL_FOOTING_FINAL
                elif p.at("ALL"):
                    p.error("TYPE CONTROL FOOTING ALL non pris en charge")
                else:
                    entry.flags |= CONTROL_HEADING if heading else CONTROL_FOOTING
                    if not p.t.string and p.candidates(p.t.key):
                        ref = p.variable()
                        if ref.indices or ref.start is not None:
                            p.error("contrôle de rapport sans indice ni sous-chaîne requis")
                        entry.control = ref.name
                if p.at("OR"):
                    p.error("TYPE CONTROL ... OR PAGE non pris en charge")
            elif not p.t.string and p.t.key in TYPES:
                entry.flags |= TYPES[p.take().key]
            else:
                p.error("TYPE de groupe de rapport non pris en charge")
        elif p.at("NEXT") and p.tokens[p.i + 1].key == "GROUP":
            once("NEXT GROUP")
            p.take(); p.take()
            p.accept("IS")
            if p.accept("NEXT") or p.accept("PAGE"):
                p.accept("PAGE")
                entry.flags |= NEXT_GROUP_PAGE
            else:
                plus = p.accept("PLUS")
                signed = not p.t.string and p.t.text.startswith("+")
                if signed:
                    token = p.take()
                    entry.next_group = int(token.text[1:]) if token.text[1:].isdigit() else p.error("NEXT GROUP entier attendu")
                else:
                    entry.next_group = integer(p, "NEXT GROUP")
                entry.flags |= NEXT_GROUP_PLUS if plus or signed else NEXT_GROUP_LINE
        elif p.at("GROUP") and not (p.tokens[p.i + 1].string or p.tokens[p.i + 1].key == "."):
            once("GROUP INDICATE")
            p.take()
            p.accept("INDICATE")
            entry.flags |= GROUP_INDICATE
        elif p.at("GROUP"):
            once("GROUP INDICATE")
            p.take()
            entry.flags |= GROUP_INDICATE
        elif p.accept("SUM"):
            once("SUM")
            p.accept("OF")
            while not p.t.string and p.t.key not in {"RESET", "UPON", "."} and not (
                    p.t.key in {"COLUMN", "COL", "COLUMNS", "COLS", "PIC", "PICTURE", "LINE", "LINES", "SOURCE",
                                "VALUE", "NEXT", "TYPE"} | set(REFUSED_CLAUSES)):
                if p.candidates(p.t.key):
                    ref = p.variable()
                    if ref.indices or ref.start is not None:
                        p.error("opérande SUM sans indice ni sous-chaîne requis")
                    entry.sum.append((ref.name, None))
                else:
                    entry.sum.append((None, p.name()))
            if not entry.sum:
                p.error("SUM requiert au moins un opérande")
            if p.accept("RESET"):
                # cobc keeps RESET ON identifier in report_reset, which
                # codegen.c only writes in a comment; RESET FINAL sets a flag.
                p.accept("ON")
                if p.accept("FINAL"):
                    entry.flags |= RESET_FINAL
                else:
                    p.variable()
        elif p.at("LINE") or p.at("LINES"):
            once("LINE")
            if p.take().key == "LINE":
                p.accept("NUMBER") or p.accept("NUMBERS")
            p.accept("IS") or p.accept("ARE")
            if p.at("NEXT"):
                p.error("LINE NEXT PAGE non pris en charge")
            plus = p.accept("PLUS") or p.accept("+")
            entry.line = integer(p, "LINE")
            entry.flags |= LINE | (LINE_PLUS if plus else 0)
            if plus and entry.line == 0:
                p.error("LINE PLUS 0 non pris en charge par cobc")
            if p.at("NEXT") or (not p.t.string and p.t.text.isdigit()):
                p.error("options multiples de LINE non prises en charge")
        elif not p.t.string and p.t.key in {"COLUMN", "COL", "COLUMNS", "COLS"}:
            once("COLUMN")
            p.take()
            p.accept("NUMBER") or p.accept("NUMBERS")
            if p.at("LEFT") or p.at("RIGHT") or p.at("CENTER"):
                p.error("COLUMN LEFT/RIGHT/CENTER non pris en charge")
            p.accept("IS") or p.accept("ARE")
            if p.accept("PLUS") or p.accept("+"):
                # col_or_plus: PLUS 0 is no COLUMN at all.
                entry.column = integer(p, "COLUMN PLUS")
                entry.column_plus = entry.column != 0
            else:
                entry.column = integer(p, "COLUMN")
                if entry.column == 0:
                    p.error("invalid COLUMN integer; must be > 0")
            if not p.t.string and p.t.text.isdigit():
                p.error("liste de COLUMN (OCCURS) non prise en charge")
        elif p.at("PIC") or p.at("PICTURE"):
            once("PICTURE")
            entry.picture = [p.take()]
            if p.at("IS"):
                entry.picture.append(p.take())
            entry.picture.append(p.take())
        elif p.accept("SOURCE"):
            once("SOURCE")
            p.accept("IS")
            if "SUM" in seen:
                p.error("SOURCE et SUM non pris en charge ensemble")
            entry.source = p.expr()
            if entry.source.op not in {"var", "report_counter"}:
                p.error("SOURCE limité à un identifiant, LINE-COUNTER ou PAGE-COUNTER")
            if p.at("ROUNDED"):
                p.error("SOURCE ROUNDED non pris en charge")
        elif p.accept("VALUE"):
            once("VALUE")
            p.accept("IS")
            # VALUE ALL literal: its first character over the item's size.
            entry.value_all = bool(p.accept("ALL"))
            if not p.t.string or not p.t.text.isascii():
                p.error("VALUE de rapport limité à un littéral alphanumérique")
            entry.value = p.take()
        elif not p.t.string and p.t.key in REFUSED_CLAUSES:
            p.error(f"clause de rapport {REFUSED_CLAUSES[p.t.key]} non prise en charge")
        else:
            p.error("clause de groupe de rapport non prise en charge")
    p.expect(".")
    return entry


def report_description(p, report):
    """RD name [options]. then its report groups."""
    seen = set()
    while not p.at("."):
        if p.at("PAGE"):
            if "PAGE" in seen:
                p.error("clause RD PAGE dupliquée")
            seen.add("PAGE")
            p.take()
            page_limits(p, report)
        elif p.at("GLOBAL") or p.at("IS"):
            p.error("GLOBAL is not allowed with RD")
        elif p.at("CODE") or p.at("WITH"):
            p.error("clause RD CODE non prise en charge")
        elif p.at("CONTROL") or p.at("CONTROLS"):
            if "CONTROL" in seen:
                p.error("clause RD CONTROL dupliquée")
            seen.add("CONTROL")
            p.take()
            p.accept("IS") or p.accept("ARE")
            if p.accept("FINAL"):
                report.control_final = True
            while not p.t.string and p.candidates(p.t.key) and not p.at("PAGE"):
                ref = p.variable()
                if ref.indices or ref.start is not None:
                    p.error("CONTROL sans indice ni sous-chaîne requis")
                if getattr(p.fields[ref.name], "local", False):
                    p.error("CONTROL de rapport en LOCAL-STORAGE non pris en charge (descripteur natif non constant)")
                report.controls.insert(0, ref.name)
            if not report.controls and not report.control_final:
                p.error("CONTROL requiert FINAL ou des identifiants")
        else:
            p.error("clause RD non prise en charge")
    p.expect(".")
    # Without PAGE the limits stay 0 (first detail 1, see check_limits), as
    # in the cob_report that cobc emits.
    stack = []
    while not p.t.string and p.t.key.isdigit():
        entry = group_entry(p, report)
        while stack and stack[-1].level >= entry.level:
            stack.pop()
        if stack:
            if entry.flags & ~(LINE | LINE_PLUS | RESET_FINAL | GROUP_INDICATE) or entry.next_group or entry.control:
                p.error("TYPE et NEXT GROUP limités aux groupes de niveau 01")
            stack[-1].children.append(entry)
        else:
            if entry.level != 1:
                p.error("groupe de rapport de niveau 01 attendu")
            if not entry.flags & GROUP_TYPES:
                p.error("groupe de rapport 01 sans TYPE non pris en charge")
            report.entries.append(entry)
        stack.append(entry)
        if entry.sum and not entry.picture:
            p.error("needs PICTURE clause for SUM")
        if entry.picture:
            if entry.source is None and entry.value is None and not entry.sum:
                p.error("article de rapport sans SOURCE, SUM ni VALUE non pris en charge")
            if entry.source is not None and entry.value is not None:
                p.error("article de rapport avec SOURCE et VALUE non pris en charge")
            entry.item = p.report_item(report, entry.picture)
            item = p.fields[entry.item]
            entry.size = item.size
            if entry.size > SMALL_MAX:
                p.error("article de rapport de plus de 1023 octets non pris en charge")
            if entry.value is not None:
                literal = entry.value.text.encode("latin-1")
                if getattr(entry, "value_all", False):
                    literal = literal[:1] * entry.size
                if item.kind != "text" or item.alnum_edit or len(literal) > entry.size or not literal:
                    p.error("VALUE de rapport limité à un littéral tenant dans un article alphanumérique")
        elif entry.source is not None or entry.value is not None or entry.column:
            p.error("SOURCE, VALUE et COLUMN limités aux articles élémentaires")
    if not report.entries:
        p.error(f"RD {report.name} sans groupe de rapport")
    sum_counters(p, report)
    build_lines(p, report)
    check_limits(p, report)


def sum_counters(p, report):
    """build_sum_counter for each SUM item, then the counter list in the
    order of codegen.c output_report_sum_counters (its sum_prv chain)."""
    from .frontend import DataRef, Expr
    named = {}

    def walk(entry, parents):
        if entry.label:
            named.setdefault(entry.label, entry)
        if entry.sum:
            item = p.fields[entry.item]
            if item.kind not in {"number", "edited"}:
                p.error("SUM vers un article non numérique non pris en charge")
            digits = 16 if item.digits == 0 else 18 if item.digits > 17 else item.digits + 2
            scale = item.scale
            if scale > 0 and digits - scale < 0:
                p.error("compteur SUM à PICTURE P non pris en charge")
            picture = f"S9({digits - scale})V9({scale})" if scale > 0 and digits > scale else \
                f"SV9({scale})" if scale > 0 else f"S9({digits})"
            entry.counter = p.sum_counter(report, picture)
            entry.source = Expr("var", (DataRef(entry.counter),))
            control, final = None, False
            for parent in [entry, *reversed(parents)]:
                if parent.control:
                    control = parent.control
                    break
                if parent.flags & CONTROL_FOOTING_FINAL:
                    final = True
                    break
            entry.sum_control = (control, final)
        for child in entry.children:
            walk(child, parents + [entry])
    for entry in report.entries:
        walk(entry, [])

    def operands(entry):
        result, subtotal = [], False
        for key, label in entry.sum:
            if label is not None:
                other = named.get(label)
                if other is None or other.counter is None:
                    p.error(f"opérande SUM inconnu ou non sommé: {label}")
                result.append(other.counter)
                subtotal = True
                continue
            f = p.fields[key]
            if f.kind != "number" or f.usage != "DISPLAY" or f.sign_separate or f.sign_leading:
                # cob_add_fields copies the operand into a DISPLAY item of
                # its own size: other usages are not modelled.
                p.error("opérande SUM limité aux numériques DISPLAY à signe incorporé final")
            result.append(key)
        return list(reversed(result)), subtotal   # rsprv chain: last listed first

    emitted = []

    def emit(entry, sisters, top):
        if sisters:
            emit(sisters[0], sisters[1:], top)
        if entry.children:
            emit(entry.children[0], entry.children[1:], False)
        if entry.sum and entry not in emitted:
            emitted.append(entry)
    for index in range(len(report.entries) - 1, -1, -1):
        emit(report.entries[index], report.entries[index + 1:], True)
    for entry in reversed(emitted):
        sources, subtotal = operands(entry)
        control, final = entry.sum_control
        report.sums.append((entry.counter, sources, control, final, subtotal))


def layout(entry, offset):
    """Group sizes and offsets of the report storage (compute_size)."""
    entry.offset = offset
    if entry.children:
        size = 0
        for child in entry.children:
            size += layout(child, offset + size)
        entry.size = size
    elif not entry.picture:
        entry.size = 0
    return entry.size


def report_columns(entries, parent):
    """output_report_data: COLUMN PLUS n and a missing COLUMN follow the
    previous item of the line (report_col_pos), which a 01 group, a LINE or
    a group TYPE starts again at 1. PLUS on the first item of a LINE is
    ignored (col_or_plus): n is then the column."""
    position = 1

    def walk(entries, parent):
        nonlocal position
        for index, entry in enumerate(entries):
            if entry.level == 1 or entry.flags & (LINE | GROUP_TYPES):
                previous = position = 1
            else:
                first_of_line = index == 0 and parent is not None and bool(parent.flags & LINE)
                column = entry.column
                if entry.column_plus and not first_of_line:
                    column = position + entry.column - 1
                elif column <= 0:
                    column = position
                if entry.picture:
                    # A group's column only moves report_col_pos.
                    entry.column = column
                previous = position
                position = column + entry.size
            if entry.children:
                position = previous
                walk(entry.children, entry)
    walk(entries, parent)


def build_lines(p, report):
    """output_report_define_lines: one line per 01 group and per item with
    LINE, chained by sister (next 01, next LINE sibling) and child (first
    LINE child of a 01); the fields of a line are the items below it in
    declaration order, or the elementary LINE item itself."""
    rcsz = 0
    for entry in report.entries:
        layout(entry, 0)
    report_columns(report.entries, None)

    def sizes(entry):
        nonlocal rcsz
        if entry.flags & LINE or entry.level == 1:
            rcsz = max(rcsz, entry.offset + entry.size)
        if entry.column > 0:
            rcsz = max(rcsz, entry.column - 1 + entry.size)
        for child in entry.children:
            sizes(child)
    for entry in report.entries:
        sizes(entry)
    if rcsz > MAX_COLS:
        p.error("ligne de rapport de plus de 999 colonnes non prise en charge")
    report.size = rcsz

    def fields_of(entries):
        result = []
        for entry in entries:
            if entry.flags & LINE:
                p.error("LINE après des articles sans LINE non prise en charge")
            if entry.children:
                if any(child.flags & LINE for child in entry.children):
                    p.error("LINE dans un groupe sans LINE non pris en charge")
                result += fields_of(entry.children)
            else:
                result.append(field_of(entry))
        return result

    def field_of(entry):
        literal = entry.value.text.encode("latin-1") if entry.value is not None else None
        if literal is not None and getattr(entry, "value_all", False):
            literal = literal[:1] * entry.size
        return ReportField(entry.column, literal, entry.source, entry.item if entry.source is not None else None,
                           entry.line if entry.flags & LINE else 0, bool(entry.flags & GROUP_INDICATE))

    def line_of(entry, top):
        if entry.flags & LINE and entry.children and entry.children[0].flags & LINE:
            p.error("LINE imbriquée dans un groupe avec LINE non prise en charge")
        if entry.flags & LINE and entry.children:
            fields = fields_of(entry.children)
        elif not entry.children and entry.flags & LINE:
            fields = [field_of(entry)]
        else:
            fields = []
        index = len(report.report_lines)
        line = ReportLine(entry.flags, entry.line, fields, label=entry.label, next_group=entry.next_group,
                          control=entry.control)
        report.report_lines.append(line)
        if top and entry.label:
            if entry.label in report.groups:
                p.error(f"groupe de rapport dupliqué: {entry.label}")
            report.groups[entry.label] = index
        if top and entry.children and entry.children[0].flags & LINE:
            previous = None
            for child in entry.children:
                if not child.flags & LINE:
                    p.error("articles avec et sans LINE mêlés dans un groupe non pris en charge")
                child_index = line_of(child, False)
                if previous is None:
                    line.child = child_index
                else:
                    report.report_lines[previous].sister = child_index
                previous = child_index
        elif top and entry.children:
            if any(child.flags & LINE for child in entry.children):
                p.error("articles avec et sans LINE mêlés dans un groupe non pris en charge")
        if not fields and line.child is None:
            p.error("groupe de rapport sans article imprimé non pris en charge")
        return index

    previous = None
    for entry in report.entries:
        index = line_of(entry, True)
        if previous is not None:
            report.report_lines[previous].sister = index
        previous = index
