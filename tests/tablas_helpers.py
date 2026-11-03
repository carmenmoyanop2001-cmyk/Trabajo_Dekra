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
    if text in (None,''):
        return None
    if cell.get('t') in ('str', 'e'):
        return text
    value = float(text)
    return int(value) if value.is_integer() else value


def table(path, number):
    with zipfile.ZipFile(path) as z:
        root = E.fromstring(z.read(f'xl/worksheets/sheet{number}.xml'))
    ref = root.find('s:autoFilter', NS).get('ref')
    first = re.match(r'([A-Z]+)(\d+)',ref)
    header_row = int(first[2])
    end = re.search(r':([A-Z]+)(\d+)$', ref)
    last_col, last_row = col2n(end[1]), int(end[2])
    hidden = set()
    for col in root.findall('s:cols/s:col', NS):
        if col.get('hidden') == '1':
            hidden.update(range(int(col.get('min')), int(col.get('max')) + 1))
    rows = root.findall('s:sheetData/s:row', NS)
    fields = {}
    header = next(r for r in rows if int(r.get('r')) == header_row)
    for cell in header:
        col = col2n(re.sub(r'\d', '', cell.get('r')))
        if col <= last_col and col not in hidden:
            label = cell_value(cell)
            if isinstance(label,str):label=re.sub(r'\s+',' ',label).strip()
            aliases = {2:'Región',10:'Tecnología',11:'Banda',20:'Canal',21:'Frecuencia (MHz)'}
            if header_row > 1 and col in aliases:
                label = aliases[col]
            if label:
                label = {'Frequency':'Frecuencia (MHz)','Notes':'Notas'}.get(label,label)
                if header_row>1 and col==col2n('M'):label='Bandwidth (MHz)'
                if header_row>1 and col==col2n('BO'):label='Notas'
                fields[col] = label
    result = []
    for row in rows:
        if int(row.get('r')) <= header_row or int(row.get('r')) > last_row or row.get('hidden')=='1':
            continue
        cells = {col2n(re.sub(r'\d', '', c.get('r'))): c for c in row}
        value = {name: cell_value(cells.get(col)) for col, name in fields.items()}
        if header_row > 1 and value.get('Tecnología') in ('GPRS','EGPRS'):
            slots = cell_value(cells.get(col2n('X')))
            if slots is not None:
                value['Tecnología'] += f' {int(slots)}TX'
        result.append(value)
    return list(fields.values()), result
