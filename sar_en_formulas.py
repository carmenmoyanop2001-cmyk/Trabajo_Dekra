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
