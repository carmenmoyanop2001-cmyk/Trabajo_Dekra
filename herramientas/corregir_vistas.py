"""Corregir únicamente la vista de tecnologías en una copia de un libro existente."""
from copy import deepcopy
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as E

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tecnologias_originales import vista_desplazable

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NAMES = {'2G', '3G', '2G-3G', 'LTE', '5G', 'WiFi'}


def corregir(source, destination):
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError('Utiliza un archivo de salida diferente para conservar el original.')
    changed = {}
    with ZipFile(source) as z:
        wb = E.fromstring(z.read('xl/workbook.xml'))
        rels = {r.get('Id'):r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in wb.find('{' + M + '}sheets'):
            if sheet.get('name').removeprefix('Conducted ') not in NAMES:
                continue
            target = rels[sheet.get('{' + R + '}id')]
            part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            raw = z.read(part)
            view = re.search(rb'<sheetViews\b[^>]*>.*?</sheetViews>', raw, re.S)
            header = re.search(rb'<autoFilter\b[^>]*\bref="[A-Z]+(\d+):', raw)
            if view is None or header is None:
                continue
            wrapper = E.fromstring(f'<worksheet xmlns="{M}"></worksheet>')
            vista_desplazable(wrapper, int(header[1]))
            replacement = E.tostring(wrapper[0], encoding='UTF-8')
            changed[part] = raw[:view.start()] + replacement + raw[view.end():]
        with ZipFile(destination, 'w', ZIP_DEFLATED) as out:
            for info in z.infolist():
                out.writestr(deepcopy(info), changed.get(info.filename, z.read(info.filename)))
    return sorted(changed)


if __name__ == '__main__':
    print('\n'.join(corregir(sys.argv[1], sys.argv[2])))
