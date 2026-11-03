"""Incorpora la hoja 5G íntegra conservada antes de dividir los adjuntos.

El adjunto 5G recibido solo tiene n1. El compacto original guarda las 25
bandas/variantes, todas sus filas, constantes, fórmulas y presentación.
No cambia ninguna plantilla usada por SAR ni la copia del adjunto recibido.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import re
import lzma
import struct

from lxml import etree as E

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nucleo import Hoja, _cell_xml, _attr_str
from sarlib import T1, T2, n2col, _fmt_sheet


class CompresorPreparacion(zipfile.LZMACompressor):
    """ZIP-LZMA estándar con nivel 3, apropiado para preparar hojas muy grandes."""
    def _init(self):
        filtro = {'id': lzma.FILTER_LZMA1, 'preset': 3}
        props = lzma._encode_filter_properties(filtro)
        self._comp = lzma.LZMACompressor(lzma.FORMAT_RAW, filters=[filtro])
        return struct.pack('<BBH',9,4,len(props)) + props


def formulas_identidad(patterns):
    token = re.compile(re.escape(T1) + r'([^|]*)\|([^|]*)\|([ra]):(-?\d+)' + re.escape(T2))
    compiled = []
    for pattern in patterns:
        parts, at = [], 0
        for m in token.finditer(pattern):
            parts.append(pattern[at:m.start()])
            parts.append((_fmt_sheet(m[1]) + m[2], m[3], int(m[4])))
            at = m.end()
        parts.append(pattern[at:])
        compiled.append(parts)
    return compiled


def fila_original(h, index, compiled):
    old, tid, constants, aid, metadata = h.rows[index]
    values = iter(constants)
    cached = {col: h.cpool[i][1] for col, i in metadata}
    cells = []
    for ci, style, kind, payload in h.templates[tid]:
        col = n2col(ci)
        value = h.cpool[next(values)][1] if kind in (1,2,9,10) else None
        cache = None
        if kind == 3:
            value = ''.join(piece if isinstance(piece,str) else piece[0] +
                ('$' + str(piece[2]) if piece[1]=='a' else str(old+piece[2])) for piece in compiled[payload])
            cache = cached.get(col, h.sd.get('formula_cache',{}).get(old,{}).get(col))
        cells.append(_cell_xml(col, old, style, kind, value, cache))
    return f'<row r="{old}"{_attr_str(h.attrs[aid])}>' + ''.join(cells) + '</row>'


def completar(root):
    carpeta = root / 'plantilla/originales'
    path = carpeta / 'inventario.json'
    inventario = json.loads(path.read_text(encoding='utf-8'))
    anterior = inventario['pestanas']['Conducted 5G']
    h = Hoja(root / 'plantilla/cond_5g.xz')
    compiled = formulas_identidad(h.patterns)
    salida = carpeta / '5g_completo.zip'
    parts = {}
    with zipfile.ZipFile(root / 'plantilla/plantilla_base.zip') as base, zipfile.ZipFile(salida, 'w', zipfile.ZIP_LZMA) as out:
        manifest = json.loads(base.read('manifest.json'))
        number = next(n for n, name in manifest['grandes'].items() if name == h.name)
        part = f'xl/worksheets/sheet{number}.xml'
        for info in base.infolist():
            if info.filename == 'manifest.json':
                continue
            data = base.read(info.filename)
            copied = deepcopy(info)
            copied.compress_type = zipfile.ZIP_LZMA
            out.writestr(copied, data)
            parts[info.filename] = hashlib.sha256(data).hexdigest()
        ct = E.Element('{http://schemas.openxmlformats.org/package/2006/content-types}Types',
                       nsmap={None:'http://schemas.openxmlformats.org/package/2006/content-types'})
        for ext, content in manifest['defaults'].items():
            E.SubElement(ct, '{http://schemas.openxmlformats.org/package/2006/content-types}Default', Extension=ext, ContentType=content)
        for name, content in manifest['overrides'].items():
            if name.lstrip('/') in out.namelist() or name.lstrip('/') == part:
                E.SubElement(ct, '{http://schemas.openxmlformats.org/package/2006/content-types}Override', PartName=name, ContentType=content)
        ct_data = E.tostring(ct, encoding='UTF-8', xml_declaration=True, standalone=True)
        out.writestr('[Content_Types].xml', ct_data)
        parts['[Content_Types].xml'] = hashlib.sha256(ct_data).hexdigest()
        sha, size = hashlib.sha256(), 0
        with out.open(part, 'w', force_zip64=True) as stream:
            def escribir(text):
                nonlocal size
                data = text.encode('utf-8')
                stream.write(data)
                sha.update(data)
                size += len(data)
            escribir(h.sd['head'] + '<sheetData>')
            for i, row in enumerate(h.rows):
                escribir(fila_original(h, i, compiled))
                if i and i % 20000 == 0:
                    print(i, 'filas de 5G conservadas', flush=True)
            escribir(h.sd['tail'])
        parts[part] = sha.hexdigest()
    inventario['archivos'][salida.name] = dict(origen='plantilla/cond_5g.xz + plantilla_base.zip (original íntegro previamente guardado)', partes=parts)
    inventario['pestanas']['Conducted 5G'] = dict(archivo=salida.name, parte=part, bytes=size,
        filas=len(h.rows), copia_del_adjunto=anterior)
    path.write_text(json.dumps(inventario, ensure_ascii=False, indent=2), encoding='utf-8')
    print('5G completa incorporada:',len(h.rows),'filas;',salida.stat().st_size,'bytes',flush=True)


if __name__ == '__main__':
    # Solo cambia la compresión durante esta preparación. Los lectores no
    # necesitan código especial: las propiedades quedan en la cabecera ZIP.
    zipfile.LZMACompressor = CompresorPreparacion
    completar(Path(__file__).resolve().parents[1])
