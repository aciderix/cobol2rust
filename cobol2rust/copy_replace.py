"""COPY ... REPLACING as GnuCOBOL 3.2 performs it (cobc/pplex.l, ppparse.y,
replace.c): the copybook is cut into pplex texts, and at each text that is
not a space the replacements are tried in order; a pseudo-text matches its
texts case-insensitively, skipping spaces on both sides."""
from __future__ import annotations

import re

from .frontend import CobolError

_WORD = r"[_0-9A-Za-z\x80-\xff-]+"
_NUMERIC = r"[+-]?[0-9,.]*[0-9]"
_LITERAL = r"\"(?:[^\"\n]|\"[0-9][0-9, ]*\")*\"|'(?:[^'\n]|'[0-9][0-9, ]+')*'"


def _longest(text, position, patterns):
    """flex picks the longest match; on a tie, the earliest rule."""
    best = None
    for pattern in patterns:
        match = re.compile(pattern).match(text, position)
        if match and (best is None or len(match[0]) > len(best)):
            best = match[0]
    return best


def statement_end(source: str, start: int) -> int:
    """The offset after the period ending a COPY statement, outside pseudo-text."""
    i, pseudo = start, False
    while i < len(source):
        if source.startswith("*>", i):
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
            continue
        if source.startswith("==", i):
            pseudo = not pseudo
            i += 2
            continue
        token = _longest(source, i, (_WORD, _NUMERIC, _LITERAL)) or source[i]
        if token == "." and not pseudo:
            return i + 1
        i += len(token)
    return -1


def texts(source: str, pseudo=False):
    """The texts pplex hands to the replacing stream. Spaces become " ",
    a newline "\\n"; outside parentheses a comma or semicolon before spaces
    is a separator, inside them ", " is kept as a text."""
    result, i, brackets = [], 0, 0
    while i < len(source):
        c = source[i]
        if source.startswith("*>", i):
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
            continue
        match = re.compile(r"[,;]?\n").match(source, i)
        if match:
            result.append("\n")
            i = match.end()
            continue
        match = re.compile(r"[,;]?[ \t]+").match(source, i)
        if match:
            result.append(", " if match[0][0] == "," and brackets and not pseudo else " ")
            i = match.end()
            continue
        token = _longest(source, i, (_WORD, _NUMERIC, _LITERAL)) or c
        if token == "(":
            brackets += 1
        elif token == ")" and brackets:
            brackets -= 1
        result.append(token)
        i += len(token)
    return result


def _space(text):
    return text[:1] in {" ", "\n"}


def apply(source: str, replacements, line, keep_lines=False) -> str:
    """check_replace / check_replace_all over the copybook texts. With
    keep_lines, the newlines of a replaced span follow its replacement, so
    that the next source lines keep their numbers."""
    stream = texts(source)
    out, i = [], 0
    while i < len(stream):
        if _space(stream[i]):
            out.append(stream[i])
            i += 1
            continue
        for replacement in replacements:
            pattern, new_text = replacement[:2]
            if len(replacement) > 2:
                # LEADING / TRAILING (is_leading_or_trailing): one text, a
                # case-insensitive prefix or suffix, then the partial echo.
                mode, strict = replacement[2:]
                source, text = pattern[0], stream[i]
                if len(text) > len(source) or (not strict and len(text) == len(source)):
                    part = text[:len(source)] if mode == "LEADING" else text[len(text) - len(source):]
                    if part.lower() == source.lower():
                        rest = text[len(source):] if mode == "LEADING" else text[:len(text) - len(source)]
                        out.extend(([] if mode == "LEADING" else [rest]) + new_text
                                   + ([rest] if mode == "LEADING" else []))
                        i += 1
                        break
                continue
            j, matched = i, True
            for want in (t for t in pattern if not _space(t)):
                while j < len(stream) and _space(stream[j]):
                    j += 1
                # A partial match at the end of the copybook fails.
                if j >= len(stream) or stream[j].lower() != want.lower():
                    matched = False
                    break
                j += 1
            if matched:
                out.extend(new_text)
                if keep_lines:
                    out.append("\n" * stream[i:j].count("\n"))
                i = j
                break
        else:
            out.append(stream[i])
            i += 1
    return "".join(out)


def parse_replacing(tokens, line):
    """REPLACING {==pseudo-text== | identifier | literal} BY {...} ... from the
    REPLACE_STATE texts of the COPY statement (spaces already dropped)."""
    replacements, k = [], 0

    def operand(target):
        nonlocal k
        if k >= len(tokens):
            raise CobolError(f"ligne {line}: COPY REPLACING incomplet")
        if tokens[k] == "==":
            end = tokens.index("==", k + 1) if "==" in tokens[k + 1:] else -1
            if end < 0:
                raise CobolError(f"ligne {line}: pseudo-texte non terminé")
            body = tokens[k + 1:end]
            k = end + 1
            # PSEUDO_STATE drops newlines; spaces stay as " " texts.
            return [t for t in body if t != "\n"]
        result = [tokens[k]]
        k += 1
        # identifier IN/OF qualifiers and (subscripts), as ppparse.y builds them.
        while k < len(tokens) and tokens[k].upper() in {"IN", "OF"} and k + 1 < len(tokens):
            result += [" ", tokens[k].upper(), " ", tokens[k + 1]]
            k += 2
        if k < len(tokens) and tokens[k] == "(":
            end = tokens.index(")", k) if ")" in tokens[k:] else -1
            if end < 0:
                raise CobolError(f"ligne {line}: sous-scripts COPY REPLACING non terminés")
            subscripts = tokens[k + 1:end]
            result += [" ", "("]
            for n, s in enumerate(subscripts):
                result += ([" "] if n else []) + [s]
            result.append(")")
            k = end + 1
        return result

    def partial(target):
        """text_partial_src / text_partial_dst: one text between == ==, or a
        literal (obsolete in default.conf, an error in cobol85)."""
        nonlocal k
        if k + 1 < len(tokens) and tokens[k] == "==" and tokens[k + 1] == "==" and target:
            k += 2
            return [], False
        if tokens[k] == "==":
            body = [t for t in tokens[k + 1:tokens.index("==", k + 1)] if not _space(t) and t != "\n"] \
                if "==" in tokens[k + 1:] else None
            if not body or len(body) != 1:
                raise CobolError(f"ligne {line}: un seul mot attendu dans un remplacement partiel")
            k = tokens.index("==", k + 1) + 1
            return body, False
        text = tokens[k]
        k += 1
        if text[:1] in "\"'":
            from . import frontend
            if frontend.STD == "cobol85":
                raise CobolError(f"ligne {line}: partial replacing with literal non conforme à -std=cobol85")
            return ([text[1:-1]] if text[1:-1] else []), True
        if target and text.upper() in {"SPACE", "SPACES"}:
            return [], False
        raise CobolError(f"ligne {line}: unexpected COBOL word in partial replacement phrase")

    while k < len(tokens):
        if tokens[k].upper() in {"LEADING", "TRAILING"}:
            mode = tokens[k].upper()
            k += 1
            if k >= len(tokens):
                raise CobolError(f"ligne {line}: COPY REPLACING incomplet")
            source, strict = partial(False)
            if k >= len(tokens) or tokens[k].upper() != "BY":
                raise CobolError(f"ligne {line}: BY attendu dans COPY REPLACING")
            k += 1
            if k >= len(tokens):
                raise CobolError(f"ligne {line}: COPY REPLACING incomplet")
            target, _ = partial(True)
            replacements.append((source, target, mode, strict))
            continue
        source = operand(False)
        if k >= len(tokens) or tokens[k].upper() != "BY":
            raise CobolError(f"ligne {line}: BY attendu dans COPY REPLACING")
        k += 1
        if k + 1 < len(tokens) and tokens[k] == "==" and tokens[k + 1] == "==":
            target = []
            k += 2
        else:
            target = operand(True)
        if not [t for t in source if not _space(t)]:
            raise CobolError(f"ligne {line}: pseudo-texte source vide")
        replacements.append((source, target))
    return replacements


def statement_texts(text: str):
    """REPLACE_STATE / PSEUDO_STATE texts: spaces dropped outside == ==."""
    result, inside = texts(text, pseudo=True), False
    # Merge "=" "=" into "==" and drop spaces outside pseudo-text.
    merged, i = [], 0
    while i < len(result):
        if result[i] == "=" and i + 1 < len(result) and result[i + 1] == "=":
            merged.append("==")
            inside = not inside
            i += 2
            continue
        if not inside and _space(result[i]):
            i += 1
            continue
        merged.append(result[i])
        i += 1
    return merged


def replace_statements(text: str, tokens) -> str:
    """REPLACE ... BY ... . and REPLACE OFF (ppparse.y replace_statement,
    cb_set_replace_list): each statement replaces the active list for the
    text that follows it, COPY expansion and COPY REPLACING included. The
    statement is removed, its lines kept blank."""
    pieces, cursor, active, i = [], 0, [], 0
    while i < len(tokens) - 1:
        if tokens[i].string or tokens[i].key != "REPLACE":
            i += 1
            continue
        start, line = tokens[i].start, tokens[i].line
        stop = statement_end(text, tokens[i].end)
        if stop < 0:
            raise CobolError(f"ligne {line}: REPLACE sans point final")
        segment = text[cursor:start]
        pieces += [apply(segment, active, line, True) if active else segment, "\n" * text[start:stop].count("\n")]
        words = statement_texts(text[start:stop - 1])[1:]
        if words and words[0].upper() in {"ALSO", "LAST"}:
            raise CobolError(f"ligne {line}: REPLACE {words[0].upper()} non pris en charge")
        active = [] if [w.upper() for w in words] == ["OFF"] else parse_replacing(words, line)
        cursor = stop
        while i < len(tokens) and tokens[i].start < stop:
            i += 1
    segment = text[cursor:]
    pieces.append(apply(segment, active, 0, True) if active else segment)
    return "".join(pieces)
