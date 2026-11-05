"""Reorganiza solo las tecnologías y conserva las partes protegidas idénticas.

Las coordenadas que usan las fórmulas SAR se mantienen ocultas. Si la hoja
2G-3G cambia de nombre, una copia de apoyo conserva el nombre anterior.
"""
from copy import deepcopy
from pathlib import Path
import os
import re
import zipfile
import tempfile
import json

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


def aplicar_minima(path, datos, catalogo, resumen):
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


def aplicar(path, datos, catalogo, resumen, overview=None):
    """Mostrar el original completo filtrado, sin alterar las siete hojas protegidas."""
    from tecnologias_originales import (EstilosOriginales, registros_vista, preparar,
        completar_cache, escribir, copiar_relacionados, copiar_estatica, verificar_apoyo, FAMILIAS)
    dir_originales = Path(__file__).parent / 'plantilla/originales'
    registros = registros_vista(catalogo, datos)
    destination = Path(path).with_name('original_filtrado.xlsm')
    with tempfile.TemporaryDirectory(prefix='sar_tecnologias_') as tmp, zipfile.ZipFile(path) as source:
        folder = Path(tmp)
        workbook = E.fromstring(source.read('xl/workbook.xml'))
        rels = E.fromstring(source.read('xl/_rels/workbook.xml.rels'))
        ct = E.fromstring(source.read('[Content_Types].xml'))
        styles = EstilosOriginales(source.read('xl/styles.xml'))
        targets = {r.get('Id'): _part(r.get('Target')) for r in rels if r.get('Type', '').endswith('/worksheet')}
        sheets = workbook.find('s:sheets', NS)
        old_order = list(sheets)
        technical = {}
        for original, records in registros.items():
            current = original if datos['conducida'] else original.removeprefix('Conducted ')
            technical[current] = original
        last_part = max(int(re.search(r'sheet(\d+)\.xml$', name)[1]) for name in source.namelist()
                        if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name))
        last_sheet = max(int(s.get('sheetId')) for s in sheets)
        last_rid = max(int(r.get('Id')[3:]) for r in rels if re.fullmatch(r'rId\d+', r.get('Id', '')))
        changed, added, public_names, support, plans = {}, {}, {}, {}, []
        extra_visibles=[]
        parts_by_name = {}
        avisos = resumen.setdefault('avisos', [])
        for sheet in old_order:
            current = sheet.get('name')
            if current not in technical:
                continue
            original = technical[current]
            part = targets[sheet.get('{' + R + '}id')]
            name = nombre_visible(original, datos)
            public_names[current] = name
            backend = source.read(part)
            if name != current:
                last_part += 1
                last_sheet += 1
                last_rid += 1
                aux_part = f'xl/worksheets/sheet{last_part}.xml'
                aux_rid = f'rId{last_rid}'
                added[aux_part] = E.tostring(_auxiliar(E.fromstring(backend)), encoding='UTF-8', xml_declaration=True, standalone=True)
                E.SubElement(sheets, '{' + M + '}sheet', name=current, sheetId=str(last_sheet), state='veryHidden', **{'{' + R + '}id': aux_rid})
                E.SubElement(rels, '{' + P + '}Relationship', Id=aux_rid, Type=R + '/worksheet', Target='worksheets/' + Path(aux_part).name)
                E.SubElement(ct, '{' + C + '}Override', PartName='/' + aux_part, ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
                support[current] = aux_part
                sheet.set('name', name)
            plan = preparar(original, name, backend, registros[original], datos, folder, dir_originales, styles, avisos)
            plans.append(plan)
            parts_by_name[name] = part
        completar_cache(plans)
        plan_by_name = {p.familia: p for p in plans}
        defined=workbook.find('s:definedNames',NS)
        if defined is None:
            defined=E.Element('{' + M + '}definedNames')
            at=next((i for i,n in enumerate(workbook) if E.QName(n).localname in ('calcPr','oleSize','customWorkbookViews','pivotCaches','smartTagPr','smartTagTypes','webPublishing','fileRecoveryPr','webPublishObjects','extLst')),len(workbook))
            workbook.insert(at,defined)
        for plan in plans:
            part = parts_by_name[plan.nombre]
            current=next(old for old,new in public_names.items() if new==plan.nombre)
            if current in support:
                added[support[current]]=E.tostring(_auxiliar(E.fromstring(plan.backend)),encoding='UTF-8',xml_declaration=True,standalone=True)
            rendered = folder / Path(part).name
            root = escribir(plan, rendered, plan_by_name, overview)
            verificar_apoyo(plan, rendered)
            if plan.referencias_rotas:
                avisos.append(f'{plan.nombre}: {plan.referencias_rotas} referencias rotas del original se han dirigido a una celda vacía; revisa esos cálculos antes de usar resultados.')
            changed[part] = rendered
            copiar_relacionados(plan, part, changed, added, ct)
        inventario=json.loads((dir_originales/'inventario.json').read_text(encoding='utf-8'))
        for nombre,info in inventario['pestanas'].items():
            if nombre in PROTEGIDAS or nombre in FAMILIAS:continue
            last_part+=1;last_sheet+=1;last_rid+=1
            part=f'xl/worksheets/sheet{last_part}.xml'
            rid=f'rId{last_rid}'
            plan,content,state=copiar_estatica(nombre,info,dir_originales,styles,plan_by_name,overview)
            added[part]=content
            attrs=dict(name=nombre,sheetId=str(last_sheet),**{'{' + R + '}id':rid})
            if state!='visible':attrs['state']=state
            else:extra_visibles.append(nombre)
            E.SubElement(sheets,'{' + M + '}sheet',**attrs)
            E.SubElement(rels,'{' + P + '}Relationship',Id=rid,Type=R+'/worksheet',Target='worksheets/'+Path(part).name)
            E.SubElement(ct,'{' + C + '}Override',PartName='/'+part,ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
            copiar_relacionados(plan,part,changed,added,ct)
        defined = workbook.find('s:definedNames', NS)
        if defined is not None:
            for item in list(defined):
                if item.get('name') != '_xlnm._FilterDatabase':
                    continue
                local = int(item.get('localSheetId', '-1'))
                if 0 <= local < len(old_order):
                    name = old_order[local].get('name')
                    plan = next((p for p in plans if p.nombre == name), None)
                    if plan:
                        source_filter = plan.root.find('s:autoFilter', NS)
                        if source_filter is not None:
                            match = re.match(r'([A-Z]+)\d+:([A-Z]+)\d+', source_filter.get('ref'))
                            end = max([match[2]] + list(plan.extras.values()), key=col2n)
                            item.text = "'" + name.replace("'", "''") + "'!" + f'${match[1]}${plan.offset+2}:${end}${plan.offset+plan.count}'
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
                for number in element.findall('.//{' + vt + '}i4'):
                    number.text = str(len(sheets))
        changed.update({'xl/workbook.xml': E.tostring(workbook, encoding='UTF-8', xml_declaration=True, standalone=True),
                        'xl/_rels/workbook.xml.rels': E.tostring(rels, encoding='UTF-8', xml_declaration=True, standalone=True),
                        '[Content_Types].xml': E.tostring(ct, encoding='UTF-8', xml_declaration=True, standalone=True),
                        'docProps/app.xml': E.tostring(props, encoding='UTF-8', xml_declaration=True, standalone=True),
                        'xl/styles.xml': styles.xml()})
        from sar_en_canales import restaurar_normales, contenido_sin_canales
        normales = {}
        for sheet in old_order:
            name = sheet.get('name')
            if name in ('SAR EN', 'SAR FCC-ISED'):
                part = targets[sheet.get('{' + R + '}id')]
                changed[part], normales[name] = restaurar_normales(source.read(part), name,
                    plan_by_name, dir_originales.parent)
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as out:
            for info in source.infolist():
                value = changed.get(info.filename)
                if isinstance(value, Path):
                    out.write(value, info.filename)
                else:
                    out.writestr(deepcopy(info), value if value is not None else source.read(info.filename))
            for part, value in added.items():
                out.writestr(part, value)
        with zipfile.ZipFile(destination) as result:
            for name in source.namelist():
                if name not in changed:
                    assert source.read(name) == result.read(name), name
            for sheet in old_order:
                if sheet.get('name') in PROTEGIDAS:
                    part = targets[sheet.get('{' + R + '}id')]
                    if sheet.get('name') not in ('SAR EN', 'SAR FCC-ISED'):
                        assert source.read(part) == result.read(part), sheet.get('name')
                    elif contenido_sin_canales(source.read(part)) != contenido_sin_canales(result.read(part)):
                        raise ValueError(sheet.get('name') + ': se ha modificado contenido fuera de CC/CD.')
    os.replace(destination, path)
    resumen['hojas'] = [public_names.get(name, name) for name in resumen['hojas']] + extra_visibles
    counts = {p.nombre: p.count - 2 for p in plans}
    resumen['filas'] = {public_names.get(name, name): counts.get(public_names.get(name, name), count)
                        for name, count in resumen['filas'].items()}
    resumen['soporte_interno'] = support
    resumen['pestanas_protegidas_identicas'] = sorted((PROTEGIDAS - {'SAR EN', 'SAR FCC-ISED'}) & set(resumen['hojas']))
    resumen['enlaces_cc_cd_originales'] = normales
    resumen['presentacion_original'] = {p.nombre: dict(cabecera=p.offset+2, inicio=p.offset+3, ultima=p.offset+p.count,
                                                     registros_base=len(p.covered), filas_originales=p.count-2)
                                       for p in plans}
    resumen['pestanas_originales_guardadas']=len(inventario['pestanas'])
    resumen['avisos'] = [w for w in resumen['avisos'] if not w.startswith('La base no informa todos los campos de modo/ancho de banda')]
