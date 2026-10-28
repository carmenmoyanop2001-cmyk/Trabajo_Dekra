# -*- coding: utf-8 -*-
"""Núcleo del generador: carga de plantillas, reubicación de referencias y escritura de hojas XML."""
import os, re, lzma, pickle, bisect
from xml.sax.saxutils import escape
import sarlib
from sarlib import T1, T2, col2n, n2col, expand, _REF, _STR, _sheetname, _fmt_sheet

NS_PREFIX = {'http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac': 'x14ac'}
HEADER_ROWS = 2


class Hoja:
    """Datos compactos de una pestaña grande de la plantilla."""

    def __init__(self, path):
        with lzma.open(path, 'rb') as f:
            self.sd = pickle.load(f)
        sd = self.sd
        self.name = sd['name']
        self.rows = sd['rows']
        self.cpool = sd['cpool']
        self.templates = sd['templates']
        self.patterns = sd['patterns']
        self.attrs = sd['attrs']
        self.by_old = {r[0]: i for i, r in enumerate(self.rows)}
        self._kv = {}

    def kv(self, i):
        d = self._kv.get(i)
        if d is None:
            d = self._kv[i] = {k: self.cpool[j][1] for k, j in self.rows[i][4]}
        return d

    def kv_old(self, old):
        return self.kv(self.by_old[old])


class Item:
    """Una fila de salida: fila original (i) con posibles sustituciones de celdas (ovr)."""
    __slots__ = ('i', 'ovr', 'clone', 'extra')

    def __init__(self, i, ovr=None, clone=False, extra=None):
        self.i, self.ovr, self.clone, self.extra = i, ovr, clone, extra


class Contexto:
    """Estado compartido durante una generación."""

    def __init__(self):
        self.rowmap = {}      # hoja -> {fila antigua: fila nueva}
        self.sorted = {}      # hoja -> [filas antiguas seleccionadas ordenadas]
        self.whole = set()    # hojas copiadas enteras y presentes (Overview, Tune-Up, Test Campaign)
        self.ov_map = lambda old: old
        self.inline = None    # sustitución de referencias a celdas maestras ausentes
        self.blank = None     # fila vacía de cada hoja (destino de referencias fuera de la selección)
        self.unresolved = {}  # hoja -> nº de fórmulas que se han dejado vacías
        self.unres_cols = {}  # (hoja, columna) -> nº
        self.examples = {}
        self.defaults = {}    # hoja -> nº de fórmulas sustituidas por el valor por defecto de la plantilla
        self.no_cache = False
        self.broken = {}  # fórmulas #REF! heredadas, sin inventar sustituciones
        self.column_aliases = {}
        self.display_merges = {}
        self.style_overrides = {}

    def set_rows(self, name, mapping):
        self.rowmap[name] = mapping
        self.sorted[name] = sorted(mapping)

    def resolver(self):
        def resolve(sheet, old, role):
            if sheet == 'Overview':
                return self.ov_map(old) if 'Overview' in self.whole else None
            if sheet in self.whole:
                return old
            m = self.rowmap.get(sheet)
            if m is None:
                return None
            if old <= HEADER_ROWS:
                return old
            v = m.get(old)
            if v is not None or role == 'single':
                return v
            s = self.sorted[sheet]
            if role == 'start':
                k = bisect.bisect_left(s, old)
                return m[s[k]] if k < len(s) else None
            k = bisect.bisect_right(s, old) - 1
            return m[s[k]] if k >= 0 else None
        return resolve


def _attr_str(attrs):
    out = []
    for k, v in attrs:
        if k == 'spans':
            continue
        if k.startswith('{'):
            uri, local = k[1:].split('}')
            k = NS_PREFIX.get(uri, '') + ':' + local if NS_PREFIX.get(uri) else local
        out.append(f' {k}="{escape(v, {chr(34): "&quot;"})}"')
    return ''.join(out)


def _inline(txt):
    sp = ' xml:space="preserve"' if (txt != txt.strip() or '\n' in txt) else ''
    return f'<is><t{sp}>{escape(txt)}</t></is>'


def _cell_xml(col, newrow, s, kind, val, cached=None):
    ref = f'{col}{newrow}'
    st = f' s="{s}"' if s else ''
    if kind == 0 or val is None:
        return f'<c r="{ref}"{st}/>'
    if kind == 1:
        return f'<c r="{ref}"{st}><v>{val}</v></c>'
    if kind == 2:
        return f'<c r="{ref}"{st} t="inlineStr">{_inline(val)}</c>'
    if kind == 9:
        return f'<c r="{ref}"{st} t="b"><v>{val}</v></c>'
    if kind == 10:
        return f'<c r="{ref}"{st} t="e"><v>{escape(val)}</v></c>'
    if kind == 3:
        # Conservar también el resultado del original. Excel y los visores
        # pueden mostrar vacío un <f> sin <v> hasta recalcular el libro.
        if cached is not None:
            try:
                float(cached)
                cache_type = ''
            except (ValueError, TypeError):
                cache_type = ' t="str"'
            return f'<c r="{ref}"{st}{cache_type}><f>{escape(val)}</f><v>{escape(str(cached))}</v></c>'
        return f'<c r="{ref}"{st}><f>{escape(val)}</f><v/></c>'
    raise ValueError(kind)



_IND = re.compile(r'INDIRECT\("\'([^\']+)\'!\$([A-Z]{1,3})\$"\s*&\s*' + T1 + r'\|([A-Z]+)\|r:(-?\d+)' + T2 + r'(?:\s*&\s*"(\d*)")?\)')


def _const_de(h, idx, ci):
    r = h.rows[idx]; k = 0
    for c, s, kind, payload in h.templates[r[1]]:
        v = None
        if kind in (1, 2, 9, 10):
            v = h.cpool[r[2][k]][1]; k += 1
        if c == ci:
            return v if kind in (1, 2) else None
    return None


def desindirect(pat, r_old, h):
    """INDIRECT("'Hoja'!$COL$" & celda_con_fila [& "3"]) -> referencia directa reubicable (token)."""
    def one(m):
        hoja, col, dcol, delta, suf = m.groups()
        idx = h.by_old.get(r_old + int(delta))
        v = _const_de(h, idx, col2n(dcol)) if idx is not None else None
        if v is None:
            return m.group(0)
        try:
            target = int(str(int(float(v))) + (suf or ''))
        except ValueError:
            return m.group(0)
        return f'{T1}{hoja}|${col}|a:{target}{T2}'
    return _IND.sub(one, pat)


_CATM_O = re.compile('IF\\(' + re.escape(T1) + r'\|\$?J\|r:0' + re.escape(T2) +
                     r'="Cat M1",(\d+),(\d+)\)')


def valor_formula_original(h, index, col, pattern):
    cached = h.kv(index).get(col)
    if h.name == 'Conducted LTE CATM1' and col == 'O':
        match = _CATM_O.fullmatch(pattern)
        if match:
            # Las expresiones del original dependen solo de J en la misma
            # fila. Guardar su resultado no reemplaza ni cambia la fórmula.
            cached = match.group(1 if h.kv(index).get('J') == 'Cat M1' else 2)
    return cached


def emit_row(h, ctx, resolve, item, newrow):
    """XML de una fila de salida."""
    r_old, tid, consts, aid, kv = h.rows[item.i]
    tm = h.templates[tid]
    ovr = item.ovr or {}
    cells = []
    k = 0
    for ci, s, kind, payload in tm:
        s = ctx.style_overrides.get((h.name, newrow, ci), s)
        col = n2col(ci)
        val = None
        cached = None
        if kind in (1, 2, 9, 10):
            val = h.cpool[consts[k]][1]
            k += 1
        elif kind == 3 and ci not in ovr:
            pat = sarlib.remap_columns(h.patterns[payload], h.name, ctx.column_aliases)
            if not item.clone:
                cached = valor_formula_original(h, item.i, col, pat)
            if 'INDIRECT(' in pat:
                pat = desindirect(pat, r_old, h)
            val = expand(pat, r_old, resolve, h.name, newrow if item.clone else None, ctx.inline, None)
            if val is None:
                cached = h.kv(item.i).get(col)         # valor por defecto que traía la plantilla (banda, canal, frecuencia, modo...)
                if cached is not None and not ctx.no_cache:
                    try:
                        float(cached); kind, val = 1, cached
                    except ValueError:
                        kind, val = 2, cached
                    ctx.defaults[h.name] = ctx.defaults.get(h.name, 0) + 1
                else:
                    val = expand(pat, r_old, resolve, h.name, newrow if item.clone else None, ctx.inline, ctx.blank)
            if val is None:
                ctx.unresolved[h.name] = ctx.unresolved.get(h.name, 0) + 1
                ctx.unres_cols[(h.name, col)] = ctx.unres_cols.get((h.name, col), 0) + 1
                ctx.examples.setdefault((h.name, col), (r_old, sarlib.LAST_MISS[0], h.patterns[payload][:150].replace('\x01', '<').replace('\x02', '>')))
                kind = 0
        if ci in ovr:
            o = ovr[ci]
            if o is None:
                kind, val = 0, None
            elif isinstance(o, tuple):          # ('f', formula ya resuelta)
                kind, val = 3, o[1]
                cached = o[2] if len(o) > 2 else None
            elif isinstance(o, (int, float)):
                kind, val = 1, repr(o) if isinstance(o, float) else str(o)
            else:
                kind, val = 2, str(o)
        if kind == 3 and val and any('#REF!' in part for part in sarlib._STR.split(val)[::2]):
            ctx.broken[h.name] = ctx.broken.get(h.name, 0) + 1
        cells.append(_cell_xml(col, newrow, s, kind, val, cached))
    return f'<row r="{newrow}"{_attr_str(h.attrs[aid])}>' + ''.join(cells) + '</row>'


# ----------------------------------------------------------------------------------------
#  Cabecera y cola de la hoja
# ----------------------------------------------------------------------------------------
def _remap_range_rows(rng, rowmap_sorted, rowmap, clones=()):
    """'AI4:AI434' -> lista de rangos (tramos contiguos en filas nuevas)."""
    m = re.match(r'^([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$', rng)
    if not m:
        return [rng]
    c1, r1 = m.group(1), int(m.group(2))
    c2, r2 = (m.group(3) or c1), int(m.group(4) or r1)
    if r2 <= HEADER_ROWS:
        return [rng]
    lo = bisect.bisect_left(rowmap_sorted, max(r1, HEADER_ROWS + 1))
    hi = bisect.bisect_right(rowmap_sorted, r2)
    news = sorted({rowmap[o] for o in rowmap_sorted[lo:hi]} |
                  {new for old, new in clones if r1 <= old <= r2})
    runs = []
    for n in news:
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    out = []
    if r1 <= HEADER_ROWS:
        out.append(f'{c1}{r1}:{c2}{HEADER_ROWS}' if c1 != c2 or r1 != HEADER_ROWS else f'{c1}{r1}')
    for a, b in runs:
        out.append(f'{c1}{a}' if (a == b and c1 == c2) else f'{c1}{a}:{c2}{b}')
    return out


def _remap_formula_text(txt, own, resolve):
    """Reubica referencias (absolutas) dentro de fórmulas de CF/DV. None si no se puede."""
    parts = _STR.split(txt)
    ok = [True]

    def one(m):
        sh = m.group(1) or ''
        sheet = _sheetname(sh) or own
        c1, ca1, ra1, r1 = m.group(3), m.group(2), m.group(4), int(m.group(5))
        two = m.group(7) is not None
        a = resolve(sheet, r1, 'start' if two else 'single')
        if a is None:
            ok[0] = False
            return m.group(0)
        out = f"{sh}{ca1}{c1}{ra1}{a}"
        if two:
            b = resolve(sheet, int(m.group(9)), 'end')
            if b is None or b < a:
                ok[0] = False
                return m.group(0)
            out += f":{m.group(6)}{m.group(7)}{m.group(8)}{b}"
        return out
    for i in range(0, len(parts), 2):
        parts[i] = _REF.sub(one, parts[i])
    return ''.join(parts) if ok[0] else None


def procesar_cola(tail, h, ctx, resolve, last_row, clones=()):
    """Ajusta autoFilter, formatos condicionales y validaciones a las nuevas filas."""
    rm, rs = ctx.rowmap[h.name], ctx.sorted[h.name]

    def fix_ref(m):
        a = re.sub(r'(\d+)$', str(last_row), m.group(2)) if True else m.group(2)
        return f'{m.group(1)}{a}"'
    tail = re.sub(r'(<autoFilter ref=")([^"]+)"', fix_ref, tail, count=1)
    tail = re.sub(r'<ignoredErrors>.*?</ignoredErrors>', '', tail, flags=re.S)
    tail = re.sub(r'<extLst>.*</extLst>', '', tail, flags=re.S)
    merges = ctx.display_merges.get(h.name, [])
    if merges:
        block = f'<mergeCells count="{len(merges)}">' + ''.join(
            f'<mergeCell ref="{ref}"/>' for ref in merges) + '</mergeCells>'
        after_merges = (r'<(?:phoneticPr|conditionalFormatting|dataValidations|hyperlinks|printOptions|'
                        r'pageMargins|pageSetup|headerFooter|rowBreaks|colBreaks|customProperties|'
                        r'cellWatches|ignoredErrors|smartTags|drawing|legacyDrawing|legacyDrawingHF|'
                        r'picture|oleObjects|controls|webPublishItems|tableParts|extLst)\b')
        at = re.search(after_merges, tail)
        index = at.start() if at else tail.rfind('</worksheet>')
        tail = tail[:index] + block + tail[index:]

    def cf_block(m):
        block = m.group(0)
        sq = re.search(r'sqref="([^"]+)"', block).group(1)
        rngs = []
        for r in sq.split():
            rngs += _remap_range_rows(r, rs, rm, clones)
        if not rngs:
            return ''
        def f(mm):
            new = _remap_formula_text(mm.group(2), h.name, resolve) if '$' in mm.group(2) else mm.group(2)
            return f'{mm.group(1)}{new}{mm.group(3)}' if new is not None else mm.group(0)
        block = re.sub(r'(<formula>)(.*?)(</formula>)', f, block, flags=re.S)
        return re.sub(r'sqref="[^"]+"', f'sqref="{" ".join(rngs)}"', block, count=1)
    tail = re.sub(r'<conditionalFormatting .*?</conditionalFormatting>', cf_block, tail, flags=re.S)

    cnt = [0]

    def dv_block(m):
        block = m.group(0)
        sq = re.search(r'sqref="([^"]+)"', block).group(1)
        rngs = []
        for r in sq.split():
            rngs += _remap_range_rows(r, rs, rm, clones)
        if not rngs:
            return ''
        def f(mm):
            txt = mm.group(2)
            if txt.startswith('"'):
                return mm.group(0)
            new = _remap_formula_text(txt, h.name, resolve)
            return f'{mm.group(1)}{new}{mm.group(3)}' if new is not None else mm.group(0)
        block = re.sub(r'(<formula[12]>)(.*?)(</formula[12]>)', f, block, flags=re.S)
        cnt[0] += 1
        return re.sub(r'sqref="[^"]+"', f'sqref="{" ".join(rngs)}"', block, count=1)
    tail = re.sub(r'<dataValidation .*?(?:</dataValidation>|/>)', dv_block, tail, flags=re.S)
    tail = re.sub(r'<dataValidations count="\d+"', f'<dataValidations count="{cnt[0]}"', tail)
    if cnt[0] == 0:
        tail = re.sub(r'<dataValidations count="0">\s*</dataValidations>', '', tail)
    return tail


def procesar_cabecera(head, last_row):
    head = re.sub(r'<dimension ref="A1:([A-Z]+)\d+"/>', lambda m: f'<dimension ref="A1:{m.group(1)}{last_row}"/>', head)
    head = re.sub(r'topLeftCell="[A-Z]+\d+"', 'topLeftCell="A3"', head, count=1)
    head = re.sub(r'<selection pane="bottomLeft"[^>]*/>', '<selection pane="bottomLeft" activeCell="A3" sqref="A3"/>', head)
    return head


def iter_hoja(h, plan, ctx, resolve):
    """Genera (por trozos) el XML completo de la hoja a partir del plan (lista de Item)."""
    last = HEADER_ROWS + len(plan)
    yield procesar_cabecera(h.sd['head'], last)
    yield '<sheetData>'
    for i, r in enumerate(h.rows):
        if r[0] > HEADER_ROWS:
            break
        yield emit_row(h, ctx, resolve, Item(i), r[0])
    n = HEADER_ROWS
    buf = []
    for it in plan:
        n += 1
        buf.append(emit_row(h, ctx, resolve, it, n))
        if len(buf) >= 500:
            yield ''.join(buf); buf = []
    if buf:
        yield ''.join(buf)
    clones = [(h.rows[it.i][0], HEADER_ROWS + 1 + i) for i, it in enumerate(plan) if it.clone]
    yield procesar_cola(h.sd['tail'], h, ctx, resolve, last, clones)
