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
            elif f.usage != "DISPLAY":
                f.size = 1 if f.digits <= 2 else 2 if f.digits <= 4 else 4 if f.digits <= 9 else 8
            else:
                f.size = f.digits
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
                    if not (f.file_record and target.file_record and f.parent is None):
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
    # A terminal ODO has a fixed address and a variable enclosing group length.
    # Sliding fields, variable strides and record I/O need a separate layout model.
    for f in fields.values():
        if not f.depending:
            continue
        controller = fields[f.depending]
        if controller.kind != "number" or controller.scale or controller.dimensions or controller.index_for:
            raise CobolError("DEPENDING ON requiert un entier scalaire avec PICTURE")
        if f.file_record or f.parent is None:
            raise CobolError("OCCURS DEPENDING ON limité à une table subordonnée WORKING-STORAGE")
        cursor = f
        while cursor.parent:
            parent = fields[cursor.parent]
            if parent.table or parent.children[-1] != cursor.name:
                raise CobolError("OCCURS DEPENDING ON doit terminer chaque groupe parent, sans OCCURS englobant")
            cursor = parent
        root = cursor
        if controller.name == root.name or controller.name.startswith(root.name + "."):
            raise CobolError("contrôleur DEPENDING ON requis hors du groupe variable")
        subtree = [item for item in fields.values() if item.name == root.name or item.name.startswith(root.name + ".")]
        if any(item.redefines for item in subtree) or any(item.redefines == root.name for item in fields.values()):
            raise CobolError("REDEFINES d'un groupe variable non pris en charge")
    return total


def leaves(fields, root, include_redefines=False):
    f = fields[root]
    if f.redefines and not include_redefines:
        return []
    if f.picture:
        return [f]
    return [leaf for key in f.children for leaf in leaves(fields, key, include_redefines)]
