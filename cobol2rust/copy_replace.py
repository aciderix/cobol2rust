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


def apply(source: str, replacements, line) -> str:
    """check_replace / check_replace_all over the copybook texts."""
    stream = texts(source)
    out, i = [], 0
    while i < len(stream):
        if _space(stream[i]):
            out.append(stream[i])
            i += 1
            continue
        for pattern, new_text in replacements:
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
        if tokens[k].upper() in {"LEADING", "TRAILING"}:
            raise CobolError(f"ligne {line}: COPY REPLACING LEADING/TRAILING non pris en charge")
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

    while k < len(tokens):
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
