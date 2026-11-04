"""Fechas nativas de Excel para 2G-3G, sin invocar MyTimestamp al introducir potencias."""
from copy import deepcopy
from pathlib import Path
import os
import re
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
from posixpath import normpath

from lxml import etree as E

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
PATRON=re.compile(r'^\s*MyTimestamp\(\s*((?:(?:\x27[^\x27]+\x27|[A-Za-z_][\w.-]*)!)?\$?[A-Z]{1,3}\$?[1-9]\d*)\s*\)\s*$',re.I)


def normalizar_fechas(root):
    """Conservar la referencia de cada fecha, incluidos maestros compartidos.

    [$-409] hace que yyyy/mm/dd funcionen también en Excel en español. El
    resultado continúa siendo texto con el formato de la función VBA original.
    No se modifica el proyecto VBA ni ninguna fórmula de potencia.
    """
    changes=0
    for f in root.iter('{'+NS['s']+'}f'):
        match=PATRON.fullmatch(f.text or '')
        if match:
            ref=match[1]
            f.text=f'IF({ref}<>"",TEXT(NOW(),"[$-409]yyyy-mm-dd hh:mm:ss"),"")'
            changes+=1
    return changes


def es_2g3g(nombre):
    return nombre in {'Conducted 2G-3G','Conducted 2G','Conducted 3G','2G-3G','2G','3G'}


def corregir_en_sitio(path):
    """Cambiar solo el XML de las hojas 2G/3G y conservar las demás partes."""
    path=Path(path)
    changed={};total=0
    with ZipFile(path) as source:
        wb=E.fromstring(source.read('xl/workbook.xml'))
        rels={r.get('Id'):r.get('Target') for r in E.fromstring(source.read('xl/_rels/workbook.xml.rels'))}
        for sheet in wb.find('s:sheets',NS):
            if not es_2g3g(sheet.get('name')):
                continue
            target=rels[sheet.get(RID)]
            part=target.lstrip('/') if target.startswith('/') else normpath('xl/'+target)
            root=E.fromstring(source.read(part))
            count=normalizar_fechas(root)
            if count:
                changed[part]=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
                total+=count
        if not changed:
            return 0
        with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
            candidate=Path(tmp)/'corregido.xlsm'
            with ZipFile(candidate,'w',ZIP_DEFLATED) as out:
                for info in source.infolist():
                    out.writestr(deepcopy(info),changed.get(info.filename,source.read(info.filename)))
            with ZipFile(candidate) as result:
                for info in source.infolist():
                    if info.filename not in changed:
                        assert source.read(info.filename)==result.read(info.filename),info.filename
            # Cerrar el archivo de entrada antes de reemplazarlo en Windows.
            source.close()
            os.replace(candidate,path)
    return total


def main():
    import argparse,shutil
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entrada',type=Path)
    parser.add_argument('salida',type=Path)
    args=parser.parse_args()
    if args.entrada.resolve()==args.salida.resolve() or args.salida.exists():
        parser.error('Elige un nombre de salida nuevo para conservar el archivo original.')
    shutil.copy2(args.entrada,args.salida)
    print('Fórmulas de fecha adaptadas:',corregir_en_sitio(args.salida))
    print('Guardado:',args.salida)


if __name__=='__main__':main()
