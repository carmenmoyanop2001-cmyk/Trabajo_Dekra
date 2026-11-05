"""No mezclar bandas regionales SAR ni congelar las filas ocultas de tecnologías."""
from pathlib import Path
import re
import tempfile
import unittest
from zipfile import ZipFile

from lxml import etree as E
from base_datos import Catalogo
from generador_excel import generar
from herramientas.corregir_vistas import corregir
from tecnologias_originales import vista_desplazable
from test_tecnologias_visibles import workbook

NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


class VistasTests(unittest.TestCase):
    def test_no_hay_panel_inmovilizado_aunque_cabecera_este_en_848(self):
        root=E.fromstring(f'<worksheet xmlns="{NS["s"]}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="848" state="frozen"/></sheetView></sheetViews><sheetData/></worksheet>')
        vista_desplazable(root,848)
        self.assertFalse(root.findall('.//s:pane',NS))
        self.assertEqual(root.find('.//s:selection',NS).get('activeCell'),'B849')


class RegionesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/'regiones.xlsm'
        cls.data=dict(proyecto='Regiones por banda',region=['EN','FCC','ISED'],exposure=['Body'],
            conducida=True,baterias=['B1','B2'],accesorios=[],spotchecking=[],
            tecnologias={'3G':{'WCDMA':['FDDI','FDDII','FDDVIII']}})
        cls.result=generar(cls.data,cls.path,catalogo=Catalogo(),log=lambda *_:None)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_sar_en_no_incluye_banda_exclusiva_fcc(self):
        names=workbook(self.path)
        with ZipFile(self.path) as z:
            for name,expected in [('SAR EN',{'FDDI','FDDVIII'}),('SAR FCC-ISED',{'FDDII'})]:
                root=E.fromstring(z.read(names[name][0]))
                bands={''.join(c.xpath('.//s:t/text() | s:v/text()',namespaces=NS))
                       for c in root.findall('s:sheetData/s:row/s:c',NS)
                       if re.fullmatch(r'BU[3-9]\d*|BU[12]\d+',c.get('r',''))}
                bands.discard('')
                self.assertEqual(bands,expected,name)

    def test_tecnologia_se_desplaza_y_conserva_sus_tres_bandas(self):
        names=workbook(self.path)
        with ZipFile(self.path) as z:
            root=E.fromstring(z.read(names['Conducted 3G'][0]))
            self.assertFalse(root.findall('.//s:pane',NS))
            bands={''.join(c.itertext()) for c in root.findall('.//s:c',NS)
                   if re.fullmatch(r'K\d+',c.get('r','')) and c.get('t')=='inlineStr'}
            self.assertTrue({'FDDI','FDDII','FDDVIII'} <= bands)

    def test_reparacion_vistas_no_modifica_formulas_ni_otros_datos(self):
        output=Path(self.temp.name)/'vista.xlsm'
        changed=corregir(self.path,output)
        with ZipFile(self.path) as before,ZipFile(output) as after:
            for part in before.namelist():
                a,b=before.read(part),after.read(part)
                if part in changed:
                    a=re.sub(rb'<sheetViews\b[^>]*>.*?</sheetViews>',b'',a,flags=re.S)
                    b=re.sub(rb'<sheetViews\b[^>]*>.*?</sheetViews>',b'',b,flags=re.S)
                self.assertEqual(a,b,part)


if __name__=='__main__':unittest.main()
