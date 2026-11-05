"""Identificar las celdas cuyas fórmulas elimina Excel al reparar un libro."""
import json
from pathlib import Path
import posixpath
import re
import sys
from zipfile import ZipFile

from lxml import etree as E

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sarlib import col2n, shift_formula

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def hojas(z):
    rels = {r.get('Id'): r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    root = E.fromstring(z.read('xl/workbook.xml'))
    return {s.get('name'): (rels[s.get('{' + R + '}id')].lstrip('/')
            if rels[s.get('{' + R + '}id')].startswith('/') else
            posixpath.normpath('xl/' + rels[s.get('{' + R + '}id')]))
            for s in root.find('{' + M + '}sheets')}


def formulas(z, part):
    result, masters, pending = {}, {}, []
    with z.open(part) as stream:
        for _, cell in E.iterparse(stream, tag='{' + M + '}c'):
            f = cell.find('{' + M + '}f')
            if f is not None:
                ref = cell.get('r')
                if f.get('t') == 'shared':
                    if f.text:
                        masters[f.get('si')] = (ref, f.text)
                        result[ref] = f.text
                    else:
                        pending.append((ref, f.get('si')))
                elif f.text:
                    result[ref] = f.text
            cell.clear()
            while cell.getprevious() is not None:
                del cell.getparent()[0]
    for ref, si in pending:
        if si not in masters:
            raise ValueError(f'{part}: fórmula compartida sin maestro en {ref}.')
        anchor, text = masters[si]
        a, b = re.fullmatch(r'([A-Z]+)(\d+)', anchor), re.fullmatch(r'([A-Z]+)(\d+)', ref)
        result[ref] = shift_formula(text, int(b[2])-int(a[2]), col2n(b[1])-col2n(a[1]))
    return result


def comparar(original, reparado, nombre='Conducted WiFi'):
    with ZipFile(original) as a, ZipFile(reparado) as b:
        before = formulas(a, hojas(a)[nombre])
        after = formulas(b, hojas(b)[nombre])
    return dict(hoja=nombre, formulas_antes=len(before), formulas_despues=len(after),
        eliminadas={ref: before[ref] for ref in sorted(before.keys()-after.keys())},
        modificadas={ref: dict(antes=before[ref], despues=after[ref])
                     for ref in sorted(before.keys() & after.keys()) if before[ref] != after[ref]})


if __name__ == '__main__':
    print(json.dumps(comparar(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv)>3 else 'Conducted WiFi'),
                     ensure_ascii=False, indent=2))
