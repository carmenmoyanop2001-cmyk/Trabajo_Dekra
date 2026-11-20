"""Procedimiento SAR de la base main12 identificada en la revisión anterior.

Se conserva únicamente _sar de 6f1ca2b; no se importa su generador de tecnologías.
"""
from collections import defaultdict
import re

from hojas_base_datos import Constructor, constante_procedimiento, sar_tech, _rf
from opciones_ensayo import seleccion_multiple
from seleccion import _celda


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
