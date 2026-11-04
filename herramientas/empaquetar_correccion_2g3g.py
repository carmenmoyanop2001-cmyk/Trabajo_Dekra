"""Crear el parche pequeño sin incluir ni reemplazar el resto del programa."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]


def empaquetar():
    files={
        'Proyecto_2G_3G_corregido.xlsm':ROOT/'entregas/Proyecto_2G_3G_corregido.xlsm',
        'corregir_2g3g.py':ROOT/'corregir_2g3g.py',
        'actualizar_programa_2g3g.py':ROOT/'herramientas/actualizar_programa_2g3g.py',
        'APLICAR_CORRECCION_2G_3G.bat':ROOT/'herramientas/APLICAR_CORRECCION_2G_3G.bat',
        'LEEME.txt':ROOT/'docs/LEEME_CORRECCION_2G3G.txt',
    }
    out=ROOT/'entregas/Correccion_2G_3G.zip'
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for name,path in files.items():
            data=path.read_bytes()
            if name.endswith('.bat'):data=data.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
            z.writestr(name,data)
    with ZipFile(out) as z:
        assert z.testzip() is None
    print(out,'—',round(out.stat().st_size/1048576,2),'MiB')
    return out

if __name__=='__main__':empaquetar()
