"""Visibilidad original de columnas, guardada sin necesitar el datasheet externo."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as E

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'s': M}
MANIFIESTO = Path(__file__).parent / 'plantilla/columnas_originales.json'


def nombre_original(name):
    if name in ('2G', '3G', '2G-3G', 'Conducted 2G', 'Conducted 3G'):
        return 'Conducted 2G-3G'
    if name.startswith(('LTE', '5G', 'WiFi', 'BT-Custom')):
        return 'Conducted ' + name
    return name


def restaurar_cols(raw, definitions):
    """Cambiar solo <cols>: las celdas, fórmulas y combinaciones quedan intactas."""
    match = re.search(rb'<cols(?:\s[^>]*)?>.*?</cols>', raw, re.S)
    if match is None:
        return raw
    root = E.fromstring(b'<worksheet xmlns="' + M.encode() + b'">' + match[0] + b'</worksheet>')
    cols = root[0]
    # Intervalos semiabiertos: hay que partir en max+1, no en max.
    limits = {int(v['min']) for v in definitions} | {int(v['max']) + 1 for v in definitions}
    last = max((int(v['max']) for v in definitions), default=0)
    result = []
    changed_visibility = False
    for col in cols:
        first, end = int(col.get('min')), int(col.get('max')) + 1
        cuts = [first] + sorted(v for v in limits if first < v < end) + [end]
        for a, b in zip(cuts, cuts[1:]):
            copied = deepcopy(col)
            copied.set('min', str(a)); copied.set('max', str(b - 1))
            if a <= last:
                hidden = next((v['hidden'] for v in definitions if int(v['min']) <= a <= int(v['max'])), False)
                changed_visibility |= hidden != (col.get('hidden') in ('1', 'true'))
                if hidden:
                    copied.set('hidden', '1')
                else:
                    copied.attrib.pop('hidden', None)
            result.append(copied)
    if not changed_visibility:
        return raw
    cols[:] = result
    changed = E.tostring(cols, encoding='UTF-8', with_tail=False)
    return raw[:match.start()] + changed + raw[match.end():]


def aplicar(path):
    manifest = json.loads(MANIFIESTO.read_text(encoding='utf-8'))['pestanas']
    path = Path(path)
    changes = {}
    checked = []
    modified = []
    with ZipFile(path) as source:
        rels = {r.get('Id'): r.get('Target') for r in E.fromstring(source.read('xl/_rels/workbook.xml.rels'))}
        wb = E.fromstring(source.read('xl/workbook.xml'))
        for sheet in wb.find('s:sheets', NS):
            canonical = nombre_original(sheet.get('name'))
            if canonical not in manifest:
                continue
            target = rels[sheet.get('{' + R + '}id')]
            part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            raw = source.read(part)
            updated = restaurar_cols(raw, manifest[canonical]['columnas'])
            if updated != raw:
                changes[part] = updated
                modified.append(sheet.get('name'))
            checked.append(sheet.get('name'))
        if changes:
            destination = path.with_name('visibilidad_original.xlsm')
            with ZipFile(destination, 'w', ZIP_DEFLATED) as out:
                for info in source.infolist():
                    out.writestr(deepcopy(info), changes.get(info.filename, source.read(info.filename)))
    if changes:
        os.replace(destination, path)
    return {'verificadas': checked, 'modificadas': modified}
