"""Guarda sin pérdida todas las partes de los originales recibidos.

Uso de preparación: python herramientas/guardar_originales_completos.py carpeta_adjuntos
La generación normal solo necesita las copias incorporadas en plantilla/originales.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from lxml import etree as E

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ARCHIVOS = {'2G_3G': '2g3g', 'LTE': 'lte', 'LTE_CATM1': 'catm1',
            'LTE_NB_IoT': 'nbiot', '5G': '5g', 'WiFi': 'wifi', 'BT': 'bt',
            'SAR_EN': 'sar_en', 'SAR_FCC': 'sar_fcc', 'Resto': 'resto'}


def guardar(carpeta, destino):
    destino.mkdir(parents=True, exist_ok=True)
    inventario = {'archivos': {}, 'pestanas': {}}
    entradas = []
    if carpeta.is_file():
        entradas.append((carpeta, 'original_completo'))
    else:
        for sufijo, clave in ARCHIVOS.items():
            matches = list(carpeta.glob('**/FAN22_09 - SAR Datasheet_Original_' + sufijo + '.xlsm'))
            if len(matches)>1 and len({hashlib.sha256(p.read_bytes()).hexdigest() for p in matches})==1:
                matches=matches[:1]
            if len(matches) != 1:
                raise ValueError(f'No se encontró un único original para {sufijo}.')
            entradas.append((matches[0], clave))
    for path, clave in entradas:
        salida = destino / (clave + '.zip')
        partes = {}
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(salida, 'w', zipfile.ZIP_LZMA) as out:
            for info in source.infolist():
                h = hashlib.sha256()
                copied = deepcopy(info)
                copied.compress_type = zipfile.ZIP_LZMA
                with source.open(info) as src, out.open(copied, 'w', force_zip64=True) as dst:
                    while chunk := src.read(1024 * 1024):
                        h.update(chunk)
                        dst.write(chunk)
                partes[info.filename] = h.hexdigest()
            wb = E.fromstring(source.read('xl/workbook.xml'))
            rels = {r.get('Id'): r.get('Target') for r in E.fromstring(source.read('xl/_rels/workbook.xml.rels'))}
            for s in wb.find('{' + M + '}sheets'):
                target = rels[s.get('{' + R + '}id')]
                part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
                size = source.getinfo(part).file_size
                old = inventario['pestanas'].get(s.get('name'))
                # Los archivos divididos dejan vacías las otras tecnologías.
                if old is None or size > old['bytes']:
                    inventario['pestanas'][s.get('name')] = dict(archivo=salida.name, parte=part, bytes=size)
        inventario['archivos'][salida.name] = dict(origen=path.name, partes=partes)
        print(salida.name, round(salida.stat().st_size / 1024**2, 2), 'MiB', flush=True)
    (destino / 'inventario.json').write_text(json.dumps(inventario, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    guardar(Path(sys.argv[1]), root / 'plantilla/originales')
