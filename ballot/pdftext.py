"""
ballot/pdftext.py - the text of a text PDF, line by line in reading order, with nothing beyond Python's own zlib:
enough to read a state's certified list of candidates.

It reads plain objects and compressed object streams, follows the page tree in order (with inherited resources),
decodes each font through its ToUnicode map when it has one (else as Windows-1252, as simple fonts are), advances
by the fonts' own glyph widths, and puts text back into lines by position. A scanned page is a picture of text and
has none to read; a state that publishes only scans needs another way, and its loader must say so.

    for page, y, text in lines("list.pdf"): ...
"""

import re
import zlib

WS = b" \t\r\n\f\x00"
DELIM = b"()<>[]{}/%"


class Ref:
    __slots__ = ("num",)

    def __init__(self, num):
        self.num = num


class Name(str):
    pass


def _skip(b, i):
    n = len(b)
    while i < n:
        c = b[i:i + 1]
        if c in (b" ", b"\t", b"\r", b"\n", b"\f", b"\x00"):
            i += 1
        elif c == b"%":
            while i < n and b[i:i + 1] not in (b"\r", b"\n"):
                i += 1
        else:
            break
    return i


def _literal(b, i):
    """A (literal string) starting just after its '('."""
    out, depth, n = bytearray(), 1, len(b)
    while i < n:
        c = b[i]
        if c == 0x5C:      # backslash
            i += 1
            e = b[i:i + 1]
            if e in b"01234567" and e:
                j = i
                while j < i + 3 and j < n and b[j:j + 1] in b"01234567":
                    j += 1
                out.append(int(b[i:j], 8) & 0xFF)
                i = j
                continue
            out += {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}.get(e, b"" if e in (b"\r", b"\n") else e)
            i += 1
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return bytes(out), i + 1
        out.append(c)
        i += 1
    return bytes(out), i


def parse(b, i=0):
    """One PDF object at b[i:], returned with the index after it."""
    i = _skip(b, i)
    c = b[i:i + 1]
    if b[i:i + 2] == b"<<":
        d, i = {}, i + 2
        while True:
            i = _skip(b, i)
            if b[i:i + 2] == b">>" or i >= len(b):
                return d, i + 2
            k, i = parse(b, i)
            v, i = parse(b, i)
            d[str(k)] = v
    if c == b"[":
        a, i = [], i + 1
        while True:
            i = _skip(b, i)
            if b[i:i + 1] == b"]" or i >= len(b):
                return a, i + 1
            v, i = parse(b, i)
            a.append(v)
    if c == b"(":
        return _literal(b, i + 1)
    if c == b"<":
        j = b.find(b">", i)
        h = re.sub(rb"[^0-9A-Fa-f]", b"", b[i + 1:j])
        return bytes.fromhex((h + b"0" * (len(h) % 2)).decode()), j + 1
    if c == b"/":
        j = i + 1
        while j < len(b) and b[j:j + 1] not in WS and b[j:j + 1] not in DELIM:
            j += 1
        return Name(re.sub(r"#([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), b[i + 1:j].decode("latin-1"))), j
    m = re.compile(rb"[+-]?(\d+\.?\d*|\.\d+)").match(b, i)
    if m:
        num = m.group(0)
        if b"." not in num:      # maybe the first half of "12 0 R"
            r = re.compile(rb"\s+(\d+)\s+R\b").match(b, m.end())
            if r:
                return Ref(int(num)), r.end()
            return int(num), m.end()
        return float(num), m.end()
    j = i
    while j < len(b) and b[j:j + 1] not in WS and b[j:j + 1] not in DELIM:
        j += 1
    word = b[i:j].decode("latin-1")
    return {"true": True, "false": False, "null": None}.get(word, word), max(j, i + 1)


class PDF:
    def __init__(self, data):
        self.data, self.raw = data, {}
        for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b", data):
            start, end = m.end(), data.find(b"endobj", m.end())
            s = data.find(b"stream", start, end if end != -1 else len(data))
            if s != -1:
                es = data.find(b"endstream", s)
                end = data.find(b"endobj", es if es != -1 else s)
            if end != -1:
                self.raw[int(m.group(1))] = data[start:end]
        self.cache = {}
        for num in list(self.raw):      # objects packed in object streams
            body = self.raw[num]
            if b"/ObjStm" in body[:400]:
                d, s = self._obj(num)
                try:
                    n, first = int(d["N"]), int(d["First"])
                except (KeyError, TypeError, ValueError):
                    continue
                head = s[:first].split()
                for k in range(n):
                    onum, off = int(head[2 * k]), int(head[2 * k + 1])
                    nxt = int(head[2 * k + 3]) if k + 1 < n else len(s) - first
                    self.raw.setdefault(onum, s[first + off:first + nxt])

    def _obj(self, num):
        """(value, decoded stream bytes or None) for an object number."""
        if num in self.cache:
            return self.cache[num]
        body = self.raw.get(num, b"null")
        val, i = parse(body, 0)
        stream = None
        k = body.find(b"stream", i)
        if isinstance(val, dict) and k != -1:
            s = body[k + 6:]
            s = s[2:] if s[:2] == b"\r\n" else (s[1:] if s[:1] in (b"\r", b"\n") else s)
            e = s.rfind(b"endstream")
            s = s[:e] if e != -1 else s
            length = self.get(val.get("Length"))
            if isinstance(length, int) and 0 < length <= len(s):
                s = s[:length]
            filt = self.get(val.get("Filter"))
            filters = filt if isinstance(filt, list) else ([filt] if filt else [])
            for f in filters:
                if f == "FlateDecode":
                    try:
                        s = zlib.decompress(s)
                    except zlib.error:
                        s = zlib.decompressobj().decompress(s)
            stream = s
        self.cache[num] = (val, stream)
        return val, stream

    def get(self, v):
        while isinstance(v, Ref):
            v = self._obj(v.num)[0]
        return v

    def stream(self, v):
        return self._obj(v.num)[1] if isinstance(v, Ref) else None

    def pages(self):
        """(page dictionary, inherited resources) in reading order."""
        cat = None
        for num, body in self.raw.items():
            if re.search(rb"/Type\s*/Catalog", body[:600]):
                cat = self._obj(num)[0]
                break
        out = []

        def walk(node, res):
            node = self.get(node)
            if not isinstance(node, dict):
                return
            res = self.get(node.get("Resources")) or res
            if node.get("Type") == "Pages" or "Kids" in node:
                for kid in self.get(node.get("Kids")) or []:
                    walk(kid, res)
            else:
                out.append((node, res))
        if cat:
            walk(cat.get("Pages"), {})
        return out


class Font:
    def __init__(self, pdf, d):
        d = pdf.get(d) or {}
        self.two = False
        self.map = {}
        self.widths, self.first, self.dw = {}, 0, 1000
        sub = d.get("Subtype")
        self.type0 = sub == "Type0"      # only a composite font reads two-byte codes; a simple font is one byte a glyph
        if sub == "Type0":
            self.two = True
            desc = (pdf.get(d.get("DescendantFonts")) or [{}])[0]
            desc = pdf.get(desc) or {}
            self.dw = pdf.get(desc.get("DW")) or 1000
            w = pdf.get(desc.get("W")) or []
            k = 0
            while k < len(w):
                a = pdf.get(w[k])
                b = pdf.get(w[k + 1]) if k + 1 < len(w) else None
                if isinstance(b, list):
                    for j, x in enumerate(b):
                        self.widths[a + j] = pdf.get(x)
                    k += 2
                else:
                    wid = pdf.get(w[k + 2]) if k + 2 < len(w) else self.dw
                    for code in range(a, (b or a) + 1):
                        self.widths[code] = wid
                    k += 3
        else:
            self.first = pdf.get(d.get("FirstChar")) or 0
            for j, x in enumerate(pdf.get(d.get("Widths")) or []):
                self.widths[self.first + j] = pdf.get(x)
            self.dw = 500
        tu = d.get("ToUnicode")
        cmap = pdf.stream(tu) if isinstance(tu, Ref) else None
        if cmap:
            self._cmap(cmap)

    def _cmap(self, b):
        text = b.decode("latin-1")
        for block in re.findall(r"begincodespacerange(.*?)endcodespacerange", text, re.S):
            for lo in re.findall(r"<([0-9A-Fa-f]+)>\s*<[0-9A-Fa-f]+>", block):
                self.two = self.type0 and len(lo) >= 4
        u = lambda h: bytes.fromhex(h + "0" * (len(h) % 2)).decode("utf-16-be", "replace") if len(h) >= 4 else chr(int(h, 16))
        for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
            for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
                self.map[int(src, 16)] = u(dst) if dst else ""
        for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
            for lo, hi, rest in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)", block):
                lo, hi = int(lo, 16), int(hi, 16)
                if rest.startswith("["):
                    for j, dst in enumerate(re.findall(r"<([0-9A-Fa-f]*)>", rest)):
                        self.map[lo + j] = u(dst)
                else:
                    dst = rest[1:-1]
                    if len(dst) >= 4:
                        base = bytes.fromhex(dst).decode("utf-16-be", "replace")
                        for j in range(hi - lo + 1):
                            self.map[lo + j] = base[:-1] + chr(ord(base[-1]) + j) if base else ""
                    else:
                        for j in range(hi - lo + 1):
                            self.map[lo + j] = chr(int(dst, 16) + j)

    def decode(self, s):
        """(text, [codes]) for a string operand."""
        codes = [int.from_bytes(s[k:k + 2], "big") for k in range(0, len(s) - 1, 2)] if self.two else list(s)
        if self.two:
            return "".join(self.map.get(c, "") for c in codes), codes
        return "".join(self.map.get(c) or bytes([c & 0xFF]).decode("cp1252", "replace") for c in codes), codes

    def width(self, code):
        return (self.widths.get(code) or self.dw) / 1000.0


def _mul(a, b):
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _ops(b):
    """Operands and operators of a content stream."""
    i, n, stack = 0, len(b), []
    while i < n:
        i = _skip(b, i)
        if i >= n:
            break
        c = b[i:i + 1]
        if c in b"([</" or (c in b"0123456789+-." ):
            if b[i:i + 2] == b"<<":
                v, i = parse(b, i)
            else:
                v, i = parse(b, i)
            stack.append(v)
            continue
        j = i
        while j < n and b[j:j + 1] not in WS and b[j:j + 1] not in DELIM:
            j += 1
        op = b[i:j].decode("latin-1") or b[i:i + 1].decode("latin-1")
        i = max(j, i + 1)
        if op == "BI":      # an inline image: skip to its end
            e = b.find(b"EI", i)
            i = e + 2 if e != -1 else n
            stack = []
            continue
        yield op, stack
        stack = []


def page_runs(pdf, page, res):
    """Every text run on a page: (x, y, size, text, x_end)."""
    fonts, runs = {}, []
    fres = pdf.get((pdf.get(res) or {}).get("Font")) or {}
    contents = pdf.get(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [page.get("Contents")]
    data = b"\n".join(pdf.stream(p) or b"" for p in parts if isinstance(p, Ref))
    ctm, saved = [1, 0, 0, 1, 0, 0], []
    tm = tlm = [1, 0, 0, 1, 0, 0]
    font, size, tc, tw, th, tl, rise = None, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0

    def show(s):
        nonlocal tm
        if font is None:
            return
        text, codes = font.decode(s if isinstance(s, (bytes, bytearray)) else b"")
        trm = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))
        adv = 0.0
        for code in codes:
            adv += (font.width(code) * size + tc + (tw if (not font.two and code == 32) else 0)) * th
        x0, y0 = trm[4], trm[5]
        tm = _mul([1, 0, 0, 1, adv, 0], tm)
        x1 = _mul(_mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm)), [1, 0, 0, 1, 0, 0])[4]
        if text.strip():
            runs.append((x0, y0, abs(trm[3]) or size, text, x1))

    for op, a in _ops(data):
        if op == "q":
            saved.append(ctm[:])
        elif op == "Q":
            ctm = saved.pop() if saved else [1, 0, 0, 1, 0, 0]
        elif op == "cm" and len(a) == 6:
            ctm = _mul([float(x) for x in a], ctm)
        elif op == "BT":
            tm = tlm = [1, 0, 0, 1, 0, 0]
        elif op == "Tf" and len(a) == 2:
            name = str(a[0])
            if name not in fonts:
                fonts[name] = Font(pdf, fres.get(name))
            font, size = fonts[name], float(a[1])
        elif op == "Tc" and a:
            tc = float(a[0])
        elif op == "Tw" and a:
            tw = float(a[0])
        elif op == "Tz" and a:
            th = float(a[0]) / 100
        elif op == "TL" and a:
            tl = float(a[0])
        elif op == "Ts" and a:
            rise = float(a[0])
        elif op in ("Td", "TD") and len(a) == 2:
            tx, ty = float(a[0]), float(a[1])
            if op == "TD":
                tl = -ty
            tlm = _mul([1, 0, 0, 1, tx, ty], tlm)
            tm = tlm
        elif op == "Tm" and len(a) == 6:
            tm = tlm = [float(x) for x in a]
        elif op == "T*":
            tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
            tm = tlm
        elif op == "Tj" and a:
            show(a[-1])
        elif op in ("'", '"') and a:
            tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
            tm = tlm
            if op == '"' and len(a) == 3:
                tw, tc = float(a[0]), float(a[1])
            show(a[-1])
        elif op == "TJ" and a and isinstance(a[-1], list):
            for item in a[-1]:
                if isinstance(item, (bytes, bytearray)):
                    show(item)
                elif isinstance(item, (int, float)):
                    tm = _mul([1, 0, 0, 1, -float(item) / 1000.0 * size * th, 0], tm)
    return runs


def join(runs):
    """Runs on one printed row as text: pieces that touch are joined, a gap wider than a fifth of the type is a space."""
    text, end = "", None
    for x0, _y, size, t, x1 in sorted(runs, key=lambda r: r[0]):
        if end is not None and x0 - end > 0.18 * size and not text.endswith(" ") and not t.startswith(" "):
            text += " "
        text += t
        end = max(end or x1, x1)
    return re.sub(r"\s+", " ", text).strip()


def rows(pdf, page, res):
    """A page's runs grouped into printed rows, top to bottom: [(y, [runs])]."""
    out = []
    for r in sorted(page_runs(pdf, page, res), key=lambda r: (-round(r[1], 1), r[0])):
        if out and abs(out[-1][0] - r[1]) <= max(1.5, 0.35 * r[2]):
            out[-1][1].append(r)
        else:
            out.append([r[1], [r]])
    return out


def lines(path, first=1, last=None):
    """(page number, y, text) for each line of text, top to bottom, left to right."""
    pdf = PDF(open(path, "rb").read())
    out = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        if n < first or (last and n > last):
            continue
        for y, rs in rows(pdf, page, res):
            text = join(rs)
            if text:
                out.append((n, round(y, 1), text))
    return out
