"""Casos reales eliminados por Excel: COLUMN no admite el valor de una celda."""
import json
import lzma
from pathlib import Path
import re
import tempfile
import unittest
from zipfile import ZipFile

from lxml import etree as E
from base_datos import Catalogo
from generador_excel import generar
from herramientas.corregir_formulas_wifi import referencias_originales, reparar
from herramientas.validar_paquete import validar
from referencias_geometricas import errores_referencia
from tecnologias_originales import PlanOriginal, formula
from sarlib import tokenize, expand

ROOT=Path(__file__).resolve().parents[1]
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


class ReferenciasTests(unittest.TestCase):
    def plan(self):
        p=PlanOriginal('Conducted WiFi','Conducted WiFi',Path(),'',b'',100,None,Path(),{},[])
        p.rows={1:[101],2:[102],10:[110]};p.sorted=sorted(p.rows)
        p.cache={('B',5):'FCC/ISED',('G',5):1}
        return p

    def test_column_conserva_numero_aunque_fila_descartada_tenga_certificacion(self):
        p=self.plan()
        result=formula('COLUMN(B5)+COLUMN(G5)',p,10,110,{p.familia:p})
        self.assertEqual(result,'COLUMN(B1)+COLUMN(G1)')
        self.assertEqual(errores_referencia(result),[])
        self.assertEqual(formula('B5',p,10,110,{p.familia:p}),'"FCC/ISED"')

    def test_no_modifica_textos_ni_necesita_una_hoja_eliminada_para_column(self):
        p=self.plan()
        text='IF(CF10="COLUMN(B5)",COLUMN(\'Conducted LTE\'!$G$900),COLUMN())'
        self.assertEqual(formula(text,p,10,110,{p.familia:p}),
                         'IF(CF110="COLUMN(B5)",COLUMN($G1),COLUMN())')

    def test_column_valida_conserva_su_reubicacion_anterior(self):
        p=self.plan()
        self.assertEqual(formula('COLUMN(B1)+COLUMN($G$2)',p,10,110,{p.familia:p}),
                         'COLUMN(B101)+COLUMN($G$102)')

    def test_validador_distingue_referencia_de_texto_y_numero(self):
        for text in ['COLUMN(1)','COLUMN("EN")','COLUMN("")','ROW(2)','COLUMN("Texto (1)")']:
            self.assertTrue(errores_referencia(text),text)
        for text in ['COLUMN(A1)','COLUMN()','COLUMN(INDIRECT("A1"))','"COLUMN(1)"']:
            self.assertEqual(errores_referencia(text),[],text)

    def test_patron_compacto_no_incrusta_valores_en_column(self):
        pat=tokenize('COLUMN(B5)+COLUMN($G$5)',10)
        text=expand(pat,10,lambda sheet,row,role:None,'Conducted WiFi',
                    inline=lambda *args:'"FCC/ISED"')
        self.assertEqual(text,'COLUMN(B1)+COLUMN($G1)')
        self.assertEqual(expand(pat,10,lambda sheet,row,role:row+100,'Conducted WiFi'),
                         'COLUMN(B105)+COLUMN($G$105)')


class ReparacionRealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(lzma.decompress((ROOT/'tests/fixtures/reparacion_wifi_05_11.json.xz').read_bytes()))
        cls.references=referencias_originales()

    def test_detecta_exactamente_las_1382_celdas_eliminadas_por_excel(self):
        detected={ref for ref,f in self.data['formulas'].items() if errores_referencia(f)}
        self.assertEqual(len(detected),1382)
        self.assertEqual(detected,set(self.data['eliminadas']))

    def test_repara_las_eliminadas_y_deja_intactas_las_8328_conservadas(self):
        removed=set(self.data['eliminadas'])
        healthy=0
        for ref,text in self.data['formulas'].items():
            column=re.sub(r'\d','',ref)
            corrected=reparar(text,self.references[column]) if column in self.references else text
            self.assertEqual(errores_referencia(corrected),[],ref)
            if ref in removed:
                self.assertNotEqual(corrected,text,ref)
            else:
                self.assertEqual(corrected,text,ref);healthy+=1
        self.assertEqual(healthy,8328)


class GeneracionWifiTests(unittest.TestCase):
    def test_catalogo_y_formulario_no_generan_column_con_valores(self):
        data=dict(proyecto='Regresión WiFi COLUMN',region=['EN','FCC'],exposure=['Body'],
                  conducida=True,baterias=['B1','B2'],accesorios=['Funda'],spotchecking=[],
                  tecnologias={'WLAN':{'2,4 GHz':['ac20'],'5 GHz':{'bandas':['U-NII-2C'],'modos':['ac20','ac40']}}})
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'wifi.xlsm'
            generar(data,output,catalogo=Catalogo(),log=lambda *_:None)
            self.assertEqual(validar(output,verbose=False),[])
            count=0
            with ZipFile(output) as z:
                root=E.fromstring(z.read('xl/worksheets/sheet8.xml'))
                for f in root.findall('.//s:f',NS):
                    if f.text and 'COLUMN(' in f.text:
                        count+=1
                        self.assertEqual(errores_referencia(f.text),[])
                self.assertGreater(count,0)


if __name__=='__main__':unittest.main()
