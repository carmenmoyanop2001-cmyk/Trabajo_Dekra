"""Recupera resultados guardados del FCC recibido, solo si su fórmula coincide.

No sustituye fórmulas, estilos ni filas de la plantilla completa por los del
libro dividido, que contiene referencias rotas. Uso: python este_script.py
original_FCC.xlsm plantilla/sar_fcc.xz informe.json
"""
import hashlib
import json
import lzma
from pathlib import Path
import pickle
import sys
import zipfile

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nucleo import Hoja
from seleccion import _celda
from sarlib import tokenize, shift_formula, col2n

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def completar(original, plantilla, informe):
    h = Hoja(str(plantilla))
    cache, shared = {}, {}
    checked = 0
    with zipfile.ZipFile(original) as z:
        workbook = etree.fromstring(z.read('xl/workbook.xml'))
        rels = {r.get('Id'): r.get('Target') for r in etree.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheet = next(s for s in workbook.find(NS + 'sheets') if s.get('name') == 'SAR FCC-ISED')
        part = 'xl/' + rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
        strings = []
        with z.open('xl/sharedStrings.xml') as f:
            for _, el in etree.iterparse(f, tag=NS + 'si'):
                strings.append(''.join(t.text or '' for t in el.iter(NS + 't')))
                el.clear()
        with z.open(part) as f:
            for _, row in etree.iterparse(f, tag=NS + 'row'):
                oldrow = int(row.get('r'))
                index = h.by_old.get(oldrow)
                for cell in row:
                    form = cell.find(NS + 'f')
                    if form is None:
                        continue
                    col = ''.join(c for c in cell.get('r') if c.isalpha())
                    formula = form.text
                    if form.get('t') == 'shared':
                        if formula:
                            shared[form.get('si')] = (formula, oldrow, col2n(col))
                        elif form.get('si') in shared:
                            source, r, c = shared[form.get('si')]
                            formula = shift_formula(source, oldrow - r, col2n(col) - c)
                    if index is None or not formula or '#REF!' in formula:
                        continue
                    kind, pattern = _celda(h, index, col)
                    if kind != 3 or tokenize(formula, oldrow) != pattern:
                        continue
                    checked += 1
                    value = cell.findtext(NS + 'v')
                    if value is None or cell.get('t') == 'e' or col in h.kv(index):
                        continue
                    if cell.get('t') == 's':
                        value = strings[int(value)]
                    cache.setdefault(oldrow, {})[col] = value
                row.clear()
                while row.getprevious() is not None:
                    del row.getparent()[0]
    h.sd['formula_cache'] = cache
    with lzma.open(plantilla, 'wb') as f:
        pickle.dump(h.sd, f, protocol=4)
    report = dict(original=Path(original).name, sha256=hashlib.sha256(Path(original).read_bytes()).hexdigest(),
                  formulas_coincidentes=checked, resultados_recuperados=sum(map(len, cache.values())),
                  columnas=sorted({col for row in cache.values() for col in row}),
                  nota='Solo resultados guardados de fórmulas idénticas; fórmulas, estilos y filas sin cambios.')
    Path(informe).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    completar(*sys.argv[1:])
