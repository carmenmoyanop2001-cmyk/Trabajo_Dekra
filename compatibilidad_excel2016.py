"""Crear una copia de prueba con cálculo en un hilo, sin cambiar hojas ni VBA.

No acredita que un cierre de Excel esté corregido: permite contrastar el
recálculo paralelo conservando todas las demás características del libro.
Solo utiliza la biblioteca estándar de Python.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
WORKBOOK = 'xl/workbook.xml'
_CALC = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?calcPr\b[^<>]*/\s*>')
_CONCURRENT = re.compile(rb'(?<![\w:.-])concurrentCalc\s*=\s*([\x22\x27])[^\x22\x27]*\1')


def ajustar_calculo(xml):
    """Cambiar únicamente concurrentCalc; no serializar el resto de workbook."""
    before = ET.fromstring(xml)
    nodes = before.findall('{' + NS + '}calcPr')
    tags = list(_CALC.finditer(xml))
    if len(nodes) != 1 or len(tags) != 1:
        raise ValueError('El libro no tiene la configuración de cálculo esperada. No se ha modificado.')
    tag = tags[0]
    if _CONCURRENT.search(tag[0]):
        changed = _CONCURRENT.sub(b'concurrentCalc="0"', tag[0], count=1)
    else:
        changed = re.sub(rb'/\s*>$', b' concurrentCalc="0"/>', tag[0])
    result = xml[:tag.start()] + changed + xml[tag.end():]
    after = ET.fromstring(result).find('{' + NS + '}calcPr')
    old_attributes = dict(nodes[0].attrib)
    new_attributes = dict(after.attrib)
    if new_attributes.pop('concurrentCalc') != '0':
        raise ValueError('No se ha podido ajustar el cálculo de la copia.')
    old_attributes.pop('concurrentCalc', None)
    if old_attributes != new_attributes:
        raise ValueError('El ajuste intentó cambiar otras opciones de cálculo.')
    return result


def _sha(stream):
    digest = hashlib.sha256()
    while data := stream.read(1024 * 1024):
        digest.update(data)
    return digest.hexdigest()


def _nombre_copia(entrada):
    stem = entrada.stem + '_compatibilidad'
    candidate = entrada.with_name(stem + entrada.suffix)
    number = 2
    while candidate.exists():
        candidate = entrada.with_name(stem + '_' + str(number) + entrada.suffix)
        number += 1
    return candidate


def crear_copia(entrada, salida=None):
    """Crear un archivo nuevo; rechazar la sobrescritura incluso por enlace."""
    entrada = Path(entrada).resolve()
    if entrada.suffix.lower() != '.xlsm':
        raise ValueError('Selecciona el archivo .xlsm recién generado por el programa.')
    salida = Path(salida).resolve() if salida is not None else _nombre_copia(entrada)
    if salida == entrada or salida.exists():
        raise ValueError('La salida ya existe. Se conserva tanto el original como cualquier copia anterior.')
    with entrada.open('rb') as f:
        source_sha = _sha(f)
    with tempfile.TemporaryDirectory(prefix='sar_calculo_compatible_') as tmp:
        candidate = Path(tmp) / 'copia.xlsm'
        with ZipFile(entrada) as source, ZipFile(candidate, 'w') as target:
            old_xml = source.read(WORKBOOK)
            xml = ajustar_calculo(old_xml)
            if len(source.namelist()) != len(set(source.namelist())):
                raise ValueError('El archivo tiene partes duplicadas. Se conserva sin modificar.')
            for info in source.infolist():
                copied = deepcopy(info)
                if info.filename == WORKBOOK:
                    target.writestr(copied, xml)
                else:
                    with source.open(info) as src, target.open(copied, 'w') as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
        # Comparación real del contenido de cada parte, sin confiar solo en CRC.
        with ZipFile(entrada) as source, ZipFile(candidate) as target:
            if set(source.namelist()) != set(target.namelist()):
                raise ValueError('La copia intentó añadir o quitar partes del libro.')
            for info in source.infolist():
                if info.filename == WORKBOOK:
                    continue
                with source.open(info) as src, target.open(info.filename) as dst:
                    if _sha(src) != _sha(dst):
                        raise ValueError('La copia intentó cambiar contenido del libro: ' + info.filename)
        with entrada.open('rb') as f:
            if _sha(f) != source_sha:
                raise ValueError('El archivo original cambió durante la lectura. Cierra Excel y repite la operación.')
        # 'xb' impide sobrescribir un archivo creado mientras se preparaba la copia.
        with salida.open('xb') as dst:
            try:
                with candidate.open('rb') as src:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
            except BaseException:
                dst.close()
                salida.unlink(missing_ok=True)
                raise
    return salida


def main():
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('entrada', type=Path)
        parser.add_argument('salida', type=Path, nargs='?')
        args = parser.parse_args()
        print(crear_copia(args.entrada, args.salida))
        return
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        chosen = filedialog.askopenfilename(parent=root, title='Selecciona el Excel que se cierra al editar AI',
            filetypes=[('Libro Excel con macros', '*.xlsm')])
        if not chosen:
            return
        output = crear_copia(chosen)
        messagebox.showinfo('Copia preparada',
            'Se ha creado esta copia de prueba:\n\n' + str(output) +
            '\n\nCierra Excel y abre la copia para probar la columna AI.\n'
            'Las hojas, fórmulas, formatos y macros conservan su contenido.\n'
            'El archivo original se conserva.', parent=root)
    except Exception as exc:
        messagebox.showerror('No se ha podido preparar la copia', str(exc), parent=root)
    finally:
        root.destroy()


if __name__ == '__main__':
    main()
