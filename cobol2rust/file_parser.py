"""FD clauses for the tested GnuCOBOL 3.2 ordinary disk-file profile.

LABEL and BLOCK clauses are retained as metadata. GnuCOBOL does not add labels
or physical blocking for the supported disk files. RECORD is accepted only as
a fixed length; the caller must validate it against every FD record after layout.
RECORD VARYING and RECORD CONTAINS m TO n give the limits of a variable file.
DATA RECORDS is obsolete documentation: GnuCOBOL parses its names without
resolving them and gives the clause no effect, so they are kept as metadata.
"""
from __future__ import annotations


# Mots réservés pouvant suivre une liste DATA RECORDS ; ils ne sont jamais des noms.
FD_WORDS = {"LABEL", "BLOCK", "RECORD", "RECORDS", "RECORDING", "DATA", "VALUE",
            "LINAGE", "CODE-SET", "EXTERNAL", "GLOBAL", "REPORT", "REPORTS",
            "IS", "ARE", "OF", "IN", "WITH", "LINES", "FOOTING", "TOP", "BOTTOM"}


def unsigned(parser, clause, minimum=0):
    token = parser.t
    if (token.string or not token.text.isascii() or not token.text.isdigit()
            or len(token.text.lstrip("0")) > 10):
        parser.error(f"{clause} requiert un entier littéral non signé")
    value = int(parser.take().text.lstrip("0") or "0")
    if not minimum <= value <= 2147483647:
        parser.error(f"{clause} limité à {minimum}..2147483647")
    return value


def linage_value(parser):
    """reference_or_literal: an unsigned integer literal or a data name,
    read by libcob with cob_get_int at OPEN and at each page change."""
    token = parser.t
    if token.string:
        parser.error("LINAGE requiert un entier ou un nom de donnée")
    if token.text.isascii() and token.text.isdigit():
        return ("literal", unsigned(parser, "LINAGE"))
    label = parser.name()
    qualifiers = []
    while parser.accept("OF") or parser.accept("IN"):
        qualifiers.append(parser.name())
    return ("name", label, tuple(qualifiers))


def parse_fd_clauses(parser, spec):
    """Consume FD options and their terminating period, preserving metadata."""
    clauses = {}

    def put(name, value):
        if name in clauses:
            parser.error(f"clause FD {name} dupliquée")
        clauses[name] = value

    while not parser.at("."):
        if parser.accept("LABEL"):
            if not (parser.accept("RECORD") or parser.accept("RECORDS")):
                parser.error("LABEL requiert RECORD ou RECORDS")
            parser.accept("IS") or parser.accept("ARE")
            if parser.accept("OMITTED"):
                label = "OMITTED"
            elif parser.accept("STANDARD"):
                label = "STANDARD"
            else:
                parser.error("LABEL RECORDS limité à OMITTED ou STANDARD")
            put("label_records", label)
        elif parser.accept("BLOCK"):
            parser.accept("CONTAINS")
            low = unsigned(parser, "BLOCK")
            high = unsigned(parser, "BLOCK") if parser.accept("TO") else low
            if high < low:
                parser.error("bornes BLOCK inversées non prises en charge")
            unit = "CHARACTERS" if parser.accept("CHARACTERS") else "RECORDS"
            if unit == "RECORDS":
                parser.accept("RECORDS")
            put("block_contains", {"minimum": low, "maximum": high, "unit": unit})
        elif parser.accept("RECORD"):
            if parser.accept("IS") or parser.at("VARYING"):
                # RECORD [IS] VARYING [IN] [SIZE] [[FROM] m] [TO n] [CHARACTERS] [DEPENDING [ON] x]
                parser.expect("VARYING")
                parser.accept("IN")
                parser.accept("SIZE")
                low = high = None
                if parser.accept("FROM") or (not parser.t.string and parser.t.text.isdigit()):
                    low = unsigned(parser, "RECORD VARYING", minimum=1)
                if parser.accept("TO"):
                    high = unsigned(parser, "RECORD VARYING", minimum=1)
                parser.accept("CHARACTERS")
                depending = None
                if parser.accept("DEPENDING"):
                    parser.accept("ON")
                    depending = parser.name()
                    if parser.at("OF") or parser.at("IN"):
                        parser.error("DEPENDING ON qualifié non pris en charge")
                if low and high and high <= low:
                    parser.error("RECORD VARYING invalide: maximum inférieur ou égal au minimum")
                put("record_varying", {"minimum": low, "maximum": high, "depending": depending})
            else:
                parser.accept("CONTAINS")
                length = unsigned(parser, "RECORD CONTAINS", minimum=1)
                if parser.accept("TO"):
                    high = unsigned(parser, "RECORD CONTAINS", minimum=1)
                    parser.accept("CHARACTERS")
                    if parser.at("DEPENDING"):
                        parser.error("RECORD CONTAINS ... DEPENDING (extension GCOS) non pris en charge")
                    if high <= length:
                        parser.error("RECORD CONTAINS invalide: maximum inférieur ou égal au minimum")
                    put("record_varying", {"minimum": length, "maximum": high, "depending": None})
                else:
                    if parser.at("DEPENDING"):
                        parser.error("RECORD variable non pris en charge; longueur fixe exacte requise")
                    parser.accept("CHARACTERS")
                    put("record_contains", length)
        elif parser.accept("RECORDING"):
            parser.accept("MODE")
            parser.accept("IS")
            if not parser.accept("F"):
                parser.error("RECORDING MODE limité à F pour des enregistrements fixes")
            put("recording_mode", "F")
        elif parser.accept("DATA"):
            if not (parser.accept("RECORD") or parser.accept("RECORDS")):
                parser.error("DATA requiert RECORD ou RECORDS")
            parser.accept("IS") or parser.accept("ARE")
            names = []
            while not names or not (parser.at(".") or parser.t.string or parser.t.key in FD_WORDS):
                if not parser.t.string and parser.t.key in FD_WORDS:
                    parser.error("nom d'enregistrement DATA RECORDS attendu")
                names.append(parser.name())
            put("data_records", names)
        elif parser.at("VALUE") and parser.tokens[parser.i + 1].key == "OF":
            # VALUE OF is obsolete documentation in default.conf; FILE-ID
            # would only name the file when ASSIGN is missing, and it is required.
            parser.take(); parser.take()
            parser.take()
            parser.accept("IS")
            if parser.t.string:
                parser.take()
            else:
                parser.name()
                while parser.accept("OF") or parser.accept("IN"):
                    parser.name()
            put("value_of", True)
        elif parser.accept("LINAGE"):
            # parser.y linage_clause: LINAGE [IS] x [LINES] then FOOTING, TOP
            # and BOTTOM in any order; the file becomes LINE SEQUENTIAL. The
            # scanner folds [LINES] [AT] before TOP/BOTTOM into one token.
            if spec.organization not in {"SEQUENTIAL", "LINE SEQUENTIAL"}:
                parser.error("LINAGE clause with wrong file type")
            parser.accept("IS")
            linage = {"lines": linage_value(parser)}
            parser.accept("LINES")
            while True:
                if parser.at("WITH") or parser.at("FOOTING"):
                    parser.accept("WITH")
                    parser.expect("FOOTING")
                    parser.accept("AT")
                    part = "footing"
                else:
                    start = parser.i
                    parser.accept("LINES")
                    parser.accept("AT")
                    if parser.accept("TOP"):
                        part = "top"
                    elif parser.accept("BOTTOM"):
                        part = "bottom"
                    else:
                        parser.i = start
                        break
                if part in linage:
                    parser.error(f"clause LINAGE {part.upper()} dupliquée")
                linage[part] = linage_value(parser)
            put("linage", linage)
            spec.organization = "LINE SEQUENTIAL"
        else:
            parser.error("clause FD non prise en charge")
    parser.expect(".")
    spec.fd_clauses = clauses
