"""Read-only binary triage. No input executable is ever launched."""
from __future__ import annotations

import hashlib
import re
import struct
from pathlib import Path

from .frontend import CobolError


class Image:
    def __init__(self, data):
        self.data = data

    def unpack(self, fmt, offset):
        if offset < 0 or offset + struct.calcsize(fmt) > len(self.data):
            raise CobolError("binaire tronqué ou pointeur hors limites")
        return struct.unpack_from(fmt, self.data, offset)

    def cstring(self, offset, limit=4096):
        if offset < 0 or offset >= len(self.data):
            raise CobolError("chaîne binaire hors limites")
        end = self.data.find(b"\0", offset, min(offset + limit, len(self.data)))
        if end < 0:
            raise CobolError("chaîne binaire non terminée")
        return self.data[offset:end].decode("ascii", errors="replace")


def pe_info(data):
    image = Image(data)
    pe = image.unpack("<I", 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise CobolError("signature PE invalide (DOS/MZ seul non pris en charge)")
    machine, count, _, _, _, optional_size, _ = image.unpack("<HHIIIHH", pe + 4)
    optional = pe + 24
    magic = image.unpack("<H", optional)[0]
    if magic not in (0x10B, 0x20B):
        raise CobolError("en-tête PE optionnel non pris en charge")
    bits = 32 if magic == 0x10B else 64
    sections = []
    for index in range(count):
        pos = optional + optional_size + index * 40
        name, vsize, rva, size, raw = image.unpack("<8sIIII", pos)
        sections.append((name.rstrip(b"\0").decode("ascii", errors="replace"), rva, vsize, raw, size))

    def offset(rva):
        for _, start, vsize, raw, size in sections:
            if start <= rva < start + max(size, vsize):
                if rva - start >= size:
                    raise CobolError("RVA PE dans une section sans données sur disque")
                return raw + rva - start
        headers = image.unpack("<I", optional + 60)[0]
        if rva < min(headers, len(data)):
            return rva
        raise CobolError("RVA PE hors sections")

    libraries, symbols = [], []
    dd_offset = 96 if bits == 32 else 112
    dir_count = image.unpack("<I", optional + dd_offset - 4)[0]
    if dir_count > 1 and optional_size >= dd_offset + 16:
        imports, size = image.unpack("<II", optional + dd_offset + 8)
        if imports:
            base = offset(imports)
            for i in range(min(size // 20 + 1, 4096)):
                original, stamp, chain, dll, first = image.unpack("<IIIII", base + i * 20)
                if (original, stamp, chain, dll, first) == (0, 0, 0, 0, 0):
                    break
                libraries.append(image.cstring(offset(dll)))
                thunk = offset(original or first)
                for j in range(65536):
                    value = image.unpack("<I" if bits == 32 else "<Q", thunk + j * (bits // 8))[0]
                    if value == 0:
                        break
                    if value & (1 << (bits - 1)):
                        symbols.append(f"{libraries[-1]}:ordinal:{value & 0xffff}")
                    else:
                        symbols.append(image.cstring(offset(value) + 2))
                else:
                    raise CobolError("table de thunks PE non terminée")
            else:
                raise CobolError("table d'import PE non terminée")
    return {"format": "PE", "bits": bits, "architecture": {0x14C: "x86", 0x8664: "x86_64", 0xAA64: "aarch64"}.get(machine, hex(machine)),
            "libraries": sorted(set(libraries)), "symbols": sorted(set(symbols)), "sections": [x[0] for x in sections]}


def elf_info(data):
    image = Image(data)
    if len(data) < 16 or data[4] not in (1, 2) or data[5] not in (1, 2):
        raise CobolError("en-tête ELF invalide")
    bits = 32 if data[4] == 1 else 64
    endian = "<" if data[5] == 1 else ">"
    header = image.unpack(endian + ("HHIIIIIHHHHHH" if bits == 32 else "HHIQQQIHHHHHH"), 16)
    machine, section_offset, entry_size, count, names_index = header[1], header[5], header[10], header[11], header[12]
    section_fmt = endian + ("IIIIIIIIII" if bits == 32 else "IIQQQQIIQQ")
    if section_offset and count == 0:
        raise CobolError("numérotation étendue ELF non prise en charge")
    sections = []
    if count:
        if entry_size < struct.calcsize(section_fmt) or names_index >= count:
            raise CobolError("table de sections ELF invalide")
        for i in range(count):
            sections.append(image.unpack(section_fmt, section_offset + i * entry_size))
    libraries, symbols, names = [], [], []
    for section in sections:
        if section[0]:
            names.append(image.cstring(sections[names_index][4] + section[0]))
        typ, start, size, link, stride = section[1], section[4], section[5], section[6], section[9]
        if typ not in (2, 6, 11):
            continue
        if link >= len(sections):
            raise CobolError("lien de section ELF invalide")
        strings = sections[link][4]
        minimum = (8 if bits == 32 else 16) if typ == 6 else (16 if bits == 32 else 24)
        if stride < minimum or size // stride > 1000000:
            raise CobolError("taille d'entrée ELF invalide")
        for pos in range(start, start + size, stride):
            if typ == 6:
                tag, value = image.unpack(endian + ("iI" if bits == 32 else "qQ"), pos)
                if tag == 1:
                    libraries.append(image.cstring(strings + value))
            else:
                index = image.unpack(endian + "I", pos)[0]
                if index:
                    symbols.append(image.cstring(strings + index))
    return {"format": "ELF", "bits": bits, "architecture": {3: "x86", 62: "x86_64", 22: "s390", 183: "aarch64"}.get(machine, str(machine)),
            "libraries": sorted(set(libraries)), "symbols": sorted(set(symbols)), "sections": names}


def inspect_binary(path: Path, aret: str | None = None):
    data = path.read_bytes()
    if data.startswith(b"MZ"):
        info = pe_info(data)
    elif data.startswith(b"\x7fELF"):
        info = elf_info(data)
    else:
        raise CobolError("format binaire non pris en charge: seuls PE et ELF sont inspectés")
    ascii_strings = {m[0].decode("ascii") for m in re.finditer(rb"[\x20-\x7e]{5,}", data)}
    strong = [s for s in info["symbols"] if s.startswith(("cob_", "CBL_", "C$"))]
    libs = [s for s in info["libraries"] if re.search(r"(?:libcob|cobcrun|cob32|cblrt|cobrts)", s, re.I)]
    hints = sorted(s for s in ascii_strings if re.search(r"GnuCOBOL|OpenCOBOL|Micro Focus|NetCOBOL|\.cob\b|\.cbl\b", s, re.I))[:100]
    gnucobol = any(s.startswith("cob_") for s in strong) or any("libcob" in s.lower() for s in libs)
    commands = []
    if info["architecture"] in {"x86", "x86_64"}:
        commands = [[aret or "aret", str(path.resolve()), "--mode", mode] for mode in ("info", "imports", "decompile")]
    return {"schema_version": 1, "path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(), **info,
            "cobol_evidence": {"runtime_libraries": libs, "runtime_symbols": strong, "string_hints": hints,
                               "assessment": "probable GnuCOBOL" if gnucobol else "COBOL possible" if libs or strong or hints else "non identifié"},
            "rust_conversion": "unsupported: binary lifting/runtime recovery not implemented",
            "aret_commands": commands,
            "next_steps": ["Identifier compilateur, architecture, runtime et dépendances externes.",
                           "Récupérer les symboles, copybooks et structures de fichiers disponibles.",
                           "Lever le code machine et modéliser les appels au runtime COBOL.",
                           "Comparer les sorties, fichiers et effets de bord avec l'exécutable original dans un environnement isolé."]}
