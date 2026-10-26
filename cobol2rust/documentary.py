"""Filter Identification Division comment entries before lexing and COPY.

Fixed-format entries consume Area B prose until the next normal Area A line.
Free-format entries consume only the physical line containing their header.
The filter deliberately leaves semantic paragraphs and unsupported forms alone.
"""
from __future__ import annotations

import re


_HEADER = re.compile(
    r"^\s*(?:AUTHOR|INSTALLATION|DATE-WRITTEN|DATE-COMPILED|SECURITY|REMARKS)\s*\.",
    re.IGNORECASE,
)
_DIVISION = re.compile(
    r"\b(?:(ID|IDENTIFICATION)\s+DIVISION|(PROGRAM-ID)\b|"
    r"(?:ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION|END\s+PROGRAM)\b",
    re.IGNORECASE,
)


def _code_text(area: str) -> str:
    """Preserve code positions, blanking quoted text and an inline comment."""
    result = []
    quote = None
    index = 0
    while index < len(area):
        char = area[index]
        if quote is None and area.startswith("*>", index):
            break
        if quote is not None:
            result.append(" ")
            if char == quote:
                if index + 1 < len(area) and area[index + 1] == quote:
                    result.append(" ")
                    index += 1
                else:
                    quote = None
        elif char in "\"'":
            quote = char
            result.append(" ")
        else:
            result.append(char)
        index += 1
    return "".join(result)


class DocumentaryFilter:
    def __init__(self):
        self._identification = False
        self._fixed_entry = False

    def format_changed(self, fmt: str) -> None:
        # A standalone source directive is processed before comment entries.
        # Switching to FREE ends the fixed entry; FIXED retains its Area B rule.
        if fmt == "free":
            self._fixed_entry = False

    def is_comment(self, area: str, fmt: str, indicator: str = " ", line: int = 0) -> bool:
        if fmt != "fixed":
            self._fixed_entry = False
        if self._fixed_entry:
            if indicator == "-":
                # Import lazily: frontend owns the diagnostic type and calls us.
                from .frontend import CobolError
                raise CobolError(f"ligne {line}: continuation fixe dans une entrée documentaire non prise en charge")
            if not area.strip() or len(area) - len(area.lstrip(" \t")) >= 4:
                return True
            # Reprocess the first Area A line; it may start another entry.
            self._fixed_entry = False

        if self._identification and _HEADER.match(area):
            self._fixed_entry = fmt == "fixed"
            return True

        for match in _DIVISION.finditer(_code_text(area)):
            # PROGRAM-ID opens the IDENTIFICATION DIVISION when its header is
            # omitted, as cobc allows.
            self._identification = bool(match[1] or match[2])
        return False
