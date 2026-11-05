"""Regresión: columnas originales y cálculos SAR sin alterar el resto de hojas."""
from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from zipfile import ZipFile

from lxml import etree as E
from base_datos import Catalogo, Registro
from columnas_originales import MANIFIESTO, restaurar_cols, nombre_original
from generador_excel import generar, _generar
from sar_en_canales import adaptar_formula, restaurar_normales
from test_tecnologias_visibles import workbook

ROOT = Path(__file__).resolve().parents[1]
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def estructura(xml):
    root = E.fromstring(xml)
    for col in root.findall('s:cols', NS): root.remove(col)
    for cell in root.findall('s:sheetData/s:row/s:c', NS):
        if re.fullmatch(r'C[CD]\d+', cell.get('r')):
            for child in list(cell): cell.remove(child)
            cell.attrib.pop('t', None)
    return E.tostring(root, method='c14n', exclusive=True)


class ConversionTests(unittest.TestCase):
    def test_base_parcial_no_pierde_canal_por_auxiliares_incompletos(self):
        xml = ('<worksheet xmlns="'+NS['s']+'"><sheetData><row r="3">'
               '<c r="BT3" t="inlineStr"><is><t>GSM</t></is></c>'
               '<c r="BU3" t="inlineStr"><is><t>900</t></is></c>'
               '<c r="BX3" t="inlineStr"><is><t>Body</t></is></c>'
               '<c r="CA3" t="inlineStr"><is><t>Front Face</t></is></c>'
               '<c r="CC3"><f>975</f><v>975</v></c>'
               '<c r="CD3"><f>880.2</f><v>880.2</v></c>'
               '</row></sheetData></worksheet>').encode()
        for channels, fallback in [([975],set()), ([975,37,124],{123})]:
            plan = SimpleNamespace(registros=[SimpleNamespace(record=Registro('GSM','900',ch,880.2)) for ch in channels],
                fallback_rows=fallback, grupos={123:('GSM','900')},
                origen_grupos={111:('GSM','900')}, mapped=lambda r:123, nombre='Conducted 2G')
            actual, count = restaurar_normales(xml, 'SAR EN', {'Conducted 2G-3G':plan}, ROOT/'plantilla')
            self.assertEqual(count, 0)
            self.assertEqual(actual, xml)

    def test_no_sustituye_referencia_ausente_por_posicion_vecina(self):
        self.assertEqual(adaptar_formula('CC12', {11: 21, 13: 22}, 14, 23), 'CC1')

    def test_fcc_conserva_su_tabla_y_sus_condiciones(self):
        formula = 'IF(COUNT(CT3:CT8)=0,"N/A",VLOOKUP(MAX(CT3:CT8),CT3:CY8,5,FALSE))'
        result = adaptar_formula(formula, {3: 13, 8: 18}, 11, 21, 'SAR FCC-ISED')
        self.assertEqual(result, formula.replace('3:', '13:').replace('8)', '18)').replace('8,', '18,'))

    def test_visibilidad_no_toca_medidas_ni_ancho_de_columna(self):
        xml = b'<worksheet><cols><col min="1" max="4" width="12"/></cols><sheetData><row r="3"><c r="CC3"><f>SUM(A3:B3)</f></c></row></sheetData></worksheet>'
        out = restaurar_cols(xml, [dict(min=2, max=3, hidden=True)])
        self.assertEqual(xml.split(b'<sheetData>')[1], out.split(b'<sheetData>')[1])
        root = E.fromstring(out)
        cols = root.find('s:cols', NS)
        self.assertEqual([(c.get('min'), c.get('max'), c.get('hidden'), c.get('width')) for c in cols],
                         [('1','1',None,'12'), ('2','3','1','12'), ('4','4',None,'12')])


class GeneracionEscritorioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        cls.cat = Catalogo()
        cls.data = dict(proyecto='Revisión escritorio', region=['EN','FCC','ISED'],
            exposure=['Close to ear','Body'], conducida=True,
            baterias=['B1','B2','B3'], accesorios=['Funda'], spotchecking=[],
            tecnologias={'2G':{'GSM':True}, 'WLAN':{'2,4 GHz':['n20']}})
        cls.before = cls.folder/'base.xlsm'
        cls.after = cls.folder/'revision.xlsm'
        _generar(cls.data, str(cls.before), catalogo=cls.cat, log=lambda *_:None)
        cls.resumen = generar(cls.data, str(cls.after), catalogo=cls.cat, log=lambda *_:None)
        cls.names = workbook(cls.after)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_sar_solo_modifica_cc_cd_y_visibilidad(self):
        with ZipFile(self.before) as before, ZipFile(self.after) as after:
            for name in ('SAR EN', 'SAR FCC-ISED'):
                part = self.names[name][0]
                self.assertEqual(estructura(before.read(part)), estructura(after.read(part)), name)
            for part in ('xl/vbaProject.bin', 'xl/worksheets/sheet1.xml', 'xl/worksheets/sheet2.xml', 'xl/worksheets/sheet10.xml'):
                if part.endswith('.xml'):
                    self.assertEqual(estructura(before.read(part)), estructura(after.read(part)), part)
                else:
                    self.assertEqual(before.read(part), after.read(part), part)

    def test_todas_las_columnas_originales_mantienen_visibilidad(self):
        manifest = json.loads(MANIFIESTO.read_text())['pestanas']
        with ZipFile(self.after) as z:
            for name, (part, *_) in self.names.items():
                canonical = nombre_original(name)
                if canonical not in manifest: continue
                root = E.fromstring(z.read(part))
                actual = {i: c.get('hidden') in ('1','true') for c in root.findall('s:cols/s:col', NS)
                          for i in range(int(c.get('min')), int(c.get('max'))+1)}
                for col in manifest[canonical]['columnas']:
                    for index in range(col['min'], col['max']+1):
                        self.assertEqual(actual.get(index,False), col['hidden'], (name,index))

    def test_canales_normales_usan_auxiliares_originales(self):
        self.assertGreater(self.resumen['enlaces_cc_cd_originales']['SAR EN'], 0)
        self.assertGreater(self.resumen['enlaces_cc_cd_originales']['SAR FCC-ISED'], 0)
        with ZipFile(self.after) as z:
            root = E.fromstring(z.read(self.names['SAR EN'][0]))
            formula = root.find('s:sheetData/s:row[@r="3"]/s:c[@r="CC3"]/s:f', NS).text
            self.assertRegex(formula, r"'Conducted 2G'!BX\d+")

    def test_bateria_y_variability_recuperan_busqueda_fcc(self):
        self.assertGreater(self.resumen['formulas_cc_cd_en'], 0)
        self.assertGreater(self.resumen['formulas_cc_cd_fcc'], 0)
        with ZipFile(self.after) as z:
            en = E.fromstring(z.read(self.names['SAR EN'][0]))
            fcc = E.fromstring(z.read(self.names['SAR FCC-ISED'][0]))
            self.assertEqual(en.find('.//s:c[@r="CC9"]/s:f', NS).text,
                'IF(COUNT(CO3:CO8)=0,"N/A",VLOOKUP(MAX(CO3:CO8),CHOOSE({1,2,3,4,5,6},CO3:CO8,CG3:CG8,CH3:CH8,CI3:CI8,CC3:CC8,CD3:CD8),5,FALSE))')
            self.assertEqual(en.find('.//s:c[@r="CC10"]/s:f', NS).text, 'CC9')
            self.assertIn('COUNTIF(CT3:CT8,">0,8")', fcc.find('.//s:c[@r="CC9"]/s:f', NS).text)
            self.assertIn('VLOOKUP', fcc.find('.//s:c[@r="CC11"]/s:f', NS).text)


if __name__ == '__main__': unittest.main()
