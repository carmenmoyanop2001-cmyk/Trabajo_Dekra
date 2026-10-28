# -*- coding: utf-8 -*-
"""Construye plantilla_base.zip: partes del paquete original que el generador reutiliza."""
import os, zipfile, re, posixpath, json, sys
Z = os.environ['DATASHEET_XLSM']      # ruta del datasheet original (.xlsm)
OUT = sys.argv[1] if len(sys.argv) > 1 else 'plantilla_base.zip'
z = zipfile.ZipFile(Z); names = z.namelist()
FULL = {1: 'Overview', 2: 'Tune-Up', 13: 'Test Campaign'}                       # hojas copiadas enteras
GRANDES = {3: 'Conducted 2G-3G', 4: 'Conducted LTE', 5: 'Conducted LTE CATM1', 6: 'Conducted LTE NB-IoT',
           7: 'Conducted 5G', 8: 'Conducted WiFi', 9: 'Conducted BT-Custom', 11: 'SAR EN', 12: 'SAR FCC-ISED'}
def rels_of(part):
    d, b = posixpath.split(part); rp = posixpath.join(d, '_rels', b + '.rels')
    if rp not in names: return None, []
    x = z.read(rp).decode('utf8'); out = []
    for m in re.finditer(r'<Relationship [^>]*/>', x):
        t = m.group(0)
        if 'External' in t: continue
        out.append(posixpath.normpath(posixpath.join(d, re.search(r'Target="([^"]*)"', t).group(1))))
    return rp, out
def owned(n):
    sp = f'xl/worksheets/sheet{n}.xml'; rp, tg = rels_of(sp); parts = [rp] if rp else []
    for t in tg:
        parts.append(t); r2, t2 = rels_of(t)
        if r2: parts.append(r2); parts += t2
    return parts
ct = z.read('[Content_Types].xml').decode('utf8')
defaults = dict(re.findall(r'<Default Extension="([^"]+)" ContentType="([^"]+)"/>', ct))
overrides = dict(re.findall(r'<Override PartName="([^"]+)" ContentType="([^"]+)"/>', ct))
GLOBAL = ['_rels/.rels', 'xl/workbook.xml', 'xl/_rels/workbook.xml.rels', 'xl/theme/theme1.xml', 'xl/styles.xml', 'xl/sharedStrings.xml', 'xl/vbaProject.bin',
          'xl/featurePropertyBag/featurePropertyBag.xml', 'docProps/core.xml']
manifest = dict(defaults=defaults, overrides=overrides, full=FULL, grandes=GRANDES, owned={}, global_parts=GLOBAL)
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zo:
    for p in GLOBAL: zo.writestr(p, z.read(p))
    for n in list(FULL) + list(GRANDES):
        parts = owned(n)
        if n in FULL: zo.writestr(f'xl/worksheets/sheet{n}.xml', z.read(f'xl/worksheets/sheet{n}.xml'))
        for p in parts:
            if p not in zo.namelist(): zo.writestr(p, z.read(p))
        manifest['owned'][str(n)] = parts
    zo.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
import os; print('base:', os.path.getsize(OUT) // 1024, 'KB', len(manifest['owned']), 'hojas')
