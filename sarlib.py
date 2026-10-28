# -*- coding: utf-8 -*-
"""Utilidades comunes: columnas, referencias A1 y formulas con tokens reubicables."""
import re
from functools import lru_cache

def col2n(c):
    n = 0
    for ch in c: n = n * 26 + ord(ch) - 64
    return n

@lru_cache(maxsize=None)
def n2col(n):
    s = ''
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s

_STR = re.compile(r'("(?:[^"]|"")*")')
# sheet! + $COL$ROW [: $COL$ROW]
_REF = re.compile(r"(?<![A-Za-z0-9_.$'\]])((?:'[^']+'|[A-Za-z_][A-Za-z0-9_.\-]*)!)?(\$?)([A-Z]{1,3})(\$?)(\d+)"
                  r"(?::(\$?)([A-Z]{1,3})(\$?)(\d+))?(?![A-Za-z0-9_(!])")

def _sheetname(p):
    if not p: return ''
    p = p[:-1]
    return p[1:-1] if p.startswith("'") else p

def _fmt_sheet(name):
    if not name: return ''
    return ("'%s'!" % name) if re.search(r"[^A-Za-z0-9_.]", name) else name + '!'

def shift_formula(f, dr, dc):
    """desplaza las referencias relativas (para formulas compartidas)"""
    def one(m):
        sh, ca, c, ra, r = m.group(1) or '', m.group(2), m.group(3), m.group(4), int(m.group(5))
        if not ca: c = n2col(col2n(c) + dc)
        if not ra: r += dr
        out = f"{sh}{ca}{c}{ra}{r}"
        if m.group(7):
            ca2, c2, ra2, r2 = m.group(6), m.group(7), m.group(8), int(m.group(9))
            if not ca2: c2 = n2col(col2n(c2) + dc)
            if not ra2: r2 += dr
            out += f":{ca2}{c2}{ra2}{r2}"
        return out
    parts = _STR.split(f)
    for i in range(0, len(parts), 2): parts[i] = _REF.sub(one, parts[i])
    return ''.join(parts)

T1, T2 = '\x01', '\x02'     # delimitadores de token

def tokenize(f, row):
    """formula A1 -> patron con tokens: \x01sheet|$COL|r:delta (o a:fila)\x02  (rangos: dos tokens unidos por ':')"""
    def tok(sh, ca, c, ra, r):
        rk = f"a:{r}" if ra else f"r:{r - row}"
        return f"{T1}{_sheetname(sh)}|{ca}{c}|{rk}{T2}"
    def one(m):
        sh, ca, c, ra, r = m.group(1) or '', m.group(2), m.group(3), m.group(4), int(m.group(5))
        out = tok(sh, ca, c, ra, r)
        if m.group(7): out += ':' + tok('', m.group(6), m.group(7), m.group(8), int(m.group(9)))
        return out
    parts = _STR.split(f)
    for i in range(0, len(parts), 2): parts[i] = _REF.sub(one, parts[i])
    return ''.join(parts)

LAST_MISS = [None]
_ONE = T1 + r"([^|]*)\|([^|]*)\|([ra]):(-?\d+)" + T2
_TOKR = re.compile(_ONE + "(?::" + _ONE + ")?")

def expand(pat, row, resolve, own_sheet, newrow=None, inline=None, blank=None):
    """Patron -> formula A1.
    resolve(hoja, fila_antigua, rol) -> fila nueva o None.  rol: 'single' | 'start' | 'end'.
    inline(hoja, col, fila_antigua) -> texto con el contenido de esa celda (celda maestra) o None.
    blank(hoja) -> fila (vacía) a la que apuntar cuando el destino no está en la selección, o None.
    Si newrow se indica (fila clonada), las referencias relativas a la propia hoja con |delta|<=1
    son posicionales (respecto a la fila nueva). Devuelve None si alguna referencia no se puede resolver."""
    state = {'ok': True}
    def one(m):
        sh = m.group(1); sheet = sh or own_sheet
        def tgt(kind, val, role):
            if newrow is not None and role == 'single' and kind == 'r' and abs(val) <= 1 and sheet == own_sheet:
                return newrow + val
            return resolve(sheet, (row + val) if kind == 'r' else val, role)
        two = m.group(8) is not None
        k1, v1 = m.group(3), int(m.group(4))
        a = tgt(k1, v1, 'start' if two else 'single')
        if not two:
            if a is None and inline is not None:
                txt = inline(sheet, m.group(2).replace('$', ''), (row + v1) if k1 == 'r' else v1)
                if txt is not None:
                    return txt if re.fullmatch(r'[A-Za-z0-9_.]+', txt) else '(' + txt + ')'
            if a is None and blank is not None:
                a = blank(sheet)
            if a is None:
                state['ok'] = False; LAST_MISS[0] = (sheet, (row + v1) if k1 == 'r' else v1); return ''
            return f"{_fmt_sheet(sh)}{m.group(2)}{'$' if k1 == 'a' else ''}{a}"
        k2, v2 = m.group(7), int(m.group(8))
        b = tgt(k2, v2, 'end')
        if a is None or b is None or b < a:
            bl = blank(sheet) if blank is not None else None
            if bl is None:
                state['ok'] = False; LAST_MISS[0] = (sheet, (row + v1) if k1 == 'r' else v1); return ''
            a = b = bl
        return (f"{_fmt_sheet(sh)}{m.group(2)}{'$' if k1 == 'a' else ''}{a}"
                f":{m.group(6)}{'$' if k2 == 'a' else ''}{b}")
    out = _TOKR.sub(one, pat)
    return out if state['ok'] else None
