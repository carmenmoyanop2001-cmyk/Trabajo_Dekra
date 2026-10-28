"""Cert. no se recalcula ni se sustituye por las regiones del cuestionario."""
from pathlib import Path
import json
import lzma
import tempfile
import unittest
import zipfile
from lxml import etree as E

from generador_excel import generar, DIR_PLANTILLA, ARCHIVOS
from nucleo import Hoja
from seleccion import plan_sar, referencias, plan_conducted, hojas_conducted_necesarias

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
DATA = dict(proyecto='Cert. todas las tecnologías', region=['EN', 'FCC', 'ISED'],
            exposure='Body', conducida=True, baterias=[], accesorios=[], spotchecking=[],
            tecnologias={'2G': {'GSM': True}, '3G': ['WCDMA'], 'LTE': ['FDD5'],
                         'LTE CAT M1': ['FDD5'], 'LTE NB-IoT': ['FDD5'],
                         '5G': ['n1'], 'WLAN': {'2,4 GHz': ['b']}})


def text(cell):
    return ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=NS)) or None


class CertTodasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with lzma.open(Path(__file__).parent / 'fixtures/cert_todas_tecnologias_original.json.xz', 'rt') as f:
            cls.originals = json.load(f)
        cls.sheets = {name: Hoja(str(Path(DIR_PLANTILLA) / ARCHIVOS[name])) for name in cls.originals}
        cls.sar = {family: Hoja(str(Path(DIR_PLANTILLA) / file))
                   for family, file in [('EN', 'sar_en.xz'), ('FCC', 'sar_fcc.xz')]}

    def test_cert_de_las_siete_plantillas_contra_80612_filas_originales(self):
        count = 0
        for name, values in self.originals.items():
            h = self.sheets[name]
            for row, expected in values.items():
                self.assertEqual(h.kv(h.by_old[int(row)]).get('B'), expected, f'{name}: B{row}')
                count += 1
        self.assertEqual(count, 80612)

    def test_excel_todas_las_tecnologias_y_regiones_conserva_cert_por_fila(self):
        with tempfile.TemporaryDirectory() as tmp:
            for regions, conducted in [('EN', True), ('FCC', True), ('ISED', True),
                                       (['EN', 'FCC', 'ISED'], True), (['EN', 'FCC'], False)]:
                with self.subTest(regions=regions, conducted=conducted):
                    data = dict(DATA, region=regions, conducida=conducted)
                    output = Path(tmp) / 'datos.xlsm'
                    generar(data, output, log=lambda *_: None)
                    selected = [regions] if isinstance(regions, str) else regions
                    families = {'EN' if r == 'EN' else 'FCC' for r in selected}
                    refs = {}
                    for family in families:
                        h = self.sar[family]
                        for name, rows in referencias(h, plan_sar(h, family, data)).items():
                            refs.setdefault(name, {})[family] = rows
                    with zipfile.ZipFile(output) as z:
                        wb = E.fromstring(z.read('xl/workbook.xml'))
                        relations = {r.get('Id'): r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
                        parts = {s.get('name'): 'xl/' + relations[s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
                                 for s in wb.findall('s:sheets/s:sheet', NS)}
                        for name in hojas_conducted_necesarias(data['tecnologias']):
                            visible_name = name if conducted else name.removeprefix('Conducted ')
                            self.assertIn(visible_name, parts)
                            root = E.fromstring(z.read(parts[visible_name]))
                            cells = {c.get('r'): c for c in root.findall('s:sheetData/s:row/s:c', NS)}
                            h = self.sheets[name]
                            plan = plan_conducted(h, data, refs.get(name))
                            self.assertEqual(len(root.findall('s:sheetData/s:row', NS)) - 2, len(plan))
                            for new, item in enumerate(plan, start=3):
                                old = h.rows[item.i][0]
                                expected = self.originals[name].get(str(old), h.kv(item.i).get('B'))
                                self.assertEqual(text(cells[f'B{new}']), expected, f'{visible_name}: B{new}, original B{old}')
                            if name == 'Conducted WiFi':
                                self.assertNotIn('EN/FCC/ISED', {text(cells[f'B{r}']) for r in range(3, len(plan) + 3)})

    def test_cert_indefinido_del_original_se_conserva_y_se_avisa(self):
        data = dict(DATA, region='EN', tecnologias={'2G': {'GSM': True}, 'LTE CAT M1': ['FDD6']})
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'cert_indefinido.xlsm'
            summary = generar(data, output, log=lambda *_: None)
            with zipfile.ZipFile(output) as z:
                root = E.fromstring(z.read('xl/worksheets/sheet5.xml'))
            self.assertIn('?', [text(c) for c in root.findall('s:sheetData/s:row/s:c', NS)
                                if ''.join(ch for ch in c.get('r') if ch.isalpha()) == 'B'])
            self.assertTrue(any('Cert. original sin región definida' in warning for warning in summary['avisos']))


if __name__ == '__main__':
    unittest.main()
