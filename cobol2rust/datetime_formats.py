"""ISO 8601 date and time formats of the intrinsic functions, as cobc
checks a literal format (cob_valid_date_format, cob_valid_time_format and
cob_valid_datetime_format of libcob/intrinsic.c)."""
from __future__ import annotations

DATESTR_MAX = 10
TIMESTR_MAX = 25
TIMEDEC_MAX = 9


def valid_date_format(text: str) -> bool:
    return text in {"YYYYMMDD", "YYYY-MM-DD", "YYYYDDD", "YYYY-DDD", "YYYYWwwD", "YYYY-Www-D"}


def decimal_places_for_seconds(text: str, point: int) -> int:
    count = 0
    while point + 1 + count < len(text) and text[point + 1 + count] == "s":
        count += 1
    return count


def valid_time_format(text: str, decimal_point: str) -> bool:
    if text.startswith("hhmmss"):
        colons, offset = False, 6
    elif text.startswith("hh:mm:ss"):
        colons, offset = True, 8
    else:
        return False
    if text[offset:offset + 1] == decimal_point:
        places = decimal_places_for_seconds(text, offset)
        offset += places + 1
        if places == 0 or places > TIMEDEC_MAX:
            return False
    rest = text[offset:]
    return not rest or rest == "Z" or rest == ("+hh:mm" if colons else "+hhmm")


def split_around_t(text: str) -> tuple[str, str, int]:
    """split_around_t: the parts before and after the first T, and the
    position past an overlong part (0 when both fit)."""
    i = text.find("T")
    i = len(text) if i < 0 else i
    error = 0
    first = text[:min(i, DATESTR_MAX)]
    if i > DATESTR_MAX:
        error = DATESTR_MAX + 1
    second = ""
    if i < len(text):
        second = text[i + 1:]
        if len(second) > TIMESTR_MAX:
            second, error = second[:TIMESTR_MAX], TIMESTR_MAX + 1 + i
    return first, second, error


def valid_datetime_format(text: str, decimal_point: str) -> bool:
    date, time, error = split_around_t(text)
    if error or not valid_date_format(date) or not valid_time_format(time, decimal_point):
        return False
    return (date[4:5] == "-") == (not time.startswith("hhmmss"))


def valid_format(kinds: tuple[str, ...], text: str, decimal_point: str) -> bool:
    """valid_format: one of the formats the function allows."""
    text = text.split("\x00")[0]
    checks = {"date": lambda: valid_date_format(text), "time": lambda: valid_time_format(text, decimal_point),
              "datetime": lambda: valid_datetime_format(text, decimal_point)}
    return any(checks[kind]() for kind in kinds)
