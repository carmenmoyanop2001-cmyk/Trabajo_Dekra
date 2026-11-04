"""Instala solo la corrección de fechas 2G-3G en una copia existente del programa."""
from pathlib import Path
import shutil
import sys


def actualizar(folder, helper=None):
    folder=Path(folder).resolve()
    helper=Path(helper) if helper else Path(__file__).with_name('corregir_2g3g.py')
    if not helper.exists():
        helper=Path(__file__).resolve().parents[1]/'corregir_2g3g.py'
    paths=[folder/'generador_excel.py',folder/'tecnologias_originales.py',folder/'presentacion_tecnologias.py']
    if not all(p.is_file() for p in paths):
        raise ValueError('Copia los archivos del parche en la carpeta que contiene generador_excel.py y tecnologias_originales.py.')
    changes={}
    for p in paths:
        raw=p.read_bytes();bom=raw.startswith(b'\xef\xbb\xbf');newline='\r\n' if b'\r\n' in raw else '\n'
        text=raw.decode('utf-8-sig').replace('\r\n','\n')
        original=text
        def replace(old,new):
            nonlocal text
            if text.count(old)!=1:
                raise ValueError(f'{p.name}: versión no reconocida. No se ha modificado ningún archivo.')
            text=text.replace(old,new,1)
        if p.name=='generador_excel.py':
            if 'from corregir_2g3g import corregir_en_sitio' not in text:
                replace("        if not datos['conducida']:","        from corregir_2g3g import corregir_en_sitio\n        corregir_en_sitio(candidate)\n        if not datos['conducida']:")
        elif p.name=='tecnologias_originales.py':
            if 'from corregir_2g3g import normalizar_fechas' not in text:
                replace('from seleccion import token_modo','from seleccion import token_modo\nfrom corregir_2g3g import normalizar_fechas')
                replace("                    for row in backend:\n                        row.set('hidden', '1')", "                    for row in backend:\n                        if plan.familia == 'Conducted 2G-3G':\n                            normalizar_fechas(row)\n                        row.set('hidden', '1')")
                replace("                        row[:] = sorted(row, key=lambda c: col2n(_col(c)))\n                        writer.write(row)","                        row[:] = sorted(row, key=lambda c: col2n(_col(c)))\n                        if plan.familia == 'Conducted 2G-3G':\n                            normalizar_fechas(row)\n                        writer.write(row)")
                if 'def verificar_apoyo(' in text:
                    replace("    original = E.fromstring(plan.backend).find('s:sheetData', NS)\n    expected", "    original = E.fromstring(plan.backend).find('s:sheetData', NS)\n    if plan.familia == 'Conducted 2G-3G':\n        normalizar_fechas(original)\n    expected")
            if '    candidate.replace(plan.spool)' in text:
                replace('    candidate.replace(plan.spool)', "    # En Windows/SMB el archivo anterior puede estar bloqueado para renombrar.\n    # Los consumidores leen plan.spool: basta con apuntar al ordenado.\n    plan.spool=candidate")
            elif '    plan.spool=candidate' not in text:
                raise ValueError(f'{p.name}: ordenación no reconocida; no se ha modificado ningún archivo.')
        else:
            old="with tempfile.TemporaryDirectory(dir=Path(path).parent) as tmp, zipfile.ZipFile(path) as source:"
            new="with tempfile.TemporaryDirectory(prefix='sar_tecnologias_') as tmp, zipfile.ZipFile(path) as source:"
            if old in text:
                replace(old,new)
            elif new not in text:
                raise ValueError(f'{p.name}: temporales no reconocidos; no se ha modificado ningún archivo.')
        if text!=original:
            compile(text,str(p),'exec')
            changes[p]=(b'\xef\xbb\xbf' if bom else b'')+text.replace('\n',newline).encode('utf-8')
    helper_bytes=helper.read_bytes()
    compile(helper_bytes.decode('utf-8'),str(helper),'exec')
    destination=folder/'corregir_2g3g.py'
    if not destination.exists() or destination.read_bytes()!=helper_bytes:
        changes[destination]=helper_bytes
    for p,data in changes.items():
        backup=p.with_name(p.name+'.antes_2g3g')
        if p.exists() and not backup.exists():shutil.copy2(p,backup)
    for p,data in changes.items():
        tmp=p.with_name(p.name+'.tmp_2g3g');tmp.write_bytes(data);tmp.replace(p)
    return [p.name for p in changes]


if __name__=='__main__':
    try:
        folder=Path(sys.argv[1]) if len(sys.argv)>1 else Path.cwd()
        if len(sys.argv)==1 and not (folder/'generador_excel.py').is_file():
            try:
                import tkinter as tk
                from tkinter import filedialog
                window=tk.Tk();window.withdraw()
                selected=filedialog.askdirectory(title='Selecciona la carpeta del programa: contiene cuestionario_ensayo.py')
                window.destroy()
            except ImportError:
                selected=input('Ruta de la carpeta del programa: ').strip().strip(chr(34))
            if not selected:
                print('Instalación cancelada. No se ha modificado ningún archivo.')
                raise SystemExit(0)
            folder=Path(selected)
        changed=actualizar(folder)
        print('Corrección 2G-3G instalada.' if changed else 'La corrección 2G-3G ya estaba instalada.')
        for name in changed:print('  '+name)
        print('Puedes iniciar el cuestionario como antes. Se han guardado copias .antes_2g3g de los archivos actualizados.')
    except Exception as error:
        print('No se ha podido instalar: '+str(error),file=sys.stderr)
        raise SystemExit(1)
