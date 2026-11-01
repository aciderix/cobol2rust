"""cob_is_valid_uri with libxml2: xmlParseURI (uri.c xmlParse3986URIReference,
libxml2 2.9), an absolute URI else a relative reference. The runtime has the
same port (runtime.rs ml::is_valid_uri)."""


def is_valid(data: bytes) -> bool:
    s = data.split(b"\0")[0]

    def at(i):
        return s[i] if i < len(s) else 0

    def alpha(c):
        return 0x41 <= c <= 0x5a or 0x61 <= c <= 0x7a

    def digit(c):
        return 0x30 <= c <= 0x39

    def hexdig(c):
        return digit(c) or 0x41 <= c <= 0x46 or 0x61 <= c <= 0x66

    def sub_delim(c):
        return c != 0 and c in b"!$&()*+,;='"

    def unreserved(c):
        return alpha(c) or digit(c) or (c != 0 and c in b"-._~")

    def pct(i):
        return at(i) == 0x25 and hexdig(at(i + 1)) and hexdig(at(i + 2))

    def pchar(i):
        c = at(i)
        return unreserved(c) or pct(i) or sub_delim(c) or c in (0x3a, 0x40)

    def next_(i):
        # NEXT: a '%' always skips three bytes.
        return i + 3 if at(i) == 0x25 else i + 1

    def query(i, extra):
        while pchar(i) or (at(i) != 0 and at(i) in extra):
            i = next_(i)
        return i

    def userinfo(i):
        while unreserved(at(i)) or pct(i) or sub_delim(at(i)) or at(i) == 0x3a:
            i = next_(i)
        return i if at(i) == 0x40 else None

    def host(i):
        # The IPv4 attempt of xmlParse3986Host never succeeds: a reg-name.
        if at(i) == 0x5b:
            i += 1
            while at(i) not in (0x5d, 0):
                i += 1
            return i + 1 if at(i) == 0x5d else None
        while unreserved(at(i)) or pct(i) or sub_delim(at(i)):
            i = next_(i)
        return i

    def port(i):
        if not digit(at(i)):
            return None
        value = 0
        while digit(at(i)):
            value = value * 10 + at(i) - 0x30
            if value > 2**31 - 1:
                return None
            i += 1
        return i

    def authority(i):
        start = i
        cur = userinfo(i)
        i = cur + 1 if cur is not None and at(cur) == 0x40 else start
        i = host(i)
        if i is None:
            return None
        if at(i) == 0x3a:
            i = port(i + 1)
        return i

    def segment(i, forbid, empty):
        if not pchar(i):
            return i if empty else None
        while pchar(i) and at(i) != forbid:
            i = next_(i)
        return i

    def ab_empty(i):
        while i is not None and at(i) == 0x2f:
            i = segment(i + 1, 0, True)
        return i

    def absolute_path(i):
        if at(i) != 0x2f:
            return None
        cur = segment(i + 1, 0, False)
        return i + 1 if cur is None else ab_empty(cur)

    def rootless(i, forbid):
        cur = segment(i, forbid, False)
        return None if cur is None else ab_empty(cur)

    def end(i):
        if i is None:
            return False
        if at(i) == 0x3f:
            i = query(i + 1, b"/?")
        if at(i) == 0x23:
            i = query(i + 1, b"/?[]")
        return at(i) == 0

    def hier(i):
        if at(i) == 0x2f and at(i + 1) == 0x2f:
            cur = authority(i + 2)
            return None if cur is None else ab_empty(cur)
        if at(i) == 0x2f:
            return absolute_path(i)
        if pchar(i):
            return rootless(i, 0)
        return i

    def absolute():
        if not alpha(at(0)):
            return False
        i = 1
        while alpha(at(i)) or digit(at(i)) or at(i) in (0x2b, 0x2d, 0x2e):
            i += 1
        if at(i) != 0x3a:
            return False
        return end(hier(i + 1))

    def relative():
        if at(0) == 0x2f and at(1) == 0x2f:
            cur = authority(2)
            return end(None if cur is None else ab_empty(cur))
        if at(0) == 0x2f:
            return end(absolute_path(0))
        if pchar(0):
            return end(rootless(0, 0x3a))
        return end(0)

    return absolute() or relative()
