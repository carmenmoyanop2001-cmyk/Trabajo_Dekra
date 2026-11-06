"""Cada generación debe conservar el ajuste después de filtros, vistas y SAR."""
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from generador_excel import generar, _validar_calculo
from herramientas.validar_paquete import validar

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


class ControlCalculoTests(unittest.TestCase):
    def libro(self, calc):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name)/'datos.xlsm'
        with ZipFile(path, 'w') as z:
            z.writestr('xl/workbook.xml', '<workbook xmlns="'+NS+'">'+calc+'</workbook>')
        return path

    def test_rechaza_si_un_postproceso_retira_el_ajuste(self):
        path = self.libro('<calcPr calcMode="auto" forceFullCalc="0"/>')
        with self.assertRaisesRegex(ValueError, 'No se ha publicado'):
            _validar_calculo(path)

    def test_rechaza_cambio_a_manual_o_recalculo_completo(self):
        for config in ('<calcPr calcMode="manual" forceFullCalc="0" concurrentCalc="0"/>',
                       '<calcPr calcMode="auto" forceFullCalc="1" concurrentCalc="0"/>', ''):
            with self.subTest(config=config), self.assertRaises(ValueError):
                _validar_calculo(self.libro(config))

    def test_acepta_false_ademas_de_cero(self):
        config = _validar_calculo(self.libro('<calcPr calcMode="auto" forceFullCalc="false" concurrentCalc="false"/>'))
        self.assertEqual(config['calcMode'], 'auto')


class RegeneracionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.outputs = []
        for n, conducted in enumerate((True, False), 1):
            data = dict(proyecto='Generación nueva '+str(n), region=['EN', 'FCC'], exposure=['Body'],
                        conducida=conducted, baterias=['B1'], accesorios=[], spotchecking=[],
                        tecnologias={'2G': {'GSM': True}, '3G': {'WCDMA': ['FDDI', 'FDDII']}})
            path = cls.folder/('nuevo_'+str(n)+'.xlsm')
            summary = generar(data, path, log=lambda *_: None)
            cls.outputs.append((path, summary))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_se_aplica_a_dos_archivos_nuevos_sin_herramienta_de_copias(self):
        for path, summary in self.outputs:
            with self.subTest(path=path.name), ZipFile(path) as z:
                calc = ET.fromstring(z.read('xl/workbook.xml')).find('{'+NS+'}calcPr')
                self.assertEqual(calc.get('concurrentCalc'), '0')
                self.assertEqual(calc.get('calcMode'), 'auto')
                self.assertEqual(calc.get('forceFullCalc'), '0')
                self.assertEqual(calc.get('fullCalcOnLoad'), '1')
                self.assertEqual(summary['configuracion_calculo'], dict(calc.attrib))
                wb = ET.fromstring(z.read('xl/workbook.xml'))
                names = {s.get('name') for s in wb.find('{'+NS+'}sheets')}
                self.assertTrue({'SAR EN', 'SAR FCC-ISED'} <= names)
                self.assertTrue(summary['sar_version12']['resto_del_paquete_identico'])

    def test_ambas_generaciones_superan_validacion_del_paquete(self):
        for path, _ in self.outputs:
            with self.subTest(path=path.name):
                self.assertEqual(validar(path, verbose=False), [])


if __name__ == '__main__':
    unittest.main()
