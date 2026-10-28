# -*- coding: utf-8 -*-
"""Selección de filas por tecnología/banda/región y construcción de filas nuevas en SAR."""
import re
from collections import defaultdict
from sarlib import col2n, T1, T2, _TOKR
from nucleo import Item, HEADER_ROWS

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
            slot = g2 and g2.get(j)
            return bool(slot) and kv.get('X') == slot[2:]
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
    t = datos['tecnologias']
    target = etiqueta_region(datos['region'])
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
    col_b = col2n('B')
    return [Item(i, {col_b: target}) for i in final]


# ----------------------------------------------------------------------------------------
#  Pestañas SAR
# ----------------------------------------------------------------------------------------
def pred_sar(kv, datos):
    t = datos['tecnologias']
    if kv.get('BX', '').lower() != datos['exposure'].lower():
        return False
    bt, bu = kv.get('BT'), kv.get('BU')
    if bt == 'GSM':
        return bool(t.get('2G') and t['2G'].get('GSM'))
    if bt == 'GPRS 4TX':
        return bool(t.get('2G') and t['2G'].get('GPRS') == 'TX4')
    if bt == 'WCDMA':
        return 'WCDMA' in t.get('3G', [])
    if bt == 'LTE':
        return bu in t.get('LTE', [])
    if bt == 'LTE CATM1':
        return bu in t.get('LTE CAT M1', [])
    if bt == '5G':
        return bu in t.get('5G', [])
    if bt == 'WLAN':
        return 'WLAN' in t and _wlan_ok(bu, kv.get('BY'), kv.get('BZ'), t['WLAN'])
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
    """Lista de Item para SAR EN / SAR FCC-ISED, con las filas de variabilidad (spotchecking),
    baterías y accesorios creadas a partir del número y los nombres introducidos."""
    spot, bats, accs = datos['spotchecking'], datos['baterias'], datos['accesorios']
    body = datos['exposure'].lower() == 'body'
    c = {k: col2n(k) for k in ('CA', 'CB', 'CC', 'CD', 'DB', 'DN')}
    na_cols = (['CC', 'CD', 'DB'] if tipo == 'EN' else ['CC', 'CD', 'DN'])
    # filas seleccionadas, en orden. Un grupo termina al cambiar (tecnología, banda, exposición, BW),
    # al perder la contigüidad o al pasar de filas extra (variabilidad/batería/accesorio) a filas normales.
    grupos, cur, prev, prev_key, prev_extra = [], None, None, None, False
    for i, r in enumerate(h.rows):
        if r[0] <= HEADER_ROWS:
            continue
        kv = h.kv(i)
        if 'BT' not in kv or not pred_sar(kv, datos):
            continue
        key = (kv['BT'], kv['BU'], kv['BX'], kv.get('BZ'))
        extra = _tipo_extra(h, i) is not None
        if cur is None or key != prev_key or r[0] != prev + 1 or (prev_extra and not extra):
            cur = []
            grupos.append(cur)
        cur.append(i)
        prev, prev_key, prev_extra = r[0], key, extra
    items = []
    for g in grupos:
        base = [i for i in g if _tipo_extra(h, i) is None]
        extra = defaultdict(list)
        for i in g:
            te = _tipo_extra(h, i)
            if te:
                extra[te].append(i)
        for i in base:
            items.append(Item(i))
        if not base:
            continue
        anchor = base[-1]

        def nuevo(proto_list, n, texto, extra_ovr=None, cb=None):
            """n filas: usa filas de plantilla si existen; si no, clona la última / la fila ancla."""
            out = []
            for k in range(n):
                if k < len(proto_list):
                    src, clone = proto_list[k], False
                else:
                    src, clone = (proto_list[-1] if proto_list else anchor), True
                ovr = {c['CA']: texto(k)}
                if cb is not None:
                    ovr[c['CB']] = cb
                if tipo == 'EN' or (not proto_list):
                    for nc in na_cols:
                        ovr[c[nc]] = 'N/A'
                if extra_ovr:
                    ovr.update(extra_ovr)
                out.append(Item(src, ovr, clone))
            return out
        items += nuevo(extra['var'], len(spot), lambda k: f'TBD - Variability: {spot[k]}')
        items += nuevo(extra['bat'], len(bats), lambda k: f'TBD - Battery check {k + 1}')
        if body and accs:
            items += nuevo(extra['fof'], 1, lambda k: 'Front of Face', cb=25)
            items += nuevo(extra['acc'], len(accs), lambda k: f'Accesorio {k + 1}: {accs[k]}', cb=0)
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
