"""Adaptar exclusivamente CC/CD de las filas adicionales EN desde FCC-ISED."""
from bisect import bisect_left, bisect_right
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


def adaptar_formula(text, rows, source_row, target_row):
    """Misma condición y VLOOKUP de FCC; su tabla se compone con columnas EN.

    CT:CY de FCC son SAR, modo, BW, posición, canal y frecuencia. En EN
    corresponden a CO, CG, CH, CI, CC y CD, que no son contiguas. CHOOSE
    conserva ese orden y los índices 5/6 sin añadir ni alterar otras celdas.
    """
    ordered = sorted(rows)
    def row(number, role='single'):
        if number == source_row:
            return target_row
        if number in rows:
            return rows[number]
        if number <= 2:
            return number
        at = bisect_left(ordered, number) if role == 'start' else bisect_right(ordered, number)-1
        if 0 <= at < len(ordered):
            return rows[ordered[at]]
        return 1  # La fila 1 queda vacía: una exposición no seleccionada no aporta resultados.
    def reference(match):
        if _sheetname(match[1]) not in ('', 'SAR FCC-ISED'):
            return match[0]
        first = row(int(match[5]), 'start' if match[7] else 'single')
        col = FCC_EN.get(match[3], match[3])
        if match[7]:
            selected = [r for r in ordered if int(match[5]) <= r <= int(match[9])]
            first,last = (rows[selected[0]],rows[selected[-1]]) if selected else (1,1)
            if match[3] == 'CT' and match[7] == 'CY':
                ranges = [f'{match[2]}{c}{match[4]}{first}:{match[6]}{c}{match[8]}{last}'
                          for c in ('CO','CG','CH','CI','CC','CD')]
                return 'CHOOSE({1,2,3,4,5,6},'+','.join(ranges)+')'
            return f'{match[2]}{col}{match[4]}{first}:{match[6]}{FCC_EN.get(match[7],match[7])}{match[8]}{last}'
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
    if 'Battery check' in position:
        return 'bat'
    if position.startswith('Accesorio'):
        return 'acc'
    if position in ('Front Face','Front of Face') and str(distance) in ('25','25.0'):
        return 'fof'
    return None


def aplicar(path, plantilla):
    """Dejar intacto el motor aprobado y corregir solo las dos columnas pedidas."""
    path = Path(path)
    with ZipFile(path) as z:
        rels = {r.get('Id'):r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        wb = E.fromstring(z.read('xl/workbook.xml'))
        sheet = next((s for s in wb.find('s:sheets',NS) if s.get('name')=='SAR EN'),None)
        if sheet is None:
            return 0
        target = rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
        part = target.lstrip('/') if target.startswith('/') else 'xl/'+target
        root = E.fromstring(z.read(part))
    # Se agrupa igual que el procedimiento: tecnología, banda, antena, TX y exposición.
    merged = {}
    lookup = {c.get('r'): c for c in root.findall('s:sheetData/s:row/s:c',NS)}
    for merge in root.findall('s:mergeCells/s:mergeCell',NS):
        match = re.fullmatch(r'(BT|BU|BV|BW|BX)(\d+):\1(\d+)',merge.get('ref'))
        if match:
            col,first,last = match[1],int(match[2]),int(match[3])
            anchor = lookup.get(col+str(first))
            if anchor is not None:
                for number in range(first,last+1):merged[(col,number)] = _group_value(anchor,lookup)
    groups=[]
    for element in root.findall('s:sheetData/s:row',NS):
        if int(element.get('r'))<=2:
            continue
        cells={re.sub(r'\d','',c.get('r')):c for c in element}
        values={c:_value(v) for c,v in cells.items()}
        key=tuple(_group_value(cells.get(c),lookup) or merged.get((c,int(element.get('r'))))
                  for c in ('BT','BU','BV','BW','BX'))
        if not groups or groups[-1][0]!=key:
            groups.append((key,[]))
        position=values.get('CA') or ''
        groups[-1][1].append((int(element.get('r')),position,_kind(position,values.get('CB')),cells))
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
        key=(v.get('BT'),v.get('BU'),v.get('BV'),v.get('BW'),v.get('BX'))
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
                formula=adaptar_formula(text,rows,old,number)
                cell=cells[col]
                for child in list(cell):cell.remove(child)
                cell.set('t','str')
                E.SubElement(cell,'{'+M+'}f').text=formula
                E.SubElement(cell,'{'+M+'}v').text='N/A'
                changes+=1
    if changes:
        destination=path.with_name('canales_en.xlsm')
        with ZipFile(path) as source,ZipFile(destination,'w',ZIP_DEFLATED) as out:
            for info in source.infolist():
                out.writestr(deepcopy(info),E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
                             if info.filename==part else source.read(info.filename))
        os.replace(destination,path)
    return changes
