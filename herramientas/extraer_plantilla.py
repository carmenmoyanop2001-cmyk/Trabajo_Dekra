#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenera la carpeta ../plantilla a partir de un datasheet .xlsm.
Solo hace falta si algún día se quiere actualizar la plantilla (nuevas bandas, columnas, fórmulas...).

Uso:  python extraer_plantilla.py  ruta/al/datasheet.xlsm  [carpeta_de_salida]
(La extracción de la pestaña de 5G tarda unos 10 minutos.)"""
import os, re, subprocess, sys, zipfile

ESPERADO = {1: 'Overview', 2: 'Tune-Up', 3: 'Conducted 2G-3G', 4: 'Conducted LTE', 5: 'Conducted LTE CATM1',
            6: 'Conducted LTE NB-IoT', 7: 'Conducted 5G', 8: 'Conducted WiFi', 9: 'Conducted BT-Custom',
            11: 'SAR EN', 12: 'SAR FCC-ISED', 13: 'Test Campaign'}
SALIDA = {3: 'cond_2g3g.xz', 4: 'cond_lte.xz', 5: 'cond_catm1.xz', 6: 'cond_nbiot.xz', 7: 'cond_5g.xz',
          8: 'cond_wifi.xz', 9: 'cond_bt.xz', 11: 'sar_en.xz', 12: 'sar_fcc.xz'}


def comprobar_hojas(xlsm):
    z = zipfile.ZipFile(xlsm)
    wb = z.read('xl/workbook.xml').decode('utf8')
    rels = z.read('xl/_rels/workbook.xml.rels').decode('utf8')
    tg = {re.search(r'Id="([^"]+)"', r).group(1): re.search(r'Target="([^"]+)"', r).group(1)
          for r in re.findall(r'<Relationship [^>]*>', rels)}
    for m in re.finditer(r'<sheet [^>]*/>', wb):
        t = m.group(0); nombre = re.search(r'name="([^"]*)"', t).group(1)
        n = int(re.search(r'sheet(\d+)\.xml', tg[re.search(r'r:id="([^"]*)"', t).group(1)]).group(1))
        if n in ESPERADO and ESPERADO[n] != nombre:
            sys.exit(f'El datasheet no coincide con lo esperado: sheet{n} es "{nombre}" y debería ser "{ESPERADO[n]}". '
                     'Hay que adaptar ESPERADO/construir_base.py.')


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    xlsm = os.path.abspath(sys.argv[1])
    aqui = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(os.path.dirname(aqui), 'plantilla')
    os.makedirs(out, exist_ok=True)
    comprobar_hojas(xlsm)
    env = dict(os.environ, DATASHEET_XLSM=xlsm)
    subprocess.check_call([sys.executable, os.path.join(aqui, 'construir_base.py'), os.path.join(out, 'plantilla_base.zip')], env=env)
    procs = []
    for n, f in SALIDA.items():
        procs.append((f, subprocess.Popen([sys.executable, os.path.join(aqui, 'extraer_hoja.py'),
                                           f'xl/worksheets/sheet{n}.xml', ESPERADO[n], os.path.join(out, f)], env=env)))
    for f, p in procs:
        if p.wait() != 0:
            sys.exit(f'Falló la extracción de {f}')
    print('Plantilla regenerada en', out)


if __name__ == '__main__':
    main()
