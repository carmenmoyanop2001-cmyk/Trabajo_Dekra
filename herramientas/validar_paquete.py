# -*- coding: utf-8 -*-
"""Comprobaciones estructurales de un .xlsm generado (sin necesidad de Excel)."""
import re, sys, zipfile, posixpath
from lxml import etree

def validar(path, verbose=True):
    z = zipfile.ZipFile(path); names = set(z.namelist()); err = []
    # 1) XML bien formado
    for n in names:
        if n.endswith(('.xml', '.rels', '.vml')) and n != 'xl/vbaProject.bin':
            try:
                if n.startswith('xl/worksheets/sheet') and z.getinfo(n).file_size > 30_000_000:
                    continue
                etree.fromstring(z.read(n))
            except Exception as e:
                err.append(f'XML mal formado: {n}: {str(e)[:80]}')
    # 2) tipos de contenido
    ct = z.read('[Content_Types].xml').decode('utf8')
    defaults = set(re.findall(r'<Default Extension="([^"]+)"', ct)); overrides = set(re.findall(r'<Override PartName="([^"]+)"', ct))
    for o in overrides:
        if o.lstrip('/') not in names: err.append(f'Override sin parte: {o}')
    for n in names:
        if n == '[Content_Types].xml': continue
        ext = n.rsplit('.', 1)[-1]
        if '/' + n not in overrides and ext not in defaults: err.append(f'Parte sin tipo de contenido: {n}')
    # 3) relaciones
    for n in names:
        if n.endswith('.rels'):
            base = posixpath.dirname(posixpath.dirname(n))
            for m in re.finditer(r'<Relationship [^>]*/>', z.read(n).decode('utf8')):
                t = m.group(0)
                if 'TargetMode="External"' in t: continue
                tg = re.search(r'Target="([^"]*)"', t).group(1)
                full = posixpath.normpath(posixpath.join(base, tg)) if not tg.startswith('/') else tg.lstrip('/')
                if full not in names: err.append(f'Relación rota en {n}: {tg}')
    # 4) libro: hojas y nombres definidos
    wb = z.read('xl/workbook.xml').decode('utf8')
    sheets = re.findall(r'<sheet name="([^"]+)" sheetId="(\d+)"[^>]*r:id="(rId\d+)"', wb)
    ids = [s[1] for s in sheets]
    if len(set(ids)) != len(ids): err.append('sheetId duplicado')
    for dn in re.findall(r"<definedName[^>]*>([^<]*)</definedName>", wb):
        sh = re.match(r"'([^']+)'!", dn)
        if sh and sh.group(1).replace('&amp;', '&') not in [s[0].replace('&amp;', '&') for s in sheets]: err.append(f'definedName a hoja inexistente: {dn}')
    # 5) orden de filas/celdas y refs en hojas
    for n in sorted(names):
        if not re.match(r'xl/worksheets/sheet\d+\.xml$', n): continue
        last_r = 0; bad = 0; nrow = 0; dup = 0
        with z.open(n) as f:
            for ev, el in etree.iterparse(f, tag='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                r = int(el.get('r')); nrow += 1
                if r <= last_r: bad += 1
                last_r = r; lc = 0
                for c in el:
                    m = re.match(r'([A-Z]+)(\d+)$', c.get('r'))
                    cn = 0
                    for ch in m.group(1): cn = cn * 26 + ord(ch) - 64
                    if int(m.group(2)) != r or cn <= lc: bad += 1
                    lc = cn
                el.clear()
                while el.getprevious() is not None: del el.getparent()[0]
        if bad: err.append(f'{n}: {bad} filas/celdas fuera de orden o con referencia incoherente')
        if verbose: print(f'  {n}: {nrow} filas')
    return err

if __name__ == '__main__':
    e = validar(sys.argv[1]); print('ERRORES:' if e else 'Paquete OK'); [print(' -', x) for x in e]
