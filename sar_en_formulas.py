"""Fórmulas de filas adicionales EN, adaptadas por significado desde FCC-ISED.

EN usa SAR de 10 g. No se copian los umbrales ni los límites de 1 g de FCC.
Los rangos de búsqueda cubren solo las filas originales del bloque seleccionado.
"""
import re
from seleccion import _celda, _tipo_extra
from sarlib import col2n, _ONE


# Correspondencia de referencias: las columnas de FCC no están en las mismas
# letras que EN. Las copias ocultas de canal/frecuencia se llevan al dato real.
FCC_EN = {c: c for c in ('BT', 'BU', 'BV', 'BW', 'BX', 'BY', 'BZ', 'CA', 'CB', 'CC', 'CD')}
FCC_EN.update(dict(CE='CE', CF='CF', CG='CE', CH='CF', CI='CG', CJ='CH', CK='CI',
    CL='CC', CM='CD', CN='CJ', CO='CK', CP='CL', CQ='CM', CR='CN', CT='CO',
    CU='CG', CV='CH', CW='CI', CX='CC', CY='CD', CZ='CP', DA='CO', DB='CP',
    DC='CQ', DD='CR', DE='CS', DF='CT', DG='CU', DH='CV', DI='CW', DJ='CX',
    DK='CY', DL='CZ', DM='DA', DN='DB', DO='DC', DP='DD', DQ='DE'))

# Se conservan las fórmulas originales EN para validez, instrucciones de
# medida, SAR comunicado y límite de 10 g. Solo se transplantan equivalentes.
EQUIVALENTES = dict(CG='CI', CH='CJ', CI='CK', CQ='DC', CS='DE', CT='DF',
                    CU='DG', CZ='DL', DC='DO', DD='DP', DE='DQ')


def _formula_local(pattern, oldrow, newrow):
    valid = True
    def replace(match):
        nonlocal valid
        sheet, col, mode, delta = match.groups()
        target_col = FCC_EN.get(col.lstrip('$'))
        row = oldrow + int(delta) if mode == 'r' else int(delta)
        if sheet not in ('', 'SAR FCC-ISED') or target_col is None or (row != oldrow and row > 2):
            valid = False
            return ''
        target_row = newrow if row == oldrow else row
        return ('$' if col.startswith('$') else '') + target_col + ('$' if mode == 'a' else '') + str(target_row)
    result = re.sub(_ONE, replace, pattern)
    return result if valid else None


def _posicion_bateria(en, meta, fcc, prototype, rowmap):
    """CONCATENATE con la posición TBD equivalente, nunca con otra batería.

    FCC usa el primer TBD para batería 1 y, según el bloque, el segundo para
    batería 2. Las baterías adicionales reutilizan el ensayo de batería 1.
    """
    _, pattern = _celda(fcc, prototype, 'CA')
    ordinal = 0
    for match in re.finditer(_ONE, pattern):
        sheet, col, mode, delta = match.groups()
        if sheet in ('', 'SAR FCC-ISED') and col.lstrip('$') == 'CA':
            old = fcc.rows[prototype][0] + int(delta) if mode == 'r' else int(delta)
            target = fcc.kv_old(old)
            while old - 1 in fcc.by_old:
                previous = fcc.kv_old(old - 1)
                if previous.get('CA') != 'TBD' or any(previous.get(k) != target.get(k) for k in ('BT', 'BU', 'BX')):
                    break
                ordinal += 1
                old -= 1
            break
    positions = [old for old in meta['grupo'] if en.kv_old(old).get('CA') == 'TBD']
    if not positions:
        # En WLAN el modo/BW provisional cambia antes de los TBD y divide el
        # grupo de búsqueda. La posición de referencia sigue estando en el
        # mismo bloque contiguo de tecnología/banda/antena/exposición.
        lo, hi = meta['grupo'][0], meta['grupo'][-1]
        key = tuple(en.kv_old(lo).get(k) for k in ('BT', 'BU', 'BV', 'BW', 'BX'))
        while lo - 1 in rowmap and tuple(en.kv_old(lo - 1).get(k) for k in ('BT', 'BU', 'BV', 'BW', 'BX')) == key:
            lo -= 1
        while hi + 1 in rowmap and tuple(en.kv_old(hi + 1).get(k) for k in ('BT', 'BU', 'BV', 'BW', 'BX')) == key:
            hi += 1
        positions = [old for old in range(lo, hi + 1) if en.kv_old(old).get('CA') == 'TBD']
    old = positions[ordinal] if ordinal < len(positions) else (positions[0] if positions else meta['grupo'][-1])
    suffix = f' - Battery check {meta["numero"]}'
    cached = (en.kv_old(old).get('CA') or 'TBD') + suffix
    return ('f', f'CONCATENATE(CA{rowmap[old]},"{suffix}")', cached)


def aplicar_formulas_extras(en, plan, fcc, rowmap):
    prototypes = []
    for index in range(len(fcc.rows)):
        kind = _tipo_extra(fcc, index)
        if kind in ('bat', 'fof', 'acc'):
            prototypes.append((index, kind, fcc.kv(index)))
    for offset, item in enumerate(plan, start=3):
        if not item.extra:
            continue
        meta, kv = item.extra, en.kv(item.i)
        candidates = [(i, v) for i, kind, v in prototypes if kind == meta['tipo'] and
                      v.get('BX', '').lower() == kv.get('BX', '').lower()]
        if candidates:
            index, _ = max(candidates, key=lambda iv: (
                iv[1].get('BT') == kv.get('BT'), iv[1].get('BU') == kv.get('BU')))
            if meta['tipo'] == 'bat':
                # Solo CA usa el prototipo de batería numerado. Las demás
                # columnas mantienen la adaptación de la versión anterior.
                number = meta['numero'] if meta['numero'] <= 2 else 1
                battery_index, _ = max(candidates, key=lambda iv: (
                    iv[1].get('BT') == kv.get('BT'), iv[1].get('BU') == kv.get('BU'),
                    f'Battery check {number}"' in _celda(fcc, iv[0], 'CA')[1]))
                item.ovr[col2n('CA')] = _posicion_bateria(en, meta, fcc, battery_index, rowmap)
            for dest, source in EQUIVALENTES.items():
                kind, pattern = _celda(fcc, index, source)
                if kind == 3:
                    formula = _formula_local(pattern, fcc.rows[index][0], offset)
                    if formula is not None:
                        item.ovr[col2n(dest)] = ('f', formula)
        # FCC busca el máximo SAR comunicado y su canal/frecuencia/potencia.
        # EN no tiene las copias ocultas contiguas CT:CY: INDEX/MATCH conserva
        # esa búsqueda sin formar un rango invertido ni mezclar 1 g con 10 g.
        first, last = (rowmap[meta['grupo'][0]], rowmap[meta['grupo'][-1]])
        measured = f'$CO${first}:$CO${last}'
        match = f'MATCH(MAX({measured}),{measured},0)'
        for column in ('CC', 'CD'):
            data = f'${column}${first}:${column}${last}'
            item.ovr[col2n(column)] = ('f', f'IF(COUNT({measured})=0,"N/A",INDEX({data},{match}))')
        item.ovr[col2n('DB')] = ('f', f'IF(COUNT({measured})=0,"N/A",IFERROR(INDEX($DB${first}:$DB${last},{match}),"N/A"))')
        # Variante de numeración de FCC para filas adicionales, ampliada a N
        # baterías/accesorios sin asumir que siempre existen solo dos.
        item.ovr[col2n('CR')] = ('f', f'IF(CO{offset}<>"",MAX($CR$3:CR{offset - 1})+1,"")')
        item.ovr[col2n('BY')] = 'N/A'
