# -*- coding: utf-8 -*-
"""Generador del Excel de toma de datos SAR (.xlsm) a partir de las respuestas del cuestionario.

No necesita el datasheet original: lleva dentro (carpeta `plantilla/`) las fórmulas, estilos, macros y
la estructura de filas extraídas del datasheet FAN22_09.
"""
import os, re, json, zipfile, sys
from pathlib import Path
import tempfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nucleo import Hoja, Contexto, iter_hoja, HEADER_ROWS
from sarlib import col2n, expand, _REF, _STR
from seleccion import (plan_conducted, plan_sar, referencias, hojas_conducted_necesarias)
from overview import editar_overview
from validacion_datos import validar_datos
from opciones_ensayo import seleccion_multiple
from nombres_hojas import renombrar_tecnologias, renombrar_resumen
from sar_en_formulas import aplicar_formulas_extras
from presentacion_sar_en import combinar_mode
from sarlib import remap_columns, remap_cells

DIR_PLANTILLA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plantilla')
ARCHIVOS = {
    'Conducted 2G-3G': 'cond_2g3g.xz', 'Conducted LTE': 'cond_lte.xz', 'Conducted LTE CATM1': 'cond_catm1.xz',
    'Conducted LTE NB-IoT': 'cond_nbiot.xz', 'Conducted 5G': 'cond_5g.xz', 'Conducted WiFi': 'cond_wifi.xz',
    'Conducted BT-Custom': 'cond_bt.xz', 'SAR EN': 'sar_en.xz', 'SAR FCC-ISED': 'sar_fcc.xz'}
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def _numero_hoja(manifest, nombre):
    for d in ('full', 'grandes'):
        for n, nm in manifest[d].items():
            if nm == nombre:
                return int(n)
    raise KeyError(nombre)


def generar(datos, salida, dir_plantilla=None, log=print):
    """Valida y genera sin reemplazar la salida hasta comprobar el paquete."""
    from herramientas.validar_paquete import validar
    validar_datos(datos)
    target = Path(salida)
    if target.suffix.lower() != '.xlsm':
        raise ValueError('La salida debe tener extensión .xlsm.')
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        candidate = Path(tmp) / 'datos.xlsm'
        resumen = _generar(datos, str(candidate), dir_plantilla, log)
        if not datos['conducida']:
            names = {s: s.removeprefix('Conducted ') for s in resumen['hojas'] if s.startswith('Conducted ')}
            if names:
                renombrar_tecnologias(candidate, names)
                renombrar_resumen(resumen, names)
        errors = validar(str(candidate), verbose=False)
        if errors:
            raise ValueError('El Excel no supera la validación: ' + '; '.join(errors))
        _validar_hojas_sar(candidate, datos['region'])
        os.replace(candidate, target)
    log(f'Excel validado: {target}')
    return resumen


def _hojas_sar(regiones):
    regions = seleccion_multiple(regiones)
    return (['SAR EN'] if 'EN' in regions else []) + (
        ['SAR FCC-ISED'] if any(r in regions for r in ('FCC', 'ISED')) else [])


def _validar_hojas_sar(path, regiones):
    """Verificar el libro emitido, no solo el plan o el mensaje de éxito."""
    from lxml import etree
    from posixpath import normpath
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    expected = set(_hojas_sar(regiones))
    with zipfile.ZipFile(path) as z:
        wb = etree.fromstring(z.read('xl/workbook.xml'))
        sheets = {s.get('name'): s for s in wb.findall('s:sheets/s:sheet', ns)}
        actual = set(sheets) & {'SAR EN', 'SAR FCC-ISED'}
        if actual != expected:
            raise ValueError('Las hojas SAR del Excel no corresponden a las regiones seleccionadas. '
                             f'Esperadas: {sorted(expected)}; encontradas: {sorted(actual)}.')
        rels = {r.get('Id'): r.get('Target') for r in etree.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for name in expected:
            sheet = sheets[name]
            if sheet.get('state', 'visible') != 'visible':
                raise ValueError(f'La hoja solicitada {name} ha quedado oculta.')
            target = rels[sheet.get('{' + NS_REL + '}id')]
            part = normpath('xl/' + target) if not target.startswith('/') else target.lstrip('/')
            found = False
            with z.open(part) as data:
                for _, row in etree.iterparse(data, tag='{' + ns['s'] + '}row'):
                    if int(row.get('r')) > 2 and any(c.get('r', '').startswith('BT') and len(c) for c in row):
                        found = True
                        break
                    row.clear()
                    while row.getprevious() is not None:
                        del row.getparent()[0]
            if not found:
                raise ValueError(f'La hoja solicitada {name} ha quedado sin filas de ensayo.')


def _generar(datos, salida, dir_plantilla=None, log=print):
    """datos: dict (ver README). Escribe el .xlsm en `salida` y devuelve un resumen (dict)."""
    dirp = dir_plantilla or DIR_PLANTILLA
    base = zipfile.ZipFile(os.path.join(dirp, 'plantilla_base.zip'))
    man = json.loads(base.read('manifest.json'))
    t = datos['tecnologias']
    conducida = bool(datos['conducida'])
    regions = seleccion_multiple(datos['region'])
    sar_names = _hojas_sar(regions)

    # ---- 1) qué hojas habrá ----
    conds = hojas_conducted_necesarias(t)
    # Las hojas seleccionadas son también plantillas de toma de datos cuando
    # no se prevén conducidos. Tune-Up conserva sus enlaces y límites originales.
    orden = ['Overview'] + (['Tune-Up'] if conds else []) + conds + sar_names + ['Test Campaign']
    orden.sort(key=lambda n: _numero_hoja(man, n))
    log('Hojas: ' + ', '.join(orden))

    # ---- 2) planes de filas ----
    hojas, planes, refs = {}, {}, {}
    for sar_name in sar_names:
        hojas[sar_name] = Hoja(os.path.join(dirp, ARCHIVOS[sar_name]))
        planes[sar_name] = plan_sar(hojas[sar_name], 'EN' if sar_name == 'SAR EN' else 'FCC', datos)
        if not planes[sar_name]:
            raise ValueError(f'La plantilla original de {sar_name} no contiene filas para la selección de '
                             f'tecnología, banda y exposición: {datos["tecnologias"]}; {datos["exposure"]}. '
                             'No se ha guardado un Excel con una hoja SAR vacía.')
        family = 'EN' if sar_name == 'SAR EN' else 'FCC'
        for sheet, rows in referencias(hojas[sar_name], planes[sar_name]).items():
            refs.setdefault(sheet, {}).setdefault(family, set()).update(rows)
    for c in conds:
        hojas[c] = Hoja(os.path.join(dirp, ARCHIVOS[c]))
        planes[c] = plan_conducted(hojas[c], datos, refs.get(c))

    ctx = Contexto()
    ctx.whole = {'Overview', 'Test Campaign'} | ({'Tune-Up'} if conds else set())
    for name, plan in planes.items():
        h = hojas[name]
        ctx.set_rows(name, {h.rows[it.i][0]: HEADER_ROWS + 1 + k for k, it in enumerate(plan) if not it.clone})

    # ---- 3) Overview ----
    ov_num = _numero_hoja(man, 'Overview')
    ov_xml = base.read(f'xl/worksheets/sheet{ov_num}.xml')
    d_part = next((p for p in man['owned'][str(ov_num)] if p.endswith('drawing1.xml')), None)
    v_part = next((p for p in man['owned'][str(ov_num)] if p.endswith('vmlDrawing1.vml')), None)
    ov_xml, drawing, vml, ctx.ov_map = editar_overview(
        ov_xml, base.read(d_part).decode('utf8') if d_part else None,
        base.read(v_part).decode('utf8', 'ignore') if v_part else None, datos)
    modificadas = {}
    if d_part: modificadas[d_part] = drawing.encode('utf8') if isinstance(drawing, str) else drawing
    if v_part: modificadas[v_part] = vml.encode('utf8') if isinstance(vml, str) else vml

    resolve = ctx.resolver()
    if 'SAR EN' in hojas and any(item.extra for item in planes['SAR EN']):
        fcc = hojas.get('SAR FCC-ISED') or Hoja(os.path.join(dirp, ARCHIVOS['SAR FCC-ISED']))
        aplicar_formulas_extras(hojas['SAR EN'], planes['SAR EN'], fcc, ctx.rowmap['SAR EN'])
    if 'SAR EN' in hojas:
        modificadas['xl/styles.xml'] = combinar_mode(hojas['SAR EN'], planes['SAR EN'], ctx,
                                                      base.read('xl/styles.xml'))
    ctx.inline = _hacer_inline(hojas, resolve, ctx.column_aliases, ctx.cell_anchors)
    ctx.blank = lambda sh: (HEADER_ROWS + len(planes[sh]) + 3) if sh in planes else None
    resumen = {'hojas': orden, 'filas': {}, 'sin_resolver': ctx.unresolved}

    # ---- 4) escribir el paquete ----
    nums = {n: _numero_hoja(man, n) for n in orden}
    partes_hoja = {n: [] for n in orden}
    for n in orden:
        partes_hoja[n] = man['owned'][str(nums[n])]
    escritas = set()
    filtros = {}
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zo:
        previstas = {p for p in man['global_parts'] if p not in ('xl/workbook.xml', 'xl/_rels/workbook.xml.rels')}
        previstas |= {'xl/workbook.xml', 'xl/_rels/workbook.xml.rels', 'docProps/app.xml'}
        for n in orden:
            previstas.add(f'xl/worksheets/sheet{nums[n]}.xml')
            previstas |= set(partes_hoja[n])
        ov = man['overrides']
        items = ''.join(f'<Default Extension="{e}" ContentType="{c}"/>' for e, c in man['defaults'].items())
        items += ''.join(f'<Override PartName="{p}" ContentType="{c}"/>' for p, c in ov.items()
                         if p.lstrip('/') in previstas)
        zo.writestr('[Content_Types].xml',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' + items + '</Types>')
        for p in man['global_parts']:
            if p in ('xl/workbook.xml', 'xl/_rels/workbook.xml.rels'):
                continue
            zo.writestr(p, modificadas.get(p, base.read(p))); escritas.add(p)
        for n in orden:
            num = nums[n]
            sp = f'xl/worksheets/sheet{num}.xml'
            if n in hojas:
                with zo.open(sp, 'w', force_zip64=True) as fo:
                    last_tail = ''
                    for trozo in iter_hoja(hojas[n], planes[n], ctx, resolve):
                        fo.write(trozo.encode('utf8'))
                        last_tail = trozo
                m = re.search(r'<autoFilter ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"', last_tail)
                if m:
                    filtros[n] = f'${m.group(1)}${m.group(2)}:${m.group(3)}${m.group(4)}'
                resumen['filas'][n] = len(planes[n])
            else:
                data = ov_xml if n == 'Overview' else base.read(sp)
                zo.writestr(sp, data)
                if n == 'Test Campaign':
                    filtros[n] = '$A$1:$BP$1'
            escritas.add(sp)
            for p in partes_hoja[n]:
                if p in escritas:
                    continue
                zo.writestr(p, modificadas.get(p) or base.read(p)); escritas.add(p)

        # workbook.xml
        wb = base.read('xl/workbook.xml').decode('utf8')
        hojas_xml = ''.join(
            f'<sheet name="{escape(n)}" sheetId="{_sheet_id(wb, n)}" r:id="rId{nums[n]}"/>' for n in orden)
        wb = re.sub(r'<sheets>.*?</sheets>', f'<sheets>{hojas_xml}</sheets>', wb, flags=re.S)
        dn = ''.join(f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
                     f"'{escape(n)}'!{filtros[n]}</definedName>" for i, n in enumerate(orden) if n in filtros)
        wb = re.sub(r'<definedNames>.*?</definedNames>', f'<definedNames>{dn}</definedNames>' if dn else '', wb, flags=re.S)
        wb = re.sub(r'<mc:AlternateContent.*?</mc:AlternateContent>', '', wb, flags=re.S)
        wb = re.sub(r'<xr:revisionPtr[^>]*/>', '', wb)
        calc = '<calcPr calcId="0" calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1" calcOnSave="1"/>'
        if re.search(r'<calcPr\b', wb):
            wb = re.sub(r'<calcPr\b[^>]*/>', calc, wb)
        else:
            wb = wb.replace('</workbook>', calc + '</workbook>')
        zo.writestr('xl/workbook.xml', wb)

        rels = base.read('xl/_rels/workbook.xml.rels').decode('utf8')
        keep = []
        for rel in re.findall(r'<Relationship [^>]*/>', rels):
            tg = re.search(r'Target="([^"]*)"', rel).group(1)
            ty = rel.split('Type="')[1].split('"')[0].split('/')[-1]
            if ty == 'calcChain':
                continue
            mm = re.match(r'worksheets/sheet(\d+)\.xml', tg)
            if mm and int(mm.group(1)) not in nums.values():
                continue
            keep.append(rel)
        zo.writestr('xl/_rels/workbook.xml.rels',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + ''.join(keep) + '</Relationships>')

        # docProps/app.xml
        titulos = ''.join(f'<vt:lpstr>{escape(n)}</vt:lpstr>' for n in orden)
        zo.writestr('docProps/app.xml',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
                    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
                    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
                    '<Application>Microsoft Excel</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop>'
                    f'<HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Hojas de cálculo</vt:lpstr></vt:variant>'
                    f'<vt:variant><vt:i4>{len(orden)}</vt:i4></vt:variant></vt:vector></HeadingPairs>'
                    f'<TitlesOfParts><vt:vector size="{len(orden)}" baseType="lpstr">{titulos}</vt:vector></TitlesOfParts>'
                    '<Company>AT4WIRELESS</Company><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc>'
                    '<HyperlinksChanged>false</HyperlinksChanged><AppVersion>16.0300</AppVersion></Properties>')
        escritas.add('docProps/app.xml')

    resumen['sin_resolver'] = dict(ctx.unresolved)
    resumen['valores_por_defecto'] = dict(ctx.defaults)
    resumen['ejemplos'] = {f'{a}:{b}': v for (a, b), v in ctx.examples.items()}
    resumen['sin_resolver_cols'] = {f'{a}:{b}': n for (a, b), n in sorted(ctx.unres_cols.items(), key=lambda x: -x[1])}
    resumen['referencias_rotas_plantilla'] = dict(ctx.broken)
    resumen['avisos'] = []
    unknown_certs = {}
    for name in conds:
        count = sum(hojas[name].kv(it.i).get('B') in ('?', '#REF!') for it in planes[name])
        if count:
            unknown_certs[name] = count
    if unknown_certs:
        resumen['avisos'].append('Cert. original sin región definida (? o #REF!): ' +
                                ', '.join(f'{name} ({count})' for name, count in unknown_certs.items()) +
                                '. Se conserva el dato de origen; no se ha asignado una región nueva.')
    if ctx.unresolved:
        resumen['avisos'].append('Hay fórmulas de la plantilla sin enlace disponible; se han dejado vacías: ' +
                                ', '.join(f'{n} ({count})' for n, count in ctx.unresolved.items()) +
                                '. Revisa las referencias de origen antes de usar los resultados.')
    if ctx.broken:
        resumen['avisos'].append('La plantilla contiene fórmulas con #REF!: ' +
                                ', '.join(f'{n} ({count})' for n, count in ctx.broken.items()) +
                                '. Revisa estas fórmulas en Excel antes de usar los resultados.')
    if not conducida:
        resumen['avisos'].append('Ensayos conducidos no previstos: se incluyen las pestañas de tecnologías como plantilla, sin añadir medidas.')
    for sar_name in sar_names:
        if not resumen['filas'].get(sar_name):
            resumen['avisos'].append(f'No hay filas compatibles en {sar_name}; revisa tecnología, región y exposición.')
    base.close()
    log(f'Generado: {salida}')
    return resumen


def _sheet_id(wb, nombre):
    m = re.search(r'<sheet name="%s" sheetId="(\d+)"' % re.escape(escape(nombre)), wb)
    return m.group(1) if m else '99'


def _hacer_inline(hojas, resolve, column_aliases=None, cell_anchors=None):
    """Contenido de una celda maestra (para sustituir referencias a filas que no están en la selección)."""
    memo = {}

    def inline(sheet, col, old):
        key = (sheet, col, old)
        if key in memo:
            return memo[key]
        memo[key] = None
        h = hojas.get(sheet)
        if h is None or old not in h.by_old:
            return None
        r_old, tid, consts, aid, kv = h.rows[h.by_old[old]]
        k, objetivo = 0, col2n(col)
        for ci, s, kind, payload in h.templates[tid]:
            val = None
            if kind in (1, 2, 9, 10):
                val = h.cpool[consts[k]][1]; k += 1
            if ci == objetivo:
                if kind == 3:
                    pattern = remap_cells(h.patterns[payload], h.name, r_old, cell_anchors or {})
                    pattern = remap_columns(pattern, h.name, column_aliases or {})
                    txt = expand(pattern, r_old, resolve, h.name, None, inline, None)
                    # solo se sustituye si la fórmula es autocontenida (sin referencias a celdas de la propia hoja)
                    if txt is not None and any(m.group(1) is None
                                               for p in _STR.split(txt)[::2] for m in _REF.finditer(p)):
                        txt = None
                    memo[key] = txt
                elif kind == 1:
                    memo[key] = val
                elif kind == 2:
                    memo[key] = '"%s"' % val.replace('"', '""')
                return memo[key]
        return None
    return inline
