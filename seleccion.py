# -*- coding: utf-8 -*-
"""Selección de filas por tecnología/banda/región y construcción de filas nuevas en SAR."""
import re
from collections import defaultdict
from sarlib import col2n, T1, T2, _TOKR
from nucleo import Item, HEADER_ROWS
from opciones_ensayo import seleccion_multiple, slots_incluidos

# ----------------------------------------------------------------------------------------
#  Correspondencia entre la selección del usuario y las filas de la plantilla
# ----------------------------------------------------------------------------------------
def etiqueta_region(region):
    return 'EN' if region == 'EN' else 'FCC/ISED'


def token_modo(modo, bw):
    """'802.11n' + '20' -> 'n20';  '802.11b' -> 'b'"""
    if modo is None:
        return None
    m = modo.replace('802.11', '').replace('*', '').strip()
    if m in ('a', 'b', 'g'):
        return m
    try:
        return f'{m}{int(float(bw))}'
    except (TypeError, ValueError):
        return m


def _wlan_ok(banda, modo, bw, wlan):
    tok = token_modo(modo, bw)
    if banda == '2.4 GHz':
        return tok in wlan.get('2,4 GHz', [])
    five = wlan.get('5 GHz')
    return bool(five) and banda in five['bandas'] and tok in five['modos']


def _wlan_sar_ok(banda, modo, bw, wlan):
    # SAR reserva filas con modo/BW TBD para el peor caso que se determine
    # posteriormente. No son un modo concreto de Conducted WiFi y no deben
    # descartarse por no llamarse literalmente n40, ac40, etc.
    # Las filas adicionales originales de FCC (baterías/variabilidad) también
    # usan N/A o un modo vacío; pertenecen al mismo bloque de banda/exposición.
    if modo is None or str(modo).strip().upper() in ('', 'TBD', 'TBD / NA', 'TBD / N/A', 'N/A', 'NA'):
        if banda == '2.4 GHz':
            return bool(wlan.get('2,4 GHz'))
        five = wlan.get('5 GHz')
        return bool(five) and banda in five['bandas'] and bool(five.get('modos'))
    return _wlan_ok(banda, modo, bw, wlan)


def pred_conducted(nombre, kv, t):
    """¿Esta fila de una pestaña Conducted pertenece a la selección?"""
    if 'K' not in kv:
        return False
    if nombre == 'Conducted 2G-3G':
        j = kv.get('J')
        g2, g3 = t.get('2G'), t.get('3G', [])
        if j == 'GSM':
            return bool(g2 and g2.get('GSM'))
        if j in ('GPRS', 'EGPRS'):
            slots = slots_incluidos(g2.get(j)) if g2 else []
            return kv.get('X') in {slot[2:] for slot in slots}
        return j in g3
    if nombre == 'Conducted LTE':
        return kv['K'] in t.get('LTE', [])
    if nombre == 'Conducted LTE CATM1':
        return kv['K'] in t.get('LTE CAT M1', [])
    if nombre == 'Conducted LTE NB-IoT':
        return kv['K'] in t.get('LTE NB-IoT', [])
    if nombre == 'Conducted 5G':
        return kv['K'] in t.get('5G', [])
    if nombre == 'Conducted WiFi':
        return 'WLAN' in t and _wlan_ok(kv['K'], kv.get('S'), kv.get('M'), t['WLAN'])
    return False


def hojas_conducted_necesarias(t):
    out = []
    if t.get('2G') or t.get('3G'):
        out.append('Conducted 2G-3G')
    if t.get('LTE'):
        out.append('Conducted LTE')
    if t.get('LTE CAT M1'):
        out.append('Conducted LTE CATM1')
    if t.get('LTE NB-IoT'):
        out.append('Conducted LTE NB-IoT')
    if t.get('5G'):
        out.append('Conducted 5G')
    if t.get('WLAN'):
        out.append('Conducted WiFi')
    return out


# ----------------------------------------------------------------------------------------
#  Pestañas Conducted
# ----------------------------------------------------------------------------------------
def plan_conducted(h, datos, refs=None):
    """Lista de Item para una pestaña Conducted.
    refs: filas antiguas de esta hoja que las filas SAR seleccionadas referencian (guían qué bloque de región se usa)."""
    families = list(dict.fromkeys('EN' if r == 'EN' else 'FCC'
                                 for r in seleccion_multiple(datos['region'])))
    if len(families) > 1:
        # Cada región debe conservar sus propios bloques aunque la otra tenga
        # referencias SAR a bloques distintos. Las filas comunes no se duplican.
        merged = {}
        for family in families:
            family_refs = refs.get(family, set()) if isinstance(refs, dict) else refs
            for item in plan_conducted(h, dict(datos, region=family), family_refs):
                if item.i not in merged:
                    merged[item.i] = item
        return [merged[i] for i in sorted(merged)]
    if isinstance(refs, dict):
        refs = refs.get(families[0], set())
    t = datos['tecnologias']
    target = etiqueta_region(families[0])
    compat = {target, 'EN/FCC/ISED', None}
    refs = refs or set()
    grupos = defaultdict(list)
    for i, r in enumerate(h.rows):
        if r[0] <= HEADER_ROWS:
            continue
        kv = h.kv(i)
        if pred_conducted(h.name, kv, t):
            grupos[(kv.get('J'), kv.get('K'))].append(i)
    final = []
    for key, idxs in grupos.items():
        tags_ref = {h.kv(i).get('B') for i in idxs if h.rows[i][0] in refs}
        if tags_ref:
            use = [i for i in idxs if h.kv(i).get('B') in tags_ref]
        else:
            use = [i for i in idxs if h.kv(i).get('B') in compat] or \
                  [i for i in idxs if h.kv(i).get('B') == '?'] or idxs
        final += use
    final.sort()
    # Cert. es un dato del datasheet, no una etiqueta de la selección actual.
    # Conservarlo también cuando una fila se comparte entre varias regiones.
    return [Item(i) for i in final]


# ----------------------------------------------------------------------------------------
#  Pestañas SAR
# ----------------------------------------------------------------------------------------
def pred_sar(kv, datos):
    t = datos['tecnologias']
    if kv.get('BX', '').lower() not in {e.lower() for e in seleccion_multiple(datos['exposure'])}:
        return False
    bt, bu = kv.get('BT'), kv.get('BU')
    if bt == 'GSM':
        return bool(t.get('2G') and t['2G'].get('GSM'))
    if bt == 'GPRS 4TX':
        return bool(t.get('2G') and 'TX4' in slots_incluidos(t['2G'].get('GPRS')))
    if bt == 'WCDMA':
        return 'WCDMA' in t.get('3G', [])
    if bt == 'LTE':
        return bu in t.get('LTE', [])
    if bt == 'LTE CATM1':
        return bu in t.get('LTE CAT M1', [])
    if bt == '5G':
        return bu in t.get('5G', [])
    if bt == 'WLAN':
        return 'WLAN' in t and _wlan_sar_ok(bu, kv.get('BY'), kv.get('BZ'), t['WLAN'])
    return False


def _celda(h, i, col):
    """(tipo, contenido) de una celda de la fila i: constante o patrón de fórmula."""
    r = h.rows[i]; k = 0; ci = col2n(col)
    for c, st, kind, payload in h.templates[r[1]]:
        v = None
        if kind in (1, 2, 9, 10):
            v = h.cpool[r[2][k]][1]; k += 1
        if c == ci:
            return kind, (h.patterns[payload] if kind == 3 else v)
    return 0, None


def _tipo_extra(h, i):
    """'var' | 'bat' | 'fof' | 'acc' | None según el contenido de la celda Position (CA)."""
    kind, txt = _celda(h, i, 'CA')
    txt = txt or ''
    if kind == 3:
        if 'Variability' in txt:
            return 'var'
        if 'Battery check' in txt:
            return 'bat'
        return None
    if txt == 'Front of Face':
        return 'fof'
    if txt.startswith('Accesorio'):
        return 'acc'
    return None


def plan_sar(h, tipo, datos):
    """FCC: filtrar originales. EN: conservar originales e insertar extras debajo.

    No generar filas Variability ni sustituir fórmulas por N/A al insertar.
    """
    selected = [i for i, r in enumerate(h.rows)
                if r[0] > HEADER_ROWS and pred_sar(h.kv(i), datos)]
    if tipo != 'EN':
        return [Item(i) for i in selected]
    bats, accs = datos['baterias'], datos['accesorios']
    c = {k: col2n(k) for k in ('CA', 'CB')}
    # filas seleccionadas, en orden. Un grupo termina al cambiar (tecnología, banda, exposición, BW),
    # al perder la contigüidad o al pasar de filas extra (variabilidad/batería/accesorio) a filas normales.
    grupos, cur, prev, prev_key, prev_extra = [], None, None, None, False
    for i in selected:
        r = h.rows[i]
        kv = h.kv(i)
        key = (kv['BT'], kv['BU'], kv['BX'], kv.get('BZ'))
        extra = _tipo_extra(h, i) is not None
        if cur is None or key != prev_key or r[0] != prev + 1 or (prev_extra and not extra):
            cur = []
            grupos.append(cur)
        cur.append(i)
        prev, prev_key, prev_extra = r[0], key, extra
    items = []
    for g in grupos:
        base = g
        for i in base:
            items.append(Item(i))
        if not base:
            continue
        anchor = base[-1]
        body = h.kv(anchor).get('BX', '').lower() == 'body'

        def nuevo(n, texto, tipo_extra, cb=None):
            """Inserta copias de la fila superior, modificando solo su posición/distancia."""
            out = []
            for k in range(n):
                ovr = {c['CA']: texto(k)}
                if cb is not None:
                    ovr[c['CB']] = cb
                out.append(Item(anchor, ovr, True, {'tipo': tipo_extra, 'numero': k + 1,
                           'grupo': tuple(h.rows[i][0] for i in base)}))
            return out
        items += nuevo(len(bats), lambda k: f'TBD - Battery check {k + 1}', 'bat')
        if body:
            items += nuevo(1, lambda k: 'Front Face', 'fof', cb=25)
            items += nuevo(len(accs), lambda k: f'Accesorio {k + 1}: {accs[k]}', 'acc', cb=0)
    # una fila de plantilla solo puede aparecer una vez como original
    vistos, res = set(), []
    for it in items:
        if not it.clone:
            if it.i in vistos:
                it = Item(it.i, it.ovr, True)
            vistos.add(it.i)
        res.append(it)
    return res


def referencias(h, items, prefijo='Conducted'):
    """Filas antiguas, por hoja, que las fórmulas de los items referencian."""
    out = defaultdict(set)
    for it in items:
        r_old, tid, consts, aid, kv = h.rows[it.i]
        for ci, s, kind, payload in h.templates[tid]:
            if kind != 3:
                continue
            for m in _TOKR.finditer(h.patterns[payload]):
                sh = m.group(1)
                if not sh.startswith(prefijo):
                    continue
                for kd, val in ((m.group(3), m.group(4)), (m.group(7), m.group(8))):
                    if kd:
                        out[sh].add(r_old + int(val) if kd == 'r' else int(val))
    return out
