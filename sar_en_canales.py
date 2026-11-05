"""Restaurar CC/CD de filas adicionales SAR desde el procedimiento FCC original."""
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import os
import re
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as E

from nucleo import Hoja
from seleccion import _celda, _tipo_extra
from sarlib import _REF, _STR, _sheetname, expand
from sar_en_formulas import FCC_EN

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
M = NS['s']


def contenido_sin_canales(xml):
    """Control de alcance: conservar toda la hoja salvo resultados/fórmulas CC/CD."""
    root = E.fromstring(xml)
    for cell in root.findall('s:sheetData/s:row/s:c', NS):
        if re.fullmatch(r'C[CD]\d+', cell.get('r')):
            for child in list(cell): cell.remove(child)
            cell.attrib.pop('t', None)
    return E.tostring(root, method='c14n', exclusive=True)


def adaptar_formula(text, rows, source_row, target_row, destino='SAR EN'):
    """Misma condición y VLOOKUP de FCC; su tabla se compone con columnas EN.

    CT:CY de FCC son SAR, modo, BW, posición, canal y frecuencia. En EN
    corresponden a CO, CG, CH, CI, CC y CD, que no son contiguas. CHOOSE
    conserva ese orden y los índices 5/6 sin añadir ni alterar otras celdas.
    """
    ordered = sorted(rows)
    columns = FCC_EN if destino == 'SAR EN' else {}
    def row(number, role='single'):
        if number == source_row:
            return target_row
        if number in rows:
            return rows[number]
        if number <= 2:
            return number
        # Una referencia escalar ausente no puede tomar el valor de la fila
        # vecina: podría ser otra posición o una batería distinta.
        return 1  # La fila 1 queda vacía: una exposición no seleccionada no aporta resultados.
    def reference(match):
        if _sheetname(match[1]) not in ('', 'SAR FCC-ISED'):
            return match[0]
        first = row(int(match[5]), 'start' if match[7] else 'single')
        col = columns.get(match[3], match[3])
        if match[7]:
            selected = [r for r in ordered if int(match[5]) <= r <= int(match[9])]
            first,last = (rows[selected[0]],rows[selected[-1]]) if selected else (1,1)
            if destino == 'SAR EN' and match[3] == 'CT' and match[7] == 'CY':
                ranges = [f'{match[2]}{c}{match[4]}{first}:{match[6]}{c}{match[8]}{last}'
                          for c in ('CO','CG','CH','CI','CC','CD')]
                return 'CHOOSE({1,2,3,4,5,6},'+','.join(ranges)+')'
            return f'{match[2]}{col}{match[4]}{first}:{match[6]}{columns.get(match[7],match[7])}{match[8]}{last}'
        return f'{match[2]}{col}{match[4]}{first}'
    pieces = _STR.split(text)
    for i in range(0,len(pieces),2):
        pieces[i] = _REF.sub(reference,pieces[i])
    return ''.join(pieces)


def _value(cell):
    if cell.get('t') == 'inlineStr':
        return ''.join(cell.itertext())
    return cell.findtext('s:v',namespaces=NS)


def _group_value(cell, lookup, seen=None):
    if cell is None:
        return None
    value = _value(cell)
    if value not in (None,''):
        return value
    text = cell.findtext('s:f',namespaces=NS)
    if not text:
        return value
    seen = set() if seen is None else seen
    if cell.get('r') in seen:
        return text
    seen.add(cell.get('r'))
    match = _REF.fullmatch(text)
    if match and not match[7] and _sheetname(match[1]) in ('','SAR EN'):
        target = lookup.get(match[3]+match[5])
        if target is not None:
            return _group_value(target,lookup,seen)
    return '='+text


def _kind(position, distance):
    if 'Variability' in position:
        return 'var'
    if 'Battery check' in position:
        return 'bat'
    if position.startswith('Accesorio'):
        return 'acc'
    if position in ('Front Face','Front of Face') and str(distance) in ('25','25.0'):
        return 'fof'
    return None


def _source_value(h, index, col, seen=None):
    """Resolver también las antenas/Tx que el original expresa con fórmulas."""
    seen = set() if seen is None else seen
    if (index, col) in seen:
        return None
    seen.add((index, col))
    kind, value = _celda(h, index, col)
    if kind in (1, 2):
        return str(value)
    if kind != 3:
        return None
    text = expand(value, h.rows[index][0], lambda sheet, row, role: row, h.name)
    match = _REF.fullmatch(text or '')
    if match and not match[7] and _sheetname(match[1]) in ('', h.name):
        target = h.by_old.get(int(match[5]))
        if target is not None:
            return _source_value(h, target, match[3], seen)
    return '=' + text if text else None


def _groups(root):
    merged = {}
    lookup = {c.get('r'): c for c in root.findall('s:sheetData/s:row/s:c', NS)}
    for merge in root.findall('s:mergeCells/s:mergeCell', NS):
        match = re.fullmatch(r'(BT|BU|BV|BW|BX)(\d+):\1(\d+)', merge.get('ref'))
        if match:
            col, first, last = match[1], int(match[2]), int(match[3])
            anchor = lookup.get(col + str(first))
            if anchor is not None:
                for number in range(first, last + 1):
                    merged[col, number] = _group_value(anchor, lookup)
    groups = []
    for element in root.findall('s:sheetData/s:row', NS):
        number = int(element.get('r'))
        if number <= 2:
            continue
        cells = {re.sub(r'\d', '', c.get('r')): c for c in element}
        key = tuple(_group_value(cells.get(col), lookup) or merged.get((col, number))
                    for col in ('BT', 'BU', 'BV', 'BW', 'BX'))
        if not groups or groups[-1][0] != key:
            groups.append((key, []))
        position = _value(cells['CA']) if 'CA' in cells else ''
        distance = _value(cells['CB']) if 'CB' in cells else None
        groups[-1][1].append((number, position or '', _kind(position or '', distance), cells))
    return groups


def restaurar_normales(xml, nombre, planes, plantilla):
    """Enlazar los canales normales con los auxiliares del original completo.

    Solo se restaura un enlace si su destino pertenece a la misma tecnología y
    banda seleccionadas. Para bandas nuevas se mantiene la fórmula de la base;
    nunca se recupera un canal RF de otra banda del datasheet.
    """
    from tecnologias_originales import _norm
    from hojas_base_datos import hoja_tecnologia
    from sarlib import _fmt_sheet
    root = E.fromstring(xml)
    complete = {}
    for family, plan in planes.items():
        channels = defaultdict(set)
        for view in plan.registros:
            record = view.record
            channels[(record.tech, _norm(record.band))].add((record.channel, record.frequency))
        new_groups = {plan.grupos[row] for row in plan.fallback_rows if row in plan.grupos}
        complete[family] = {key for key, values in channels.items() if len(values) >= 3} - new_groups
    sources = defaultdict(list)
    files = ('sar_en.xz', 'sar_fcc.xz') if nombre == 'SAR EN' else ('sar_fcc.xz', 'sar_en.xz')
    for file in files:
        path = Path(plantilla) / file
        if not path.exists():
            path = Path(plantilla) / 'formatos' / file
        h = Hoja(str(path))
        own = defaultdict(list)
        for i in range(2, len(h.rows)):
            v = h.kv(i)
            if not _tipo_extra(h, i):
                own[(v.get('BT'), v.get('BU'), str(v.get('BX')).casefold())].append((h, i))
        for key, indices in own.items():
            if key not in sources:
                sources[key] = indices
    count = 0
    for key, block in _groups(root):
        tech, band, ant, tx, exposure = key
        indices = sources.get((tech, band, str(exposure).casefold()), [])
        if not indices:
            continue
        normal = defaultdict(list)
        for h, index in indices:
            normal[str(h.kv(index).get('CA') or '')].append((h, index))
        ordinals = defaultdict(int)
        for number, position, kind, cells in block:
            if kind:
                continue
            matches = normal.get(position, [])
            if not matches:
                continue
            # La lista puede contener varias antenas. Elegir su procedimiento.
            same_ant = [(h, i) for h, i in matches if _source_value(h, i, 'BV') == ant]
            matches = same_ant or matches
            ordinal = ordinals[position]; ordinals[position] += 1
            if ordinal >= len(matches):
                continue
            h, index = matches[ordinal]
            for col in ('CC', 'CD'):
                cell = cells.get(col)
                k, pattern = _celda(h, index, col)
                if cell is None or k != 3:
                    continue
                text = expand(pattern, h.rows[index][0], lambda s, r, role: r, h.name)
                ref = _REF.fullmatch(text or '')
                if not ref or ref[7]:
                    continue
                source_name = _sheetname(ref[1])
                plan = planes.get(source_name)
                actual_tech = 'LTE CAT M1' if tech == 'LTE CATM1' else tech
                if plan is None or source_name != hoja_tecnologia(actual_tech):
                    continue
                # Los auxiliares originales clasifican canales Low/Mid/High.
                # Con una base parcial o registros nuevos podrían devolver una
                # celda vacía: en ese caso manda la fórmula de la base cargada.
                if (actual_tech, _norm(band)) not in complete[source_name]:
                    continue
                old = int(ref[5])
                if plan.origen_grupos.get(old) != (actual_tech, _norm(band)):
                    continue
                target = plan.mapped(old)
                if target is None:
                    continue
                for child in list(cell): cell.remove(child)
                cell.attrib.pop('t', None)
                E.SubElement(cell, '{' + M + '}f').text = f'{_fmt_sheet(plan.nombre)}{ref[2]}{ref[3]}{ref[4]}{target}'
                E.SubElement(cell, '{' + M + '}v')
                count += 1
    return (E.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True) if count else xml), count


def aplicar(path, plantilla, destino='SAR EN'):
    """Cambiar únicamente fórmulas/resultados CC/CD de las filas adicionales."""
    path = Path(path)
    with ZipFile(path) as z:
        rels = {r.get('Id'):r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        wb = E.fromstring(z.read('xl/workbook.xml'))
        sheet = next((s for s in wb.find('s:sheets',NS) if s.get('name')==destino),None)
        if sheet is None:
            return 0
        target = rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
        part = target.lstrip('/') if target.startswith('/') else 'xl/'+target
        root = E.fromstring(z.read(part))
    groups = _groups(root)
    if not any(kind for _,block in groups for _,_,kind,_ in block):
        return 0
    fcc_path=Path(plantilla)/'sar_fcc.xz'
    if not fcc_path.exists():
        fcc_path=Path(plantilla)/'formatos/sar_fcc.xz'
    fcc=Hoja(str(fcc_path))
    sources=[]
    previous=None
    for i in range(2,len(fcc.rows)):
        v=fcc.kv(i)
        key=(v.get('BT'),v.get('BU'),_source_value(fcc,i,'BV'),
             _source_value(fcc,i,'BW'),v.get('BX'))
        if key!=previous:
            sources.append((key,[]))
            previous=key
        sources[-1][1].append(i)
    changes=0
    pending=[]
    all_rows=defaultdict(dict)
    for key,block in groups:
        tech,band,ant,tx,exposure=key
        choices=[(k,indices) for k,indices in sources
                 if k[0] in (tech,'LTE' if tech=='LTE CATM1' else tech)
                 and str(k[4]).casefold()==str(exposure).casefold()]
        if not choices:
            continue
        source_key,indices=max(choices,key=lambda pair:(pair[0][0]==tech,str(pair[0][1])==str(band),
                                                        str(pair[0][2])==str(ant),str(pair[0][3])==str(tx)))
        normal=defaultdict(list)
        extras=defaultdict(list)
        for i in indices:
            kind=_tipo_extra(fcc,i)
            if kind:
                extras[kind].append(i)
            else:
                normal[str(fcc.kv(i).get('CA') or '')].append(i)
        rows={}
        counts=defaultdict(int)
        for number,position,kind,_ in block:
            if kind is None:
                matches=normal.get(position,[])
                ordinal=counts[position];counts[position]+=1
                if ordinal<len(matches):rows[fcc.rows[matches[ordinal]][0]]=number
        counts=defaultdict(int)
        assignments=[]
        for number,position,kind,cells in block:
            if kind is None or not extras[kind]:
                continue
            ordinal=counts[kind];counts[kind]+=1
            prototype=extras[kind][ordinal] if ordinal<len(extras[kind]) else extras[kind][0]
            old=fcc.rows[prototype][0]
            # Las baterías/accesorios adicionales reutilizan el primer prototipo.
            rows.setdefault(old,number)
            assignments.append((prototype,number,cells))
        scope=key[:4]
        all_rows[scope].update(rows)
        pending.append((scope,assignments))
    for scope,assignments in pending:
        rows=all_rows[scope]
        for prototype,number,cells in assignments:
            old=fcc.rows[prototype][0]
            for col in ('CC','CD'):
                kind,pattern=_celda(fcc,prototype,col)
                if kind!=3 or col not in cells:
                    continue
                text=expand(pattern,old,lambda sheet,r,role:r,'SAR FCC-ISED')
                if text is None or '#REF!' in text:
                    continue
                formula=adaptar_formula(text,rows,old,number,destino)
                cell=cells[col]
                for child in list(cell):cell.remove(child)
                cell.set('t','str')
                E.SubElement(cell,'{'+M+'}f').text=formula
                E.SubElement(cell,'{'+M+'}v').text='N/A'
                changes+=1
    if changes:
        destination=path.with_name('canales_sar.xlsm')
        with ZipFile(path) as source,ZipFile(destination,'w',ZIP_DEFLATED) as out:
            for info in source.infolist():
                out.writestr(deepcopy(info),E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
                             if info.filename==part else source.read(info.filename))
        os.replace(destination,path)
    return changes
