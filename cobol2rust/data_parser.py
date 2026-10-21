"""Data division parsing, with explicit storage hierarchy and condition names."""
import re

from .frontend import Condition, Field, Token, VERBS

USAGES = {"DISPLAY", "COMP", "COMPUTATIONAL", "BINARY", "COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL", "COMP-4", "COMPUTATIONAL-4"}


def literal(p):
    negative = p.accept("-")
    if not negative:
        p.accept("+")
    token = p.take()
    if token.string:
        if negative:
            p.error("signe sur un littéral texte")
        return token
    if token.key in {"ZERO", "ZEROS", "ZEROES"}:
        token = Token("0", token.line)
    elif token.key in {"SPACE", "SPACES"}:
        token = Token(" ", token.line, True)
    elif not re.fullmatch(r"\d+(?:\.\d+)?", token.text):
        p.error("littéral attendu")
    if negative:
        token = Token("-" + token.text, token.line, token.string)
    return token


def declaration(p, file_record=False):
    if p.t.string or not p.t.key.isdigit():
        p.error("niveau de donnée attendu")
    level = int(p.take().key)
    label = p.name()
    if level == 88:
        if not p.last_data or not p.fields[p.last_data].picture:
            p.error("niveau 88 requiert une donnée élémentaire précédente")
        key = p.last_data + "." + label
        if key in p.conditions or label in VERBS:
            p.error("condition dupliquée ou réservée")
        if not (p.accept("VALUE") or p.accept("VALUES")):
            p.error("VALUE attendu au niveau 88")
        p.accept("IS") or p.accept("ARE")
        values = []
        while not p.at(".") and not p.at("WHEN"):
            low = literal(p)
            high = literal(p) if p.accept("THRU") or p.accept("THROUGH") else low
            values.append((low, high))
            p.accept(",")
        if not values:
            p.error("VALUE de condition vide")
        false_value = None
        if p.accept("WHEN"):
            p.expect("SET"); p.expect("TO"); p.expect("FALSE")
            p.accept("IS")
            false_value = literal(p)
        p.expect(".")
        p.conditions[key] = Condition(key, label, p.last_data, values, false_value)
        return key
    if level not in {1, 77} and not 2 <= level <= 49:
        p.error("niveaux pris en charge: 01-49, 77 et 88")
    if level in {1, 77}:
        p.data_stack = []
    else:
        while p.data_stack and p.fields[p.data_stack[-1]].level >= level:
            p.data_stack.pop()
        if not p.data_stack or p.fields[p.data_stack[-1]].level == 77:
            p.error("donnée subordonnée sans groupe parent")
    parent = p.data_stack[-1] if p.data_stack else None
    if parent and p.fields[parent].picture:
        p.error("un champ élémentaire ne peut pas contenir de sous-champs")
    filler = label == "FILLER"
    if filler:
        p.filler_count += 1
        component = f"$FILLER{p.filler_count}"
    else:
        component = label
    key = (parent + "." if parent else "") + component
    if key in p.fields or label in VERBS or label in {"ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES"}:
        p.error(f"nom de donnée réservé ou dupliqué: {label}")
    picture, usage, initial = "", "DISPLAY", None
    has_usage, table, count, redefines = False, False, 1, None
    minimum, depending = 1, None
    if p.accept("REDEFINES"):
        target = p.name()
        siblings = [f for f in p.fields.values() if f.parent == parent]
        matches = [f for f in siblings if f.label == target]
        if not matches or matches[-1].level != level:
            p.error("REDEFINES requiert un champ précédent au même niveau")
        # Restrict to a contiguous redefine family; indirect redefines are dialect-dependent.
        last = siblings[-1]
        if last.name != matches[-1].name and last.redefines != matches[-1].name:
            p.error("REDEFINES indirect non pris en charge")
        redefines = matches[-1].name
    while not p.at("."):
        if p.accept("PIC") or p.accept("PICTURE"):
            if picture:
                p.error("PICTURE dupliquée")
            p.accept("IS")
            while p.t.key not in {"VALUE", "USAGE", "OCCURS", "REDEFINES", "INDEXED", ".", "<EOF>"} | USAGES:
                if p.t.string:
                    p.error("PICTURE invalide")
                picture += p.take().key
        elif p.accept("OCCURS"):
            if table or not p.t.key.isdigit():
                p.error("nombre OCCURS attendu")
            count = int(p.take().key)
            minimum = count
            variable = p.accept("TO")
            if variable:
                if not p.t.key.isdigit():
                    p.error("borne maximale OCCURS attendue")
                count = int(p.take().key)
            if not 1 <= count <= 10000 or not 0 <= minimum <= count or (not variable and minimum == 0):
                p.error("OCCURS limité à 1..10000, minimum variable 0..maximum")
            table = True
            p.accept("TIMES")
            if variable:
                p.expect("DEPENDING"); p.expect("ON")
                depending = p.name()
        elif p.accept("INDEXED"):
            if not table:
                p.error("INDEXED BY requiert OCCURS")
            p.expect("BY")
            names = [p.name()]
            while p.t.key not in {"PIC", "PICTURE", "VALUE", "USAGE", ".", "<EOF>"} | USAGES:
                p.accept(",")
                names.append(p.name())
            for name in names:
                if name in p.indexes or name in VERBS:
                    p.error(f"index dupliqué ou réservé: {name}")
                p.indexes[name] = key
        elif p.accept("VALUE"):
            if initial is not None:
                p.error("VALUE dupliqué")
            p.accept("IS")
            initial = literal(p)
        else:
            if has_usage:
                p.error("clause de donnée non prise en charge")
            has_usage = True
            if p.accept("USAGE"):
                p.accept("IS")
            if p.t.string or p.t.key not in USAGES:
                p.error("USAGE/clause non pris en charge")
            usage = p.take().key
    p.expect(".")
    expanded = re.sub(r"([9X])\((\d+)\)", lambda m: m[1] * min(int(m[2]), 257), picture)
    if not picture:
        kind, digits, scale, signed = "text", 0, 0, False
        if initial or has_usage:
            p.error("VALUE/USAGE de groupe non pris en charge")
        if level == 77:
            p.error("niveau 77 requiert une PICTURE")
    elif re.fullmatch(r"X+", expanded):
        kind, digits, scale, signed = "text", len(expanded), 0, False
        if digits > 256 or usage != "DISPLAY":
            p.error("PIC X limité à 256 caractères DISPLAY")
    elif re.fullmatch(r"S?9+(?:V9+)?", expanded):
        kind, digits, signed = "number", expanded.count("9"), expanded.startswith("S")
        scale = len(expanded.split("V")[1]) if "V" in expanded else 0
        if digits > 18:
            p.error("PIC numérique limité à 18 chiffres")
    else:
        p.error(f"PICTURE non prise en charge: {picture}")
    if initial is not None:
        if file_record or redefines:
            p.error("VALUE sur FD/REDEFINES non pris en charge")
        if (kind == "text") != initial.string:
            p.error("VALUE incompatible avec la PICTURE")
    else:
        initial = Token("" if kind == "text" else "0", p.t.line, kind == "text")
    descriptor = Field(key, picture, kind, digits, scale, signed, initial, usage,
                       label, level, parent, [], count, table, redefines, filler, file_record)
    descriptor.occurs_min, descriptor.depending = minimum, depending
    p.fields[key] = descriptor
    if parent:
        p.fields[parent].children.append(key)
    p.data_stack.append(key)
    p.last_data = key
    return key
