"""Cambiar los títulos de tecnologías sin perder los enlaces del libro."""
from pathlib import Path
import os
import zipfile
from lxml import etree


def renombrar_tecnologias(path, names):
    """Conserva las partes del paquete y actualiza títulos y referencias A1/INDIRECT.

    Las hojas grandes se procesan por bloques para no cargar todo su XML en memoria.
    El proyecto VBA, los estilos y las relaciones entre partes se copian sin cambios.
    """
    replacements = []
    for old, new in names.items():
        reference = ("'" + new.replace("'", "''") + "'!").encode()
        replacements.append((f"'{old}'!".encode(), reference))
        replacements.append((f'&apos;{old}&apos;!'.encode(), reference))
    tail_size = max(len(old) for old, _ in replacements)
    dest = Path(path).with_name('renombrado.xlsm')
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as out:
        for entry in source.infolist():
            if entry.filename in ('xl/workbook.xml', 'docProps/app.xml'):
                root = etree.fromstring(source.read(entry.filename))
                for el in root.iter():
                    if el.tag.endswith('}sheet') and el.get('name') in names:
                        el.set('name', names[el.get('name')])
                    if el.tag.endswith('}lpstr') and el.text in names:
                        el.text = names[el.text]
                data = etree.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
                for old, new in replacements:
                    data = data.replace(old, new)
                out.writestr(entry, data)
            elif entry.filename.endswith('.xml'):
                with source.open(entry) as src, out.open(entry, 'w', force_zip64=True) as dst:
                    pending = b''
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            dst.write(pending)
                            break
                        pending += chunk
                        for old, new in replacements:
                            pending = pending.replace(old, new)
                        if len(pending) > tail_size:
                            dst.write(pending[:-tail_size])
                            pending = pending[-tail_size:]
            else:
                with source.open(entry) as src, out.open(entry, 'w', force_zip64=True) as dst:
                    while chunk := src.read(1 << 20):
                        dst.write(chunk)
    os.replace(dest, path)


def renombrar_resumen(summary, names):
    def name(value):
        for old in sorted(names, key=len, reverse=True):
            value = value.replace(old, names[old])
        return value
    summary['hojas'] = [names.get(s, s) for s in summary['hojas']]
    for key in ('filas', 'sin_resolver', 'valores_por_defecto', 'ejemplos',
                'sin_resolver_cols', 'referencias_rotas_plantilla'):
        summary[key] = {name(k): v for k, v in summary[key].items()}
    summary['avisos'] = [name(w) for w in summary['avisos']]
