# -*- coding: utf-8 -*-
"""Comprobaciones estructurales de un .xlsm generado (sin necesidad de Excel)."""
import re, sys, zipfile, posixpath
from collections import Counter
from lxml import etree


def _comentarios(z, names, dibujos_por_hoja):
    """La validez XML no detecta comentarios sin enlace a sus formas VML."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    x = 'urn:schemas-microsoft-com:office:excel'
    errors = []
    for part in sorted(names):
        if not re.fullmatch(r'xl/worksheets/_rels/sheet\d+\.xml\.rels', part):
            continue
        try:
            relaciones = list(etree.fromstring(z.read(part)))
        except etree.XMLSyntaxError:
            continue  # Ya informado como XML mal formado.
        comentarios = [r for r in relaciones if r.get('Type', '').endswith('/comments')]
        if not comentarios:
            continue
        hoja = posixpath.dirname(posixpath.dirname(part)) + '/' + posixpath.basename(part)[:-5]
        def destino(rel):
            target = rel.get('Target', '')
            return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(hoja) + '/' + target)
        refs = []
        for rel in comentarios:
            target = destino(rel)
            if target not in names:
                continue  # Ya informado como relación rota.
            try:
                root = etree.fromstring(z.read(target))
            except etree.XMLSyntaxError:
                continue
            refs.extend(c.get('ref') for c in root.findall('{' + ns + '}commentList/{' + ns + '}comment'))
        if not refs:
            continue
        ids = dibujos_por_hoja.get(hoja, [])
        dibujos = [r for r in relaciones if r.get('Type', '').endswith('/vmlDrawing') and r.get('Id') in ids]
        if len(dibujos) != 1:
            errors.append(f'{hoja}: comentarios sin enlace legacyDrawing a su dibujo VML.')
            continue
        target = destino(dibujos[0])
        if target not in names:
            continue
        try:
            root = etree.fromstring(z.read(target))
            posiciones = []
            for data in root.findall('.//{' + x + '}ClientData'):
                if data.get('ObjectType') != 'Note':
                    continue
                row, col = int(data.findtext('{' + x + '}Row')), int(data.findtext('{' + x + '}Column'))
                if row < 0 or col < 0:
                    raise ValueError('Coordenada negativa')
                letters, col = '', col + 1
                while col:
                    col, resto = divmod(col - 1, 26)
                    letters = chr(65 + resto) + letters
                posiciones.append(letters + str(row + 1))
            if Counter(refs) != Counter(posiciones) or len(refs) != len(set(refs)):
                errors.append(f'{hoja}: las celdas de los comentarios y sus formas VML no coinciden.')
        except (etree.XMLSyntaxError, ValueError, TypeError):
            errors.append(f'{target}: dibujo VML de comentarios no válido.')
    return errors


def _dibujos(z, names):
    """Excel repara anclajes invertidos aunque el XML cumpla su esquema."""
    d = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
    errors = []
    for part in sorted(names):
        if not part.endswith('.xml') or '/drawings/' not in part:
            continue
        try:
            root = etree.fromstring(z.read(part))
            for anchor in root.findall('{' + d + '}twoCellAnchor'):
                def coordenadas(tag, eje):
                    marker = anchor.find('{' + d + '}' + tag)
                    return (int(marker.findtext('{' + d + '}' + eje)),
                            int(marker.findtext('{' + d + '}' + eje + 'Off')))
                for eje in ('row', 'col'):
                    start, end = coordenadas('from', eje), coordenadas('to', eje)
                    if min(start + end) < 0 or end <= start:
                        errors.append(f'{part}: anclaje de dibujo invertido o sin tamaño ({eje}).')
        except (etree.XMLSyntaxError, ValueError, TypeError, AttributeError):
            errors.append(f'{part}: anclaje de dibujo no válido.')
    return errors


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
    dibujos_por_hoja = {}
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    for n in sorted(names):
        if not re.match(r'xl/worksheets/sheet\d+\.xml$', n): continue
        last_r = 0; bad = 0; nrow = 0; dup = 0
        with z.open(n) as f:
            for ev, el in etree.iterparse(f, tag=('{' + ns + '}row', '{' + ns + '}legacyDrawing')):
                if el.tag == '{' + ns + '}legacyDrawing':
                    dibujos_por_hoja.setdefault(n, []).append(el.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'))
                    el.clear()
                    continue
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
    err.extend(_comentarios(z, names, dibujos_por_hoja))
    err.extend(_dibujos(z, names))
    z.close()
    return err

if __name__ == '__main__':
    e = validar(sys.argv[1]); print('ERRORES:' if e else 'Paquete OK'); [print(' -', x) for x in e]
