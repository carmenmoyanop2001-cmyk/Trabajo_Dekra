# -*- coding: utf-8 -*-
"""Extrae una pestaña grande del datasheet a un formato compacto (plantillas de fila + constantes)."""
import os, sys, re, zipfile, pickle, lzma, time
from array import array
from lxml import etree
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sarlib import *
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
Z = os.environ['DATASHEET_XLSM']      # ruta del datasheet original (.xlsm)
KEYCOLS = ['B','F','J','K','M','N','Q','R','S','T','U','X','Y','BT','BU','BW','BX','BY','BZ','CA','CB','CC','CD']

def sst():
    z = zipfile.ZipFile(Z); out = []
    for ev, el in etree.iterparse(z.open('xl/sharedStrings.xml'), tag=NS + 'si'):
        out.append(''.join(t.text or '' for t in el.iter(NS + 't'))); el.clear()
    return out

def head_tail(part):
    z = zipfile.ZipFile(Z); head = b''
    with z.open(part) as f:
        buf = b''
        while True:
            ch = f.read(1 << 20)
            if not ch: break
            buf += ch; i = buf.find(b'<sheetData')
            if i >= 0: head = buf[:i]; break
    win = b''
    with z.open(part) as f:
        while True:
            ch = f.read(1 << 22)
            if not ch: break
            win = (win + ch)[-(8 << 20):]
    j = win.rfind(b'</sheetData>')
    return head.decode('utf8'), win[j:].decode('utf8')

def extract(part, name, out):
    S = sst(); t0 = time.time()
    head, tail = head_tail(part)
    pats, patid = [], {}          # patrones de formula
    cpool, cid = [], {}           # constantes (kind, texto)
    tmpls, tid_of = [], {}        # plantillas de fila
    attrs, attr_of = [], {}
    rows = []                     # (fila, tid, consts[], attr, kv)
    shared = {}
    nform = 0; nshared_bad = 0; arrays = 0

    def pool(k, txt):
        key = (k, txt); i = cid.get(key)
        if i is None: i = cid[key] = len(cpool); cpool.append(key)
        return i

    z = zipfile.ZipFile(Z)
    with z.open(part) as f:
        for ev, el in etree.iterparse(f, tag=NS + 'row'):
            r = int(el.get('r'))
            cells = []; consts = []; kv = {}
            for c in el.iter(NS + 'c'):
                ref = c.get('r'); m = re.match(r'([A-Z]+)(\d+)', ref); col = m.group(1)
                s_ = int(c.get('s') or 0); t = c.get('t')
                v = c.find(NS + 'v'); fm = c.find(NS + 'f')
                val = None
                if v is not None: val = S[int(v.text)] if t == 's' else v.text
                elif t == 'inlineStr': val = ''.join(x.text or '' for x in c.iter(NS + 't'))
                if col in KEYCOLS and val is not None: kv[col] = val
                form = None
                if fm is not None:
                    if fm.get('t') == 'array': arrays += 1
                    if fm.get('t') == 'shared':
                        si = fm.get('si')
                        if fm.text: shared[si] = (fm.text, int(m.group(2)), col2n(col)); form = fm.text
                        elif si in shared:
                            ft, r0, c0 = shared[si]
                            form = shift_formula(ft, r - r0, col2n(col) - c0)
                        else: nshared_bad += 1
                    else: form = fm.text
                ci = col2n(col)
                if form:
                    nform += 1
                    p = tokenize(form, r); pid = patid.get(p)
                    if pid is None: pid = patid[p] = len(pats); pats.append(p)
                    cells.append((ci, s_, 3, pid))
                elif val is None:
                    cells.append((ci, s_, 0, 0))
                else:
                    if t in ('s', 'inlineStr', 'str'): k = 2
                    elif t == 'b': k = 9
                    elif t == 'e': k = 10
                    else: k = 1
                    cells.append((ci, s_, k, None)); consts.append(pool(k, val))
            tm = tuple(cells); tid = tid_of.get(tm)
            if tid is None: tid = tid_of[tm] = len(tmpls); tmpls.append(tm)
            at = tuple(sorted((k, v) for k, v in el.attrib.items() if k != 'r')); aid = attr_of.get(at)
            if aid is None: aid = attr_of[at] = len(attrs); attrs.append(at)
            kvt = tuple(sorted((k, pool(2, v)) for k, v in kv.items()))
            rows.append((r, tid, array('I', consts), aid, kvt))
            el.clear()
            while el.getprevious() is not None: del el.getparent()[0]
    data = dict(name=name, head=head, tail=tail, patterns=pats, cpool=cpool, templates=tmpls, attrs=attrs, rows=rows,
                nform=nform, arrays=arrays)
    with lzma.open(out, 'wb', preset=6) as fo: pickle.dump(data, fo, protocol=4)
    print(f"{name}: filas={len(rows)} plantillas={len(tmpls)} patrones={len(pats)} constantes={len(cpool)} formulas={nform} "
          f"arrays={arrays} compartidas_sin_master={nshared_bad} -> {out} {__import__('os').path.getsize(out)//1024} KB  {time.time()-t0:.0f}s", flush=True)

if __name__ == '__main__':
    extract(sys.argv[1], sys.argv[2], sys.argv[3])
