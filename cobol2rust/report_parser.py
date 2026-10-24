"""REPORT SECTION of GnuCOBOL 3.2 (parser.y report_description, tree.c
finalize_report, codegen.c output_report_define_lines/def_fields).

The modelled subset: RD with a literal PAGE LIMIT, HEADING, FIRST DETAIL,
LAST DETAIL and FOOTING; report groups of TYPE REPORT HEADING, PAGE HEADING,
DETAIL, PAGE FOOTING and REPORT FOOTING with LINE [PLUS] n; elementary items
with PICTURE, COLUMN n and either SOURCE (an identifier, LINE-COUNTER or
PAGE-COUNTER) or an alphanumeric VALUE literal. CONTROL, SUM, NEXT GROUP,
GROUP INDICATE, PRESENT WHEN, OCCURS, COLUMN PLUS/LEFT/RIGHT/CENTER, CODE and
PAGE limits given by data items are refused.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# libcob common.h COB_REPORT_* flags.
LINE, LINE_PLUS = 1 << 0, 1 << 1
HEADING, FOOTING, PAGE_HEADING, PAGE_FOOTING = 1 << 4, 1 << 5, 1 << 6, 1 << 7
DETAIL = 1 << 12

TYPES = {"DETAIL": DETAIL, "DE": DETAIL, "PH": PAGE_HEADING, "PF": PAGE_FOOTING,
         "RH": HEADING, "RF": FOOTING}
REFUSED_CLAUSES = {
    "NEXT": "NEXT GROUP", "GROUP": "GROUP INDICATE", "SUM": "SUM", "PRESENT": "PRESENT WHEN",
    "ABSENT": "ABSENT WHEN", "OCCURS": "OCCURS", "VARYING": "VARYING", "USAGE": "USAGE",
    "SIGN": "SIGN", "JUSTIFIED": "JUSTIFIED", "JUST": "JUSTIFIED", "BLANK": "BLANK WHEN ZERO",
    "RESET": "RESET", "UPON": "SUM UPON",
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
    picture: list = field(default_factory=list)
    source: Expr | None = None
    value: Token | None = None
    children: list = field(default_factory=list)
    item: str | None = None
    size: int = 0
    offset: int = 0


@dataclass
class ReportField:
    """cob_report_field: column, then a literal or a SOURCE moved to `item`."""
    column: int
    literal: bytes | None = None
    source: Expr | None = None
    item: str | None = None
    line: int = 0


@dataclass
class ReportLine:
    """cob_report_line: flags, LINE value, fields, child and sister lines."""
    flags: int
    line: int
    fields: list
    child: int | None = None
    sister: int | None = None
    label: str | None = None


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
    for line in report.report_lines:
        if (line.line > 0 and report.lines > 0 and line.line > report.lines
                or any(f.line and f.line > report.lines for f in line.fields)):
            p.error(f"INITIATE {report.name} LINE exceeds PAGE LIMIT {report.lines}")


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
            elif not p.t.string and p.t.key in TYPES:
                entry.flags |= TYPES[p.take().key]
            else:
                p.error("TYPE CONTROL HEADING/FOOTING non pris en charge")
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
            if p.at("PLUS") or p.at("+"):
                p.error("COLUMN PLUS non pris en charge")
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
            entry.source = p.expr()
            if entry.source.op not in {"var", "report_counter"}:
                p.error("SOURCE limité à un identifiant, LINE-COUNTER ou PAGE-COUNTER")
            if p.at("ROUNDED"):
                p.error("SOURCE ROUNDED non pris en charge")
        elif p.accept("VALUE"):
            once("VALUE")
            p.accept("IS")
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
            p.error("clause RD CONTROL non prise en charge")
        else:
            p.error("clause RD non prise en charge")
    p.expect(".")
    if "PAGE" not in seen:
        p.error("RD sans PAGE LIMIT non pris en charge")
    stack = []
    while not p.t.string and p.t.key.isdigit():
        entry = group_entry(p, report)
        while stack and stack[-1].level >= entry.level:
            stack.pop()
        if stack:
            if entry.flags & ~(LINE | LINE_PLUS):
                p.error("TYPE limité aux groupes de niveau 01")
            stack[-1].children.append(entry)
        else:
            if entry.level != 1:
                p.error("groupe de rapport de niveau 01 attendu")
            if not entry.flags & (DETAIL | PAGE_HEADING | PAGE_FOOTING | HEADING | FOOTING):
                p.error("groupe de rapport 01 sans TYPE non pris en charge")
            report.entries.append(entry)
        stack.append(entry)
        if entry.picture:
            if entry.source is None and entry.value is None:
                p.error("article de rapport sans SOURCE ni VALUE non pris en charge")
            if entry.source is not None and entry.value is not None:
                p.error("article de rapport avec SOURCE et VALUE non pris en charge")
            if not entry.column:
                p.error("article de rapport sans COLUMN non pris en charge")
            entry.item = p.report_item(report, entry.picture)
            item = p.fields[entry.item]
            entry.size = item.size
            if entry.size > SMALL_MAX:
                p.error("article de rapport de plus de 1023 octets non pris en charge")
            if entry.value is not None:
                literal = entry.value.text.encode("latin-1")
                if item.kind != "text" or item.alnum_edit or len(literal) > entry.size:
                    p.error("VALUE de rapport limité à un littéral tenant dans un article alphanumérique")
        elif entry.source is not None or entry.value is not None or entry.column:
            p.error("SOURCE, VALUE et COLUMN limités aux articles élémentaires")
    if not report.entries:
        p.error(f"RD {report.name} sans groupe de rapport")
    build_lines(p, report)
    check_limits(p, report)


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


def build_lines(p, report):
    """output_report_define_lines: one line per 01 group and per item with
    LINE, chained by sister (next 01, next LINE sibling) and child (first
    LINE child of a 01); the fields of a line are the items below it in
    declaration order, or the elementary LINE item itself."""
    rcsz = 0
    for entry in report.entries:
        layout(entry, 0)

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
        return ReportField(entry.column, literal, entry.source, entry.item if entry.source is not None else None,
                           entry.line if entry.flags & LINE else 0)

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
        line = ReportLine(entry.flags, entry.line, fields, label=entry.label)
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
