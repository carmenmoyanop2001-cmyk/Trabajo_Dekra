"""Sustituir solo los SAR por la base main12 conservada en el historial.

La sustitución se hace después de generar la entrega actual. Así no puede
alterar las tecnologías, Overview, Tune-Up ni las demás hojas aprobadas.
"""
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import json
import os
import re
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as E

from nucleo import Contexto, Hoja, iter_hoja
from hojas_base_datos import construir, hoja_tecnologia, indice_tune_up, restaurar_modos_dinamicos
from presentacion_sar_en import combinar_mode
from sar_version12_motor import _sar
from sar_version12_canales import aplicar as canales_version12

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'s': M}
SAR = ('SAR EN', 'SAR FCC-ISED')
VERSION = '6f1ca2ba79e315d2fabfb025076e34fbfd22aa16'


def _pestanas(z):
    from posixpath import normpath
    rels = {r.get('Id'): r.get('Target')
            for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    wb = E.fromstring(z.read('xl/workbook.xml'))
    return {s.get('name'): (t.lstrip('/') if t.startswith('/') else normpath('xl/' + t))
            for s in wb.find('s:sheets', NS)
            for t in [rels[s.get('{' + R + '}id')]]}


def _xml(root):
    return E.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)


def _estilos(actual, donante):
    """Reutilizar o añadir estilos sin cambiar índices/definiciones existentes."""
    root, source = E.fromstring(actual), E.fromstring(donante)
    maps = {}
    key = lambda n: E.tostring(n, method='c14n', exclusive=True)
    original = {g.tag: [key(n) for n in g] for g in root}
    formats = root.find('s:numFmts', NS)
    fmtmap = {}
    known = {n.get('formatCode'): n.get('numFmtId') for n in formats}
    next_id = max([163] + [int(n.get('numFmtId')) for n in formats]) + 1
    for node in source.find('s:numFmts', NS):
        code = node.get('formatCode')
        if code not in known:
            copied = deepcopy(node)
            copied.set('numFmtId', str(next_id))
            formats.append(copied)
            known[code] = str(next_id)
            next_id += 1
        fmtmap[node.get('numFmtId')] = known[code]
    formats.set('count', str(len(formats)))
    for tag in ('fonts', 'fills', 'borders', 'cellStyleXfs', 'cellXfs', 'dxfs'):
        target = root.find('s:' + tag, NS)
        known = {key(n): i for i, n in enumerate(target)}
        mapping = maps[tag] = {}
        for i, node in enumerate(source.find('s:' + tag, NS)):
            copied = deepcopy(node)
            for item in copied.iter():
                for attr, group in (('fontId', 'fonts'), ('fillId', 'fills'),
                                    ('borderId', 'borders'), ('xfId', 'cellStyleXfs')):
                    if attr in item.attrib:
                        item.set(attr, str(maps[group][int(item.get(attr))]))
                if item.get('numFmtId') in fmtmap:
                    item.set('numFmtId', fmtmap[item.get('numFmtId')])
            identity = key(copied)
            if i < len(target) and key(target[i]) == identity:
                mapping[i] = i
                continue
            if identity not in known:
                known[identity] = len(target)
                target.append(copied)
            mapping[i] = known[identity]
        target.set('count', str(len(target)))
    for group in root:
        for before, after in zip(original[group.tag], group):
            if before != key(after):
                raise ValueError('La restauración SAR intentó cambiar un estilo existente.')
    return _xml(root), maps


def _crear(dato, catalogo, plantilla, carpeta, nombres):
    """Emitir únicamente los SAR; las tablas RF solo aportan sus coordenadas."""
    from generador_excel import ARCHIVOS, _hacer_inline
    from overview import BAT_LIBRES, FILA_CORTE
    cache = {}

    def source(name):
        if name not in cache:
            cache[name] = Hoja(str(plantilla / 'formatos' / ARCHIVOS[name]))
        return cache[name]

    with ZipFile(plantilla / 'plantilla_base.zip') as base:
        # seleccionar() depende de tecnologías/bandas/modos, no de región.
        # Se omite la construcción SAR actual, sin modificarla ni ejecutarla.
        hojas, planes, records, warnings = construir(catalogo, dict(dato, region=[]), source, base)
        groups = defaultdict(lambda: defaultdict(list))
        for record in records:
            groups[hoja_tecnologia(record.tech)][(record.tech, record.band)].append(record)
        ranges = {}
        for name, bands in groups.items():
            row = 3
            for band, items in bands.items():
                ranges[band] = [name, row, row + len(items) - 1]
                row += len(items)
        tune = indice_tune_up(base)
        for name in nombres:
            hojas[name], planes[name] = _sar(source(name), records, dato, ranges, warnings, tune,
                source('SAR FCC-ISED') if name == 'SAR EN' else None)
        ctx = Contexto()
        ctx.whole = {'Overview', 'Tune-Up', 'Validations', 'Test Campaign', 'Pretesting-Others'}
        extra = max(0, len(dato['baterias']) - BAT_LIBRES)
        ctx.ov_map = lambda row: row + extra if row >= FILA_CORTE else row
        for name, plan in planes.items():
            ctx.set_rows(name, {hojas[name].rows[it.i][0]: i for i, it in enumerate(plan, 3)
                               if not it.clone})
        resolve = ctx.resolver()
        styles = base.read('xl/styles.xml')
        if 'SAR EN' in nombres:
            styles = combinar_mode(hojas['SAR EN'], planes['SAR EN'], ctx, styles)
            restaurar_modos_dinamicos(hojas['SAR EN'], planes['SAR EN'], ctx, resolve)
        ctx.inline = _hacer_inline(hojas, resolve, ctx.column_aliases, ctx.cell_anchors)
        ctx.blank = lambda name: len(planes[name]) + 5 if name in planes else None
        changes = {name: ''.join(iter_hoja(hojas[name], planes[name], ctx, resolve)).encode('utf8')
                   for name in nombres}
        # El adaptador histórico de CC/CD actúa solo sobre SAR EN.
        scratch = carpeta / 'sar12.xlsm'
        with ZipFile(scratch, 'w', ZIP_DEFLATED) as z:
            z.writestr('xl/workbook.xml', base.read('xl/workbook.xml'))
            z.writestr('xl/_rels/workbook.xml.rels', base.read('xl/_rels/workbook.xml.rels'))
            man = json.loads(base.read('manifest.json'))
            parts = {name: 'xl/worksheets/sheet' + str(number) + '.xml'
                     for number, name in man['grandes'].items() if name in nombres}
            for name, xml in changes.items():
                z.writestr(parts[name], xml)
        count = canales_version12(scratch, plantilla) if 'SAR EN' in nombres else 0
        with ZipFile(scratch) as z:
            changes = {name: z.read(parts[name]) for name in nombres}
    return changes, styles, {name: len(planes[name]) for name in nombres}, count


def aplicar(path, datos, catalogo, plantilla, resumen):
    """La única escritura permitida afecta SAR, sus filtros y estilos añadidos."""
    path, plantilla = Path(path), Path(plantilla)
    with ZipFile(path) as z:
        parts = _pestanas(z)
        nombres = [name for name in SAR if name in parts]
    if not nombres:
        return
    with tempfile.TemporaryDirectory(prefix='sar_version12_') as tmp:
        folder = Path(tmp)
        donor, donor_styles, counts, formulas = _crear(datos, catalogo, plantilla, folder, nombres)
        with ZipFile(path) as src:
            styles, maps = _estilos(src.read('xl/styles.xml'), donor_styles)
            changes = {'xl/styles.xml': styles}
            wb = src.read('xl/workbook.xml').decode('utf8')
            for name, xml in donor.items():
                root = E.fromstring(xml)
                # Mantener la visibilidad aprobada en la última entrega.
                current = E.fromstring(src.read(parts[name]))
                old_cols, new_cols = current.find('s:cols', NS), root.find('s:cols', NS)
                if new_cols is not None and old_cols is not None:
                    root.replace(new_cols, deepcopy(old_cols))
                for node in root.iter():
                    local = E.QName(node).localname
                    for attr, group in (('s', 'cellXfs'), ('style', 'cellXfs'), ('dxfId', 'dxfs')):
                        if attr in node.attrib and local != 'col':
                            node.set(attr, str(maps[group][int(node.get(attr))]))
                xml = _xml(root)
                if not datos['conducida']:
                    for original in groups_rf(datos):
                        xml = xml.replace(("'" + original + "'!").encode(),
                                          ("'" + original.removeprefix('Conducted ') + "'!").encode())
                changes[parts[name]] = xml
                # Solo cambia la extensión del filtro de esa misma pestaña.
                auto = root.find('s:autoFilter', NS)
                if auto is not None:
                    ref = re.sub(r'([A-Z]+)(\d+)', r'$\1$\2', auto.get('ref'))
                    pattern = r'(<definedName\b[^>]*name="_xlnm\._FilterDatabase"[^>]*>\s*\'' + re.escape(name) + r"'!)[^<]+"
                    wb = re.sub(pattern, lambda m: m[1] + ref, wb)
            changes['xl/workbook.xml'] = wb.encode('utf8')
            destination = path.with_name('sar_version12_final.xlsm')
            with ZipFile(destination, 'w', ZIP_DEFLATED) as out:
                for info in src.infolist():
                    out.writestr(deepcopy(info), changes.get(info.filename, src.read(info.filename)))
            with ZipFile(destination) as result:
                for info in src.infolist():
                    if info.filename not in changes and src.read(info.filename) != result.read(info.filename):
                        raise ValueError('Se intentó modificar una parte ajena a SAR: ' + info.filename)
        os.replace(destination, path)
    resumen['filas'].update(counts)
    resumen['formulas_cc_cd_en'] = formulas
    resumen['formulas_cc_cd_fcc'] = 0
    resumen['enlaces_cc_cd_originales'] = {name: 0 for name in nombres}
    resumen['sar_version12'] = {'base': VERSION, 'pestanas': nombres,
                               'resto_del_paquete_identico': True}


def groups_rf(datos):
    """Nombres internos estables, también cuando la pestaña visible dice 2G/3G."""
    from seleccion import hojas_conducted_necesarias
    return hojas_conducted_necesarias(datos['tecnologias'])
