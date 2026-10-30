"""Reorganiza solo las tecnologías y conserva las partes protegidas idénticas.

Las coordenadas que usan las fórmulas SAR se mantienen ocultas. Si la hoja
2G-3G cambia de nombre, una copia de apoyo conserva el nombre anterior.
"""
from copy import deepcopy
from pathlib import Path
import os
import re
import zipfile

from lxml import etree as E

from generador_excel import ARCHIVOS
from sarlib import _REF, _sheetname, col2n, n2col
from tablas_tecnologias import tabla, crear_hoja, nombre_visible, EstilosVisibles, NS, M, R

PROTEGIDAS = {'Overview', 'Tune-Up', 'Validations', 'SAR EN', 'SAR FCC-ISED',
              'Test Campaign', 'Pretesting-Others'}
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
C = 'http://schemas.openxmlformats.org/package/2006/content-types'


def _part(target):
    return target.lstrip('/') if target.startswith('/') else 'xl/' + target


def _col(cell):
    return col2n(re.sub(r'\d', '', cell.get('r')))


def columnas_necesarias(roots, technical):
    """Cierre de dependencias de las fórmulas protegidas, por columna."""
    needed = {name: set() for name in technical}
    formulas = {name: [(c.get('r'), c.findtext('s:f', namespaces=NS))
                       for c in root.findall('s:sheetData/s:row/s:c', NS) if c.find('s:f', NS) is not None]
                for name, root in roots.items()}

    def references(formula, owner):
        for match in _REF.finditer(formula or ''):
            sheet = _sheetname(match.group(1)) or owner
            if sheet not in needed:
                continue
            first = col2n(match.group(3))
            last = col2n(match.group(7)) if match.group(7) else first
            yield sheet, set(range(first, last + 1))

    for name in PROTEGIDAS & roots.keys():
        for _, formula in formulas[name]:
            for target, columns in references(formula, name):
                needed[target].update(columns)
    while True:
        changed = False
        for name in technical:
            for address, formula in formulas[name]:
                if col2n(re.sub(r'\d', '', address)) not in needed[name]:
                    continue
                for target, columns in references(formula, name):
                    if columns - needed[target]:
                        needed[target].update(columns)
                        changed = True
                if re.search(r'\b(?:INDIRECT|OFFSET)\(', formula or '', re.I):
                    # Las referencias calculadas se conservan de forma
                    # conservadora: ninguna columna de apoyo se sobrescribe.
                    for target in technical:
                        columns = {_col(c) for c in roots[target].findall('s:sheetData/s:row/s:c', NS)}
                        if columns - needed[target]:
                            needed[target].update(columns)
                            changed = True
        if not changed:
            break
    return needed


def _integrar_visible(original, visible, necessary, pictures):
    """La tabla ocupa columnas libres; los datos usados por SAR no se mueven."""
    visible_data = visible.find('s:sheetData', NS)
    count = len(visible_data[0])
    slots = []
    candidate = 1
    while len(slots) < count:
        if candidate not in necessary and not (pictures and 79 <= candidate <= 104):
            slots.append(candidate)
        candidate += 1
    assert slots[0] == 1, 'La columna A debe quedar disponible para Región.'
    original_columns = visible.find('s:cols', NS)
    widths = {int(c.get('min')): c.get('width') for c in original_columns
              if int(c.get('min')) == int(c.get('max')) and int(c.get('min')) <= count}
    for row in visible_data:
        for cell in row:
            rn = re.search(r'\d+$', cell.get('r'))[0]
            cell.set('r', n2col(slots[_col(cell) - 1]) + rn)
    last_row = len(visible_data)
    legacy_rows = original.findall('s:sheetData/s:row', NS)
    rows = {int(r.get('r')): r for r in visible_data}
    for old in legacy_rows:
        keep = [c for c in old if _col(c) in necessary]
        if not keep:
            continue
        rn = int(old.get('r'))
        if rn not in rows:
            rows[rn] = E.Element('{' + M + '}row', r=str(rn))
            if rn > last_row and not (pictures and rn <= 100):
                rows[rn].set('hidden', '1')
        for cell in keep:
            rows[rn].append(deepcopy(cell))
    for row in list(visible_data):
        visible_data.remove(row)
    for rn in sorted(rows):
        row = rows[rn]
        cells = sorted(list(row), key=_col)
        for cell in list(row):
            row.remove(cell)
        for cell in cells:
            row.append(cell)
        visible_data.append(row)
    cols = visible.find('s:cols', NS)
    for col in list(cols):
        cols.remove(col)
    max_col = max(slots + list(necessary) + ([104] if pictures else []))
    old_widths = {}
    old_cols = original.find('s:cols', NS)
    for col in old_cols if old_cols is not None else []:
        for cn in range(int(col.get('min')), int(col.get('max')) + 1):
            if cn <= max_col:
                old_widths[cn] = col.get('width', '9')
    for cn in range(1, max_col + 1):
        attributes = dict(min=str(cn), max=str(cn), customWidth='1')
        if cn in slots:
            attributes['width'] = widths[slots.index(cn) + 1]
        elif pictures and 79 <= cn <= 104:
            attributes['width'] = old_widths.get(cn, '9')
        else:
            attributes.update(width=old_widths.get(cn, '9'), hidden='1')
        E.SubElement(cols, '{' + M + '}col', **attributes)
    visible.find('s:dimension', NS).set('ref', f'A1:{n2col(max_col)}{max(rows)}')
    visible.find('s:autoFilter', NS).set('ref', f'A1:{n2col(slots[-1])}{last_row}')
    for old in legacy_rows:
        rn = int(old.get('r'))
        actual = {_col(c): c for c in rows.get(rn, [])}
        for cell in old:
            if _col(cell) in necessary:
                assert E.tostring(actual[_col(cell)], method='c14n', exclusive=True) == E.tostring(cell, method='c14n', exclusive=True)
    return visible


def _auxiliar(root):
    copy = deepcopy(root)
    properties = copy.find('s:sheetPr', NS)
    if properties is not None:
        properties.attrib.pop('codeName', None)
    for element in list(copy.iter()):
        if E.QName(element).localname in ('drawing', 'legacyDrawing', 'legacyDrawingHF',
                                         'oleObjects', 'controls', 'hyperlinks', 'picture'):
            element.getparent().remove(element)
            continue
        for key in list(element.attrib):
            if key.startswith('{' + R + '}'):
                del element.attrib[key]
    return copy


def aplicar(path, datos, catalogo, resumen):
    records = catalogo.seleccionar(datos)
    destination = Path(path).with_name('tecnologias_ordenadas.xlsm')
    with zipfile.ZipFile(path) as source:
        workbook = E.fromstring(source.read('xl/workbook.xml'))
        rels = E.fromstring(source.read('xl/_rels/workbook.xml.rels'))
        ct = E.fromstring(source.read('[Content_Types].xml'))
        styles = EstilosVisibles(source.read('xl/styles.xml'))
        targets = {r.get('Id'): _part(r.get('Target')) for r in rels if r.get('Type', '').endswith('/worksheet')}
        sheets = workbook.find('s:sheets', NS)
        old_order = list(sheets)
        roots = {s.get('name'): E.fromstring(source.read(targets[s.get('{' + R + '}id')])) for s in sheets}
        technical = {}
        for original in ARCHIVOS:
            if original.startswith('SAR '):
                continue
            current = original if datos['conducida'] else original.removeprefix('Conducted ')
            if current in roots:
                technical[current] = original
        necessary = columnas_necesarias(roots, technical)
        last_part = max(int(re.search(r'sheet(\d+)\.xml$', name)[1]) for name in source.namelist()
                        if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name))
        last_sheet = max(int(s.get('sheetId')) for s in sheets)
        last_rid = max(int(r.get('Id')[3:]) for r in rels if re.fullmatch(r'rId\d+', r.get('Id', '')))
        changed, added, public_names, rows_count, support = {}, {}, {}, {}, {}
        for index, sheet in enumerate(old_order):
            current = sheet.get('name')
            if current not in technical:
                continue
            original = technical[current]
            fields, rows = tabla(catalogo, records, original)
            part = targets[sheet.get('{' + R + '}id')]
            name = nombre_visible(original, datos)
            public_names[current] = name
            rows_count[name] = len(rows)
            visible = E.fromstring(crear_hoja(source.read(part), fields, rows, original, styles))
            needed = necessary[current]
            if name != current:
                # El nombre anterior debe seguir resolviéndose en las fórmulas
                # protegidas. Su copia de apoyo queda fuera de la interfaz.
                last_part += 1
                last_sheet += 1
                last_rid += 1
                aux_part = f'xl/worksheets/sheet{last_part}.xml'
                aux_rid = f'rId{last_rid}'
                added[aux_part] = E.tostring(_auxiliar(roots[current]), encoding='UTF-8', xml_declaration=True, standalone=True)
                E.SubElement(sheets, '{' + M + '}sheet', name=current, sheetId=str(last_sheet), state='veryHidden',
                             **{'{' + R + '}id': aux_rid})
                E.SubElement(rels, '{' + P + '}Relationship', Id=aux_rid, Type=R + '/worksheet', Target='worksheets/' + Path(aux_part).name)
                E.SubElement(ct, '{' + C + '}Override', PartName='/' + aux_part,
                             ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
                support[current] = aux_part
                sheet.set('name', name)
                needed = set()
            visible = _integrar_visible(roots[current], visible, needed, original == 'Conducted 2G-3G')
            changed[part] = E.tostring(visible, encoding='UTF-8', xml_declaration=True, standalone=True)
        defined = workbook.find('s:definedNames', NS)
        if defined is not None:
            for item in list(defined):
                if item.get('name') != '_xlnm._FilterDatabase':
                    continue
                local = int(item.get('localSheetId', '-1'))
                if 0 <= local < len(old_order):
                    current = old_order[local].get('name')
                    # El elemento de hoja ya puede tener el título nuevo.
                    original_name = next((old for old, new in public_names.items() if new == current), current)
                    if original_name in technical:
                        root = E.fromstring(changed[targets[old_order[local].get('{' + R + '}id')]])
                        ref = root.find('s:autoFilter', NS).get('ref')
                        item.text = "'" + current.replace("'", "''") + "'!" + re.sub(r'([A-Z]+)(\d+)', lambda m: '$' + m[1] + '$' + m[2], ref)
        changed['xl/workbook.xml'] = E.tostring(workbook, encoding='UTF-8', xml_declaration=True, standalone=True)
        changed['xl/_rels/workbook.xml.rels'] = E.tostring(rels, encoding='UTF-8', xml_declaration=True, standalone=True)
        changed['[Content_Types].xml'] = E.tostring(ct, encoding='UTF-8', xml_declaration=True, standalone=True)
        props = E.fromstring(source.read('docProps/app.xml'))
        vt = 'http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'
        for element in props.iter():
            if E.QName(element).localname == 'TitlesOfParts':
                vector = element[0]
                for child in list(vector):
                    vector.remove(child)
                for s in sheets:
                    E.SubElement(vector, '{' + vt + '}lpstr').text = s.get('name')
                vector.set('size', str(len(sheets)))
            elif E.QName(element).localname == 'HeadingPairs':
                numbers = element.findall('.//{' + vt + '}i4')
                if numbers:
                    numbers[0].text = str(len(sheets))
        changed['docProps/app.xml'] = E.tostring(props, encoding='UTF-8', xml_declaration=True, standalone=True)
        changed['xl/styles.xml'] = styles.xml()
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as out:
            for info in source.infolist():
                out.writestr(deepcopy(info), changed.get(info.filename, source.read(info.filename)))
            for part, data in added.items():
                out.writestr(part, data)
        # Además de las hojas protegidas se preservan imágenes, relaciones,
        # macros y estilos. Solo se permiten las partes enumeradas arriba.
        with zipfile.ZipFile(destination) as result:
            for name in source.namelist():
                if name not in changed:
                    assert source.read(name) == result.read(name), name
            for name in PROTEGIDAS & roots.keys():
                part = targets[next(s.get('{' + R + '}id') for s in old_order if s.get('name') == name)]
                assert source.read(part) == result.read(part), name
    os.replace(destination, path)
    resumen['hojas'] = [public_names.get(name, name) for name in resumen['hojas']]
    resumen['filas'] = {public_names.get(name, name): rows_count.get(public_names.get(name, name), count)
                        for name, count in resumen['filas'].items()}
    resumen['soporte_interno'] = support
    resumen['pestanas_protegidas_identicas'] = sorted(PROTEGIDAS & roots.keys())
    resumen['avisos'] = [w for w in resumen.get('avisos', [])
                        if not w.startswith('La base no informa todos los campos de modo/ancho de banda')]
