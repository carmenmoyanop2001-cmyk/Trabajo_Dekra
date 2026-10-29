"""Rellena formatos guardados con registros RF del catálogo y respuestas.

El datasheet aporta exclusivamente presentación, posiciones y fórmulas de
ensayo. No se reutilizan sus bandas, canales, frecuencias ni parámetros RF.
"""
from array import array
from collections import defaultdict
import re

from lxml import etree as E
from nucleo import Hoja, Item
from opciones_ensayo import seleccion_multiple
from seleccion import _celda
from sarlib import col2n, n2col, tokenize, expand

PARAM_COL = dict(scs='L', bw='M', modulation='N', mpr='O', nb_index='P',
                 rb='Q', rb_start='R', mode='S', data_rate='V', duty='W', cert='B')


def hoja_tecnologia(tech):
    if tech == 'GSM' or re.fullmatch(r'E?GPRS [1-4]TX', tech) or tech in ('WCDMA', 'HSPA', 'HSPA+', 'HSDPA', 'DC-HSDPA'):
        return 'Conducted 2G-3G'
    if tech in ('BT',) or tech.startswith('Custom'):
        return 'Conducted BT-Custom'
    return {'LTE': 'Conducted LTE', 'LTE CAT M1': 'Conducted LTE CATM1',
            'LTE NB-IoT': 'Conducted LTE NB-IoT', '5G': 'Conducted 5G', 'WLAN': 'Conducted WiFi'}.get(tech)


def sar_tech(tech):
    if tech == 'LTE CAT M1':
        return 'LTE CATM1'
    return tech


def constante_procedimiento(h, i, col, seen=None):
    """Valor fijo o alias simple de una posición/antena de la plantilla."""
    seen = set() if seen is None else seen
    if (i, col) in seen:
        return None
    seen.add((i, col))
    kind, value = _celda(h, i, col)
    if kind == 1:
        number = float(value)
        return int(number) if number.is_integer() else number
    if kind == 2:
        return value
    if kind == 3:
        from sarlib import _ONE
        match = re.fullmatch(_ONE, value)
        if match:
            sheet, letter, mode, delta = match.groups()
            old = h.rows[i][0] + int(delta) if mode == 'r' else int(delta)
            if sheet in ('', h.name) and old in h.by_old:
                return constante_procedimiento(h, h.by_old[old], letter.lstrip('$'), seen)
        return h.kv(i).get(col)
    return None


class Constructor:
    """Copia estilos de filas de referencia; todo valor nuevo es explícito."""
    def __init__(self, source):
        self.source = source
        h = self.h = object.__new__(Hoja)
        h.name = source.name
        h.cpool, h.patterns, h.templates = list(source.cpool), list(source.patterns), list(source.templates)
        h.attrs = source.attrs
        h.rows = list(source.rows[:2])
        h.by_old = {r[0]: i for i, r in enumerate(h.rows)}
        h._kv = {i: dict(source.kv(i)) for i in range(2)}
        h.sd = dict(source.sd, formula_cache={})
        # Se conservan los desplegables no RF que contenga la plantilla.
        # Solo se retiran restricciones RF que apuntaban al catálogo antiguo.
        h.sd['tail'] = validaciones_formato(h.sd['tail'], source.name.startswith('SAR '),
                                           source.name == 'Conducted BT-Custom')
        self.pending_formulas = 0

    def append(self, index, values, mapping=None, preserve=()):
        src = self.source
        old, tid, _, aid, _ = src.rows[index]
        row = len(self.h.rows) + 1
        cells, constants, kv = [], [], {}
        for ci, style, kind, payload in src.templates[tid]:
            col = n2col(ci)
            value = values.get(col)
            if col not in values:
                if col in preserve:
                    k, v = _celda(src, index, col)
                    value = v if k in (1, 2) else src.kv(index).get(col)
                    if k == 1 and v is not None:
                        num = float(v)
                        value = int(num) if num.is_integer() else num
                if kind == 3:
                    text = self._formula(src.patterns[payload], old, row, mapping or {})
                    if text is not None:
                        # Solo valores iniciales del procedimiento (posición,
                        # distancia, identificador), nunca resultados RF viejos.
                        value = ('f', text, value if col in preserve else None)
            if isinstance(value, tuple):
                pattern = tokenize(value[1], row)
                pid = len(self.h.patterns)
                self.h.patterns.append(pattern)
                cells.append((ci, style, 3, pid))
                if len(value) > 2 and value[2] is not None:
                    kv[col] = str(value[2])
            elif value is None or value == '':
                cells.append((ci, style, 0, 0))
            else:
                kind = 1 if isinstance(value, (int, float)) else 2
                value = str(value)
                pi = len(self.h.cpool)
                self.h.cpool.append((kind, value))
                constants.append(pi)
                kv[col] = value
                cells.append((ci, style, kind, None))
        self.h.templates.append(tuple(cells))
        self.h.rows.append((row, len(self.h.templates) - 1, array('I', constants), aid, ()))
        index = len(self.h.rows) - 1
        self.h._kv[index] = kv
        self.h.by_old[row] = index
        return row

    def _formula(self, pattern, old, new, mapping):
        def resolve(sheet, target, role):
            if sheet in ('Overview', 'Validations'):
                return target
            if sheet != self.source.name:
                return None
            if target == old:
                return new
            if target in mapping:
                return mapping[target]
            return target if target <= 2 else None
        if '#REF!' in pattern or 'INDIRECT(' in pattern:
            return None
        formula = expand(pattern, old, resolve, self.source.name)
        if formula is None:
            self.pending_formulas += 1
        return formula

    def terminar(self):
        self.h.sd.update(rows=self.h.rows, templates=self.h.templates, patterns=self.h.patterns, cpool=self.h.cpool)
        return self.h, [Item(i) for i in range(2, len(self.h.rows))]


def validaciones_formato(tail, sar, bt=False):
    rf = ({col2n(c) for c in ('BT', 'BU', 'BW', 'BY', 'BZ', 'CC', 'CD', 'DA', 'DB', 'DM', 'DN')} |
          set(range(col2n('J'), col2n('Z') + 1))) if sar else (
          {col2n('B')} | set(range(col2n('J'), col2n('Z') + 1)))
    if bt:
        rf |= set(range(col2n('BT'), col2n('CA') + 1))
    def keep(match):
        block = match.group(0)
        refs = re.search(r'sqref="([^"]+)"', block)
        if refs:
            for ref in refs[1].split():
                ends = re.findall(r'\$?([A-Z]+)\$?\d+', ref)
                if ends and any(c in rf for c in range(col2n(ends[0]), col2n(ends[-1]) + 1)):
                    return ''
        return block
    tail = re.sub(r'<dataValidation\b[^>]*(?:/>|>.*?</dataValidation>)', keep, tail, flags=re.S)
    count = len(re.findall(r'<dataValidation\b', tail))
    if not count:
        return re.sub(r'<dataValidations\b.*?</dataValidations>', '', tail, flags=re.S)
    return re.sub(r'(<dataValidations\b[^>]*\bcount=")\d+', lambda m: m[1] + str(count), tail)


def _prototype(h, tech, band=None):
    tags = {'LTE CAT M1': 'Cat M1', 'BT': 'Bluetooth'}
    wanted = tags.get(tech, tech)
    if re.fullmatch(r'E?GPRS [1-4]TX', tech):
        wanted = tech.split()[0]
    choices = [i for i, row in enumerate(h.rows) if row[0] > 2 and
               (h.kv(i).get('J') == wanted or h.kv(i).get('BT') == wanted)]
    if not choices:
        choices = [i for i, row in enumerate(h.rows) if row[0] > 2]
    return next((i for i in choices if h.kv(i).get('K') == band), choices[0])


def _rf(record):
    values = {col: record.params.get(key) for key, col in PARAM_COL.items()}
    values.update(J=record.tech, K=record.band, T=record.channel, U=record.frequency,
                  BO=record.notes or None)
    if record.tech == 'LTE CAT M1':
        values['J'] = 'Cat M1'
    match = re.fullmatch(r'(E?GPRS) ([1-4])TX', record.tech)
    if match:
        values.update(J=match[1], X=int(match[2]))
    return values


def construir(catalogo, datos, sources, base):
    records = catalogo.seleccionar(datos)
    groups = defaultdict(list)
    for record in records:
        name = hoja_tecnologia(record.tech)
        if name is None:
            raise ValueError(f'No hay formato guardado para la tecnología {record.tech}.')
        groups[name].append(record)
    hojas, planes, ranges = {}, {}, {}
    for name, rows in groups.items():
        builder = Constructor(sources(name))
        by_band = defaultdict(list)
        for record in rows:
            by_band[(record.tech, record.band)].append(record)
        for record in [r for group in by_band.values() for r in group]:
            new = len(builder.h.rows) + 1
            values = _rf(record)
            # Los auxiliares del datasheet que resumían datos RF antiguos se
            # regeneran desde las columnas de esta tabla, no desde otra banda.
            lastcol = max(c[0] for c in builder.source.templates[builder.source.rows[2][1]])
            values.update({n2col(c): None for c in range(col2n('BS'), lastcol + 1)})
            if name == 'Conducted BT-Custom':
                values.update(BT=record.tech, BU=record.params.get('cert'), BW=record.band,
                              BX=record.params.get('mode'), BY=record.channel, BZ=record.frequency,
                              CA=record.params.get('modulation'),
                              AH=('f', f'IF(CB{new}="","",CB{new})'))
            builder.append(_prototype(builder.source, record.tech, record.band), values)
            ranges.setdefault((record.tech, record.band), [name, new, new])[2] = new
        hojas[name], planes[name] = builder.terminar()
    warnings = list(catalogo.avisos)
    tune = indice_tune_up(base)
    for record in records:
        if record.notes and record.notes not in warnings:
            warnings.append(record.notes)
    for sar_name in (['SAR EN'] if 'EN' in seleccion_multiple(datos['region']) else []) + (
            ['SAR FCC-ISED'] if any(r in seleccion_multiple(datos['region']) for r in ('FCC', 'ISED')) else []):
        hojas[sar_name], planes[sar_name] = _sar(sources(sar_name), records, datos, ranges, warnings, tune,
                                               sources('SAR FCC-ISED') if sar_name == 'SAR EN' else None)
    pending = sorted({r.tech for r in records if 'mode' not in r.params or 'bw' not in r.params})
    if pending:
        warnings.append('La base no informa todos los campos de modo/ancho de banda para: ' + ', '.join(pending) +
                        '. Los campos ausentes quedan vacíos; no se recuperan del datasheet.')
    return hojas, planes, records, warnings


def _sar(source, records, datos, ranges, warnings, tune, fcc=None):
    builder = Constructor(source)
    battery_candidates, battery_prototypes = defaultdict(list), {}
    if fcc is not None and datos['baterias']:
        # Se indexan una sola vez: recorrer 25.000 filas por cada batería
        # repetía trabajo y hacía lenta la generación con varias tecnologías.
        for k in range(2, len(fcc.rows)):
            kind, pattern = _celda(fcc, k, 'CA')
            if kind == 3 and 'Battery check' in pattern:
                for number in (1, 2):
                    if f'Battery check {number}"' in pattern:
                        battery_candidates[(fcc.kv(k).get('BX', '').lower(), number)].append(k)
    by_band = defaultdict(list)
    for record in records:
        by_band[(record.tech, record.band)].append(record)
    for (tech, band), rows in by_band.items():
        # La plantilla guarda el procedimiento, no define el catálogo RF.
        # GPRS 1-3TX/EGPRS/HSPA/NB-IoT no tienen un procedimiento SAR propio.
        if re.fullmatch(r'E?GPRS [1-3]TX', tech) or tech.startswith('EGPRS') or tech in ('LTE NB-IoT', 'HSPA', 'HSPA+', 'HSDPA', 'DC-HSDPA'):
            continue
        family = sar_tech(tech)
        candidates = [i for i, row in enumerate(source.rows) if row[0] > 2 and source.kv(i).get('BT') == family]
        if not candidates and tech == 'LTE CAT M1':
            # Mismo formato de posición y columnas; RF siempre viene de CAT M1.
            candidates = [i for i, row in enumerate(source.rows) if row[0] > 2 and source.kv(i).get('BT') == 'LTE']
        if not candidates:
            warnings.append(f'{source.name}: no hay procedimiento de posiciones guardado para {tech}; se conserva su hoja de tecnología.')
            continue
        template_band = next((source.kv(i)['BU'] for i in candidates if source.kv(i).get('BU') == band), source.kv(candidates[0])['BU'])
        selected = [i for i in candidates if source.kv(i).get('BU') == template_band and
                    source.kv(i).get('BX', '').lower() in {e.lower() for e in seleccion_multiple(datos['exposure'])}]
        # Los grupos se separan por exposición y antena/Tx. No por valores RF.
        blocks = []
        band_mapping = {}
        previous = None
        for i in selected:
            kv = source.kv(i)
            key = (constante_procedimiento(source, i, 'BV'), kv.get('BW'), kv.get('BX'))
            if key != previous:
                blocks.append([])
            blocks[-1].append(i)
            previous = key
        for block in blocks:
            start = len(builder.h.rows) + 1
            mapping = {source.rows[i][0]: start + k for k, i in enumerate(block)}
            band_mapping.update(mapping)
            data_name, data_first, data_last = ranges[(tech, band)]
            powers = f"'{data_name}'!$AH${data_first}:$AH${data_last}"
            match = f'MATCH(MAX({powers}),{powers},0)'
            values_by_column = {'CC': 'T', 'CD': 'U', 'BY': 'S', 'BZ': 'M'}
            ordered = sorted(rows, key=lambda r: (r.frequency, r.channel))
            middle = ordered[len(ordered) // 2]
            for i in block:
                kv = source.kv(i)
                new = len(builder.h.rows) + 1
                values = _rf(middle)
                ant_value = constante_procedimiento(source, i, 'BV')
                values.update(BT=family, BU=band, BW=None,
                              BX=next(e for e in seleccion_multiple(datos['exposure']) if e.lower() == kv['BX'].lower()))
                if ant_value is not None:
                    values['BV'] = ant_value
                for dest, data_col in values_by_column.items():
                    fallback = {'CC': middle.channel, 'CD': middle.frequency,
                                'BY': middle.params.get('mode'), 'BZ': middle.params.get('bw')}[dest]
                    # Modo/BW no se inventan si no constan en la base.
                    if fallback is None:
                        values[dest] = None
                    else:
                        literal = str(fallback) if isinstance(fallback, (int, float)) else '"' + str(fallback).replace('"', '""') + '"'
                        data_range = f"'{data_name}'!${data_col}${data_first}:${data_col}${data_last}"
                        values[dest] = ('f', f'IF(COUNT({powers})=0,{literal},INDEX({data_range},{match}))', fallback)
                # Tune-Up sí se conserva del original, por indicación del
                # usuario. Se busca su fila por tecnología/banda, no por orden.
                target_row = tune.get((tech, band))
                target = ('f', f'IF(\'Tune-Up\'!H{target_row}="","",\'Tune-Up\'!H{target_row})') if target_row else None
                values.update(DA=target, DB=None) if source.name == 'SAR EN' else values.update(DM=target, DN=None)
                for col in ('CG', 'CH', 'CI') if source.name == 'SAR EN' else ('CU', 'CV', 'CW'):
                    # Copias ocultas del propio registro, nunca resultados viejos.
                    letter = {'CG': 'BY', 'CH': 'BZ', 'CI': 'CA', 'CU': 'BY', 'CV': 'BZ', 'CW': 'CA'}[col]
                    values[col] = ('f', f'{letter}{new}')
                if source.name == 'SAR EN':
                    values['CP'] = ('f', 'IF(COUNTIF(Overview!K12:K14,TRUE)>0,2,IF(COUNTIF(Overview!L12:L14,TRUE)>0,4,0))')
                else:
                    values['CZ'] = ('f', 'IF(COUNTIF(Overview!K12:K14,TRUE)>0,1.6,IF(COUNTIF(Overview!L12:L14,TRUE)>0,8,0))')
                builder.append(i, values, band_mapping, preserve=('F', 'CA', 'CB'))
            if source.name == 'SAR EN':
                # Posición dinámica: usar los TBD originales de este bloque.
                tbd = [mapping[source.rows[i][0]] for i in block if source.kv(i).get('CA') == 'TBD']
                anchor = tbd[0] if tbd else start
                exposure = source.kv(block[0])['BX']
                template = block[-1]
                for n, _ in enumerate(datos['baterias'], start=1):
                    new = len(builder.h.rows) + 1
                    ref = tbd[n - 1] if n <= len(tbd) and n <= 2 else anchor
                    extra = dict(values, CA=('f', f'CONCATENATE(CA{ref}," - Battery check {n}")', f'TBD - Battery check {n}'))
                    if fcc is not None:
                        number = n if n <= 2 else 1
                        candidates = battery_candidates[(exposure.lower(), number)]
                        if candidates:
                            key = family, band, exposure.lower(), number
                            if key not in battery_prototypes:
                                battery_prototypes[key] = max(candidates, key=lambda k: (
                                    fcc.kv(k).get('BT') == family, fcc.kv(k).get('BU') == band))
                            prototype = battery_prototypes[key]
                            from sar_en_formulas import _posicion_bateria
                            extra['CA'] = _posicion_bateria(builder.h,
                                {'numero': n, 'grupo': tuple(mapping.values())}, fcc, prototype,
                                {r: r for r in builder.h.by_old})
                    extra.update(CG=('f', f'BY{new}'), CH=('f', f'BZ{new}'), CI=('f', f'CA{new}'))
                    builder.append(template, extra, mapping, preserve=('F', 'CB'))
                if exposure.lower() == 'body':
                    for label, distance in [('Front Face', 25)] + [(f'Accesorio {n}: {text}', 0) for n, text in enumerate(datos['accesorios'], 1)]:
                        new = len(builder.h.rows) + 1
                        extra = dict(values, CA=label, CB=distance)
                        extra.update(CG=('f', f'BY{new}'), CH=('f', f'BZ{new}'), CI=('f', f'CA{new}'))
                        builder.append(template, extra, mapping, preserve=('F',))
    h, plan = builder.terminar()
    if not plan:
        raise ValueError(f'{source.name}: la selección no tiene un procedimiento SAR guardado. Las filas RF se leen de la base, pero no se inventan posiciones de ensayo.')
    return h, plan


def indice_tune_up(base):
    """Índice de la hoja original guardada; su XML no se modifica."""
    from base_datos import tecnologia
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    strings = [''.join(si.xpath('.//s:t/text()', namespaces=ns))
               for si in E.fromstring(base.read('xl/sharedStrings.xml'))]
    root = E.fromstring(base.read('xl/worksheets/sheet2.xml'))
    result = {}
    for row in root.findall('s:sheetData/s:row', ns)[2:]:
        data = {}
        for c in row:
            col = re.sub(r'\d+', '', c.get('r'))
            v = c.findtext('s:v', namespaces=ns)
            if c.get('t') == 's' and v is not None:
                v = strings[int(v)]
            elif c.get('t') == 'inlineStr':
                v = ''.join(c.xpath('.//s:t/text()', namespaces=ns))
            if v is not None:
                data[col] = v
        if data.get('B') and data.get('D'):
            result.setdefault((tecnologia(data['B']), data['D']), int(row.get('r')))
    return result


def restaurar_modos_dinamicos(h, plan, ctx, resolve):
    """Una celda Mode por banda, conservando el vínculo al peor caso medido."""
    anchors = {int(ref.split(':')[0][2:]) for ref in ctx.display_merges[h.name] if ref.startswith('BY')}
    for row, item in enumerate(plan, 3):
        kind, pattern = _celda(h, item.i, 'BY')
        if kind != 3:
            continue
        formula = expand(pattern, h.rows[item.i][0], resolve, h.name)
        if formula is not None:
            value = ('f', formula, h.kv(item.i).get('BY', ''))
            item.ovr[col2n('CG')] = value
            if row in anchors:
                item.ovr[col2n('BY')] = value
