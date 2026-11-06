"""La prueba de cálculo no puede modificar el contenido del libro del usuario."""
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

from compatibilidad_excel2016 import ajustar_calculo, crear_copia, NS


def workbook(calc):
    return ('<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="'+NS+'">'
            '<sheets/><definedNames/>'+calc+'</workbook>').encode()


class ConfiguracionTests(unittest.TestCase):
    def test_solo_cambia_concurrencia_y_conserva_auto_y_caches(self):
        tag = b'<calcPr calcId="0" calcMode="auto" fullCalcOnLoad="1" forceFullCalc="0" calcOnSave="1"/>'
        original = workbook(tag.decode())
        actual = ajustar_calculo(original)
        self.assertEqual(actual, original.replace(tag, tag[:-2]+b' concurrentCalc="0"/>'))
        self.assertEqual(ajustar_calculo(actual), actual)
        config = ET.fromstring(actual).find('{'+NS+'}calcPr')
        self.assertEqual(config.get('calcMode'), 'auto')
        self.assertEqual(config.get('forceFullCalc'), '0')

    def test_conserva_prefijos_espacios_y_otras_opciones(self):
        for enabled in ('1', 'true', '0'):
            xml = ('<x:workbook xmlns:x="'+NS+'"><x:calcPr calcMode="manual" concurrentCalc=\''+
                   enabled+'\' concurrentManualCount="2" /></x:workbook>').encode()
            expected = xml.replace(('concurrentCalc=\''+enabled+'\'').encode(), b'concurrentCalc="0"')
            self.assertEqual(ajustar_calculo(xml), expected)

    def test_rechaza_configuracion_ausente_sin_inventarla(self):
        with self.assertRaises(ValueError):
            ajustar_calculo(workbook(''))


class CopiaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.source = self.folder/'Proyecto.xlsm'
        with ZipFile(self.source, 'w', ZIP_DEFLATED) as z:
            z.writestr('xl/workbook.xml', workbook('<calcPr calcMode="auto"/>'))
            z.writestr('xl/worksheets/sheet3.xml', '<worksheet><f>AI75+$CL$74</f></worksheet>')
            z.writestr('xl/worksheets/sar_en.xml', '<worksheet><f>MyTimestamp(CQ3)</f></worksheet>')
            z.writestr('xl/worksheets/sar_fcc.xml', '<worksheet><f>INDEX(A1:A9,3)</f></worksheet>')
            z.writestr('xl/styles.xml', '<styles/>')
            z.writestr('xl/vbaProject.bin', b'\x00\x01VBA preservado')

    def test_todas_las_partes_menos_workbook_son_identicas_y_origen_intacto(self):
        original = self.source.read_bytes()
        result = crear_copia(self.source)
        self.assertEqual(self.source.read_bytes(), original)
        with ZipFile(self.source) as source, ZipFile(result) as target:
            self.assertEqual(set(source.namelist()), set(target.namelist()))
            for name in source.namelist():
                if name != 'xl/workbook.xml':
                    self.assertEqual(source.read(name), target.read(name), name)

    def test_no_sobrescribe_original_ni_copias_previas(self):
        with self.assertRaises(ValueError):
            crear_copia(self.source, self.source)
        first = crear_copia(self.source)
        raw = first.read_bytes()
        with self.assertRaises(ValueError):
            crear_copia(self.source, first)
        second = crear_copia(self.source)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), raw)

    def test_si_configuracion_invalida_no_se_publica_copia(self):
        bad = self.folder/'sin_calc.xlsm'
        with ZipFile(bad, 'w') as z:
            z.writestr('xl/workbook.xml', workbook(''))
        with self.assertRaises(ValueError):
            crear_copia(bad, self.folder/'salida.xlsm')
        self.assertFalse((self.folder/'salida.xlsm').exists())


if __name__ == '__main__':
    unittest.main()
