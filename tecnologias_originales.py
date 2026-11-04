"""Pestañas completas del original, filtradas por catálogo y cuestionario.

Las coordenadas que lee SAR permanecen en filas ocultas. La vista completa
del original ocupa las filas siguientes, con sus columnas y estilos intactos.
Las partes originales se guardan dentro del programa y nunca se modifican.
"""
from bisect import bisect_left, bisect_right
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path
import pickle
import posixpath
import re
import zipfile

from lxml import etree as E

from base_datos import normalizar
from hojas_base_datos import hoja_tecnologia, PARAM_COL
from seleccion import token_modo
from corregir_2g3g import normalizar_fechas
from sarlib import _REF, _STR, _sheetname, col2n, n2col, shift_formula

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
C = 'http://schemas.openxmlformats.org/package/2006/content-types'
NS = {'s': M}
FAMILIAS = {'Conducted 2G-3G': '2g3g.zip', 'Conducted LTE': 'lte.zip',
            'Conducted LTE CATM1': 'catm1.zip', 'Conducted LTE NB-IoT': 'nbiot.zip',
            'Conducted 5G': '5g.zip', 'Conducted WiFi': 'wifi.zip',
            'Conducted BT-Custom': 'bt.zip'}


def _q(tag):
    return '{' + M + '}' + tag


def _fmt_sheet(name):
    return "'" + name.replace("'","''") + "'!" if name else ''


def _target(owner, target):
    return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(owner) + '/' + target)


def _relpart(part):
    return posixpath.dirname(part) + '/_rels/' + posixpath.basename(part) + '.rels'


def _xml(element):
    return E.tostring(element, encoding='UTF-8', xml_declaration=True, standalone=True)


class EstilosOriginales:
    """Añadir estilos de cada original sin modificar ninguna definición existente."""
    def __init__(self, xml):
        self.root = E.fromstring(xml)
        self.before = deepcopy(self.root)

    def incorporar(self, source):
        src = E.fromstring(source)
        fmts = self.root.find('s:numFmts', NS)
        if fmts is None:
            fmts = E.Element(_q('numFmts'), count='0')
            self.root.insert(0, fmts)
        fmtmap = {}
        codes = {e.get('formatCode'): e.get('numFmtId') for e in fmts}
        next_id = max([163] + [int(e.get('numFmtId')) for e in fmts]) + 1
        source_fmts = src.find('s:numFmts', NS)
        for node in source_fmts if source_fmts is not None else []:
            code = node.get('formatCode')
            if code not in codes:
                copied = deepcopy(node)
                copied.set('numFmtId', str(next_id))
                fmts.append(copied)
                codes[code] = str(next_id)
                next_id += 1
            fmtmap[node.get('numFmtId')] = codes[code]
        fmts.set('count', str(len(fmts)))
        offsets, indices = {}, {}
        for tag in ('fonts', 'fills', 'borders', 'cellStyleXfs', 'cellXfs', 'dxfs'):
            target = self.root.find('s:' + tag, NS)
            source_group = src.find('s:' + tag, NS)
            if target is None:
                if source_group is None:
                    offsets[tag] = 0
                    continue
                target = E.Element(_q(tag), count='0')
                # Las plantillas ya contienen estos grupos salvo dxfs.
                at = next((i for i, n in enumerate(self.root) if E.QName(n).localname in ('tableStyles','colors','extLst')), len(self.root))
                self.root.insert(at, target)
            offsets[tag] = len(target)
            indices[tag]={}
            known={E.tostring(n,method='c14n',exclusive=True):i for i,n in enumerate(target)} if tag in ('fonts','fills','borders') else {}
            for original_index,node in enumerate(source_group if source_group is not None else []):
                copied = deepcopy(node)
                for item in copied.iter():
                    for attr, group in (('fontId','fonts'), ('fillId','fills'), ('borderId','borders'), ('xfId','cellStyleXfs')):
                        if attr in item.attrib:
                            old_id=int(item.get(attr))
                            item.set(attr, str(indices[group].get(old_id,old_id+offsets[group])))
                    if item.get('numFmtId') in fmtmap:
                        item.set('numFmtId', fmtmap[item.get('numFmtId')])
                key=E.tostring(copied,method='c14n',exclusive=True)
                if tag in ('fonts','fills','borders') and key in known:
                    indices[tag][original_index]=known[key]
                else:
                    indices[tag][original_index]=len(target)
                    known[key]=len(target)
                    target.append(copied)
            target.set('count', str(len(target)))
        return offsets

    def xml(self):
        # El prefijo original de cada colección debe continuar idéntico.
        for group in self.before:
            actual = self.root.find(group.tag)
            for old, new in zip(group, actual):
                assert E.tostring(old, method='c14n', exclusive=True) == E.tostring(new, method='c14n', exclusive=True)
        return _xml(self.root)


def _estructura(z, part):
    """Leer cabecera y cola sin materializar los cientos de MB de sheetData."""
    head, end = None, b''
    prefix = b''
    with z.open(part) as stream:
        while chunk := stream.read(1024 * 1024):
            if head is None:
                prefix += chunk
                start = prefix.find(b'<sheetData')
                if start >= 0:
                    head = prefix[:start]
                    prefix = b''
            end = (end + chunk)[-16 * 1024 * 1024:]
    marker = end.rfind(b'</sheetData>')
    if head is None or marker < 0:
        raise ValueError('El original no contiene una estructura de hoja reconocible: ' + part)
    return E.fromstring(head + b'<sheetData/>' + end[marker + len(b'</sheetData>'):])


def _strings(z):
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    return list(E.fromstring(z.read('xl/sharedStrings.xml')))


def _value(cell, strings):
    if cell is None:
        return None
    if cell.get('t') == 'inlineStr':
        return ''.join(t.text or '' for t in cell.iter(_q('t')))
    text = cell.findtext('s:v', namespaces=NS)
    if text is None:
        return None
    if cell.get('t') == 's':
        return ''.join(t.text or '' for t in strings[int(text)].iter(_q('t')))
    if cell.get('t') in ('str', 'e'):
        return text
    try:
        number = float(text)
        return int(number) if number.is_integer() else number
    except ValueError:
        return text


def _col(cell):
    return re.sub(r'\d', '', cell.get('r'))


def _norm(value):
    if value is None:
        return None
    try:
        return round(float(str(value).replace(',', '.')), 6)
    except ValueError:
        return str(value).strip().casefold()


def _regiones(value):
    tokens = set(re.findall(r'EN|EU|FCC|ISED', str(value).upper()))
    if 'EU' in tokens:
        tokens.add('EN')
    return tokens - {'EU'}


def _tecnologia(familia, values):
    name = str(values.get('J') or values.get('BT') or '')
    if not name:
        return None
    if familia == 'Conducted 2G-3G':
        if name in ('GPRS', 'EGPRS'):
            slot = values.get('X')
            return f'{name} {int(float(slot))}TX' if slot is not None else None
        return name
    if familia == 'Conducted BT-Custom':
        return 'BT' if name in ('Bluetooth', 'BT') else name
    return {'Conducted LTE': 'LTE', 'Conducted LTE CATM1': 'LTE CAT M1',
            'Conducted LTE NB-IoT': 'LTE NB-IoT', 'Conducted 5G': '5G',
            'Conducted WiFi': 'WLAN'}[familia]


@dataclass
class RegistroVista:
    record: object
    campos: dict
    labels: dict


def registros_vista(catalogo, datos):
    result = defaultdict(list)
    for record in catalogo.seleccionar(datos):
        variantes = getattr(catalogo, 'variantes_fuente', {}).get(record.source, [record.source])
        seen = set()
        for source in variantes:
            fields, labels = {}, {}
            for key, label, value in getattr(catalogo, 'campos_fuente', {}).get(source, []):
                if key is None and value is not None and str(value).strip().upper() not in ('','-','N/A','NA'):
                    fields[normalizar(label)] = value
                    labels[normalizar(label)] = label
            identity = tuple((k, str(v)) for k, v in fields.items())
            if identity not in seen:
                result[hoja_tecnologia(record.tech)].append(RegistroVista(record, fields, labels))
                seen.add(identity)
    return result


def _celda(row, col):
    return next((c for c in row if _col(c) == col), None)


def _poner(row, col, value):
    cell = _celda(row, col)
    if cell is None:
        reference=_celda(row,'K')
        attrs={'r':col+row.get('r')}
        if reference is not None and reference.get('s') is not None:attrs['s']=reference.get('s')
        cell = E.SubElement(row, _q('c'), **attrs)
    style, ref = cell.get('s'), cell.get('r')
    cell.clear()
    cell.set('r', ref)
    if style is not None:
        cell.set('s', style)
    if value is None:
        return
    if isinstance(value,bool):
        cell.set('t','b')
        E.SubElement(cell,_q('v')).text='1' if value else '0'
    elif isinstance(value, (int, float)):
        E.SubElement(cell, _q('v')).text = str(value)
    else:
        cell.set('t', 'inlineStr')
        text = E.SubElement(E.SubElement(cell, _q('is')), _q('t'))
        text.text = str(value)
        if str(value).strip() != str(value) or '\n' in str(value):
            text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def _inline(row, strings, shared):
    rownum = int(row.get('r'))
    for cell in row:
        if cell.get('t') == 's':
            value = cell.find('s:v', NS)
            si = strings[int(value.text)]
            cell.remove(value)
            cell.set('t', 'inlineStr')
            inline = E.SubElement(cell, _q('is'))
            for child in si:
                inline.append(deepcopy(child))
        formula = cell.find('s:f', NS)
        if formula is not None and formula.get('t') == 'shared':
            key = formula.get('si')
            if formula.text:
                shared[key] = (formula.text, rownum, col2n(_col(cell)))
            elif key in shared:
                text, oldrow, oldcol = shared[key]
                formula.text = shift_formula(text, rownum - oldrow, col2n(_col(cell)) - oldcol)
            else:
                raise ValueError('Fórmula compartida sin origen en el original: ' + cell.get('r'))
            formula.attrib.clear()


def _merges(root):
    result = []
    for merge in root.findall('s:mergeCells/s:mergeCell', NS):
        match = re.fullmatch(r'([A-Z]+)(\d+):([A-Z]+)(\d+)', merge.get('ref'))
        if match:
            a, r, b, s = match.groups()
            result.append((col2n(a), int(r), col2n(b), int(s)))
    return result


@dataclass
class PlanOriginal:
    familia: str
    nombre: str
    archivo: Path
    parte: str
    backend: bytes
    offset: int
    root: object
    spool: Path
    styles: dict
    strings: list
    rows: dict = field(default_factory=dict)
    count: int = 0
    covered: set = field(default_factory=set)
    references: set = field(default_factory=set)
    cache: dict = field(default_factory=dict)
    anchors: dict = field(default_factory=dict)
    merge_ranges: list = field(default_factory=list)
    alias: dict = field(default_factory=dict)
    fallback_rows: set = field(default_factory=set)
    extras: dict = field(default_factory=dict)
    segmentos: dict = field(default_factory=dict)
    view_rows: dict = field(default_factory=dict)
    registros: list = field(default_factory=list)
    mostrar: set = field(default_factory=set)
    referencias_rotas: int = 0
    grupos: dict = field(default_factory=dict)
    origen_grupos: dict = field(default_factory=dict)
    nuevos_grupos: set = field(default_factory=set)
    ranges_cache: dict = field(default_factory=dict)
    valores_rf: dict = field(default_factory=dict)

    def mapped(self, old, role='single'):
        if old in self.rows:
            valid=[r for r in self.rows[old] if r not in self.nuevos_grupos]
            return valid[-1 if role == 'end' else 0] if valid else None
        sorted_rows = self.sorted
        if role == 'start':
            at = bisect_left(sorted_rows, old)
            return self.rows[sorted_rows[at]][0] if at < len(sorted_rows) else None
        if role == 'end':
            at = bisect_right(sorted_rows, old) - 1
            return self.rows[sorted_rows[at]][-1] if at >= 0 else None
        return None

    def range_rows(self, start, end, contexto=None, incluir_nuevos=False):
        group=self.grupos.get(contexto) if contexto in self.nuevos_grupos and end>2 else None
        key=(start,end,group,incluir_nuevos)
        if key not in self.ranges_cache:
            keys=self.sorted[bisect_left(self.sorted,start):bisect_right(self.sorted,end)]
            values=[r for old in keys for r in self.rows[old]
                    if (self.grupos.get(r)==group if group is not None else incluir_nuevos or r not in self.nuevos_grupos)]
            self.ranges_cache[key]=(min(values),max(values)) if values else (None,None)
        return self.ranges_cache[key]


def coincidencias_especificas(indices, registros):
    """Un resumen RF no duplica una fila ya cubierta por su detalle.

    Solo se comparan coincidencias de la MISMA fila original: se conservan
    las repeticiones del procedimiento original y las variantes diferentes.
    """
    def campos(index):
        view = registros[index]
        values = {('param', k): _norm(v) for k, v in view.record.params.items() if v is not None}
        values.update({('extra', k): _norm(v) for k, v in view.campos.items() if v is not None})
        if view.record.notes:
            values['notes'] = view.record.notes
        return values
    fields = {i: campos(i) for i in indices}
    return [i for i in indices if not any(
        i != j and fields[i].items() < fields[j].items() for j in indices)]


def preparar(familia, nombre, backend, registros, datos, folder, dir_originales, estilos, avisos):
    inventario = json.loads((dir_originales / 'inventario.json').read_text(encoding='utf-8'))
    original_guardado = inventario['pestanas'].get(familia)
    if original_guardado is None:
        raise ValueError('No está guardada la pestaña original: ' + familia)
    archivo = dir_originales / original_guardado['archivo']
    if not archivo.exists():
        raise ValueError('Falta la copia completa del original: ' + str(archivo))
    with zipfile.ZipFile(archivo) as z:
        part = original_guardado['parte']
        root = _estructura(z, part)
        backend_root = E.fromstring(backend)
        offset = max(int(r.get('r')) for r in backend_root.findall('s:sheetData/s:row', NS)) + 4
        plan = PlanOriginal(familia, nombre, archivo, part, backend, offset, root,
                            folder / (FAMILIAS[familia] + '.filas'), estilos.incorporar(z.read('xl/styles.xml')), _strings(z))
        plan.segmentos = original_guardado.get('segmentos',{})
        plan.registros = registros
        for view in registros:
            r=view.record
            for group in (None,(r.tech,_norm(r.band))):
                values=plan.valores_rf.setdefault(group,{'T':set(),'U':set()})
                values['T'].add(_norm(r.channel));values['U'].add(_norm(r.frequency))
        plan.mostrar={'J','K','T','U'} | {PARAM_COL[k] for v in registros for k,val in v.record.params.items() if k in PARAM_COL and val is not None}
        if any(v.record.notes for v in registros):plan.mostrar.add('BO')
        native_merges = _merges(root)
        anchor_keys = {(a, r) for a, r, b, s in native_merges}
        spans = defaultdict(list)
        for a, r, b, s in native_merges:
            for col in range(a, b + 1):
                spans[n2col(col)].append((r, s, a, r))
        for values in spans.values():
            values.sort()
        span_starts = {c: [v[0] for v in values] for c, values in spans.items()}
        core = defaultdict(list)
        chosen_techs = set()
        for i, view in enumerate(registros):
            record = view.record
            core[(record.tech, _norm(record.band), _norm(record.channel), _norm(record.frequency))].append(i)
            chosen_techs.add(record.tech)
        shared, prototypes, headers = {}, {}, {}
        requested = set(datos['region'] if isinstance(datos['region'], list) else [datos['region']])
        header_columns = {}
        all_labels = {k: label for view in registros for k, label in view.labels.items()}
        filter_columns={'B','J','K','T','U','X','BT','BU','S','M'} | {PARAM_COL[k] for v in registros for k in v.record.params if k in PARAM_COL}

        def guardar(row, old, stream, fallback=False, view_id=None, grupo_origen=None):
            plan.count += 1
            new = plan.offset + plan.count
            plan.rows.setdefault(old, []).append(new)
            if fallback:
                plan.fallback_rows.add(new)
            if view_id is not None:
                plan.view_rows.setdefault(view_id,[]).append(new)
                record=registros[view_id].record
                plan.grupos[new]=(record.tech,_norm(record.band))
                plan.origen_grupos[old]=grupo_origen or plan.grupos[new]
                if fallback and plan.grupos[new]!=plan.origen_grupos[old]:plan.nuevos_grupos.add(new)
            for f in row.findall('s:c/s:f', NS):
                for piece in _STR.split(f.text or '')[::2]:
                    for match in _REF.finditer(piece):
                        plan.references.add((_sheetname(match[1]) or familia, match[3], int(match[5])))
                        if match[7]:
                            plan.references.add((_sheetname(match[1]) or familia, match[7], int(match[9])))
            pickle.dump((old, new, E.tostring(row)), stream, protocol=4)

        def ajustar(row, view, fallback):
            record = view.record
            native_band = _value(_celda(row,'K'), [])
            tech=record.tech
            match=re.fullmatch(r'(E?GPRS) [1-4]TX',tech)
            label=match[1] if match else {'LTE CAT M1':'LTE','BT':'Bluetooth'}.get(tech,tech)
            values = {'J':label,'K': record.band, 'T': record.channel, 'U': record.frequency}
            values.update({PARAM_COL[k]: v for k, v in record.params.items() if k in PARAM_COL})
            if familia == 'Conducted WiFi' and record.params.get('mode'):
                modo = re.fullmatch(r'(ac|ax|n|a|b|g)(\d+)?', record.params['mode'])
                if modo:
                    values['S'] = '802.11' + modo[1]
                    if modo[2] and 'bw' not in record.params:
                        values['M'] = int(modo[2])
            if record.notes:
                values['BO'] = record.notes
            for key, value in view.campos.items():
                values[header_columns.get(key, plan.extras.get(key))] = value
            if familia == 'Conducted BT-Custom':
                values.update(BW=record.band, BY=record.channel, BZ=record.frequency)
                if 'cert' in record.params:
                    values['BU'] = record.params['cert']
                if 'mode' in record.params:
                    values['BX'] = record.params['mode']
                if 'modulation' in record.params:
                    values['CA'] = record.params['modulation']
            if fallback:
                for c in row:
                    if col2n('AC') <= col2n(_col(c)) <= col2n('BH') and c.find('s:f', NS) is None:
                        _poner(row, _col(c), None)
                # Un registro que no existe en el original usa su formato;
                # no hereda parámetros RF de otra combinación o banda.
                for key,col in PARAM_COL.items():
                    current = _celda(row,col)
                    if col not in values and current is not None and current.find('s:f',NS) is None:
                        if key != 'cert' or _norm(native_band) != _norm(record.band):
                            values[col] = None
            changed_columns = set()
            for col, value in values.items():
                if col:
                    if _norm(_value(_celda(row, col), [])) != _norm(value):
                        changed_columns.add(col)
                    _poner(row, col, value)
            # Conservar cachés independientes de los datos modificados, como
            # MPR en O = IF(J="Cat M1",1,0). Invalidar solo sus dependientes.
            affected = set(changed_columns)
            if familia == 'Conducted LTE CATM1':
                # La etiqueta solicitada cambia respecto a la salida anterior:
                # conservar las fórmulas y recalcular sus resultados en Excel.
                affected.add('J')
            while True:
                more = set()
                for cell in row:
                    f = cell.find('s:f', NS)
                    if f is not None and any(m[3] in affected or m[7] in affected
                        for piece in _STR.split(f.text or '')[::2] for m in _REF.finditer(piece)):
                        more.add(_col(cell))
                if not more - affected:
                    break
                affected.update(more)
            for cell in row:
                if _col(cell) in affected and cell.find('s:f', NS) is not None:
                    value = cell.find('s:v', NS)
                    if value is not None:
                        cell.remove(value)
            row[:] = sorted(row, key=lambda c: col2n(_col(c)))

        partes = [part]
        if plan.segmentos:
            bandas = {_norm(view.record.band) for view in registros}
            partes += [segmento['parte'] for band,segmento in plan.segmentos.items() if _norm(band) in bandas]
            if any(not any(_norm(band)==b for band in plan.segmentos) for b in bandas):
                extra = next(iter(plan.segmentos.values()))['parte']
                if extra not in partes:partes.append(extra)
        with plan.spool.open('wb') as out:
            for row in _fuente(z,partes):
                old = int(row.get('r'))
                cells = {_col(c): c for c in row}
                # CAT M1 conserva casi un millón de filas de formato vacías.
                # No son registros RF ni contienen maestros de sus columnas.
                hay_rf = any(c is not None and (c.findtext('s:v',namespaces=NS) is not None or c.find('s:is',NS) is not None)
                             for c in (cells.get('T'),cells.get('U')))
                if old>2 and not hay_rf:
                    for cell in row:
                        f=cell.find('s:f',NS)
                        if f is not None and f.get('t')=='shared' and f.text:
                            shared[f.get('si')]=(f.text,old,col2n(_col(cell)))
                        key=(col2n(_col(cell)),old)
                        if key in anchor_keys:
                            anchor_row=E.Element(_q('row'),r=str(old));anchor_row.append(deepcopy(cell))
                            _inline(anchor_row,plan.strings,shared)
                            plan.anchors[key]=anchor_row[0]
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
                    continue
                columns=set(cells) if old<=2 else filter_columns
                values = {c: _value(cells.get(c), plan.strings) for c in columns}
                for col, spans_col in spans.items():
                    if old>2 and col not in filter_columns:continue
                    if values.get(col) is not None:
                        continue
                    at = bisect_right(span_starts[col], old) - 1
                    if at >= 0 and spans_col[at][1] >= old:
                        _, _, a, r = spans_col[at]
                        anchor = plan.anchors.get((a, r))
                        if anchor is not None:
                            values[col] = _value(anchor, plan.strings)
                # Registrar maestros compartidos aunque su fila no se seleccione.
                for cell in row:
                    formula = cell.find('s:f', NS)
                    if formula is not None and formula.get('t') == 'shared' and formula.text:
                        shared[formula.get('si')] = (formula.text, old, col2n(_col(cell)))
                    key = (col2n(_col(cell)), old)
                    if key in anchor_keys:
                        anchor_row = E.Element(_q('row'), r=str(old))
                        anchor_row.append(deepcopy(cell))
                        _inline(anchor_row, plan.strings, shared)
                        plan.anchors[key] = anchor_row[0]
                if old <= 2:
                    copied = deepcopy(row)
                    _inline(copied, plan.strings, shared)
                    headers[old] = copied
                    for col, val in values.items():
                        if isinstance(val, str):
                            header_columns.setdefault(normalizar(val), col)
                    if old == 2:
                        max_col = max(col2n(c) for c in cells)
                        for key, label in all_labels.items():
                            if key not in header_columns:
                                max_col += 1
                                plan.extras[key] = n2col(max_col)
                                _poner(headers[2], n2col(max_col), label)
                        plan.mostrar.update(header_columns[k] for k in all_labels if k in header_columns)
                        filter_columns.update(header_columns[k] for k in all_labels if k in header_columns)
                        for number in sorted(headers):
                            guardar(headers[number], number, out)
                else:
                    tech = _tecnologia(familia, values)
                    if tech in chosen_techs and values.get('K') is not None:
                        band = _norm(values['K'])
                        pkey = (tech, band)
                        if pkey not in prototypes:
                            copied = deepcopy(row)
                            _inline(copied, plan.strings, shared)
                            prototypes[pkey] = (old, copied)
                        key = (tech, band, _norm(values.get('T')), _norm(values.get('U')))
                        coincidencias = []
                        for i in core.get(key, []):
                            view, ok = registros[i], True
                            record = view.record
                            cert = _regiones(record.params.get('cert'))
                            source_cert = _regiones(values.get('B') or values.get('BU'))
                            if cert and not cert & requested or source_cert and not source_cert & requested:
                                continue
                            for param, val in record.params.items():
                                if param in PARAM_COL and param != 'cert' and val not in (None, '', '-', 'N/A'):
                                    actual = values.get(PARAM_COL[param])
                                    if param == 'mode' and familia == 'Conducted WiFi':
                                        actual = token_modo(str(actual), values.get('M')) if actual is not None else None
                                    if actual not in (None, '', 'TBD', 'N/A') and _norm(actual) != _norm(val):
                                        ok = False
                                        break
                            if ok:
                                for field, val in view.campos.items():
                                    actual = values.get(header_columns.get(field))
                                    if actual is not None and _norm(actual) != _norm(val):
                                        ok = False
                                        break
                            if ok:
                                coincidencias.append(i)
                        elegidas = coincidencias
                        if familia == 'Conducted LTE NB-IoT':
                            elegidas = coincidencias_especificas(coincidencias, registros)
                        for i in elegidas:
                            copied = deepcopy(row)
                            _inline(copied, plan.strings, shared)
                            ajustar(copied, registros[i], False)
                            guardar(copied, old, out, view_id=i)
                        plan.covered.update(coincidencias)
                row.clear()
                while row.getprevious() is not None:
                    del row.getparent()[0]
            for i, view in enumerate(registros):
                if i in plan.covered:
                    continue
                record = view.record
                if _regiones(record.params.get('cert')) and not _regiones(record.params['cert']) & requested:
                    continue
                proto = prototypes.get((record.tech, _norm(record.band)))
                if proto is None:
                    proto = next((p for (t, _), p in prototypes.items() if t == record.tech), None)
                if proto is None:
                    raise ValueError(f'El original no contiene un formato para {record.tech}.')
                old, copied = proto[0], deepcopy(proto[1])
                native_group=(record.tech,_norm(_value(_celda(copied,'K'),[])))
                ajustar(copied, view, True)
                guardar(copied, old, out, True, view_id=i, grupo_origen=native_group)
                plan.covered.add(i)
        _ordenar_filas(plan)
        plan.sorted = sorted(plan.rows)
        if plan.fallback_rows:
            avisos.append(f'{nombre}: {len(plan.fallback_rows)} registros nuevos o sin coincidencia exacta usan el formato de su tecnología, con los valores de la base.')
        _preparar_merges(plan, native_merges)
        return plan


def _ordenar_filas(plan):
    """Insertar los registros nuevos de una banda junto a su fila de formato.

    Las bandas completamente nuevas forman bloques separados al final, para
    que las fórmulas de un bloque original no incluyan otra banda por accidente.
    Solo se indexan posiciones del fichero temporal; no se cargan sus filas.
    """
    entries=[]
    foreign_order={}
    with plan.spool.open('rb') as stream:
        while True:
            pos=stream.tell()
            try:old,new,_=pickle.load(stream)
            except EOFError:break
            if new in plan.nuevos_grupos:
                group=plan.grupos[new]
                foreign_order.setdefault(group,len(foreign_order))
                key=(1,foreign_order[group],old,new)
            else:key=(0,0,old,new)
            entries.append((key,pos,new))
    entries.sort()
    candidate=plan.spool.with_suffix('.ordenadas')
    changed={}
    rows={}
    with plan.spool.open('rb') as src,candidate.open('wb') as dst:
        for index,(_,pos,previous) in enumerate(entries,1):
            src.seek(pos)
            old,_,raw=pickle.load(src)
            new=plan.offset+index
            changed[previous]=new
            rows.setdefault(old,[]).append(new)
            pickle.dump((old,new,raw),dst,protocol=4)
    candidate.replace(plan.spool)
    plan.rows=rows
    plan.grupos={changed[r]:g for r,g in plan.grupos.items()}
    plan.fallback_rows={changed[r] for r in plan.fallback_rows}
    plan.nuevos_grupos={changed[r] for r in plan.nuevos_grupos}
    plan.view_rows={v:[changed[r] for r in values] for v,values in plan.view_rows.items()}


def _preparar_merges(plan, native):
    for a, r, b, s in native:
        positions = sorted(new for old in plan.sorted[bisect_left(plan.sorted, r):bisect_right(plan.sorted, s)] for new in plan.rows[old]
                           if new not in plan.fallback_rows or r == s)
        runs = []
        for row in positions:
            if runs and row == runs[-1][-1] + 1:
                runs[-1].append(row)
            else:
                runs.append([row])
        for run in runs:
            if a == b and len(run) == 1:
                continue
            plan.merge_ranges.append((a, run[0], b, run[-1], (a, r)))
            plan.alias.setdefault((n2col(a), r), (n2col(a), run[0]))


def _filas(plan):
    with plan.spool.open('rb') as f:
        while True:
            try:
                yield pickle.load(f)
            except EOFError:
                break


def _fuente(z, partes):
    for parte in partes:
        with z.open(parte) as stream:
            for _,row in E.iterparse(stream,tag=_q('row')):
                yield row


def completar_cache(planes):
    por_nombre = {p.familia: p for p in planes}
    pending = defaultdict(set)
    for plan in planes:
        for sheet, col, row in plan.references:
            target = por_nombre.get(sheet)
            if target is not None and row not in target.rows and (col, row) not in target.alias:
                pending[sheet].add((col, row))
    for plan in planes:
        needed = pending[plan.familia]
        if not needed:
            continue
        needed_rows = {r for _, r in needed}
        partes=[plan.parte]
        if plan.segmentos:
            partes += [s['parte'] for s in plan.segmentos.values() if any(s['primera']<=r<=s['ultima'] for r in needed_rows)]
        with zipfile.ZipFile(plan.archivo) as z:
            for row in _fuente(z,partes):
                number = int(row.get('r'))
                if number in needed_rows:
                    for cell in row:
                        key = (_col(cell), number)
                        if key in needed:
                            plan.cache[key] = _value(cell, plan.strings)
                row.clear()
                while row.getprevious() is not None:
                    del row.getparent()[0]


def _literal(value):
    if value is None:
        return '""'
    if isinstance(value, (int, float)):
        return str(value)
    return '"' + str(value).replace('"', '""') + '"'


def formula(text, plan, old, new, planes, overview=None):
    """Reubicar también referencias absolutas; no alterar textos entre comillas."""
    def indirecta(m):
        target=planes.get(m[2])
        return m[1] + (target.nombre if target is not None else m[2]) + m[3]
    text=re.sub(r'(INDIRECT\(\s*"\x27)([^\x27]+)(\x27![^"]*")',indirecta,text,flags=re.I)
    def one(match):
        sheet = _sheetname(match[1]) or plan.familia
        target = planes.get(sheet)
        sh = match[1] or ''
        col, row = match[3], int(match[5])
        if target is None:
            if sheet in FAMILIAS:
                return '""'
            if sheet == 'Overview' and overview is not None:
                a = overview(row)
                b = overview(int(match[9])) if match[7] else None
                return f'{sh}{match[2]}{col}{match[4]}{a}' + (f':{match[6]}{match[7]}{match[8]}{b}' if b is not None else '')
            return match[0]
        if match[7]:
            a, b = target.range_rows(row,int(match[9]),new if target is plan else None)
            if a is None or b is None or a > b:
                return f'{_fmt_sheet(target.nombre)}{match[2]}{col}{match[4]}{target.offset - 1}'
            return f'{_fmt_sheet(target.nombre) if sh or target is not plan else ""}{match[2]}{col}{match[4]}{a}:{match[6]}{match[7]}{match[8]}{b}'
        alias = target.alias.get((col, row))
        if target is plan and new in plan.nuevos_grupos and row>2:
            possible=[r for r in target.rows.get(row,[]) if target.grupos.get(r)==target.grupos.get(new)]
            dest=new if row==old else possible[0] if possible else None
            if dest is None and col in set(PARAM_COL.values())|{'J','K','T','U','AH','CB','CC','CD','CE'}:
                return '""'
        else:
            dest = new if target is plan and row == old else alias[1] if alias else target.mapped(row)
        if dest is None:
            cached=target.cache.get((col,row))
            role=col if col in ('T','U') else None
            aliases=({'BX':'T','BY':'U'} if target.familia=='Conducted 2G-3G' else
                     {'BY':'T','BZ':'U'} if target.familia in ('Conducted WiFi','Conducted BT-Custom') else
                     {'CA':'T','CB':'U'})
            role=role or aliases.get(col)
            group=target.grupos.get(new) if target is plan else None
            if role and _norm(cached) not in target.valores_rf.get(group,target.valores_rf.get(None,{})).get(role,set()):
                return '""'
            return _literal(cached)
        return f'{_fmt_sheet(target.nombre) if sh or target is not plan else ""}{match[2]}{col}{match[4]}{dest}'
    parts = _STR.split(text)
    for i in range(0, len(parts), 2):
        parts[i] = _REF.sub(one, parts[i])
        if '#REF!' in parts[i]:
            plan.referencias_rotas+=1
            parts[i]=parts[i].replace('#REF!',f'{_fmt_sheet(plan.nombre)}$A${max(1,plan.offset-1)}')
    return ''.join(parts)


def _range(ref, plan):
    match = re.fullmatch(r'\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?', ref)
    if not match:
        return None
    a, r, b, s = match.groups()
    first,last=plan.range_rows(int(r),int(s or r),incluir_nuevos=True)
    if first is None or last is None or first > last:
        return None
    return f'{a}{first}:{b or a}{last}' if b or first != last else f'{a}{first}'


def escribir(plan, output, planes, overview=None):
    root = deepcopy(plan.root)
    data = root.find('s:sheetData', NS)
    data.clear()
    original_pr = E.fromstring(plan.backend).find('s:sheetPr', NS)
    pr = root.find('s:sheetPr', NS)
    if pr is not None and original_pr is not None and original_pr.get('codeName'):
        pr.set('codeName', original_pr.get('codeName'))
    dimension = root.find('s:dimension', NS)
    last = plan.offset + plan.count
    if dimension is not None:
        last_col = re.search(r'([A-Z]+)\d+$', dimension.get('ref'))[1]
        if plan.extras:
            last_col = max([last_col] + list(plan.extras.values()), key=col2n)
        dimension.set('ref', f'A1:{last_col}{last}')
    if plan.familia == 'Conducted WiFi':
        # Reconstruir la vista: ningún panel hereda las filas ocultas de apoyo
        # como parte inmovilizada de la tabla visible.
        views = root.find('s:sheetViews', NS)
        if views is None:
            views = E.Element(_q('sheetViews'))
            root.insert(next((i for i,n in enumerate(root) if E.QName(n).localname in ('sheetFormatPr','cols','sheetData')),len(root)),views)
        views.clear()
        view = E.SubElement(views, _q('sheetView'), workbookViewId='0', view='normal',
                            topLeftCell='A'+str(plan.offset+1), zoomScale='100')
        E.SubElement(view, _q('selection'), activeCell='B'+str(plan.offset+3), sqref='B'+str(plan.offset+3))
    else:
        for view in root.findall('s:sheetViews/s:sheetView', NS):
            view.set('topLeftCell', 'A' + str(plan.offset + 1))
            pane = view.find('s:pane', NS)
            if pane is not None:
                pane.set('ySplit', str(plan.offset + 2))
                pane.set('topLeftCell', 'A' + str(plan.offset + 3))
                pane.set('state', 'frozen')
            for selection in view.findall('s:selection', NS):
                selection.set('activeCell', 'A' + str(plan.offset + 3))
                selection.set('sqref', 'A' + str(plan.offset + 3))
    for element in list(root):
        tag = E.QName(element).localname
        if tag == 'mergeCells':
            root.remove(element)
        elif tag == 'autoFilter':
            ref = element.get('ref')
            start = re.match(r'([A-Z]+)\d+:([A-Z]+)\d+', ref)
            if start:
                end = max([start[2]] + list(plan.extras.values()), key=col2n)
                element.set('ref', f'{start[1]}{plan.offset+2}:{end}{last}')
        elif tag in ('conditionalFormatting','dataValidations','hyperlinks','ignoredErrors','rowBreaks','extLst'):
            if tag in ('ignoredErrors','rowBreaks','extLst'):
                root.remove(element)
                continue
            nodes = list(element) if tag in ('dataValidations','hyperlinks') else [element]
            for node in nodes:
                attr = 'sqref' if tag != 'hyperlinks' else 'ref'
                refs = [_range(r, plan) for r in node.get(attr, '').split()]
                refs = [r for r in refs if r]
                if not refs:
                    if node is element:
                        root.remove(element)
                    else:
                        element.remove(node)
                    continue
                node.set(attr, ' '.join(refs))
                for f in node.iter():
                    if E.QName(f).localname in ('formula','formula1','formula2') and f.text and not f.text.startswith('"'):
                        f.text = formula(f.text, plan, 2, plan.offset+2, planes, overview)
                    if f.get('dxfId') is not None:
                        f.set('dxfId', str(int(f.get('dxfId')) + plan.styles['dxfs']))
            if tag in ('dataValidations','hyperlinks'):
                if not len(element):
                    root.remove(element)
                elif tag == 'dataValidations':
                    element.set('count', str(len(element)))
    if plan.merge_ranges:
        merges = E.Element(_q('mergeCells'), count=str(len(plan.merge_ranges)))
        for a, r, b, s, _ in plan.merge_ranges:
            E.SubElement(merges, _q('mergeCell'), ref=f'{n2col(a)}{r}:{n2col(b)}{s}')
        index = next((i for i, n in enumerate(root) if E.QName(n).localname in ('phoneticPr','conditionalFormatting','dataValidations','hyperlinks','printOptions','pageMargins','pageSetup','headerFooter','drawing','legacyDrawing')), len(root))
        root.insert(index, merges)
    for col in root.findall('s:cols/s:col', NS):
        if col.get('style') is not None:
            col.set('style', str(int(col.get('style')) + plan.styles['cellXfs']))
    cols = root.find('s:cols', NS)
    if cols is not None:
        for extra in sorted(set(plan.extras.values()) | plan.mostrar, key=col2n):
            index = col2n(extra)
            attributes=None
            for col in list(cols):
                start, end = int(col.get('min')), int(col.get('max'))
                if start <= index <= end:
                    attributes=dict(col.attrib)
                    at = list(cols).index(col)
                    cols.remove(col)
                    if start < index:
                        before = deepcopy(col);before.set('max',str(index-1));cols.insert(at,before);at+=1
                    if index < end:
                        after = deepcopy(col);after.set('min',str(index+1));cols.insert(at,after)
            attributes=attributes or dict(width='25',customWidth='1')
            attributes.update(min=str(index),max=str(index))
            attributes.pop('hidden',None)
            if extra in plan.extras.values():attributes.update(width='25',customWidth='1')
            E.SubElement(cols,_q('col'),**attributes)
        cols[:] = sorted(cols,key=lambda c:int(c.get('min')))
    backend = E.fromstring(plan.backend).find('s:sheetData', NS)
    merge_starts = defaultdict(list)
    for merge in plan.merge_ranges:
        merge_starts[merge[1]].append(merge)
    active_merges = []
    with E.xmlfile(str(output), encoding='UTF-8') as writer:
        writer.write_declaration(standalone=True)
        with writer.element(root.tag, dict(root.attrib), nsmap=root.nsmap):
            for element in root:
                if element.tag != _q('sheetData'):
                    writer.write(element)
                    continue
                with writer.element(_q('sheetData')):
                    last_backend = 0
                    for row in backend:
                        if plan.familia == 'Conducted 2G-3G':
                            normalizar_fechas(row)
                        row.set('hidden', '1')
                        last_backend = int(row.get('r'))
                        writer.write(row)
                    for number in range(last_backend + 1, plan.offset + 1):
                        writer.write(E.Element(_q('row'), r=str(number), hidden='1'))
                    for old, new, raw in _filas(plan):
                        active_merges = [m for m in active_merges if m[3] >= new] + merge_starts[new]
                        row = E.fromstring(raw)
                        row.set('r', str(new))
                        row.attrib.pop('spans', None)
                        if row.get('s') is not None:
                            row.set('s', str(int(row.get('s')) + plan.styles['cellXfs']))
                        for a, r, b, s, anchor in merge_starts[new]:
                            if r == new and anchor in plan.anchors:
                                current = _celda(row, n2col(a))
                                if current is None or not len(current):
                                    cell = deepcopy(plan.anchors[anchor])
                                    cell.set('r', n2col(a) + str(old))
                                    if current is not None:
                                        row.remove(current)
                                    row.append(cell)
                        for cell in row:
                            col = _col(cell)
                            cell.set('r', col + str(new))
                            if cell.get('s') is not None:
                                cell.set('s', str(int(cell.get('s')) + plan.styles['cellXfs']))
                            for a, r, b, s, anchor in active_merges:
                                if r <= new <= s and a <= col2n(col) <= b and (new != r or col2n(col) != a):
                                    for child in list(cell):
                                        cell.remove(child)
                                    cell.attrib.pop('t', None)
                                    break
                            f = cell.find('s:f', NS)
                            if f is not None and f.text:
                                broken=any('#REF!' in piece for piece in _STR.split(f.text)[::2])
                                f.text = formula(f.text, plan, old, new, planes, overview)
                                if broken:
                                    cached=cell.find('s:v',NS)
                                    if cached is not None:cell.remove(cached)
                                    cell.attrib.pop('t',None)
                                if f.get('ref'):
                                    newref = _range(f.get('ref'), plan)
                                    if newref:
                                        f.set('ref', newref)
                                    else:
                                        f.attrib.clear()
                        row[:] = sorted(row, key=lambda c: col2n(_col(c)))
                        if plan.familia == 'Conducted 2G-3G':
                            normalizar_fechas(row)
                        writer.write(row)
    return root


def verificar_apoyo(plan, rendered):
    """Impedir que la vista nueva cambie las entradas del SAR aprobado."""
    original = E.fromstring(plan.backend).find('s:sheetData', NS)
    if plan.familia == 'Conducted 2G-3G':
        normalizar_fechas(original)
    expected = {c.get('r'): E.tostring(c, method='c14n', exclusive=True)
                for row in original for c in row}
    found = {}
    with Path(rendered).open('rb') as stream:
        for _, row in E.iterparse(stream, tag=_q('row')):
            if int(row.get('r')) > plan.offset:
                break
            for cell in row:
                found[cell.get('r')] = E.tostring(cell, method='c14n', exclusive=True)
            row.clear()
            while row.getprevious() is not None:
                del row.getparent()[0]
    if expected != found:
        raise ValueError(f'{plan.nombre}: la presentación ha cambiado las celdas de apoyo de SAR.')


def reubicar_dibujo(root, plan):
    """Trasladar cada captura entera: sus dos extremos conservan la distancia.

    Reubicar por separado los extremos podía invertir un dibujo cuando uno
    caía en una fila descartada y el otro en una fila seleccionada.
    """
    d = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
    for anchor in root:
        markers = [anchor.find('{' + d + '}' + tag) for tag in ('from', 'to')]
        rows = [marker.find('{' + d + '}row') for marker in markers if marker is not None]
        rows = [row for row in rows if row is not None]
        if not rows:
            continue
        old = int(rows[0].text) + 1
        new = plan.mapped(old, 'start') or plan.mapped(old, 'end') or plan.offset + old
        delta = new - old
        for row in rows:
            row.text = str(int(row.text) + delta)


def copiar_relacionados(plan, destino_parte, changed, added, ct):
    """Copiar los dibujos, comentarios, controles e imágenes propios del original."""
    prefix = 'xl/original_vista/' + Path(FAMILIAS.get(plan.familia,normalizar(plan.familia)+'.zip')).stem + '/'
    visited = {}
    with zipfile.ZipFile(plan.archivo) as z:
        source_ct = E.fromstring(z.read('[Content_Types].xml'))
        overrides = {c.get('PartName').lstrip('/'): c.get('ContentType') for c in source_ct if c.get('PartName')}
        defaults = {c.get('Extension'): c.get('ContentType') for c in source_ct if c.get('Extension')}
        def relacionar(src, dst):
            relpart = _relpart(src)
            if relpart not in z.namelist():
                return
            rels = E.fromstring(z.read(relpart))
            for rel in rels:
                if rel.get('TargetMode') == 'External':
                    continue
                target = _target(src, rel.get('Target'))
                newtarget = prefix + target
                rel.set('Target', posixpath.relpath(newtarget, posixpath.dirname(dst)))
                if target in visited:
                    continue
                visited[target] = newtarget
                content = z.read(target)
                if rel.get('Type', '').endswith('/comments'):
                    root = E.fromstring(content)
                    for comment in list(root.find('s:commentList', NS)):
                        match = re.fullmatch(r'([A-Z]+)(\d+)', comment.get('ref'))
                        new = plan.mapped(int(match[2]))
                        if new is None:
                            comment.getparent().remove(comment)
                        else:
                            comment.set('ref', match[1] + str(new))
                    content = _xml(root)
                elif target.endswith('.vml'):
                    root = E.fromstring(content)
                    x = 'urn:schemas-microsoft-com:office:excel'
                    for data in root.findall('.//{' + x + '}ClientData'):
                        row = data.find('{' + x + '}Row')
                        if data.get('ObjectType') == 'Note' and row is not None:
                            new = plan.mapped(int(row.text) + 1)
                            if new is None:
                                shape = data.getparent()
                                shape.getparent().remove(shape)
                                continue
                            row.text = str(new - 1)
                        anchor = data.find('{' + x + '}Anchor')
                        if anchor is not None and anchor.text:
                            vals = [int(v.strip()) for v in anchor.text.split(',')]
                            if len(vals) == 8:
                                for index in (2, 6):
                                    vals[index] = (plan.mapped(vals[index]+1) or plan.offset+vals[index]+1) - 1
                                anchor.text = ', '.join(map(str, vals))
                    content = _xml(root)
                elif rel.get('Type', '').endswith('/drawing'):
                    root = E.fromstring(content)
                    reubicar_dibujo(root, plan)
                    content = _xml(root)
                added[newtarget] = content
                if target in overrides:
                    E.SubElement(ct, '{' + C + '}Override', PartName='/' + newtarget, ContentType=overrides[target])
                else:
                    ext = target.rsplit('.', 1)[-1]
                    if not any(n.get('Extension') == ext for n in ct) and ext in defaults:
                        entry = E.Element('{' + C + '}Default', Extension=ext, ContentType=defaults[ext])
                        ct.insert(next((i for i, n in enumerate(ct) if n.get('PartName')), len(ct)), entry)
                relacionar(target, newtarget)
            part = _relpart(dst)
            (changed if dst == destino_parte and destino_parte not in added else added)[part] = _xml(rels)
        relacionar(plan.parte, destino_parte)


def copiar_estatica(nombre, info, carpeta, estilos, planes, overview=None):
    """Conservar también las pestañas auxiliares del original que no son RF."""
    archivo=carpeta/info['archivo']
    with zipfile.ZipFile(archivo) as z:
        raw=z.read(info['parte'])
        root=E.fromstring(raw)
        strings=_strings(z)
        offsets=estilos.incorporar(z.read('xl/styles.xml'))
        plan=PlanOriginal(nombre,nombre,archivo,info['parte'],raw,0,root,Path(),offsets,strings)
        rows=root.findall('s:sheetData/s:row',NS)
        plan.rows={int(r.get('r')):[int(r.get('r'))] for r in rows}
        plan.sorted=sorted(plan.rows)
        shared={}
        for row in rows:
            old=int(row.get('r'))
            _inline(row,strings,shared)
            if row.get('s') is not None:row.set('s',str(int(row.get('s'))+offsets['cellXfs']))
            for cell in row:
                if cell.get('s') is not None:cell.set('s',str(int(cell.get('s'))+offsets['cellXfs']))
                f=cell.find('s:f',NS)
                if f is not None and f.text:f.text=formula(f.text,plan,old,old,planes,overview)
        for col in root.findall('s:cols/s:col',NS):
            if col.get('style') is not None:col.set('style',str(int(col.get('style'))+offsets['cellXfs']))
        for node in root.iter():
            if node.get('dxfId') is not None:node.set('dxfId',str(int(node.get('dxfId'))+offsets['dxfs']))
        wb=E.fromstring(z.read('xl/workbook.xml'))
        original_sheet=next(s for s in wb.find('s:sheets',NS) if s.get('name')==nombre)
        estado=original_sheet.get('state','visible')
        return plan,_xml(root),estado
