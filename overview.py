# -*- coding: utf-8 -*-
"""Edición de la pestaña Overview: nombre del proyecto, baterías y accesorios.
Si hacen falta más filas de las que caben, se insertan filas desplazando el resto (sin borrar nada)."""
import re
from lxml import etree
from sarlib import col2n, n2col, shift_formula
from nucleo import _remap_formula_text

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
Q = lambda t: '{%s}%s' % (M, t)
CELL_PROYECTO = 'E4'          # "Projet/Offer:" (D4) -> valor
FILA_BAT0 = 28                # primera fila de la tabla "Additional battery"
FILA_ACC0 = 28                # primera fila de la tabla "Accessories"
BAT_LIBRES = 5                # baterías que caben (filas 28-32) sin desplazar nada
FILA_CORTE = 33               # desde aquí empieza la tabla de la muestra S/01 (título incluido)
COLS_ACC = ('O', 'P')


def _split(ref):
    m = re.match(r'([A-Z]+)(\d+)$', ref)
    return m.group(1), int(m.group(2))


def _row_el(sd, r):
    for row in sd:
        if int(row.get('r')) == r:
            return row
    # crear en orden
    new = etree.Element(Q('row')); new.set('r', str(r))
    pos = 0
    for k, row in enumerate(sd):
        if int(row.get('r')) < r:
            pos = k + 1
    sd.insert(pos, new)
    return new


def _cell_el(row, col, create=True):
    cn = col2n(col)
    pos = 0
    for k, c in enumerate(row):
        cc = col2n(_split(c.get('r'))[0])
        if cc == cn:
            return c
        if cc < cn:
            pos = k + 1
    if not create:
        return None
    c = etree.Element(Q('c')); c.set('r', f"{col}{row.get('r')}")
    row.insert(pos, c)
    return c


def _set_text(c, text, style=None):
    for ch in list(c):
        c.remove(ch)
    for a in ('t',):
        if a in c.attrib:
            del c.attrib[a]
    if style is not None:
        c.set('s', str(style))
    c.set('t', 'inlineStr')
    is_ = etree.SubElement(c, Q('is'))
    t = etree.SubElement(is_, Q('t')); t.text = text
    if text != text.strip():
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def _style(sd, ref):
    col, r = _split(ref)
    for row in sd:
        if int(row.get('r')) == r:
            c = _cell_el(row, col, create=False)
            if c is not None:
                return c.get('s')
    return None


def _expandir_compartidas(sd):
    masters = {}
    for row in sd:
        for c in row:
            f = c.find(Q('f'))
            if f is not None and f.get('t') == 'shared' and f.text:
                col, r = _split(c.get('r'))
                masters[f.get('si')] = (f.text, r, col2n(col))
    for row in sd:
        for c in row:
            f = c.find(Q('f'))
            if f is not None and f.get('t') == 'shared':
                si = f.get('si'); col, r = _split(c.get('r'))
                if not f.text and si in masters:
                    ft, r0, c0 = masters[si]
                    f.text = shift_formula(ft, r - r0, col2n(col) - c0)
                for a in ('t', 'si', 'ref'):
                    if a in f.attrib:
                        del f.attrib[a]


def _shift_ref(ref, k, desde):
    def one(m):
        r = int(m.group(2))
        return f"{m.group(1)}{r + k if r >= desde else r}"
    return re.sub(r'([A-Z]+)(\d+)', one, ref)


def editar_overview(xml, drawing, vml, datos):
    """Devuelve (xml, drawing, vml, ov_map). xml/drawing/vml son bytes/str de las partes originales."""
    bats, accs = datos['baterias'], datos['accesorios']
    k = max(0, len(bats) - BAT_LIBRES)
    root = etree.fromstring(xml if isinstance(xml, bytes) else xml.encode('utf8'))
    sd = root.find(Q('sheetData'))
    ov_map = (lambda old: old + k if old >= FILA_CORTE else old) if k else (lambda old: old)

    if k:
        _expandir_compartidas(sd)
        # 1) la tabla de accesorios (O:P, filas 27-40) no se mueve: se aparta y se vuelve a poner
        apart = {}
        for row in sd:
            r = int(row.get('r'))
            if 27 <= r <= 40:
                for col in COLS_ACC:
                    c = _cell_el(row, col, create=False)
                    if c is not None:
                        apart[(col, r)] = c
                        row.remove(c)
        # 2) desplazar filas >= FILA_CORTE
        def resolve(sheet, old, role):
            return ov_map(old)
        for row in sd:
            r = int(row.get('r'))
            if r >= FILA_CORTE:
                row.set('r', str(r + k))
                for c in row:
                    col, rr = _split(c.get('r'))
                    c.set('r', f'{col}{rr + k}')
        for row in sd:
            for c in row:
                f = c.find(Q('f'))
                if f is not None and f.text:
                    new = _remap_formula_text(f.text, 'Overview', resolve)
                    f.text = new if new is not None else f.text
        for mc in root.iter(Q('mergeCell')):
            mc.set('ref', _shift_ref(mc.get('ref'), k, FILA_CORTE))
        for cf in root.iter(Q('conditionalFormatting')):
            cf.set('sqref', ' '.join(_shift_ref(x, k, FILA_CORTE) for x in cf.get('sqref').split()))
            for fm in cf.iter(Q('formula')):
                if fm.text:
                    new = _remap_formula_text(fm.text, 'Overview', resolve)
                    fm.text = new if new is not None else fm.text
        dim = root.find(Q('dimension'))
        if dim is not None:
            dim.set('ref', re.sub(r'(\d+)$', lambda m: str(int(m.group(1)) + k), dim.get('ref')))
        # anclajes de controles (0-based)
        XDR = '{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}row'
        for el in root.iter(XDR):
            if el.text and int(el.text) >= FILA_CORTE - 1:
                el.text = str(int(el.text) + k)
        # 3) devolver los accesorios a su sitio
        for (col, r), c in apart.items():
            row = _row_el(sd, r)
            old = _cell_el(row, col, create=False)
            if old is not None:
                row.remove(old)
            cn = col2n(col); pos = 0
            for j, e in enumerate(row):
                if col2n(_split(e.get('r'))[0]) < cn:
                    pos = j + 1
            row.insert(pos, c)
        if drawing:
            d = drawing if isinstance(drawing, str) else drawing.decode('utf8')
            d = re.sub(r'(<xdr:row>)(\d+)(</xdr:row>)',
                       lambda m: f"{m.group(1)}{int(m.group(2)) + k if int(m.group(2)) >= FILA_CORTE - 1 else m.group(2)}{m.group(3)}", d)
            drawing = d
        if vml:
            v = vml if isinstance(vml, str) else vml.decode('utf8', 'ignore')
            def anc(m):
                p = [x.strip() for x in m.group(2).split(',')]
                for idx in (2, 6):
                    if int(p[idx]) >= FILA_CORTE - 1:
                        p[idx] = str(int(p[idx]) + k)
                return f"{m.group(1)}{', '.join(p)}{m.group(3)}"
            vml = re.sub(r'(<x:Anchor>\s*)([^<]+?)(\s*</x:Anchor>)', anc, v)
        # filas nuevas 34..33+k: celdas de baterías con el estilo de la tabla
    # --- escritura de datos ---
    sty_lab = _style(sd, 'J29') or _style(sd, 'J28')
    sty_nom = _style(sd, 'K29') or _style(sd, 'K28')
    sa_lab = _style(sd, 'O29') or _style(sd, 'O28')
    sa_nom = _style(sd, 'P29') or _style(sd, 'P28')
    c = _cell_el(_row_el(sd, int(CELL_PROYECTO[1:])), CELL_PROYECTO[0])
    if datos.get('proyecto'):
        _set_text(c, datos['proyecto'])
    for i, name in enumerate(bats):
        row = _row_el(sd, FILA_BAT0 + i)
        _set_text(_cell_el(row, 'J'), f'Battery {i + 1}', sty_lab)
        _set_text(_cell_el(row, 'K'), name, sty_nom)
    for i, name in enumerate(accs):
        row = _row_el(sd, FILA_ACC0 + i)
        _set_text(_cell_el(row, 'O'), f'Accessory {i + 1}', sa_lab)
        _set_text(_cell_el(row, 'P'), name, sa_nom)
    out = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    return out, drawing, vml, ov_map
