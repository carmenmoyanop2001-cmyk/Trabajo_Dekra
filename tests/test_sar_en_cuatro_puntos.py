"""Ejemplo GSM del original: insertar tras los cuatro bloques de exposición."""
from pathlib import Path
import tempfile
import unittest
import zipfile
from lxml import etree as E
from generador_excel import generar

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


class CuatroPuntosTests(unittest.TestCase):
    def test_gsm_original_y_dos_baterias_en_cada_flecha(self):
        data = dict(proyecto='Cuatro puntos GSM', region='EN',
            exposure=['Close to ear', 'Close to Head', 'Body', 'Extremity'],
            conducida=False, baterias=['Batería A', 'Batería B'],
            accesorios=['Funda', 'Clip'], spotchecking=['No añadir Variability'],
            tecnologias={'2G': {'GSM': True}})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'cuatro_puntos.xlsm'
            generar(data, out, log=lambda *_: None)
            with zipfile.ZipFile(out) as z:
                root = E.fromstring(z.read('xl/worksheets/sheet11.xml'))
        rows = {int(r.get('r')): {''.join(x for x in c.get('r') if x.isalpha()): c
                                for c in r} for r in root.findall('s:sheetData/s:row', NS)}
        def text(row, col):
            return ''.join(rows[row][col].xpath('.//s:t/text() | s:v/text()', namespaces=NS))
        for start, end, first_battery in ((3, 8, 9), (11, 18, 19), (21, 28, 29), (34, 41, 42)):
            for n in (1, 2):
                row = first_battery + n - 1
                self.assertEqual(text(row, 'CA'), f'TBD - Battery check {n}')
                self.assertEqual(rows[row]['CA'].find('s:f', NS).text,
                                 f'CONCATENATE(CA{end - 2 + n}," - Battery check {n}")')
                self.assertEqual(rows[row]['CA'].get('t'), 'str')
                self.assertIn(f'$CO${start}:$CO${end}', rows[row]['CC'].find('s:f', NS).text)
                self.assertIn(f'$CO${start}:$CO${end}', rows[row]['DB'].find('s:f', NS).text)
                self.assertEqual(rows[row]['CQ'].find('s:f', NS).text,
                                 f'IF(CO{row}="","",IF(CO{row}>CP{row},"Fail","Pass"))')
                self.assertEqual(rows[row]['CS'].find('s:f', NS).text, f'MyTimestamp(CQ{row})')
                self.assertIn(f'COUNT(CE{row}:CF{row})', rows[row]['CT'].find('s:f', NS).text)
                self.assertIn(f'DC{row}', rows[row]['DE'].find('s:f', NS).text)
                self.assertIn(f'DD{row}', rows[row]['DE'].find('s:f', NS).text)
        self.assertEqual(text(31, 'CA'), 'Front Face')
        self.assertEqual(text(32, 'CA'), 'Accesorio 1: Funda')
        self.assertEqual(text(33, 'CA'), 'Accesorio 2: Clip')
        # Cada bloque siguiente sigue presente tras las inserciones anteriores.
        self.assertEqual(text(3, 'CA'), 'Left Cheek')
        for row in (11, 21, 34):
            self.assertEqual(text(row, 'CA'), 'Front Face')
        self.assertEqual(text(44, 'CA'), 'Left Cheek')
        self.assertTrue(all('Variability' not in text(r, 'CA') for r in rows if r > 2))

    def test_no_sobrescribe_un_excel_con_una_seleccion_sar_sin_filas_originales(self):
        data = dict(proyecto='Banda ausente en EN', region='EN', exposure='Body',
                    conducida=True, baterias=[], accesorios=[], spotchecking=[],
                    tecnologias={'LTE': ['FDD2']})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'previo.xlsm'
            out.write_bytes(b'conservar archivo previo')
            with self.assertRaisesRegex(ValueError, 'no contiene filas'):
                generar(data, out, log=lambda *_: None)
            self.assertEqual(out.read_bytes(), b'conservar archivo previo')


if __name__ == '__main__':
    unittest.main()
