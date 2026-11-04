"""Cuatro correcciones acotadas solicitadas el 4 de noviembre."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
from zipfile import ZipFile
from lxml import etree as E
from base_datos import Registro,Catalogo
from generador_excel import generar
from tecnologias_originales import coincidencias_especificas,_col,_value
from sar_en_canales import adaptar_formula
from comparacion_sar import sin_canales
from test_tecnologias_visibles import workbook

ROOT=Path(__file__).resolve().parents[1]
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

class FormulasYDuplicadosTests(unittest.TestCase):
    def test_resumen_no_duplica_el_detalle_de_la_misma_fila(self):
        def view(params):return SimpleNamespace(record=Registro('LTE NB-IoT','FDD1',18010,1921,params),campos={})
        values=[view({'cert':'EN/FCC/ISED'}),view({'cert':'EN/FCC/ISED','scs':15,'modulation':'QPSK'})]
        self.assertEqual(coincidencias_especificas([0,1],values),[1])
        self.assertEqual(coincidencias_especificas([0],values),[0])
        values.append(view({'cert':'EN/FCC/ISED','scs':3.75,'modulation':'BPSK'}))
        self.assertEqual(coincidencias_especificas([0,1,2],values),[1,2])

    def test_misma_busqueda_fcc_con_columnas_en_no_contiguas(self):
        text='IF(COUNT(CT3:CT8)=0,"N/A",VLOOKUP(MAX(CT3:CT8),CT3:CY8,5,FALSE))'
        expected='IF(COUNT(CO13:CO18)=0,"N/A",VLOOKUP(MAX(CO13:CO18),CHOOSE({1,2,3,4,5,6},CO13:CO18,CG13:CG18,CH13:CH18,CI13:CI18,CC13:CC18,CD13:CD18),5,FALSE))'
        self.assertEqual(adaptar_formula(text,{3:13,8:18,11:21},11,21),expected)
        self.assertEqual(adaptar_formula('CC11',{11:21},12,22),'CC21')

    def test_exposicion_no_seleccionada_no_toma_otro_bloque(self):
        self.assertEqual(adaptar_formula('COUNT(CT3:CT8)',{13:23,20:30},23,31),'COUNT(CO1:CO1)')

class CuatroCambiosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=ROOT/'ejemplos/Proyecto_SAR_restaurados.xlsm'
        cls.tmp=tempfile.TemporaryDirectory()
        cls.after=Path(cls.tmp.name)/'correcciones.xlsm'
        d=json.loads((ROOT/'ejemplos/ejemplo_sar_restaurado.json').read_text())
        cls.summary=generar(d,cls.after,catalogo=Catalogo(),log=lambda *_:None)
        cls.names_before=workbook(cls.before);cls.names_after=workbook(cls.after)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def xml(self,z,name,after=True):
        return z.read((self.names_after if after else self.names_before)[name][0])

    def visibles(self,z,name):
        info=self.summary['presentacion_original'][name]
        with z.open(self.names_after[name][0]) as stream:
            for _,row in E.iterparse(stream,tag='{'+NS['s']+'}row'):
                if int(row.get('r'))>info['cabecera']:
                    yield {_col(c):_value(c,[]) for c in row}
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]

    def test_solo_cambian_las_hojas_autorizadas(self):
        allowed={'Conducted LTE CATM1','Conducted LTE NB-IoT','Conducted WiFi','SAR EN'}
        with ZipFile(self.before) as a,ZipFile(self.after) as b:
            for name in self.names_before:
                if name not in allowed:
                    self.assertEqual(self.xml(a,name,False),self.xml(b,name),name)
            self.assertEqual(a.read('xl/styles.xml'),b.read('xl/styles.xml'))
            self.assertEqual(sin_canales(self.xml(a,'SAR EN',False)),sin_canales(self.xml(b,'SAR EN')))

    def test_catm1_solo_etiqueta_lte(self):
        with ZipFile(self.after) as z:
            labels={v.get('J') for v in self.visibles(z,'Conducted LTE CATM1') if v.get('J')}
            self.assertEqual(labels,{'LTE'})

    def test_catm1_no_cambia_otras_columnas(self):
        def rows(z,part):
            with z.open(part) as stream:
                for _,row in E.iterparse(stream,tag='{' + NS['s'] + '}row'):
                    for cell in list(row):
                        if _col(cell)=='J':row.remove(cell)
                    yield E.tostring(row,method='c14n',exclusive=True)
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
        with ZipFile(self.before) as a,ZipFile(self.after) as b:
            for old,new in zip(rows(a,self.names_before['Conducted LTE CATM1'][0]),
                               rows(b,self.names_after['Conducted LTE CATM1'][0])):
                self.assertEqual(old,new)

    def test_nbiot_conserva_el_orden_del_procedimiento_original(self):
        with ZipFile(self.after) as z:
            rows=[v for v in self.visibles(z,'Conducted LTE NB-IoT') if v.get('K')=='FDD1']
            self.assertEqual([float(v['L']) for v in rows[:4]],[3.75,15,15,15])
            self.assertEqual([v['Q'] for v in rows[:4]],[1,1,3,12])
            self.assertEqual([v['R'] for v in rows[:4]],[0,0,3,0])
            self.assertEqual([v['S'] for v in rows[:4]],['1RB Low','1RB Low','50% RB Mid','100% RB'])
            self.assertEqual([v['T'] for v in rows[:14]],[18010]*14)

    def test_wifi_se_desplaza_sin_paneles_inmovilizados(self):
        with ZipFile(self.after) as z:
            root=E.fromstring(self.xml(z,'Conducted WiFi'))
            self.assertFalse(root.findall('s:sheetViews/s:sheetView/s:pane',NS))
            self.assertTrue(list(self.visibles(z,'Conducted WiFi')))

    def test_baterias_sar_en_buscan_dentro_de_su_bloque(self):
        with ZipFile(self.after) as z:
            root=E.fromstring(self.xml(z,'SAR EN'))
            first=root.find('s:sheetData/s:row[@r="9"]/s:c[@r="CC9"]/s:f',NS).text
            second=root.find('s:sheetData/s:row[@r="10"]/s:c[@r="CC10"]/s:f',NS).text
            self.assertIn('COUNT(CO3:CO8)',first)
            self.assertIn('CHOOSE({1,2,3,4,5,6}',first)
            self.assertEqual(second,'CC9')

if __name__=='__main__':unittest.main()
