"""Data division parsing, with explicit storage hierarchy and condition names."""
import re

from .frontend import Condition, Field, Token, VERBS

USAGES = {"DISPLAY", "COMP", "COMPUTATIONAL", "BINARY", "COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL", "COMP-4", "COMPUTATIONAL-4",
          "INDEX"}


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
    elif token.key in {"QUOTE", "QUOTES"}:
        token = Token('"', token.line, True)
    elif token.key in getattr(p, "symbolic", {}) and not p.candidates(token.key):
        token = Token(chr(p.symbolic[token.key]), token.line, True)
    elif token.key in {"HIGH-VALUE", "HIGH-VALUES"}:
        token = Token(getattr(p, "high_value", "\xff"), token.line, True)
    elif token.key in {"LOW-VALUE", "LOW-VALUES"}:
        token = Token(getattr(p, "low_value", "\x00"), token.line, True)
    elif not re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", token.text):
        p.error("littéral attendu")
    if negative:
        token = Token("-" + token.text, token.line, token.string)
    return token


# cobc tree.c valid_char_order: PRECEDENCE[current][seen] allows the current
# symbol type after a symbol type already seen (standard PICTURE precedence).
PRECEDENCE = [list(map(int, row.split())) for row in """
1 1 1 0 1 0 0 1 0 1 1 1 1 1 1 1 1 0 0 1 0 1 0 1 0
1 1 1 0 1 0 0 1 0 1 1 1 1 1 1 1 0 0 0 1 0 1 0 0 0
1 1 0 0 1 0 0 1 0 1 0 1 0 1 0 1 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 0 0 0 1 1 1 1 0 0 1 1 1 0 0 0 1 1 1 0 0 0
1 1 1 0 0 0 0 1 1 1 1 0 0 1 1 1 0 0 0 1 1 1 0 0 0
0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 1 0 0 0 0 1 1 0 0 0 0 1 0 0 0 1 1 1 0 0 0
1 1 0 0 1 0 0 1 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 1 0 0 1 0 1 1 0 0 0 0 0 0 0 0 1 0 1 0 0 0
1 1 0 0 0 0 0 1 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 0 0 0 1 0 0 0 1 1 0 0 0 0 0 0 1 0 0 0 0 0
1 1 0 0 1 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 1 0 0 0 0 0 0 0 0 1 1 0 0 0 0 1 0 0 0 0 0
1 1 1 1 1 0 0 1 0 1 0 1 0 1 0 1 1 1 1 1 0 1 0 0 1
1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 0 0 1 0 0 1 0 1 0 1 0 1 0 1 0 0 1 0 1 0 0 0 0
1 1 0 0 1 0 0 1 0 1 0 1 0 1 0 1 0 0 1 0 1 0 0 0 0
0 0 0 0 1 0 0 1 0 0 0 0 0 0 0 0 0 0 1 1 0 1 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0
1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0
1 1 1 0 1 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0
""".strip().splitlines()]


def valid_char_order(symbols):
    """cobc's find_floating_insertion_str, char_to_precedence_idx and
    valid_char_order for the default currency $, decimal point . and comma."""
    simple = set("B0/,")
    first = last = None
    previous, floating = None, " "
    index = 0
    while index < len(symbols):
        c, n = symbols[index]
        if first is None and c in "+-$":
            if previous is not None and symbols[previous][0] == c:
                first, floating = previous, c
                index += 1
                continue
            if n > 1:
                first, floating = index, c
                index += 1
                continue
        if first is None and c not in simple:
            previous = index
        elif first is not None and not (c in simple or c == floating):
            last = index - 1
            break
        index += 1
    if index == len(symbols) and first is not None:
        last = index - 1
    elif index < len(symbols) and symbols[index][0] in ".V":
        if all(c in simple or c == floating for c, _ in symbols[index + 1:]):
            last = len(symbols) - 1
    seen, before_point, non_p = set(), True, False
    for position, (c, n) in enumerate(symbols):
        for _ in range(2 if n > 1 else 1):
            floating_here = first is not None and last is not None and first <= position <= last
            if c in "B0/":
                kind = 0
            elif c in ".,":
                kind = 2 if c == "." else 1
            elif c in "+-":
                kind = (11 if before_point else 12) if floating_here else (5 if position == len(symbols) - 1 and position else 4)
            elif c in "CD":
                kind = 6
            elif c in "Z*":
                kind = 9 if before_point else 10
            elif c == "9":
                kind = 15
            elif c == "V":
                kind = 19
            elif c == "P":
                kind = 20 if non_p and before_point else 21
            else:  # currency
                if floating_here:
                    kind = 13 if before_point else 14
                else:
                    kind = 7 if position <= 1 else 8 if position >= len(symbols) - 2 else 7
            if 9 <= kind <= 15:
                non_p = True
            if any(not PRECEDENCE[kind][other] for other in seen):
                return False
            seen.add(kind)
            if c in ".V":
                before_point = False
    return True


def edited_picture(p, picture):
    """Numeric-edited PICTURE as cobc's cb_build_picture: the symbol list
    (identical consecutive symbols grouped, CR/DB as C/D), size, digits, scale.

    The grouping matters at run time: libcob's editing tells a floating
    insertion from a fixed one by the repetition count of each group.
    """
    symbols, i = [], 0
    text = picture.upper()
    while i < len(text):
        c = text[i]
        if c in "CD":
            if text[i + 1:i + 2] != ("R" if c == "C" else "B"):
                p.error(f"PICTURE éditée invalide: {picture}")
            i += 1
        n = 1
        while i + 1 < len(text) and text[i + 1] == c and c not in "CD":
            n += 1
            i += 1
        if i + 1 < len(text) and text[i + 1] == "(":
            close = text.find(")", i + 2)
            if close < 0 or not text[i + 2:close].isdigit() or int(text[i + 2:close]) < 1:
                p.error(f"PICTURE éditée invalide: {picture}")
            n += min(int(text[i + 2:close]), 65536) - 1
            i = close
        symbols.append((c, n))
        i += 1
    if any(c not in "9Z*+-$.,VPB0/CD" for c, _ in symbols):
        p.error(f"PICTURE non prise en charge: {picture}")
    digits = scale = size = v_count = s_edit = c_count = 0
    for index, (c, n) in enumerate(symbols):
        if c in "9Z*":
            digits += n
            scale += n if v_count else 0
        elif c in "+-":
            digits += n - (1 if s_edit == 0 else 0)
            if v_count:
                scale += n - (1 if s_edit == 0 else 0)
            s_edit += 1
        elif c in "CD":
            if n != 1 or index != len(symbols) - 1:
                p.error(f"PICTURE éditée invalide: {picture}")
            s_edit += 1
        elif c == "$":
            digits += n - 1 if c_count == 0 else n
            c_count += n - 1 if c_count == 0 else n
        elif c in ".V":
            v_count += n
        elif c == "P":
            previous = "".join(symbol for symbol, _ in symbols[:index])
            at_end = index == len(symbols) - 1 or (index == len(symbols) - 2 and symbols[-1][0] == "V")
            if previous in {"", "V"}:
                v_count += 1
            elif at_end:
                digits += n
            else:
                p.error(f"PICTURE éditée invalide: {picture}")
            scale += n if v_count else -n
        size += 0 if c in "VP" else 2 * n if c in "CD" else n
    used = {c for c, _ in symbols}
    if v_count > 1 or digits < 1 or {"Z", "*"} <= used or not valid_char_order(symbols):
        p.error(f"PICTURE éditée invalide pour cobc: {picture}")
    return symbols, size, digits, scale, s_edit > 0


def declaration(p, file_record=False):
    if p.t.string or not p.t.key.isdigit():
        p.error("niveau de donnée attendu")
    level = int(p.take().key)
    # A description without a name is an implicit FILLER.
    implicit_filler = level != 88 and not p.t.string and p.t.key in {
        "PIC", "PICTURE", "VALUE", "VALUES", "USAGE", "OCCURS", "REDEFINES", "SIGN", "BLANK", "JUSTIFIED",
        "JUST", "LEADING", "TRAILING", "SYNC", "SYNCHRONIZED", "."} | USAGES
    if implicit_filler and p.t.key in {"PIC", "PICTURE"} and p.tokens[p.i + 1].key in {"PIC", "PICTURE"}:
        p.error("nom réservé: " + p.t.key)
    label = "FILLER" if implicit_filler else p.name()
    if label != "FILLER":
        p.user_word(label)
    if level == 88:
        if not p.last_data:
            p.error("niveau 88 requiert une donnée précédente")
        # A group's condition compares its storage as alphanumeric text.
        group_condition = not p.fields[p.last_data].picture and p.fields[p.last_data].usage != "INDEX"
        key = p.last_data + "." + label
        if key in p.conditions or label in VERBS:
            p.error("condition dupliquée ou réservée")
        if not (p.accept("VALUE") or p.accept("VALUES")):
            p.error("VALUE attendu au niveau 88")
        p.accept("IS") or p.accept("ARE")
        values = []
        while not p.at(".") and not p.at("WHEN"):
            parent = p.fields[p.last_data]
            figurative = not p.t.string and p.t.key in {"QUOTE", "QUOTES", "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES"} | (
                {"ZERO", "ZEROS", "ZEROES"} if parent.kind == "text" else set())
            if group_condition and not p.t.string:
                p.error("niveau 88 de groupe limité aux littéraux alphanumériques")
            if p.accept("ALL") or figurative:
                # ALL literal and figurative constants: repeated over the item.
                token = literal(p)
                if not token.string:
                    token = Token(token.text, token.line, True)
                if not token.string or parent.kind != "text":
                    p.error("VALUE ALL de niveau 88 limité aux PIC X/A")
                low = Token((token.text * parent.digits)[:parent.digits], token.line, True)
                values.append((low, low))
                p.accept(",")
                continue
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
    if level == 66:
        # renames_entry: the item follows its record and aliases storage
        # once the record is laid out (Parser.apply_renames).
        if not p.data_stack or p.fields[p.data_stack[0]].level != 1:
            p.error("66 RENAMES doit suivre un enregistrement 01")
        founder = p.data_stack[0]
        line = p.t.line
        p.expect("RENAMES")

        def target():
            name, qualifiers = p.name(), []
            while p.accept("OF") or p.accept("IN"):
                qualifiers.append(p.name())
            if p.candidates(name, True) and not p.candidates(name):
                p.error("RENAMES may not reference a level 88")
            return p.resolve(name, qualifiers)
        first = target()
        thru = target() if p.accept("THRU") or p.accept("THROUGH") else None
        p.expect(".")
        key = founder + "." + label
        taken = lambda name: name in p.fields or any(r[0] == name for r in p.renames)
        if taken(key):
            # A homonym of an item of the record: references are ambiguous
            # (cb_ref), keys stay distinct like homonymous siblings.
            duplicate = 2
            while taken(f"{key}${duplicate}"):
                duplicate += 1
            key = f"{key}${duplicate}"
        p.renames.append((key, label, first, thru, founder, line))
        return key
    if level not in {1, 77} and not 2 <= level <= 49:
        p.error("niveaux pris en charge: 01-49, 66, 77 et 88")
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
    if parent and key in p.fields and label not in VERBS:
        # Homonymous siblings are valid; a reference to them is ambiguous
        # (cb_ref), which resolve() reports. Keep their keys distinct.
        duplicate = 2
        while f"{key}${duplicate}" in p.fields:
            duplicate += 1
        key = f"{key}${duplicate}"
    if key in p.fields or label in VERBS or label in {"ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES"}:
        p.error(f"nom de donnée réservé ou dupliqué: {label}")
    picture, usage, initial = "", "DISPLAY", None
    has_usage, table, count, redefines = False, False, 1, None
    minimum, depending = 1, None
    figurative = None
    blank_zero = justified = False
    sign_clause = None
    synchronized = False
    search_keys = []
    external = is_global = False
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
            if p.t.string or p.t.key in {".", "<EOF>", "VALUE", "USAGE", "OCCURS", "INDEXED"} | USAGES:
                p.error("mot PICTURE contigu attendu")
            picture = p.picture_symbols(p.take().key)
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
                p.expect("DEPENDING"); p.accept("ON")
                depending = p.name()
        elif p.at("ASCENDING") or p.at("DESCENDING"):
            # ASCENDING/DESCENDING KEY: the keys of SEARCH ALL, in order.
            if not table:
                p.error("KEY requiert OCCURS")
            descending = p.take().key == "DESCENDING"
            p.accept("KEY"); p.accept("IS")
            search_keys.append((descending, p.name()))
            while not p.t.string and p.t.key not in {"ASCENDING", "DESCENDING", "INDEXED", "PIC", "PICTURE",
                                                     "VALUE", "USAGE", ".", "<EOF>"} | USAGES:
                search_keys.append((descending, p.name()))
        elif p.accept("INDEXED"):
            if not table:
                p.error("INDEXED BY requiert OCCURS")
            p.accept("BY")
            names = [p.name()]
            while p.t.key not in {"PIC", "PICTURE", "VALUE", "USAGE", "ASCENDING", "DESCENDING", ".", "<EOF>"} | USAGES:
                p.accept(",")
                names.append(p.name())
            for name in names:
                p.user_word(name)
                if name in p.indexes or name in VERBS:
                    p.error(f"index dupliqué ou réservé: {name}")
                p.indexes[name] = key
        elif p.accept("VALUE"):
            if initial is not None:
                p.error("VALUE dupliqué")
            p.accept("IS")
            repeated = p.accept("ALL")
            # A group VALUE fills its whole area: keep ZERO distinct from 0.
            figurative = None if p.t.string else (
                "0" if p.t.key in {"ZERO", "ZEROS", "ZEROES"} else " " if p.t.key in {"SPACE", "SPACES"}
                else '"' if p.t.key in {"QUOTE", "QUOTES"} else getattr(p, "high_value", "\xff") if p.t.key in {"HIGH-VALUE", "HIGH-VALUES"}
                else getattr(p, "low_value", "\x00") if p.t.key in {"LOW-VALUE", "LOW-VALUES"}
                else chr(p.symbolic[p.t.key]) if p.t.key in getattr(p, "symbolic", {}) and not p.candidates(p.t.key)
                else None)
            initial = literal(p)
            if repeated:
                # VALUE ALL literal repeats the literal over the item.
                if figurative == "0":
                    initial = Token("0", initial.line, True)
                if not initial.string:
                    p.error("VALUE ALL limité aux littéraux alphanumériques et constantes figuratives")
                figurative = ("ALL", initial.text)
        elif p.at("SIGN") or p.at("LEADING") or p.at("TRAILING"):
            # SIGN [IS] LEADING|TRAILING [SEPARATE [CHARACTER]]
            if sign_clause is not None:
                p.error("SIGN dupliqué")
            if p.accept("SIGN"):
                p.accept("IS")
            if not (p.at("LEADING") or p.at("TRAILING")):
                p.error("SIGN requiert LEADING ou TRAILING")
            position = p.take().key
            separate = p.accept("SEPARATE")
            if separate:
                p.accept("CHARACTER")
            sign_clause = (position, separate)
        elif p.at("EXTERNAL") or p.at("GLOBAL") or (p.at("IS") and p.tokens[p.i + 1].key in {"EXTERNAL", "GLOBAL"}):
            # external_clause / global_clause: 01 or 77 data names only.
            p.accept("IS")
            clause = p.take().key
            if level not in {1, 77} or filler:
                p.error(f"{clause} only allowed at 01/77 level")
            if clause == "EXTERNAL":
                if file_record or getattr(p, "in_linkage", False):
                    p.error("EXTERNAL not allowed here")
                if redefines:
                    p.error("EXTERNAL and REDEFINES are mutually exclusive")
                if p.at("AS"):
                    p.error("EXTERNAL AS non pris en charge")
                external = True
            else:
                is_global = True
        elif p.accept("SYNCHRONIZED") or p.accept("SYNC"):
            p.accept("LEFT") or p.accept("RIGHT")
            synchronized = True
        elif p.accept("JUSTIFIED") or p.accept("JUST"):
            if justified:
                p.error("JUSTIFIED dupliqué")
            p.accept("RIGHT")
            justified = True
        elif p.accept("BLANK"):
            p.accept("WHEN")
            if blank_zero or not (p.accept("ZERO") or p.accept("ZEROS") or p.accept("ZEROES")):
                p.error("BLANK WHEN ZERO attendu")
            blank_zero = True
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
    # USAGE INDEX without PICTURE is an elementary index data item, unless
    # subordinate entries follow (a group whose USAGE they inherit).
    has_children = (not p.t.string and p.t.key.isdigit() and level not in {66, 77}
                    and int(p.t.key) not in {66, 77, 88} and level < int(p.t.key) <= 49)
    # Group USAGE applies to subordinate elementary items without their own
    # USAGE; GnuCOBOL lets an explicit subordinate USAGE take precedence.
    ancestors = []
    cursor = parent
    while cursor:
        ancestors.append(p.fields[cursor])
        cursor = p.fields[cursor].parent
    if not has_usage:
        usage = next((a.group_usage for a in ancestors if a.group_usage), usage)
    if any(a.group_value is not None for a in ancestors) and initial is not None:
        p.error("VALUE subordonné à un VALUE de groupe non pris en charge")
    alnum_edit = ""

    def repeat(match):
        count = int(match[2])
        if count < 1:
            p.error("répétition PICTURE strictement positive requise")
        return match[1] * min(count, 65536)

    if usage == "INDEX" and not picture and not has_children:
        if initial is not None:
            p.error("VALUE sur un article USAGE INDEX non pris en charge")
        # cobc: a native signed int (4 bytes), holding an occurrence number.
        picture = "S9(9)"
    elif usage == "INDEX" and picture:
        p.error("USAGE INDEX ne prend pas de PICTURE")
    expanded = re.sub(r"([9XZAP])\((\d+)\)", repeat, picture)
    group_value = group_usage = None
    if not picture:
        kind, digits, scale, signed = "text", 0, 0, False
        if level == 77:
            p.error("niveau 77 requiert une PICTURE")
        if initial is not None:
            if not initial.string and figurative != "0":
                p.error("VALUE de groupe limité à un littéral alphanumérique, ZERO ou SPACE")
            if not getattr(p, "in_communication", False):
                if file_record or redefines or any(a.redefines or a.file_record for a in ancestors):
                    p.error("VALUE de groupe sur FD/REDEFINES non pris en charge")
                group_value = (initial.text, figurative)
            # CD records are static storage that cobc never initializes.
        if has_usage:
            group_usage = usage
            usage = "DISPLAY"
        initial = None
    elif (re.fullmatch(r"[XA9B0/]+", re.sub(r"([XA9B0/])\((\d+)\)", repeat, picture.upper()))
          and set(picture.upper()) & set("XA") and set(re.sub(r"\(\d+\)", "", picture.upper())) & set("B0/")):
        # Alphanumeric-edited: stored and compared as text, edited on MOVE.
        alnum_edit = re.sub(r"([XA9B0/])\((\d+)\)", repeat, picture.upper())
        kind, digits, scale, signed = "text", len(alnum_edit), 0, False
        if digits > 65535 or usage != "DISPLAY":
            p.error("PIC alphanumérique éditée limitée à 65535 caractères DISPLAY")
    elif re.fullmatch(r"X+|A+", expanded) or (re.fullmatch(r"[XA9]+", expanded) and set(expanded) - {"9"}
                                                and len(set(expanded)) > 1):
        # PIC A is alphabetic: stored and compared like PIC X; the emitter
        # refuses the numeric MOVEs that GnuCOBOL rejects for it.
        kind, digits, scale, signed = "text", len(expanded), 0, False
        if digits > 65535 or usage != "DISPLAY":
            p.error("PIC X/A limité à 65535 caractères DISPLAY")
    elif re.fullmatch(r"S?(?:9+(?:V9*)?|V9+)", expanded):
        kind, digits, signed = "number", expanded.count("9"), expanded.startswith("S")
        scale = len(expanded.split("V")[1]) if "V" in expanded else 0
        if digits > 18:
            p.error("PIC numérique limité à 18 chiffres")
    elif re.fullmatch(r"S?9+P+V?|S?V?P+9+", expanded):
        # Scaling positions, as cobc's picture analysis: trailing P give a
        # negative scale (units of 10^n), leading P an implicit V before them.
        # Only the 9 positions are stored; P is limited to USAGE DISPLAY.
        kind, digits, signed = "number", expanded.count("9"), expanded.startswith("S")
        positions = expanded.count("P")
        scale = -positions if expanded.lstrip("S").startswith("9") else positions + digits
        if digits > 18 or usage != "DISPLAY":
            p.error("PICTURE P limitée à 18 chiffres USAGE DISPLAY")
    elif (re.fullmatch(r"[9Z*+\-$.,VPB0/()0-9]*(?:CR|DB)?", picture.upper())
          and set(re.sub(r"\(\d+\)", "", picture.upper())) - set("9VP")):
        kind = "edited"
        symbols, edit_size, digits, scale, signed = edited_picture(p, picture)
        if digits > 18 or edit_size > 256 or usage != "DISPLAY":
            p.error("PIC éditée limitée à 18 chiffres, 256 caractères DISPLAY")
    else:
        p.error(f"PICTURE non prise en charge: {picture}")
    if blank_zero:
        # field.c: a numeric DISPLAY item with BLANK WHEN ZERO becomes
        # numeric-edited with a reconstructed 9(n) picture.
        if kind == "number" and usage == "DISPLAY" and not signed and scale == 0:
            kind, symbols, edit_size = "edited", [("9", digits)], digits
        elif kind != "edited" or any(c == "*" for c, _ in symbols):
            p.error("BLANK WHEN ZERO limité aux PICTURE éditées sans * et aux entiers DISPLAY non signés")
    if figurative == "0" and initial is not None and kind == "text" and picture and not alnum_edit:
        # VALUE ZERO of an alphanumeric item: zeros in every position.
        initial = Token("0" * digits, initial.line, True)
    if isinstance(figurative, tuple) and figurative[1] == "0" and kind == "number":
        # VALUE ALL ZERO of a numeric item is its zero value.
        initial, figurative = Token("0", initial.line), "0"
    if isinstance(figurative, tuple):
        if kind != "text" or alnum_edit:
            p.error("VALUE ALL limité aux PIC X/A et groupes")
        if picture:
            initial = Token((figurative[1] * digits)[:digits], initial.line, True)
    elif isinstance(figurative, str) and figurative not in {"0", " "} and initial is not None and kind == "text":
        # A figurative constant fills every position of the item.
        initial = Token(figurative * digits, initial.line, True)
    group_sign = None
    if not picture:
        # A group SIGN clause applies to its signed numeric DISPLAY items.
        group_sign, sign_clause = sign_clause, None
    elif sign_clause is None:
        sign_clause = next((a.group_sign for a in ancestors if a.group_sign), None)
        if sign_clause and not (kind == "number" and signed and usage == "DISPLAY"):
            sign_clause = None
    if sign_clause and not (kind == "number" and signed and usage == "DISPLAY"):
        p.error("SIGN requiert une PICTURE numérique signée USAGE DISPLAY")
    if justified and (kind != "text" or alnum_edit or not picture):
        p.error("JUSTIFIED limité aux PIC X/A élémentaires")
    if initial is not None and getattr(p, "in_communication", False):
        if kind != "edited" and picture and (kind == "text") != initial.string:
            p.error("VALUE incompatible avec la PICTURE")
        initial = None
    explicit_value = initial is not None
    if initial is not None:
        if file_record or redefines:
            p.error("VALUE sur FD/REDEFINES non pris en charge")
        if kind != "edited" and (kind == "text") != initial.string:
            p.error("VALUE incompatible avec la PICTURE")
    else:
        initial = Token("" if kind == "text" else "0", p.t.line, kind == "text")
    linkage = getattr(p, "in_linkage", False)
    if linkage and (explicit_value or group_value is not None):
        p.error("VALUE en LINKAGE SECTION non pris en charge")
    descriptor = Field(key, picture, kind, digits, scale, signed, initial, usage,
                       label, level, parent, [], count, table, redefines, filler, file_record)
    descriptor.linkage = linkage
    descriptor.explicit_value = explicit_value
    descriptor.occurs_min, descriptor.depending = minimum, depending
    descriptor.search_keys = search_keys
    descriptor.group_value, descriptor.group_usage = group_value, group_usage
    descriptor.editing = expanded if kind == "edited" else ""
    descriptor.alnum_edit = alnum_edit
    descriptor.synchronized = synchronized
    descriptor.group_sign = group_sign
    descriptor.sign_leading = bool(sign_clause and sign_clause[0] == "LEADING")
    descriptor.sign_separate = bool(sign_clause and sign_clause[1])
    descriptor.justified = justified
    descriptor.external, descriptor.is_global = external, is_global
    if kind == "edited":
        descriptor.edit_symbols, descriptor.edit_size = symbols, edit_size
        descriptor.blank_zero = blank_zero
    p.fields[key] = descriptor
    if parent:
        p.fields[parent].children.append(key)
    p.data_stack.append(key)
    p.last_data = key
    return key
