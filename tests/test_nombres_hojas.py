"""Nombres sin Conducted y enlaces directos/dinámicos a sus hojas."""
from pathlib import Path
import tempfile
import unittest
import zipfile
from lxml import etree as E

from nombres_hojas import renombrar_tecnologias
from generador_excel import generar_heredado as generar


class NombresTests(unittest.TestCase):
    def test_formula_y_indirect_en_limite_de_bloque_sin_tocar_macros(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'paquete.xlsm'
            text = b'<worksheet><f>' + b' ' * ((1 << 20) - 25) + b"'Conducted 5G'!A1+INDIRECT(&quot;'Conducted LTE'!A1&quot;)</f></worksheet>"
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('xl/worksheets/sheet1.xml', text)
                z.writestr('xl/vbaProject.bin', b'macro sin modificar')
            renombrar_tecnologias(path, {'Conducted LTE': 'LTE', 'Conducted 5G': '5G'})
            with zipfile.ZipFile(path) as z:
                actual = z.read('xl/worksheets/sheet1.xml')
                self.assertNotIn(b'Conducted', actual)
                self.assertIn(b"'5G'!A1", actual)
                self.assertIn(b"INDIRECT(&quot;'LTE'!A1&quot;)", actual)
                self.assertEqual(z.read('xl/vbaProject.bin'), b'macro sin modificar')
                E.fromstring(actual)

    def test_lte_seleccionado_sin_prefijo_y_con_enlaces_sar_actualizados(self):
        data = dict(proyecto='Nombres de hojas', region=['EN', 'FCC'], exposure='Body',
                    conducida=False, baterias=[], accesorios=[], spotchecking=[],
                    tecnologias={'LTE': ['FDD5'], 'LTE CAT M1': ['FDD5']})
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'sin_conducidos.xlsm'
            summary = generar(data, output, log=lambda *_: None)
            self.assertIn('LTE', summary['hojas'])
            self.assertNotIn('Conducted LTE', summary['hojas'])
            with zipfile.ZipFile(output) as z:
                wb = E.fromstring(z.read('xl/workbook.xml'))
                names = wb.xpath('//*[local-name()="sheet"]/@name')
                self.assertEqual(names, summary['hojas'])
                formulas = []
                for name in z.namelist():
                    if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                        xml = z.read(name)
                        self.assertNotIn(b"'Conducted LTE'!", xml)
                        self.assertNotIn(b"'Conducted LTE CATM1'!", xml)
                        root = E.fromstring(xml)
                        formulas.extend(root.xpath('//*[local-name()="f"]/text()'))
                self.assertTrue(any("'LTE'!" in formula for formula in formulas))
                self.assertTrue(any("'LTE CATM1'!" in formula for formula in formulas))


if __name__ == '__main__':
    unittest.main()
