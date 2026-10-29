"""Cambios puntuales: Cert. original en 2G-3G y BX combinado en EN."""
from pathlib import Path
import json
import lzma
import tempfile
import unittest
import zipfile
from lxml import etree as E

from generador_excel import generar_heredado as generar, DIR_PLANTILLA
from nucleo import Hoja
from seleccion import plan_sar, referencias, plan_conducted
from sarlib import _REF, _STR, _sheetname

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
DATA = dict(proyecto='Cert y exposición', region=['EN', 'FCC'],
            exposure=['Close to ear', 'Body', 'Extremity'], conducida=True,
            baterias=['B1', 'B2'], accesorios=['Acc1', 'Acc2'], spotchecking=[],
            tecnologias={'2G': {'GSM': True}, '3G': ['WCDMA']})


def text(cell):
    return ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=NS))


class CertExposicionTests(unittest.TestCase):
    def test_cert_original_no_se_reescribe_para_ninguna_region(self):
        with lzma.open(Path(__file__).parent / 'fixtures/cert_2g3g_original.json.xz', 'rt') as f:
            source_values = json.load(f)['values']
        conducted = Hoja(str(Path(DIR_PLANTILLA) / 'cond_2g3g.xz'))
        with tempfile.TemporaryDirectory() as tmp:
            for regions in ('EN', 'FCC', ['EN', 'FCC', 'ISED']):
                with self.subTest(regions=regions):
                    data = dict(DATA, region=regions)
                    path = Path(tmp) / 'datos.xlsm'
                    generar(data, path, log=lambda *_: None)
                    refs = {}
                    for family, file in [('EN', 'sar_en.xz'), ('FCC', 'sar_fcc.xz')]:
                        if family not in ([regions] if isinstance(regions, str) else regions):
                            continue
                        h = Hoja(str(Path(DIR_PLANTILLA) / file))
                        refs[family] = referencias(h, plan_sar(h, family, data)).get('Conducted 2G-3G', set())
                    plan = plan_conducted(conducted, data, refs)
                    with zipfile.ZipFile(path) as z:
                        root = E.fromstring(z.read('xl/worksheets/sheet3.xml'))
                    output = {c.get('r'): c for c in root.findall('s:sheetData/s:row/s:c', NS)}
                    for row, item in enumerate(plan, start=3):
                        original_row = str(conducted.rows[item.i][0])
                        self.assertEqual(text(output[f'B{row}']), source_values[original_row])

    def test_bx_combina_todo_el_bloque_incluyendo_filas_adicionales(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'exposicion.xlsm'
            generar(DATA, path, log=lambda *_: None)
            with zipfile.ZipFile(path) as z:
                root = E.fromstring(z.read('xl/worksheets/sheet11.xml'))
                styles = E.fromstring(z.read('xl/styles.xml'))
        cells = {c.get('r'): c for c in root.findall('s:sheetData/s:row/s:c', NS)}
        ranges = [r for r in root.xpath('//s:mergeCell/@ref', namespaces=NS) if r.startswith('BX')]
        covered = {}
        has_batteries = has_accessories = False
        for span in ranges:
            first, last = (int(c[2:]) for c in span.split(':'))
            exposure = text(cells[f'BX{first}'])
            xf = styles.find('s:cellXfs', NS)[int(cells[f'BX{first}'].get('s', '0'))]
            font = styles.find('s:fonts', NS)[int(xf.get('fontId'))]
            self.assertEqual(font.find('s:color', NS).attrib, {'rgb': 'FF000000'})
            key = (text(cells[f'BT{first}']), text(cells[f'BU{first}']))
            self.assertIn(exposure, ('Close to Ear', 'Body', 'Extremity'))
            for row in range(first, last + 1):
                self.assertNotIn(row, covered)
                covered[row] = first
                self.assertEqual((text(cells[f'BT{row}']), text(cells[f'BU{row}'])), key)
                if row != first:
                    self.assertEqual(text(cells[f'BX{row}']), '')
                position = text(cells[f'CA{row}'])
                has_batteries |= position.startswith('TBD - Battery check ')
                if position.startswith('Accesorio '):
                    has_accessories = True
                    self.assertEqual(exposure, 'Body')
        rows = root.findall('s:sheetData/s:row', NS)[2:]
        self.assertEqual(set(covered), {int(row.get('r')) for row in rows})
        self.assertTrue(has_batteries and has_accessories)
        # Los únicos cálculos que leen BX deben apuntar al ancla de su bloque.
        for node in root.xpath('//s:c/s:f', namespaces=NS):
            row = int(''.join(x for x in node.getparent().get('r') if x.isdigit()))
            if row < 3:
                continue
            for part in _STR.split(node.text or '')[::2]:
                for ref in _REF.finditer(part):
                    if (_sheetname(ref.group(1) or '') or 'SAR EN') == 'SAR EN' and ref.group(3) == 'BX':
                        self.assertEqual(int(ref.group(5)), covered[row])


if __name__ == '__main__':
    unittest.main()
