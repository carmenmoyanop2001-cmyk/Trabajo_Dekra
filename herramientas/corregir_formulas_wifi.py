"""Corregir COLUMN(valor) en una copia SIN reparar, usando la referencia original."""
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as E

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from herramientas.comparar_formulas_excel import hojas
from referencias_geometricas import llamadas_simples, errores_referencia
from sarlib import _REF

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ROOT = Path(__file__).resolve().parents[1]


def referencias_originales():
    folder = ROOT / 'plantilla/originales'
    metadata = json.loads((folder / 'inventario.json').read_text())['pestanas']['Conducted WiFi']
    columns = defaultdict(set)
    with ZipFile(folder / metadata['archivo']) as z, z.open(metadata['parte']) as stream:
        for _, cell in E.iterparse(stream, tag='{' + M + '}c'):
            formula = cell.findtext('{' + M + '}f')
            if formula:
                for call in llamadas_simples(formula):
                    ref = _REF.fullmatch(call[2].strip())
                    if call[1].upper() == 'COLUMN' and ref is not None and not ref[7]:
                        col = re.sub(r'\d', '', cell.get('r'))
                        columns[col].add(ref[2] + ref[3] + '1')
            cell.clear()
            while cell.getprevious() is not None:
                del cell.getparent()[0]
    return {col: next(iter(refs)) for col, refs in columns.items() if len(refs) == 1}


def reparar(text, reference):
    changes = []
    for call in llamadas_simples(text):
        if call[1].upper() == 'COLUMN' and errores_referencia(call[0]):
            changes.append((call.start(), call.end(), f'COLUMN({reference})'))
    for first, last, fixed in reversed(changes):
        text = text[:first] + fixed + text[last:]
    return text


def corregir(source, destination):
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError('Conserva el original y utiliza otra ruta de salida.')
    references = referencias_originales()
    changed = []
    with ZipFile(source) as z:
        part = hojas(z)['Conducted WiFi']
        root = E.fromstring(z.read(part))
        for cell in root.findall('.//{' + M + '}c'):
            f = cell.find('{' + M + '}f')
            if f is None or not f.text or not errores_referencia(f.text):
                continue
            col = re.sub(r'\d', '', cell.get('r'))
            if col not in references:
                raise ValueError('No hay una referencia original inequívoca para ' + cell.get('r'))
            text = reparar(f.text, references[col])
            if errores_referencia(text):
                raise ValueError('No se han podido resolver todas las referencias de ' + cell.get('r'))
            if text != f.text:
                f.text = text
                changed.append(cell.get('r'))
        with ZipFile(destination, 'w', ZIP_DEFLATED) as out:
            for info in z.infolist():
                out.writestr(deepcopy(info), E.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
                             if info.filename == part else z.read(info.filename))
    return changed


if __name__ == '__main__':
    print(json.dumps({'celdas_corregidas': corregir(sys.argv[1], sys.argv[2])}, ensure_ascii=False))
