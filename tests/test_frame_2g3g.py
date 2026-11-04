"""Corrección acotada a las fechas de 2G-3G al editar potencias AI/AH."""
from copy import deepcopy
from pathlib import Path
import ast
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

from lxml import etree as E

from corregir_2g3g import normalizar_fechas,corregir_en_sitio
from herramientas.actualizar_programa_2g3g import actualizar
from herramientas.validar_paquete import validar
from tecnologias_originales import _inline,_strings,_col
from generador_excel import generar

ROOT=Path(__file__).resolve().parents[1]
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


class FechasNativasTests(unittest.TestCase):
    def test_cero_negativos_y_referencias_son_entradas_validas(self):
        for ref in ('AI75','$AI$79','AH340'):
            root=E.fromstring(f'<row xmlns="{NS["s"]}" r="75"><c r="BE75" t="str"><f>MyTimestamp({ref})</f><v/></c><c r="AJ75"><f>AI75+$CL$74</f></c></row>')
            self.assertEqual(normalizar_fechas(root),1)
            text=root.find('s:c/s:f',NS).text
            self.assertEqual(text,f'IF({ref}<>"",TEXT(NOW(),"[$-409]yyyy-mm-dd hh:mm:ss"),"")')
            self.assertEqual(root.find('s:c[@r="AJ75"]/s:f',NS).text,'AI75+$CL$74')
            self.assertEqual(normalizar_fechas(root),0)

    def test_compartidas_conservan_rangos_y_se_desplazan(self):
        root=E.fromstring(f'<worksheet xmlns="{NS["s"]}"><sheetData><row r="75"><c r="BE75" t="str"><f t="shared" si="1" ref="BE75:BE76">MyTimestamp(AI75)</f><v/></c></row><row r="76"><c r="BE76" t="str"><f t="shared" si="1"/><v/></c></row></sheetData></worksheet>')
        self.assertEqual(normalizar_fechas(root),1)
        master=root.find('.//s:f',NS)
        self.assertEqual(master.attrib,{'t':'shared','si':'1','ref':'BE75:BE76'})
        shared={}
        for row in root.findall('s:sheetData/s:row',NS):_inline(row,[],shared)
        self.assertIn('IF(AI76<>"",',root.find('.//s:c[@r="BE76"]/s:f',NS).text)

    def test_instalador_preserva_otros_metodos_y_es_idempotente(self):
        for version in ('9bb8aa0','bc7b062','2ba272b'):
            with self.subTest(version=version),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)
                originals={}
                for file in ['generador_excel.py','tecnologias_originales.py']:
                    data=subprocess.check_output(['git','show',version+':'+file],cwd=ROOT)
                    (folder/file).write_bytes(data);originals[file]=data.decode()
                helper=ROOT/'corregir_2g3g.py'
                changed=actualizar(folder,helper)
                self.assertEqual(set(changed),{'generador_excel.py','tecnologias_originales.py','corregir_2g3g.py'})
                self.assertEqual(actualizar(folder,helper),[])
                for file,src in originals.items():
                    before=ast.parse(src);after=ast.parse((folder/file).read_text())
                    allowed={'_publicar','escribir','verificar_apoyo'}
                    functions=lambda tree:{n.name:ast.dump(n) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name not in allowed}
                    self.assertEqual(functions(before),functions(after),file)
                    self.assertEqual((folder/(file+'.antes_2g3g')).read_text(),src)

    def test_version_desconocida_no_modifica_archivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for f in ['generador_excel.py','tecnologias_originales.py']:(p/f).write_text('x=1\n')
            with self.assertRaises(ValueError):actualizar(p,ROOT/'corregir_2g3g.py')
            self.assertEqual((p/'generador_excel.py').read_text(),'x=1\n')
            self.assertFalse((p/'corregir_2g3g.py').exists())


class Generacion2G3GTests(unittest.TestCase):
    def test_fechas_nativas_2g3g_y_sar_intacto(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'2g3g.xlsm'
            data=dict(proyecto='Prueba AI 2G3G',region=['FCC'],exposure=['Body'],
                      conducida=True,baterias=[],accesorios=[],spotchecking=[],
                      tecnologias={'2G':{'GSM':True,'GPRS':'TX2'},'3G':{'WCDMA':['FDDI']}})
            result=generar(data,output,log=lambda *_:None)
            self.assertIn('Conducted 2G-3G',result['hojas'])
            self.assertEqual(validar(output,verbose=False),[])
            with ZipFile(output) as z:
                root=E.fromstring(z.read('xl/worksheets/sheet3.xml'))
                formulas=[f.text or '' for f in root.findall('.//s:f',NS)]
                self.assertFalse(any('MyTimestamp(' in f for f in formulas))
                self.assertTrue(any('TEXT(NOW(),"[$-409]' in f for f in formulas))
                self.assertTrue(any('+$CL$' in f for f in formulas))
            self.assertEqual(corregir_en_sitio(output),0)

if __name__=='__main__':unittest.main()
