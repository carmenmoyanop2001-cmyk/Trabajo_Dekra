"""Lectura de las tablas visibles, excluyendo las columnas de apoyo ocultas."""
import re
import zipfile
from lxml import etree as E
from sarlib import col2n

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def cell_value(cell):
    if cell is None:
        return None
    if cell.get('t') == 'inlineStr':
        return ''.join(cell.xpath('.//s:t/text()', namespaces=NS))
    text = cell.findtext('s:v', namespaces=NS)
    if text is None:
        return None
    if cell.get('t') in ('str', 'e'):
        return text
    value = float(text)
    return int(value) if value.is_integer() else value


def table(path, number):
    with zipfile.ZipFile(path) as z:
        root = E.fromstring(z.read(f'xl/worksheets/sheet{number}.xml'))
    ref = root.find('s:autoFilter', NS).get('ref')
    end = re.search(r':([A-Z]+)(\d+)$', ref)
    last_col, last_row = col2n(end[1]), int(end[2])
    hidden = set()
    for col in root.findall('s:cols/s:col', NS):
        if col.get('hidden') == '1':
            hidden.update(range(int(col.get('min')), int(col.get('max')) + 1))
    rows = root.findall('s:sheetData/s:row', NS)
    fields = {}
    for cell in rows[0]:
        col = col2n(re.sub(r'\d', '', cell.get('r')))
        if col <= last_col and col not in hidden:
            fields[col] = cell_value(cell)
    result = []
    for row in rows[1:]:
        if int(row.get('r')) > last_row:
            continue
        cells = {col2n(re.sub(r'\d', '', c.get('r'))): c for c in row}
        result.append({name: cell_value(cells.get(col)) for col, name in fields.items()})
    return list(fields.values()), result
