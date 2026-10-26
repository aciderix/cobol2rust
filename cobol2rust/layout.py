"""Concrete storage layout for the default GnuCOBOL 3.2 data profile."""
from .frontend import CobolError


def layout_fields(fields):
    def size(key):
        f = fields[key]
        if f.picture:
            if f.kind == "edited":
                f.size = f.edit_size
            elif f.usage in {"COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL"}:
                f.size = (f.digits + 2) // 2
            elif f.usage == "COMP-6":
                # compute_size: no sign nibble.
                f.size = (f.digits + 1) // 2
            elif f.usage != "DISPLAY":
                f.size = 1 if f.digits <= 2 else 2 if f.digits <= 4 else 4 if f.digits <= 9 else 8
            else:
                f.size = f.digits + (1 if f.sign_separate else 0)
        else:
            if not f.children:
                raise CobolError(f"groupe vide: {f.name}")
            f.size = siblings(f.children, 0)
        if f.size * f.occurs > 16 * 1024 * 1024:
            raise CobolError(f"zone de données trop grande: {f.name}")
        return f.size * f.occurs

    extents = {}

    def siblings(keys, start):
        cursor = start
        for key in keys:
            f = fields[key]
            total = size(key)
            if f.redefines:
                target = fields[f.redefines]
                extent = extents.get(target.name, target.size * target.occurs)
                if total > extent:
                    # Alternate FD records follow their first record and may be
                    # larger: the record area grows to the largest one.
                    # A larger 01 REDEFINES grows the area (memory_size, field.c).
                    if not (f.parent is None and target.parent is None and f.file_record == target.file_record):
                        raise CobolError(f"REDEFINES plus grand que sa zone non pris en charge: {key}")
                    cursor += total - extent
                    extents[target.name] = total
                f.offset = target.offset
            else:
                f.offset = cursor
                cursor += total
        return cursor - start

    roots = [key for key, f in fields.items() if f.parent is None]
    total = siblings(roots, 0)
    if total > 16 * 1024 * 1024:
        raise CobolError("mémoire COBOL limitée à 16 Mio")

    def locate(key, parent_offset, dimensions):
        f = fields[key]
        f.offset += parent_offset
        f.dimensions = [*dimensions, *([(f.size, f.occurs)] if f.table else [])]
        if len(f.dimensions) > 7:
            raise CobolError("tableaux limités à 7 dimensions")
        for child in f.children:
            locate(child, f.offset, f.dimensions)
    for key in roots:
        locate(key, 0, [])
    # SYNCHRONIZED aligns binary items of 2, 4 or 8 bytes inside their record
    # (cobc compute_size), padding before them and after table entries; it
    # has no effect on other items. Only layouts needing no padding are kept.
    for f in fields.values():
        cursor, synced = f, f.synchronized
        while cursor.parent:
            cursor = fields[cursor.parent]
            synced = synced or (cursor.synchronized and f.usage != "DISPLAY")
        if not synced or not f.picture or f.usage in {"DISPLAY", "COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL", "COMP-6"}:
            continue
        align = f.size if f.size in {2, 4, 8} else 1
        if f.index_for or f.usage == "INDEX":
            align = 4
        if align == 1:
            continue
        aligned = (f.offset - cursor.offset) % align == 0
        tables = []
        parent = f.parent
        while parent:
            if fields[parent].table:
                tables.append(fields[parent])
            parent = fields[parent].parent
        if not aligned or any(table.size % align for table in tables) or (f.table and f.size % align):
            raise CobolError(f"SYNCHRONIZED avec remplissage d'alignement non pris en charge: {f.label}")
    # A terminal ODO has a fixed address and a variable enclosing group length.
    # Sliding fields, variable strides and record I/O need a separate layout model.
    for f in fields.values():
        if not f.depending:
            continue
        controller = fields[f.depending]
        if controller.kind != "number" or controller.scale or controller.dimensions or controller.index_for:
            raise CobolError("DEPENDING ON requiert un entier scalaire avec PICTURE")
        if f.parent is None:
            raise CobolError("OCCURS DEPENDING ON limité à une table subordonnée")
        cursor = f
        while cursor.parent:
            parent = fields[cursor.parent]
            if parent.table or parent.children[-1] != cursor.name:
                raise CobolError("OCCURS DEPENDING ON doit terminer chaque groupe parent, sans OCCURS englobant")
            cursor = parent
        root = cursor
        if controller.name.startswith(f.name + "."):
            raise CobolError("contrôleur DEPENDING ON dans sa propre table non pris en charge")
        subtree = [item for item in fields.values() if item.name == root.name or item.name.startswith(root.name + ".")]
        # The other 01 records of an FD share its area (an implicit REDEFINES).
        if any(item.redefines for item in subtree if not (item is root and root.file_record)) or any(
                item.redefines == root.name and not (item.file_record and item.parent is None) for item in fields.values()):
            raise CobolError("REDEFINES d'un groupe variable non pris en charge")
    return total


def leaves(fields, root, include_redefines=False):
    f = fields[root]
    if f.redefines and not include_redefines:
        return []
    if f.picture:
        return [f]
    return [leaf for key in f.children for leaf in leaves(fields, key, include_redefines)]
