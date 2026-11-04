"""No renombrar temporales que Windows/SMB puede mantener bloqueados."""
import ast
from copy import deepcopy
from pathlib import Path
import pickle
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from generador_excel import generar
from tecnologias_originales import PlanOriginal,_ordenar_filas

ROOT=Path(__file__).resolve().parents[1]


def legacy_sort():
    source=subprocess.check_output(['git','show','94b0830:tecnologias_originales.py'],cwd=ROOT).decode()
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_ordenar_filas')
    scope={'pickle':pickle}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'ordenacion_anterior','exec'),scope)
    return scope['_ordenar_filas']


def plan(folder):
    result=PlanOriginal('Conducted WiFi','Conducted WiFi',Path(),'',b'',10,None,folder/'wifi.zip.filas',{},[])
    result.grupos={11:('WLAN','2.4 GHz'),12:('WLAN','2.4 GHz'),14:('WLAN','nueva')}
    result.nuevos_grupos={14};result.fallback_rows={14};result.view_rows={0:[11,12],1:[14]}
    with result.spool.open('wb') as stream:
        for row in [(9,11,b'fila 9'),(3,12,b'fila 3'),(1,13,b'cabecera'),(3,14,b'banda nueva')]:
            pickle.dump(row,stream,protocol=4)
    return result


class OrdenacionWindowsTests(unittest.TestCase):
    def test_archivo_anterior_abierto_no_requiere_reemplazarlo(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=plan(Path(tmp));old=p.spool
            with old.open('rb') as locked,patch.object(Path,'replace',side_effect=PermissionError('[WinError 5] Acceso denegado')) as rename:
                _ordenar_filas(p)
                self.assertFalse(locked.closed)
                rename.assert_not_called()
                self.assertTrue(p.spool.exists())
                self.assertEqual(p.spool.suffix,'.ordenadas')
                self.assertEqual(p.rows,{1:[11],3:[12,14],9:[13]})

    def test_bytes_y_asignaciones_iguales_a_ordenacion_anterior(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            old,new=plan(Path(a)),plan(Path(b))
            legacy_sort()(old);_ordenar_filas(new)
            self.assertEqual(old.spool.read_bytes(),new.spool.read_bytes())
            for field in ('rows','grupos','fallback_rows','nuevos_grupos','view_rows'):
                self.assertEqual(getattr(old,field),getattr(new,field),field)

    def test_generacion_wifi_y_2g_no_cambia_ninguna_parte_del_excel(self):
        data=dict(proyecto='Temporales Windows',region=['FCC'],exposure=['Body'],
                  conducida=True,baterias=[],accesorios=[],spotchecking=[],
                  tecnologias={'2G':{'GSM':True},'WLAN':{'2,4 GHz':['b']}})
        with tempfile.TemporaryDirectory() as tmp:
            old,new=Path(tmp)/'antes.xlsm',Path(tmp)/'despues.xlsm'
            with patch('tecnologias_originales._ordenar_filas',legacy_sort()):
                generar(data,old,log=lambda *_:None)
            original=tempfile.TemporaryDirectory;calls=[]
            def working(*args,**kwargs):
                if kwargs.get('prefix')=='sar_tecnologias_':calls.append(kwargs)
                return original(*args,**kwargs)
            with patch('presentacion_tecnologias.tempfile.TemporaryDirectory',working):
                generar(data,new,log=lambda *_:None)
            self.assertTrue(calls)
            self.assertTrue(all('dir' not in call for call in calls))
            with ZipFile(old) as a,ZipFile(new) as b:
                self.assertEqual(set(a.namelist()),set(b.namelist()))
                for part in a.namelist():self.assertEqual(a.read(part),b.read(part),part)

if __name__=='__main__':unittest.main()
